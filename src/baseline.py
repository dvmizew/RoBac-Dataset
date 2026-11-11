"""Baseline ML model for RoBac-Eval (Section 5: Validation Plan).

Demonstrates downstream discipline classification on exercise prompts
using a TF-IDF vectorizer and LinearSVC classifier, with stratified
cross-validation and classification metrics.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import classification_report
from sklearn.model_selection import StratifiedKFold, cross_val_predict, cross_val_score
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
    """Train baseline classifier on sample dataset and report metrics."""
    items = load_jsonl(data_path)
    if not items:
        logger.warning("No items found in %s", data_path)
        return None

    x_train = np.asarray(
        [f"{it.cerinta_text} {it.context_suport or ''}".strip() for it in items]
    )
    y_train = np.asarray([str(it.materie) for it in items])

    class_counts = Counter(y_train)
    if len(class_counts) < 2:
        logger.warning(
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

    min_count = min(class_counts.values())
    if min_count >= 2:
        n_splits = min(5, min_count)
        cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
        cv_scores = cross_val_score(clf, x_train, y_train, cv=cv, scoring="accuracy")
        logger.info(
            "%d-Fold Stratified Cross-Validation: %.1f%% (+/- %.1f%%)",
            n_splits,
            cv_scores.mean() * 100,
            cv_scores.std() * 100,
        )

    return clf


def evaluate_baseline(
    data_path: Path = REPO_ROOT / "data/sample.jsonl",
    n_splits: int = 5,
) -> str | None:
    """Compute out-of-fold cross-validation metrics and classification report."""
    items = load_jsonl(data_path)
    if not items:
        logger.warning("No items found in %s", data_path)
        return None

    x_train = np.asarray(
        [f"{it.cerinta_text} {it.context_suport or ''}".strip() for it in items]
    )
    y_train = np.asarray([str(it.materie) for it in items])

    class_counts = Counter(y_train)
    min_count = min(class_counts.values()) if class_counts else 0
    if len(class_counts) < 2 or min_count < 2:
        logger.warning(
            "Insufficient samples per class for cross-validation evaluation."
        )
        return None

    splits = min(n_splits, min_count)
    clf = make_pipeline(
        TfidfVectorizer(ngram_range=(1, 2)),
        LinearSVC(),
    )
    cv = StratifiedKFold(n_splits=splits, shuffle=True, random_state=42)
    y_pred = cross_val_predict(clf, x_train, y_train, cv=cv)
    return str(classification_report(y_train, y_pred, digits=2))


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
    parser.add_argument(
        "--eval",
        action="store_true",
        help="Print detailed out-of-fold cross-validation classification report",
    )
    args = parser.parse_args()

    clf = train_baseline(data_path=args.data)
    if clf is None:
        return

    if args.eval:
        report = evaluate_baseline(data_path=args.data)
        if report:
            print("\n--- 5-Fold Out-of-Fold Classification Report ---")
            print(report)

    if args.predict:
        pred = clf.predict([args.predict])[0]
        print("\n--- Live Custom Prediction ---")
        print(f"Prompt    : '{args.predict}'")
        print(f"Prediction: [{pred}]")
    elif not args.eval:
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
