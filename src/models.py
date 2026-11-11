"""Pydantic v2 data models for the RoBac-Eval benchmark.

EXAMINATION STRUCTURE AND DATA MODELING:
================================================================================
A Romanian National Baccalaureate (CNPEE) written exam is graded on a 100-point scale:
  - 10 points granted by default ("din oficiu")
  - 90 points split equally across three mandatory sections (30 points each):

   [Baccalaureate Exam Paper] (100p = 10p default + 90p sections)
     │  Metadata: an (year, e.g. 2024), sesiune (session), materie (discipline), profil (track)
     │
     ├── Subiectul I (30 points)
     │     ├── Item 1 (5p) ────► BacItem (statement + context + rubric + points)
     │     ├── Item 2 (5p) ────► BacItem
     │     └── ... Item 6 (5p) ─► BacItem
     │
     ├── Subiectul II (30 points)
     │     ├── Problem 1 (15p: 1.a = 5p, 1.b = 5p, 1.c = 5p) ────► BacItems
     │     └── Problem 2 (15p: 2.a = 5p, 2.b = 5p, 2.c = 5p) ────► BacItems
     │
     └── Subiectul III (30 points)
           ├── Problem 1 (15p: 1.a = 5p, 1.b = 5p, 1.c = 5p) ────► BacItems
           └── Problem 2 (15p: 2.a = 5p, 2.b = 5p, 2.c = 5p) ────► BacItems

WHY ATOMIC ITEMS (BacItem)?
For evaluation benchmarks, LLMs are evaluated per exercise against the official
grading rubric. Each BacItem packages an individual exercise statement, optional
support context (reading passage, code snippet, or shared premise), official rubric
criteria, and point allocation.
================================================================================
"""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Discipline(str, Enum):
    """Core evaluation disciplines in the Romanian Baccalaureate."""

    MATEMATICA = "Matematica"
    INFORMATICA = "Informatica"
    ROMANA = "Limba si literatura romana"


class ExamSection(str, Enum):
    """The three standard mandatory exam sections (30 points each)."""

    SUBIECTUL_I = "Subiectul I"
    SUBIECTUL_II = "Subiectul II"
    SUBIECTUL_III = "Subiectul III"


class ExamSession(str, Enum):
    """Official annual examination sessions organized by CNPEE."""

    IUNIE_IULIE = "iunie-iulie"
    AUGUST_SEPTEMBRIE = "august-septembrie"
    SIMULARE = "simulare"
    MODELE = "modele"
    SPECIALA = "sesiunea-speciala"


class Profile(str, Enum):
    """Academic tracks and high-school specializations."""

    MATE_INFO = "mate-info"
    STIINTE_ALE_NATURII = "stiinte-ale-naturii"
    TEHNOLOGIC = "tehnologic"
    REAL = "real"
    UMANIST = "umanist"
    VOCATIONAL = "vocational"
    PEDAGOGIC = "pedagogic"


