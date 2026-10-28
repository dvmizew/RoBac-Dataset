"""PDF parsing and item extraction pipeline for Romanian Baccalaureate exams.

Uses PyMuPDF (fitz) and pdfplumber to extract text from subject and rubric PDFs,
cleans institutional noise/headers via regex, splits documents into hierarchical
sections (Subiectul I, II, III), and parses individual exercise items aligned
with their official grading points.
"""

from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.models import BacItem, MaterieEnum, ProfilEnum, SectiuneEnum, SesiuneEnum

logger = logging.getLogger("RoBac.Parser")


class ExamNoiseFilter:
    """Regex-based cleaning utilities to remove recurring institutional noise."""

    HEADER_FOOTER_PATTERNS = [
        re.compile(
            r"Ministerul\s+Educa[țt]iei(?:\s+[șs]i\s+Cercet[ăa]rii)?",
            re.IGNORECASE,
        ),
        re.compile(
            r"Centrul\s+Na[țt]ional\s+de\s+Politici\s+[șs]i\s+Evaluare\s+[îi]n\s+Educa[țt]ie",
            re.IGNORECASE,
        ),
        re.compile(
            r"Centrul\s+Na[țt]ional\s+de\s+Evaluare\s+[șs]i\s+Examinare",
            re.IGNORECASE,
        ),
        re.compile(
            r"Examenul\s+na[țt]ional\s+de\s+bacalaureat\s+\d{4}",
            re.IGNORECASE,
        ),
        re.compile(
            r"Prob[ăa]\s+scris[ăa]\s+la\s+[^\n]+",
            re.IGNORECASE,
        ),
        re.compile(
            r"Barem\s+de\s+evaluare\s+[șs]i\s+de\s+notare",
            re.IGNORECASE,
        ),
        re.compile(
            r"Pagina\s+\d+\s+din\s+\d+",
            re.IGNORECASE,
        ),
        re.compile(
            r"•\s*Toate\s+subiectele\s+sunt\s+obligatorii[^\n]*",
            re.IGNORECASE,
        ),
        re.compile(
            r"•\s*Timpul\s+de\s+lucru\s+efectiv\s+este\s+de\s+trei\s+ore[^\n]*",
            re.IGNORECASE,
        ),
        re.compile(
            r"Se\s+acord[ăa]\s+zece\s+puncte\s+din\s+oficiu[^\n]*",
            re.IGNORECASE,
        ),
    ]

    @classmethod
    def clean(cls, text: str) -> str:
        """Strip boilerplate headers, footers, and administrative lines."""
        cleaned = text
        for pattern in cls.HEADER_FOOTER_PATTERNS:
            cleaned = pattern.sub("", cleaned)
        # Normalize multiple blank lines
        cleaned = re.sub(r"\n\s*\n\s*\n+", "\n\n", cleaned)
        return cleaned.strip()


class PDFTextExtractor:
    """Extracts raw text from PDF files using PyMuPDF with pdfplumber fallback."""

    @staticmethod
    def extract_text(pdf_path: Path) -> str:
        """Extract text content from all pages of a PDF."""
        text = ""

        # Try PyMuPDF (fitz)
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(pdf_path)
            pages_text = [page.get_text("text") for page in doc]
            doc.close()
            return "\n".join(pages_text)
        except ImportError:
            pass
        except Exception as exc:
            logger.warning("PyMuPDF failed on %s: %s. Falling back to pdfplumber.", pdf_path, exc)

        # Fallback to pdfplumber
        try:
            import pdfplumber

            with pdfplumber.open(pdf_path) as pdf:
                pages_text = [(page.extract_text() or "") for page in pdf.pages]
            return "\n".join(pages_text)
        except ImportError:
            raise RuntimeError(
                "Nici PyMuPDF (fitz) nici pdfplumber nu sunt instalate. "
                "Instalați dependențele folosind 'pip install -r requirements.txt'."
            )


