"""Crawler module for subiecte.edu.ro exam archives.

Provides both asynchronous and synchronous download pipelines for Romanian
Baccalaureate examination PDFs (statements and grading rubrics), structured
hierarchically into local raw storage: data/raw/<year>/<session>/<subject>/.
Supports both direct PDF links and official session ZIP packages.
"""

from __future__ import annotations

import argparse
import asyncio
import io
import logging
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Union
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("RoBac.Crawler")


@dataclass
class ExamResource:
    """Metadata for an identified exam resource link."""

    year: int
    session: str
    subject: str
    resource_type: str  # 'subiect' or 'barem'
    url: str
    filename: str


class BacCrawler:
    """Modular crawler for discovering and downloading Romanian Baccalaureate files."""

    DEFAULT_BASE_URL = "http://subiecte.edu.ro"
    DEFAULT_USER_AGENT = "RoBac-Eval-Research-Crawler/1.0 (+https://github.com/dvmizew/RoBac-Dataset)"

    # Heuristics for subject identification from filename / text
    SUBJECT_PATTERNS = {
        "Matematica": re.compile(r"matematica|mate_info|mate_st_nat|mate_tehn", re.IGNORECASE),
        "Informatica": re.compile(r"informatica|info_c|info_pascal", re.IGNORECASE),
        "Limba si literatura romana": re.compile(r"romana|limba_si_literatura_romana|llr", re.IGNORECASE),
    }

    # Heuristics for resource type (subiect vs. barem)
    BAREM_PATTERN = re.compile(r"bar(?:em)?|_bar_", re.IGNORECASE)
    SUBIECT_PATTERN = re.compile(r"var|subiect|_var_|_sub_", re.IGNORECASE)

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        output_dir: Union[str, Path] = "data/raw",
        request_delay: float = 0.3,
        timeout: float = 45.0,
        max_retries: int = 3,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.output_dir = Path(output_dir)
        self.request_delay = request_delay
        self.timeout = timeout
        self.max_retries = max_retries
        self.headers = {"User-Agent": user_agent}

    def _determine_subject(self, text: str) -> str:
        """Infer subject category from filename or link anchor."""
        for subject, pattern in self.SUBJECT_PATTERNS.items():
            if pattern.search(text):
                return subject
        return "Altele"

    def _determine_resource_type(self, filename: str) -> str:
        """Determine whether the file is a subject statement or grading rubric."""
        if self.BAREM_PATTERN.search(filename):
            return "barem"
        if self.SUBIECT_PATTERN.search(filename):
            return "subiect"
        return "document"

    def get_year_base_url(self, year: int) -> str:
        """Construct official year subdomain used by CNPEE."""
        return f"http://subiecte{year}.edu.ro/{year}/bacalaureat"

    def build_session_urls(self, year: int) -> Dict[str, str]:
        """Construct candidate entry points for an examination year."""
        year_base = self.get_year_base_url(year)
        return {
            "iunie-iulie": f"{year_base}/Subiecte_si_bareme/",
            "modele": f"{year_base}/modeledesubiecte/",
            "simulare": f"{year_base}/Simulare/",
            "august-septembrie": f"{year_base}/Subiecte_si_bareme/",
        }

    async def fetch_page(self, client: httpx.AsyncClient, url: str) -> Optional[str]:
        """Fetch page HTML content with retry backoff."""
        for attempt in range(1, self.max_retries + 1):
            try:
                response = await client.get(url, headers=self.headers, timeout=self.timeout)
                if response.status_code == 200:
                    return response.text
                if response.status_code == 404:
                    logger.debug("Page not found (404): %s", url)
                    return None
            except (httpx.RequestError, httpx.TimeoutException) as exc:
                logger.warning("Error fetching %s (attempt %d/%d): %s", url, attempt, self.max_retries, exc)
            await asyncio.sleep(self.request_delay * attempt)
        return None

    def extract_links(
        self,
        html_content: str,
        base_url: str,
        year: int,
        session: str,
    ) -> List[Dict[str, str]]:
        """Parse HTML page to extract links to PDFs and ZIP archives."""
        soup = BeautifulSoup(html_content, "html.parser")
        links: List[Dict[str, str]] = []

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].strip()
            lower_href = href.lower()
            if not (lower_href.endswith(".pdf") or lower_href.endswith(".zip")):
                continue

            absolute_url = urljoin(base_url, href)
            label = anchor.get_text().strip()
            links.append({"url": absolute_url, "label": label, "filename": Path(urlparse(absolute_url).path).name})

        return links

    async def process_zip_package(
        self,
        client: httpx.AsyncClient,
        zip_url: str,
        year: int,
        session: str,
        filter_subjects: Optional[Set[str]] = None,
        download: bool = True,
    ) -> List[ExamResource]:
        """Download and extract PDFs from an official Ministry ZIP bundle."""
        extracted: List[ExamResource] = []
        try:
            logger.info("Downloading ZIP bundle: %s", zip_url)
            resp = await client.get(zip_url, headers=self.headers, timeout=self.timeout)
            if resp.status_code != 200:
                logger.warning("Failed to download ZIP (status %d): %s", resp.status_code, zip_url)
                return []

            with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
                for member_name in z.namelist():
                    lower_name = member_name.lower()
                    if not lower_name.endswith(".pdf"):
                        continue
                    # Prefer Romanian language files
                    if "lge" in lower_name or "lma" in lower_name or "lsk" in lower_name or "lsr" in lower_name:
                        continue

                    filename = Path(member_name).name
                    subject = self._determine_subject(filename)
                    if filter_subjects and subject not in filter_subjects:
                        continue

                    res_type = self._determine_resource_type(filename)
                    resource = ExamResource(
                        year=year,
                        session=session,
                        subject=subject,
                        resource_type=res_type,
                        url=zip_url,
                        filename=filename,
                    )
                    extracted.append(resource)

                    if download:
                        target_dir = self.output_dir / str(year) / session / subject
                        target_dir.mkdir(parents=True, exist_ok=True)
                        dest_file = target_dir / filename
                        if not dest_file.exists() or dest_file.stat().st_size == 0:
                            dest_file.write_bytes(z.read(member_name))
                            logger.info("Extracted %s -> %s", filename, dest_file)

        except Exception as exc:
            logger.error("Error processing ZIP package %s: %s", zip_url, exc)

        return extracted

    async def crawl_year(
        self,
        client: httpx.AsyncClient,
        year: int,
        sessions: Optional[Iterable[str]] = None,
        filter_subjects: Optional[Set[str]] = None,
        download: bool = False,
    ) -> List[ExamResource]:
        """Crawl examination sessions for a given calendar year."""
        session_endpoints = self.build_session_urls(year)
        if sessions:
            session_endpoints = {k: v for k, v in session_endpoints.items() if k in sessions}

        all_resources: List[ExamResource] = []
        visited_urls: Set[str] = set()

        for session_name, session_url in session_endpoints.items():
            if session_url in visited_urls:
                continue
            visited_urls.add(session_url)

            logger.info("Scanning year %d, session '%s': %s", year, session_name, session_url)
            html = await self.fetch_page(client, session_url)
            if not html:
                continue

            links = self.extract_links(html, session_url, year, session_name)
            for link_info in links:
                url = link_info["url"]
                filename = link_info["filename"]

                if filename.lower().endswith(".zip"):
                    zip_res = await self.process_zip_package(
                        client=client,
                        zip_url=url,
                        year=year,
                        session=session_name,
                        filter_subjects=filter_subjects,
                        download=download,
                    )
                    all_resources.extend(zip_res)
                elif filename.lower().endswith(".pdf"):
                    subject = self._determine_subject(filename)
                    if filter_subjects and subject not in filter_subjects:
                        continue
                    res = ExamResource(
                        year=year,
                        session=session_name,
                        subject=subject,
                        resource_type=self._determine_resource_type(filename),
                        url=url,
                        filename=filename,
                    )
                    all_resources.append(res)
                    if download:
                        target_dir = self.output_dir / str(year) / session_name / subject
                        target_dir.mkdir(parents=True, exist_ok=True)
                        dest_file = target_dir / filename
                        if not dest_file.exists():
                            resp = await client.get(url, headers=self.headers, timeout=self.timeout)
                            if resp.status_code == 200:
                                dest_file.write_bytes(resp.content)
                                logger.info("Downloaded %s", dest_file)

        return all_resources

    def run(
        self,
        years: List[int],
        sessions: Optional[List[str]] = None,
        subjects: Optional[List[str]] = None,
        download: bool = False,
    ) -> List[ExamResource]:
        """Synchronous entry point executing the crawler."""

        async def _main():
            filter_subjects = set(subjects) if subjects else None
            results: List[ExamResource] = []
            async with httpx.AsyncClient(follow_redirects=True) as client:
                for year in tqdm(years, desc="Crawling Bacalaureat Years"):
                    year_results = await self.crawl_year(
                        client=client,
                        year=year,
                        sessions=sessions,
                        filter_subjects=filter_subjects,
                        download=download,
                    )
                    results.extend(year_results)
            return results

        return asyncio.run(_main())


def main() -> None:
    """CLI entry point for running the crawler."""
    parser = argparse.ArgumentParser(description="RoBac-Eval: subiecte.edu.ro PDF & ZIP Crawler")
    parser.add_argument("--years", nargs="+", type=int, default=[2024], help="Years to crawl (e.g. 2024)")
    parser.add_argument(
        "--sessions",
        nargs="+",
        default=["iunie-iulie"],
        help="Sessions to crawl (iunie-iulie, modele, simulare)",
    )
    parser.add_argument(
        "--subjects",
        nargs="+",
        default=["Matematica", "Informatica", "Limba si literatura romana"],
        help="Target subjects to filter",
    )
    parser.add_argument("--output-dir", type=str, default="data/raw", help="Target output directory")
    parser.add_argument("--download", action="store_true", help="Download PDFs to disk")

    args = parser.parse_args()

    crawler = BacCrawler(output_dir=args.output_dir)
    found = crawler.run(
        years=args.years,
        sessions=args.sessions,
        subjects=args.subjects,
        download=args.download,
    )
    print(f"\n[OK] Crawling complete. Total discovered resources: {len(found)}")


if __name__ == "__main__":
    main()
