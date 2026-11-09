"""Pydantic v2 data models for the RoBac-Eval dataset.

Defines schemas for Romanian Baccalaureate examination items, supporting
structured representation of problem statements, grading rubrics (bareme),
and pedagogical metadata.
"""

from __future__ import annotations

import json
from collections.abc import Generator
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SesiuneEnum(str, Enum):
    """Official examination sessions."""

    IUNIE_IULIE = "iunie-iulie"
    AUGUST_SEPTEMBRIE = "august-septembrie"
    SIMULARE = "simulare"
    MODELE = "modele"
    SESIUNE_SPECIALA = "sesiune-speciala"


class MaterieEnum(str, Enum):
    """Evaluation disciplines included in the dataset."""

    MATEMATICA = "Matematica"
    INFORMATICA = "Informatica"
    ROMANA = "Limba si literatura romana"


class ProfilEnum(str, Enum):
    """High school academic tracks and specializations."""

    MATE_INFO = "mate-info"
    STIINTE_ALE_NATURII = "stiinte-ale-naturii"
    TEHNOLOGIC = "tehnologic"
    PEDAGOGIC = "pedagogic"
    FILOLOGIE = "filologie"
    STIINTE_SOCIALE = "stiinte-sociale"
    GENERAL = "general"


class SectiuneEnum(str, Enum):
    """Exam paper section identifiers."""

    SUBIECTUL_I = "Subiectul I"
    SUBIECTUL_II = "Subiectul II"
    SUBIECTUL_III = "Subiectul III"


class BacItem(BaseModel):
    """Structured representation of a single Baccalaureate exercise and its grading rubric.

    Attributes:
        id: Unique identifier (e.g. 'bac_2024_iunie_matematica_mate_info_s1_ex1').
        an: Calendar year of the examination session (e.g. 2024).
        sesiune: Official examination session name.
        materie: Examination discipline.
        profil: High school academic track / profile.
        sectiune: Exam paper section (Subiectul I, Subiectul II, Subiectul III).
        numar_cerinta: Exercise number or sub-question label (e.g. '1', '2.a').
        context_suport: Optional reading passage, pseudocode block, or contextual support text.
        cerinta_text: Full text of the problem statement or question.
        barem_text: Detailed solution steps, grading criteria, and point distribution.
        puncte: Allocated points according to official grading rubric.
        topic_curricular: Standardized curricular topic classification label.
    """

    model_config = ConfigDict(
        use_enum_values=True,
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
                "cerinta_text": "Arătați că numărul n = log_2(3) + log_2(12) - 2 * log_2(3) este număr natural.",
                "barem_text": "log_2(3) + log_2(12) - log_2(9) = log_2(36/9) = log_2(4) (3p); log_2(4) = 2, care este număr natural (2p).",
                "puncte": 5.0,
                "topic_curricular": "Algebră - Logaritmi și proprietăți",
            }
        },
    )

    id: str = Field(
        ...,
        description="Unique composite identifier: bac_{year}_{session}_{subject}_{profile}_{section}_{num}",
        min_length=5,
    )
    an: int = Field(
        ...,
        description="Calendar year of examination (2010-2030)",
        ge=2010,
        le=2030,
    )
    sesiune: SesiuneEnum | str = Field(
        ...,
        description="Official examination session name",
    )
    materie: MaterieEnum | str = Field(
        ...,
        description="Evaluation discipline / subject",
    )
    profil: ProfilEnum | str = Field(
        ...,
        description="High school academic track / specialization",
    )
    sectiune: SectiuneEnum | str = Field(
        ...,
        description="Exam paper section: Subiectul I, Subiectul II, or Subiectul III",
    )
    numar_cerinta: str = Field(
        ...,
        description="Exercise number or sub-question label (e.g. '1', '2.b', 'Subiectul I.A.3')",
    )
    context_suport: str | None = Field(
        default=None,
        description="Optional support text, literary passage, or pseudocode context",
    )
    cerinta_text: str = Field(
        ...,
        description="Full text of the problem statement or question",
        min_length=3,
    )
    barem_text: str = Field(
        ...,
        description="Official grading rubric steps and point allocation criteria",
        min_length=3,
    )
    puncte: float = Field(
        ...,
        description="Allocated points according to official grading rubric",
        gt=0.0,
        le=100.0,
    )
    topic_curricular: str = Field(
        ...,
        description="Curricular topic category (e.g. Analytic Geometry, Graph Theory)",
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


def load_jsonl(file_path: str | Path) -> list[BacItem]:
    """Load a list of BacItem instances from a JSONL file."""
    path = Path(file_path)
    items: list[BacItem] = []
    with path.open("r", encoding="utf-8") as f:
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
            f.write(json.dumps(item.model_dump(), ensure_ascii=False) + "\n")


def stream_jsonl(file_path: str | Path) -> Generator[BacItem, None, None]:
    """Yield BacItem instances sequentially from a large JSONL file."""
    path = Path(file_path)
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if line_str:
                yield BacItem.model_validate_json(line_str)
