"""Automated unit test suite for the RoBac-Eval pipeline.

Covers:
- Pydantic v2 data model validation (BacItem).
- Regex institutional noise cleaning.
- JSONL serialization and deserialization roundtrip.
- Dataset profiling statistics computation.
- Baseline machine learning classifier training and inference.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from src.baseline import evaluate_baseline, train_baseline
from src.models import (
    BacExamPaper,
    BacItem,
    Discipline,
    ExamSection,
    ExamSession,
    Profile,
    load_jsonl,
    save_jsonl,
)
from src.parser import clean_institutional_noise
from src.stats import compute_statistics


class TestBacItemModel(unittest.TestCase):
    """Tests for Pydantic v2 schema constraints on BacItem."""

    def test_valid_bac_item(self) -> None:
        item = BacItem(
            id="bac_2024_iunie_matematica_mate_info_s1_ex1",
            an=2024,
            sesiune="iunie-iulie",
            materie="Matematica",
            profil="mate-info",
            sectiune="Subiectul I",
            numar_cerinta="1",
            context_suport=None,
            cerinta_text="Arătați că 2 + 2 = 4.",
            barem_text="Calcul direct: 2 + 2 = 4 (5p).",
            puncte=5.0,
            topic_curricular="Algebră elementară",
        )
        self.assertEqual(item.id, "bac_2024_iunie_matematica_mate_info_s1_ex1")
        self.assertEqual(item.puncte, 5.0)

    def test_invalid_id_prefix(self) -> None:
        with self.assertRaises(ValueError):
            BacItem(
                id="invalid_id_format",
                an=2024,
                sesiune="iunie-iulie",
                materie="Matematica",
                profil="mate-info",
                sectiune="Subiectul I",
                numar_cerinta="1",
                cerinta_text="Test statement",
                barem_text="Test rubric",
                puncte=5.0,
                topic_curricular="Topic",
            )

    def test_negative_or_zero_points(self) -> None:
        with self.assertRaises(ValidationError):
            BacItem(
                id="bac_2024_iunie_matematica_mate_info_s1_ex1",
                an=2024,
                sesiune="iunie-iulie",
                materie="Matematica",
                profil="mate-info",
                sectiune="Subiectul I",
                numar_cerinta="1",
                cerinta_text="Test statement",
                barem_text="Test rubric",
                puncte=0.0,
                topic_curricular="Topic",
            )

    def test_invalid_year_out_of_bounds(self) -> None:
        with self.assertRaises(ValidationError):
            BacItem(
                id="bac_1990_iunie_matematica_mate_info_s1_ex1",
                an=1990,
                sesiune="iunie-iulie",
                materie="Matematica",
                profil="mate-info",
                sectiune="Subiectul I",
                numar_cerinta="1",
                cerinta_text="Test statement",
                barem_text="Test rubric",
                puncte=5.0,
                topic_curricular="Topic",
            )

    def test_bac_exam_paper_aggregation(self) -> None:
        items = [
            BacItem(
                id=f"bac_2024_iunie_matematica_mate_info_s1_ex{i}",
                an=2024,
                sesiune=ExamSession.IUNIE_IULIE,
                materie=Discipline.MATEMATICA,
                profil=Profile.MATE_INFO,
                sectiune=ExamSection.SUBIECTUL_I,
                numar_cerinta=str(i),
                cerinta_text=f"Exercitiul {i}",
                barem_text=f"Barem {i}",
                puncte=5.0,
                topic_curricular="Algebra",
            )
            for i in range(1, 7)
        ]
        paper = BacExamPaper(
            an=2024,
            sesiune=ExamSession.IUNIE_IULIE,
            materie=Discipline.MATEMATICA,
            profil=Profile.MATE_INFO,
            varianta="Varianta 1",
            items=items,
        )
        self.assertEqual(paper.total_item_points, 30.0)
        self.assertEqual(paper.total_exam_points, 40.0)  # 30p items + 10p default
        s1_items = paper.filter_by_section(ExamSection.SUBIECTUL_I)
        self.assertEqual(len(s1_items), 6)


class TestNoiseCleaner(unittest.TestCase):
    """Tests for regex-based boilerplate noise removal."""

    def test_strips_ministerul_educatiei(self) -> None:
        raw = "Ministerul Educației\nCentrul Național de Politici și Evaluare în Educație\nSUBIECTUL I\n1. Enunț"
        cleaned = clean_institutional_noise(raw)
        self.assertNotIn("Ministerul Educației", cleaned)
        self.assertNotIn("Centrul Național", cleaned)
        self.assertIn("SUBIECTUL I", cleaned)
        self.assertIn("1. Enunț", cleaned)

    def test_strips_timing_and_official_notices(self) -> None:
        raw = "• Timpul de lucru efectiv este de trei ore.\n• Se acordă zece puncte din oficiu.\nRezolvați ecuația."
        cleaned = clean_institutional_noise(raw)
        self.assertNotIn("Timpul de lucru", cleaned)
        self.assertNotIn("puncte din oficiu", cleaned)
        self.assertIn("Rezolvați ecuația.", cleaned)

    def test_preserves_legitimate_prose_with_keywords(self) -> None:
        raw = (
            "Personajul deschide la pagina 45 și analizează varianta a doua a textului."
        )
        cleaned = clean_institutional_noise(raw)
        self.assertIn("pagina 45", cleaned)
        self.assertIn("varianta a doua", cleaned)


class TestJSONLRoundtrip(unittest.TestCase):
    """Tests for saving and loading BacItem records from JSONL files."""

    def test_save_and_load(self) -> None:
        sample_item = BacItem(
            id="bac_2024_iunie_matematica_mate_info_s1_ex1",
            an=2024,
            sesiune="iunie-iulie",
            materie="Matematica",
            profil="mate-info",
            sectiune="Subiectul I",
            numar_cerinta="1",
            cerinta_text="Test statement text",
            barem_text="Test rubric text (5p)",
            puncte=5.0,
            topic_curricular="Test Topic",
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / "test.jsonl"
            save_jsonl([sample_item], tmp_path)
            loaded = load_jsonl(tmp_path)
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0].id, sample_item.id)
            self.assertEqual(loaded[0].cerinta_text, sample_item.cerinta_text)

    def test_load_with_utf8_bom(self) -> None:
        raw_jsonl_with_bom = (
            b'\xef\xbb\xbf{"id": "bac_2024_iunie_matematica_mate_info_s1_ex1", '
            b'"an": 2024, "sesiune": "iunie-iulie", "materie": "Matematica", '
            b'"profil": "mate-info", "sectiune": "Subiectul I", "numar_cerinta": "1", '
            b'"cerinta_text": "Sample", "barem_text": "Rubric", "puncte": 5.0, '
            b'"topic_curricular": "Topic"}\n'
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            bom_path = Path(tmp_dir) / "bom.jsonl"
            bom_path.write_bytes(raw_jsonl_with_bom)
            loaded = load_jsonl(bom_path)
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0].id, "bac_2024_iunie_matematica_mate_info_s1_ex1")
            self.assertEqual(loaded[0].cerinta_text, "Sample")


class TestBaselineAndStats(unittest.TestCase):
    """Tests for dataset statistics and ML baseline classifier."""

    def test_stats_computation(self) -> None:
        sample_path = Path(__file__).resolve().parent.parent / "data/sample.jsonl"
        items = load_jsonl(sample_path)
        stats = compute_statistics(items)
        self.assertEqual(stats["total"], 50)
        by_disc = dict(stats["by_discipline"])
        self.assertIn("Matematica", by_disc)
        self.assertIn("Informatica", by_disc)
        self.assertIn("Limba si literatura romana", by_disc)

    def test_baseline_classifier_training(self) -> None:
        sample_path = Path(__file__).resolve().parent.parent / "data/sample.jsonl"
        clf = train_baseline(sample_path)
        self.assertIsNotNone(clf)
        assert clf is not None
        pred = clf.predict(["Rezolvați în R ecuația logaritmică log_2(x) = 3."])[0]
        self.assertEqual(pred, "Matematica")

    def test_baseline_single_class_graceful_exit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            single_path = Path(tmp_dir) / "single.jsonl"
            save_jsonl(
                [
                    BacItem(
                        id="bac_2024_iunie_matematica_mate_info_s1_ex1",
                        an=2024,
                        sesiune="iunie-iulie",
                        materie="Matematica",
                        profil="mate-info",
                        sectiune="Subiectul I",
                        numar_cerinta="1",
                        cerinta_text="Sample statement 1",
                        barem_text="Sample rubric 1",
                        puncte=5.0,
                        topic_curricular="Algebra",
                    ),
                    BacItem(
                        id="bac_2024_iunie_matematica_mate_info_s1_ex2",
                        an=2024,
                        sesiune="iunie-iulie",
                        materie="Matematica",
                        profil="mate-info",
                        sectiune="Subiectul I",
                        numar_cerinta="2",
                        cerinta_text="Sample statement 2",
                        barem_text="Sample rubric 2",
                        puncte=5.0,
                        topic_curricular="Algebra",
                    ),
                ],
                single_path,
            )
            clf = train_baseline(single_path)
            self.assertIsNone(clf)

    def test_baseline_evaluation_report(self) -> None:
        sample_path = Path(__file__).resolve().parent.parent / "data/sample.jsonl"
        report = evaluate_baseline(sample_path, n_splits=5)
        self.assertIsNotNone(report)
        assert report is not None
        self.assertIn("Informatica", report)
        self.assertIn("Matematica", report)
        self.assertIn("Limba si literatura romana", report)
        self.assertIn("macro avg", report)


if __name__ == "__main__":
    unittest.main()