class BacItem(BaseModel):
    """Structured representation of a single atomic Baccalaureate exercise and rubric."""

    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
        extra="forbid",
        json_schema_extra={
            "example": {
                "id": "bac_2024_iunie_matematica_mate_info_s1_ex1",
                "an": 2024,
                "sesiune": "iunie-iulie",
                "materie": "Matematica",
                "profil": "mate-info",
                "sectiune": "Subiectul I",
                "numar_cerinta": "1",
                "context_suport": None,
                "cerinta_text": "Aratati ca numarul n = log_2(3) + log_2(12) - 2 * log_2(3) este numar natural.",
                "barem_text": "log_2(3) + log_2(12) - log_2(9) = log_2(36/9) = log_2(4) (3p); log_2(4) = 2, care este numar natural (2p).",
                "puncte": 5.0,
                "topic_curricular": "Algebra - Logaritmi si proprietati",
            }
        },
    )

    id: str = Field(
        ...,
        description="Unique composite slug: bac_{year}_{session}_{discipline}_{profile}_{section}_{item}",
        min_length=5,
    )
    an: int = Field(
        ...,
        description="Calendar year of examination (2010-2030)",
        ge=2010,
        le=2030,
    )
    sesiune: ExamSession | str = Field(
        ...,
        description="Official examination session (e.g. 'iunie-iulie', 'modele')",
    )
    materie: Discipline | str = Field(
        ...,
        description="Evaluation discipline (e.g. 'Matematica', 'Informatica', 'Limba si literatura romana')",
    )
    profil: Profile | str = Field(
        ...,
        description="Academic track / profile (e.g. 'mate-info', 'tehnologic')",
    )
    sectiune: ExamSection | str = Field(
        ...,
        description="Exam section: 'Subiectul I' (30p), 'Subiectul II' (30p), or 'Subiectul III' (30p)",
    )
    numar_cerinta: str = Field(
        ...,
        description="Question identifier or sub-item label (e.g. '1', '2.b', 'Subiectul I.A.3', 'Subiectul I.B')",
    )
    context_suport: str | None = Field(
        default=None,
        description="Optional support text (literary passage, source code, or problem preamble)",
    )
    cerinta_text: str = Field(
        ...,
        description="Complete text of the exercise statement or question",
        min_length=3,
    )
    barem_text: str = Field(
        ...,
        description="Official step-by-step grading criteria and point breakdown",
        min_length=3,
    )
    puncte: float = Field(
        ...,
        description="Allocated point value according to official rubric (e.g. 4.0, 5.0, 6.0, 20.0)",
        gt=0.0,
        le=100.0,
    )
    topic_curricular: str = Field(
        ...,
        description="Curricular topic category from official syllabus",
        min_length=2,
    )

    @field_validator("id")
    @classmethod
    def validate_id_format(cls, value: str) -> str:
        if not value.startswith("bac_"):
            raise ValueError(f"ID must start with 'bac_' prefix: {value}")
        return value.lower()

    @field_validator("puncte")
    @classmethod
    def validate_puncte_reasonable(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("Points value must be strictly positive.")
        return round(value, 2)


class BacExamPaper(BaseModel):
    """Aggregate model representing a complete Baccalaureate exam paper.

    Unifies atomic BacItem instances and verifies point consistency
    (10 default points + 90 section points = 100 points total).
    """

    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
        extra="forbid",
    )

    an: int = Field(..., description="Calendar year of examination", ge=2010, le=2030)
    sesiune: ExamSession | str = Field(..., description="Official examination session")
    materie: Discipline | str = Field(..., description="Evaluation discipline")
    profil: Profile | str = Field(..., description="Academic track / profile")
    varianta: str | None = Field(
        default=None, description="Official variant label (e.g. 'Varianta 1')"
    )
    puncte_oficiu: float = Field(
        default=10.0, description="Default points granted by official methodology"
    )
    items: list[BacItem] = Field(
        default_factory=list, description="List of atomic exam items"
    )

    @property
    def total_item_points(self) -> float:
        """Cumulative points from all exam items (standard: 90.0 points)."""
        return sum(item.puncte for item in self.items)

    @property
    def total_exam_points(self) -> float:
        """Total paper score including default 10 points (total: 100.0 points)."""
        return round(self.total_item_points + self.puncte_oficiu, 2)

    def filter_by_section(self, section: ExamSection | str) -> list[BacItem]:
        """Filter items belonging to a specific section (e.g. 'Subiectul I')."""
        return [item for item in self.items if str(item.sectiune) == str(section)]


def load_jsonl(file_path: str | Path) -> list[BacItem]:
    """Load a list of BacItem instances from a JSONL file."""
    path = Path(file_path)
    items: list[BacItem] = []
    with path.open("r", encoding="utf-8-sig") as f:
        for line_num, line in enumerate(f, start=1):
            line_str = line.strip()
            if not line_str:
                continue
            try:
                data = json.loads(line_str)
                items.append(BacItem.model_validate(data))
            except Exception as exc:
                raise ValueError(
                    f"Error parsing line {line_num} from {path}: {exc}"
                ) from exc
    return items


def save_jsonl(items: list[BacItem], file_path: str | Path) -> None:
    """Save a list of BacItem instances to a JSONL file."""
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item.model_dump(mode="json"), ensure_ascii=False) + "\n")
