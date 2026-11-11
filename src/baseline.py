"""Baseline ML model for RoBac-Eval (Section 5: Validation Plan).

Demonstrates downstream discipline classification on exercise prompts
using a TF-IDF vectorizer and LinearSVC classifier.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.svm import LinearSVC

from src.models import load_jsonl

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("RoBac.Baseline")


def train_baseline(
    data_path: Path = REPO_ROOT / "data/sample.jsonl",
) -> Pipeline | None:
    """Train and evaluate baseline classifier on sample dataset."""
    items = load_jsonl(data_path)
    if not items:
        logger.error("No items found in %s", data_path)
        return None

    x_train = [f"{it.cerinta_text} {it.context_suport or ''}".strip() for it in items]
    y_train = [it.materie for it in items]

    if len(set(y_train)) < 2:
        logger.error(
            "Baseline classifier requires at least 2 distinct disciplines in dataset."
        )
        return None

    clf = make_pipeline(
        TfidfVectorizer(ngram_range=(1, 2)),
        LinearSVC(),
    )
    clf.fit(x_train, y_train)

    train_acc = clf.score(x_train, y_train)
    logger.info("Baseline classifier trained on %d samples.", len(items))
    logger.info("Training accuracy across disciplines: %.1f%%", train_acc * 100)
    return clf


def main() -> None:
    parser = argparse.ArgumentParser(
        description="RoBac-Eval: Baseline Discipline Classifier"
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=REPO_ROOT / "data/sample.jsonl",
        help="Path to training JSONL data (default: data/sample.jsonl)",
    )
    parser.add_argument(
        "--predict",
        type=str,
        default=None,
        help="Optional custom prompt to classify interactively",
    )
    args = parser.parse_args()

    clf = train_baseline(data_path=args.data)
    if clf is None:
        return

    if args.predict:
        pred = clf.predict([args.predict])[0]
        print("\n--- Live Custom Prediction ---")
        print(f"Prompt    : '{args.predict}'")
        print(f"Prediction: [{pred}]")
    else:
        test_samples = [
            "Rezolvați în mulțimea numerelor reale ecuația logaritmică log_2(x) = 3.",
            "Scrieți un program C/C++ care citește o matrice pătratică și determină elementele pare.",
            "Redactează un eseu de minimum 400 de cuvinte despre tema iubirii într-o comedie studiată.",
        ]
        predictions = clf.predict(test_samples)
        print("\n--- Live Inference Demo (Downstream Task Baseline) ---")
        for prompt, pred in zip(test_samples, predictions, strict=True):
            print(f"Prompt: '{prompt}'\n -> Predicted Discipline: [{pred}]\n")


if __name__ == "__main__":
    main()
