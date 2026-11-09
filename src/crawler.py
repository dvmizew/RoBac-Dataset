"""Crawler for Romanian Baccalaureate exam PDFs.

Discovers and downloads official Subiect and Barem PDF pairs from edu.ro
archives (supporting multiple calendar years and target disciplines),
storing raw files in data/raw/<year>/.
"""

from __future__ import annotations

import argparse
import io
import logging
import re
import sys
import zipfile
from pathlib import Path
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("RoBac.Crawler")

DISCIPLINE_RULES = {
    "Matematica": {
        "zip_keywords": ["matematica", "e_c_"],
        "var_must": ["mate-info", "_var_", "lro"],
    },
    "Informatica": {
        "zip_keywords": ["informatica", "e_d_"],
        "var_must": ["sp_mi", "_var_", "lro"],
    },
    "Romana": {
        "zip_keywords": ["llr", "romana", "e_a_"],
        "var_must": ["real", "_var_"],
    },
}


def get_year_base_url(year: int) -> str:
    """Build official CNPEE entry point URL for a calendar year."""
    return f"http://subiecte{year}.edu.ro/{year}/bacalaureat/Subiecte_si_bareme/"


def find_matching_zip_urls(client: httpx.Client, year: int) -> list[str]:
    """Find all candidate exam zip packages on the ministry session index."""
    base_url = get_year_base_url(year)
    try:
        resp = client.get(base_url, timeout=15)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            urls: list[str] = []
            for a in soup.find_all("a", href=True):
                href_val = a.get("href")
                if isinstance(href_val, str) and href_val.strip().endswith(".zip"):
                    urls.append(urljoin(base_url, href_val.strip()))
            return urls
    except (httpx.HTTPError, OSError) as exc:
        logger.warning("[%d] Could not fetch session index: %s", year, exc)
    return []


def extract_discipline_from_zip(
    zip_bytes: bytes,
    discipline: str,
    output_dir: Path,
) -> tuple[Path, Path] | None:
    """Extract matching statement and rubric PDF pair from an in-memory zip archive."""
    rules = DISCIPLINE_RULES[discipline]
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        name_map = {n.lower(): n for n in z.namelist()}
        var_entry: str | None = None
        bar_entry: str | None = None

        for name in z.namelist():
            lower = name.lower()
            if not lower.endswith(".pdf"):
                continue
            # Skip minority language variants when looking for standard Romanian
            if discipline == "Romana" and ("maghiara" in lower or "minoritat" in lower):
                continue
            if all(k in lower for k in rules["var_must"]):
                # Statements for CS may include _C_var_ or _Pascal_var_, while bareme are unified _bar_
                cand_patterns = [
                    re.sub(r"_[cpascal]+_var_", "_bar_", lower, flags=re.IGNORECASE),
                    lower.replace("_var_", "_bar_"),
                    lower.replace("var_", "bar_"),
                ]
                for cand in cand_patterns:
                    if cand != lower and cand in name_map:
                        var_entry = name
                        bar_entry = name_map[cand]
                        break
                if var_entry and bar_entry:
                    break

        if var_entry and bar_entry:
            subiect_path = output_dir / Path(var_entry).name
            barem_path = output_dir / Path(bar_entry).name
            subiect_path.write_bytes(z.read(var_entry))
            barem_path.write_bytes(z.read(bar_entry))
            return subiect_path, barem_path

    return None


def crawl_discipline(
    client: httpx.Client,
    year: int,
    discipline: str,
    output_dir: Path,
    candidate_zips: list[str],
) -> tuple[Path, Path] | None:
    """Find and download exam pair for a given year and discipline."""
    rules = DISCIPLINE_RULES[discipline]
    # Filter zips matching discipline keywords, prioritizing primary summer session
    relevant = [
        z
        for z in candidate_zips
        if any(kw in z.lower() for kw in rules["zip_keywords"])
    ]
    relevant.sort(
        key=lambda z: 0 if "iulie" in z.lower() or "iunie" in z.lower() else 1
    )

    for zip_url in relevant:
        logger.info(
            "[%d - %s] Downloading %s", year, discipline, zip_url.split("/")[-1]
        )
        try:
            resp = client.get(zip_url, timeout=30.0)
            if resp.status_code != 200:
                continue
            pair = extract_discipline_from_zip(resp.content, discipline, output_dir)
            if pair:
                subiect, barem = pair
                logger.info(
                    "[%d - %s] Extracted %s and %s",
                    year,
                    discipline,
                    subiect.name,
                    barem.name,
                )
                return pair
        except (httpx.HTTPError, OSError) as exc:
            logger.warning(
                "[%d - %s] Error downloading %s: %s", year, discipline, zip_url, exc
            )

    return None


def crawl_year(
    client: httpx.Client,
    year: int,
    disciplines: list[str],
    raw_root: Path = REPO_ROOT / "data/raw",
) -> dict[str, tuple[Path, Path]]:
    """Crawl exam pairs for a calendar year."""
    output_dir = raw_root / str(year)
    output_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, tuple[Path, Path]] = {}

    candidate_zips = find_matching_zip_urls(client, year)
    if not candidate_zips:
        logger.warning("[%d] No exam zip archives discovered on server.", year)
        return results

    for disc in disciplines:
        if disc not in DISCIPLINE_RULES:
            logger.warning("Unknown discipline '%s', skipping.", disc)
            continue
        pair = crawl_discipline(client, year, disc, output_dir, candidate_zips)
        if pair:
            results[disc] = pair

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="RoBac-Eval: Multi-Year Exam Crawler")
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=[2024],
        help="Calendar years to crawl (e.g. --years 2024 2025)",
    )
    parser.add_argument(
        "--disciplines",
        nargs="+",
        default=["Matematica", "Informatica", "Romana"],
        help="Target disciplines (Matematica, Informatica, Romana)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "data/raw",
        help="Root output directory",
    )
    args = parser.parse_args()

    print(f"Starting crawl for years {args.years} across {args.disciplines}...")
    with httpx.Client(follow_redirects=True, timeout=30.0) as client:
        for year in args.years:
            year_results = crawl_year(
                client=client,
                year=year,
                disciplines=args.disciplines,
                raw_root=args.output_dir,
            )
            print(
                f"\n[OK] Year {year}: Downloaded {len(year_results)} disciplines into {args.output_dir / str(year)}:"
            )
            for disc, (subiect, barem) in year_results.items():
                print(f" - [{disc}] {subiect.name} | {barem.name}")


if __name__ == "__main__":
    main()