class BacExamParser:
    """Splits exam documents into structured sections and exercises."""

    # Regex to split major sections (Subiectul I, Subiectul al II-lea, etc.)
    SECTION_SPLIT_REGEX = re.compile(
        r"(SUBIECTUL\s+(?:al\s+)?(?:I|II|III|1|2|3)(?:-lea)?\s*[-–—]?\s*(?:\([^)]*\)|[^\n]*))",
        re.IGNORECASE,
    )

    # Regex to match exercise numbers in STEM subjects
    EXERCISE_STEM_REGEX = re.compile(
        r"(?:^|\n)\s*(\d+)\.\s+",
    )

    # Regex to detect allocated points, e.g., (5p), (10 puncte), (30 de puncte)
    POINTS_REGEX = re.compile(
        r"\(?\s*(\d+(?:[.,]\d+)?)\s*(?:p|pct|puncte|de puncte)\s*\)?",
        re.IGNORECASE,
    )

    def __init__(self, noise_filter: Optional[ExamNoiseFilter] = None) -> None:
        self.noise_filter = noise_filter or ExamNoiseFilter()

    def parse_sections(self, raw_text: str) -> Dict[str, str]:
        """Split cleaned exam text into Subiectul I, Subiectul II, Subiectul III."""
        cleaned = self.noise_filter.clean(raw_text)
        matches = list(self.SECTION_SPLIT_REGEX.finditer(cleaned))

        sections: Dict[str, str] = {}
        if not matches:
            # If no clear section header matched, return full text under Subiectul I
            sections["Subiectul I"] = cleaned
            return sections

        for i, match in enumerate(matches):
            header = match.group(1).strip()
            # Normalize header key
            key = self._normalize_section_key(header)
            start_idx = match.end()
            end_idx = matches[i + 1].start() if i + 1 < len(matches) else len(cleaned)
            content = cleaned[start_idx:end_idx].strip()
            sections[key] = content

        return sections

    def _normalize_section_key(self, raw_header: str) -> str:
        """Standardize section naming to SectiuneEnum values."""
        upper = raw_header.upper()
        if "III" in upper or "3" in upper:
            return SectiuneEnum.SUBIECTUL_III.value
        if "II" in upper or "2" in upper:
            return SectiuneEnum.SUBIECTUL_II.value
        if "I" in upper or "1" in upper:
            return SectiuneEnum.SUBIECTUL_I.value
        return raw_header

    def split_exercises(self, section_text: str) -> List[Tuple[str, str]]:
        """Extract individual exercise items and labels from section text."""
        parts = self.EXERCISE_STEM_REGEX.split(section_text)
        exercises: List[Tuple[str, str]] = []

        if len(parts) <= 1:
            # No numbered split detected
            return [("1", section_text.strip())]

        # parts[0] is preamble before exercise 1
        preamble = parts[0].strip()
        i = 1
        while i < len(parts):
            ex_num = parts[i].strip()
            ex_body = parts[i + 1].strip() if i + 1 < len(parts) else ""
            if preamble and ex_num == "1":
                ex_body = f"{preamble}\n\n{ex_body}".strip()
                preamble = ""
            exercises.append((ex_num, ex_body))
            i += 2

        return exercises

    def extract_points(self, text: str, default: float = 5.0) -> float:
        """Infer points value from exercise or rubric text."""
        match = self.POINTS_REGEX.search(text)
        if match:
            val_str = match.group(1).replace(",", ".")
            try:
                return float(val_str)
            except ValueError:
                pass
        return default

    def parse_exam_pair(
        self,
        subject_pdf_path: Path,
        barem_pdf_path: Path,
        year: int,
        session: str,
        subject: str,
        profile: str,
    ) -> List[BacItem]:
        """End-to-end parsing of a paired subject and barem PDF into BacItem records."""
        subject_raw = PDFTextExtractor.extract_text(subject_pdf_path)
        barem_raw = PDFTextExtractor.extract_text(barem_pdf_path)

        subject_sections = self.parse_sections(subject_raw)
        barem_sections = self.parse_sections(barem_raw)

        items: List[BacItem] = []

        for section_name, sec_content in subject_sections.items():
            barem_sec_content = barem_sections.get(section_name, "")
            exercises = self.split_exercises(sec_content)
            barem_exercises = dict(self.split_exercises(barem_sec_content))

            for ex_num, ex_text in exercises:
                rubric_text = barem_exercises.get(ex_num, barem_sec_content or "Barem în curs de aliniere.")
                points = self.extract_points(ex_text)

                item_id = f"bac_{year}_{session}_{subject}_{profile}_{section_name}_{ex_num}"
                item_id = re.sub(r"[^a-zA-Z0-9_]+", "_", item_id.lower()).strip("_")

                item = BacItem(
                    id=item_id,
                    an=year,
                    sesiune=session,
                    materie=subject,
                    profil=profile,
                    sectiune=section_name,
                    numar_cerinta=ex_num,
                    context_suport=None,
                    cerinta_text=ex_text,
                    barem_text=rubric_text,
                    puncte=points,
                    topic_curricular=f"{subject} - General",
                )
                items.append(item)

        return items


def main() -> None:
    """CLI tester for the extraction parser."""
    parser = argparse.ArgumentParser(description="RoBac-Eval: PDF Extraction Parser")
    parser.add_argument("--subject-pdf", type=str, required=True, help="Path to subject statement PDF")
    parser.add_argument("--barem-pdf", type=str, required=True, help="Path to grading rubric PDF")
    parser.add_argument("--year", type=int, default=2024, help="Exam year")
    parser.add_argument("--session", type=str, default="iunie-iulie", help="Exam session")
    parser.add_argument("--subject", type=str, default="Matematica", help="Subject name")
    parser.add_argument("--profile", type=str, default="mate-info", help="Target profile")
    parser.add_argument("--output-jsonl", type=str, default=None, help="Optional output JSONL file path")

    args = parser.parse_args()

    exam_parser = BacExamParser()
    items = exam_parser.parse_exam_pair(
        subject_pdf_path=Path(args.subject_pdf),
        barem_pdf_path=Path(args.barem_pdf),
        year=args.year,
        session=args.session,
        subject=args.subject,
        profile=args.profile,
    )

    print(f"[✓] Extracted {len(items)} structured items:")
    for item in items:
        print(f" - [{item.sectiune} | Ex {item.numar_cerinta}] ({item.puncte}p): {item.cerinta_text[:70]}...")

    if args.output_jsonl:
        from src.models import save_jsonl

        save_jsonl(items, args.output_jsonl)
        print(f"[✓] Saved {len(items)} items to {args.output_jsonl}")


if __name__ == "__main__":
    main()
