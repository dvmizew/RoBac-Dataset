"""Dataset exploration and profiling statistics utility for RoBac-Eval.

Computes and displays descriptive statistics across disciplines, examination
years, sections, point distributions, and text length metrics.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.models import BacItem, load_jsonl


def compute_statistics(items: list[BacItem]) -> dict[str, Any]:
    """Compute comprehensive dataset statistics from loaded BacItem records."""
    total_items = len(items)
    if total_items == 0:
        return {"total": 0}

    by_discipline = Counter(it.materie for it in items)
    by_year = Counter(it.an for it in items)
    by_session = Counter(it.sesiune for it in items)
    by_section = Counter(it.sectiune for it in items)
    by_profile = Counter(it.profil for it in items)

    points = [it.puncte for it in items]
    total_points = sum(points)
    avg_points = total_points / total_items

    cerinta_word_counts = [len(it.cerinta_text.split()) for it in items]
    barem_word_counts = [len(it.barem_text.split()) for it in items]

    items_with_context = sum(1 for it in items if it.context_suport)

    return {
        "total": total_items,
        "by_discipline": dict(by_discipline),
        "by_year": dict(by_year),
        "by_session": dict(by_session),
        "by_section": dict(by_section),
        "by_profile": dict(by_profile),
        "points": {
            "total": round(total_points, 1),
            "mean": round(avg_points, 2),
            "min": min(points),
            "max": max(points),
        },
        "text_metrics": {
            "avg_cerinta_words": round(sum(cerinta_word_counts) / total_items, 1),
            "max_cerinta_words": max(cerinta_word_counts),
            "avg_barem_words": round(sum(barem_word_counts) / total_items, 1),
            "max_barem_words": max(barem_word_counts),
            "context_support_ratio": round(items_with_context / total_items * 100, 1),
        },
    }


def print_summary_report(data_path: Path) -> None:
    """Print formatted summary report of the dataset to standard output."""
    items = load_jsonl(data_path)
    stats = compute_statistics(items)

    total = int(stats["total"])
    print("=" * 64)
    print(f"  RoBac-Eval: Dataset Profile & Summary ({data_path.name})")
    print("=" * 64)
    print(f"Total structured items : {total}")
    print("-" * 64)

    by_disc = dict(stats["by_discipline"])
    print("\n[Distribution by Discipline]")
    for disc, count in sorted(by_disc.items()):
        pct = (count / total) * 100
        print(f"  • {disc:<30} : {count:3d} ({pct:5.1f}%)")

    by_year = dict(stats["by_year"])
    print("\n[Distribution by Year]")
    for yr, count in sorted(by_year.items()):
        pct = (count / total) * 100
        print(f"  • {yr}                           : {count:3d} ({pct:5.1f}%)")

    by_sec = dict(stats["by_section"])
    print("\n[Distribution by Section]")
    for sec, count in sorted(by_sec.items()):
        pct = (count / total) * 100
        print(f"  • {sec:<30} : {count:3d} ({pct:5.1f}%)")

    pts = dict(stats["points"])
    print("\n[Point Distribution Metrics]")
    print(
        f"  • Total exam points: {pts['total']} | Mean: {pts['mean']}p (Range: {pts['min']}p - {pts['max']}p)"
    )

    tm = dict(stats["text_metrics"])
    print("\n[NLP & Text Complexity Metrics]")
    print(
        f"  • Average prompt length   : {tm['avg_cerinta_words']} words (max: {tm['max_cerinta_words']} words)"
    )
    print(
        f"  • Average rubric length   : {tm['avg_barem_words']} words (max: {tm['max_barem_words']} words)"
    )
    print(
        f"  • Items with context text : {tm['context_support_ratio']}% of total dataset"
    )
    print("=" * 64)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="RoBac-Eval: Dataset Exploration and Statistics"
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=REPO_ROOT / "data/sample.jsonl",
        help="Path to JSONL dataset file (default: data/sample.jsonl)",
    )
    args = parser.parse_args()
    print_summary_report(args.data)


if __name__ == "__main__":
    main()
