"""Crawler module for subiecte.edu.ro exam archives.

Provides both asynchronous and synchronous download pipelines for Romanian
Baccalaureate examination PDFs (statements and grading rubrics), structured
hierarchically into local raw storage: data/raw/<year>/<session>/<subject>/.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set
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
    """Modular crawler for crawling and downloading Romanian Baccalaureate PDFs."""

    DEFAULT_BASE_URL = "http://subiecte.edu.ro"
    DEFAULT_USER_AGENT = "RoBac-Eval-Research-Crawler/1.0 (+https://github.com/RoBac-Eval)"

    # Heuristics for subject identification from URL / filenames
    SUBJECT_PATTERNS = {
        "Matematica": re.compile(r"matematica|mate_info|mate_st_nat|mate_tehn", re.IGNORECASE),
        "Informatica": re.compile(r"informatica|info_c|info_pascal", re.IGNORECASE),
        "Limba si literatura romana": re.compile(r"romana|limba_si_literatura_romana", re.IGNORECASE),
    }

    # Heuristics for resource type (subiect vs. barem)
    BAREM_PATTERN = re.compile(r"bar(?:em)?|_bar_", re.IGNORECASE)
    SUBIECT_PATTERN = re.compile(r"var|subiect|_var_|_sub_", re.IGNORECASE)

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        output_dir: Union[str, Path] = "data/raw",
        request_delay: float = 0.5,
        timeout: float = 30.0,
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

    def build_session_urls(self, year: int) -> Dict[str, str]:
        """Construct candidate entry points for an examination year."""
        year_str = str(year)
        return {
            "iunie-iulie": f"{self.base_url}/{year_str}/bacalaureat/Subiecte_si_bareme/",
            "simulare": f"{self.base_url}/{year_str}/bacalaureat/Simulare/",
            "modele": f"{self.base_url}/{year_str}/bacalaureat/Modele_subiecte/",
            "august-septembrie": f"{self.base_url}/{year_str}/bacalaureat/August_Septembrie/",
        }

    def extract_pdf_links(
        self,
        html_content: str,
        base_url: str,
        year: int,
        session: str,
    ) -> List[ExamResource]:
        """Parse HTML directory listing and extract exam PDF resource links."""
        soup = BeautifulSoup(html_content, "html.parser")
        resources: List[ExamResource] = []

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].strip()
            if not href.lower().endswith(".pdf"):
                continue

            absolute_url = urljoin(base_url, href)
            filename = Path(urlparse(absolute_url).path).name
            combined_desc = f"{filename} {anchor.get_text()}"
            subject = self._determine_subject(combined_desc)
            res_type = self._determine_resource_type(filename)

            resource = ExamResource(
                year=year,
                session=session,
                subject=subject,
                resource_type=res_type,
                url=absolute_url,
                filename=filename,
            )
            resources.append(resource)

        return resources

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
                logger.warning(
                    "Received status %d for %s (attempt %d/%d)",
                    response.status_code,
                    url,
                    attempt,
                    self.max_retries,
                )
            except (httpx.RequestError, httpx.TimeoutException) as exc:
                logger.warning(
                    "Network error fetching %s (attempt %d/%d): %s",
                    url,
                    attempt,
                    self.max_retries,
                    exc,
                )
            await asyncio.sleep(self.request_delay * attempt)
        return None

    async def download_pdf(
        self,
        client: httpx.AsyncClient,
        resource: ExamResource,
        semaphore: asyncio.Semaphore,
    ) -> Optional[Path]:
        """Download a single PDF file and store it in destination directory."""
        dest_dir = self.output_dir / str(resource.year) / resource.session / resource.subject
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / resource.filename

        if dest_file.exists() and dest_file.stat().st_size > 0:
            logger.debug("File already exists, skipping: %s", dest_file)
            return dest_file

        async with semaphore:
            for attempt in range(1, self.max_retries + 1):
                try:
                    await asyncio.sleep(self.request_delay)
                    response = await client.get(resource.url, headers=self.headers, timeout=self.timeout)
                    if response.status_code == 200 and response.content:
                        dest_file.write_bytes(response.content)
                        logger.info("Saved %s -> %s", resource.filename, dest_file)
                        return dest_file
                    logger.warning("Status %d downloading %s", response.status_code, resource.url)
                except Exception as exc:
                    logger.warning("Failed download for %s (attempt %d): %s", resource.url, attempt, exc)
                    await asyncio.sleep(self.request_delay * attempt)
        return None

    async def crawl_year(
        self,
        client: httpx.AsyncClient,
        year: int,
        sessions: Optional[Iterable[str]] = None,
        filter_subjects: Optional[Set[str]] = None,
        download: bool = False,
        concurrency: int = 4,
    ) -> List[ExamResource]:
        """Crawl exam sessions for a given year."""
        session_endpoints = self.build_session_urls(year)
        if sessions:
            session_endpoints = {k: v for k, v in session_endpoints.items() if k in sessions}

        all_resources: List[ExamResource] = []
        for session_name, session_url in session_endpoints.items():
            logger.info("Scanning year %d, session '%s': %s", year, session_name, session_url)
            html = await self.fetch_page(client, session_url)
            if not html:
                continue

            links = self.extract_pdf_links(html, session_url, year, session_name)
            if filter_subjects:
                links = [item for item in links if item.subject in filter_subjects]

            logger.info("Found %d PDF resources in %s (%d)", len(links), session_name, year)
            all_resources.extend(links)

        if download and all_resources:
            logger.info("Starting concurrent download of %d files...", len(all_resources))
            semaphore = asyncio.Semaphore(concurrency)
            tasks = [self.download_pdf(client, res, semaphore) for res in all_resources]
            await asyncio.gather(*tasks)

        return all_resources

    def run(
        self,
        years: List[int],
        sessions: Optional[List[str]] = None,
        subjects: Optional[List[str]] = None,
        download: bool = False,
    ) -> List[ExamResource]:
        """Synchronous entry point executing the async crawl pipeline."""

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
    """CLI entry point for testing and executing the crawler."""
    parser = argparse.ArgumentParser(description="RoBac-Eval: subiecte.edu.ro PDF Crawler")
    parser.add_argument("--years", nargs="+", type=int, default=[2023, 2024], help="Years to crawl")
    parser.add_argument(
        "--sessions",
        nargs="+",
        default=["iunie-iulie", "simulare", "modele"],
        help="Sessions to crawl (iunie-iulie, simulare, modele, august-septembrie)",
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
    print(f"\n[✓] Crawling complete. Total discovered resources: {len(found)}")


if __name__ == "__main__":
    main()
