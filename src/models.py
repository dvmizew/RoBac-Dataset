"""Pydantic v2 data models for the RoBac-Eval dataset.

Defines schemas for Romanian Baccalaureate examination items, supporting
structured representation of problem statements, grading rubrics (bareme),
and pedagogical metadata.
"""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SesiuneEnum(str, Enum):
    """Sesiunile oficiale de examen."""

    IUNIE_IULIE = "iunie-iulie"
    AUGUST_SEPTEMBRIE = "august-septembrie"
    SIMULARE = "simulare"
    MODELE = "modele"
    SESIUNE_SPECIALA = "sesiune-speciala"


class MaterieEnum(str, Enum):
    """Disciplinele incluse în dataset."""

    MATEMATICA = "Matematica"
    INFORMATICA = "Informatica"
    ROMANA = "Limba si literatura romana"


class ProfilEnum(str, Enum):
    """Profilul sau filiera de studiu."""

    MATE_INFO = "mate-info"
    STIINTE_ALE_NATURII = "stiinte-ale-naturii"
    TEHNOLOGIC = "tehnologic"
    PEDAGOGIC = "pedagogic"
    FILOLOGIE = "filologie"
    STIINTE_SOCIALE = "stiinte-sociale"
    GENERAL = "general"


class SectiuneEnum(str, Enum):
    """Secțiunea din cadrul probei scrise."""

    SUBIECTUL_I = "Subiectul I"
    SUBIECTUL_II = "Subiectul II"
    SUBIECTUL_III = "Subiectul III"


class BacItem(BaseModel):
    """Model structurat reprezentând un item / exercițiu din cadrul examenului de Bacalaureat.

    Attributes:
        id: Identificator unic (ex: 'bac_2024_iunie_matematica_mate_info_s1_ex1').
        an: Anul calendaristic al sesiunii (2015-2024).
        sesiune: Sesiunea examenului (iunie-iulie, simulare, etc.).
        materie: Disciplina de examen.
        profil: Filiera sau specializarea liceală.
        sectiune: Secțiunea din fișa de examen (Subiectul I, II sau III).
        numar_cerinta: Numărul sau identificatorul cerinței (ex: '1', '2.a', 'Subiectul I.A.1').
        context_suport: Fragment de text suport, cod pseudocod, graf sau context textual (opțional).
        cerinta_text: Textul integral al cerinței / exercițiului.
        barem_text: Soluția detaliată, pașii de rezolvare și criteriile de notare din baremul oficial.
        puncte: Punctajul alocat cerinței conform baremului (ex: 5.0, 6.0, 30.0).
        topic_curricular: Categoria tematică din programa școlară (ex: 'Analiză matematică').
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
        description="Identificator unic compus: bac_{an}_{sesiune}_{materie}_{profil}_{sectiune}_{cerinta}",
        min_length=5,
    )
    an: int = Field(
        ...,
        description="Anul desfășurării examenului (2015-2024)",
        ge=2010,
        le=2030,
    )
    sesiune: Union[SesiuneEnum, str] = Field(
        ...,
        description="Sesiunea oficială a examenului",
    )
    materie: Union[MaterieEnum, str] = Field(
        ...,
        description="Disciplina de evaluare",
    )
    profil: Union[ProfilEnum, str] = Field(
        ...,
        description="Filiera / Profilul de studiu al probei",
    )
    sectiune: Union[SectiuneEnum, str] = Field(
        ...,
        description="Secțiunea lucrării: Subiectul I, Subiectul II sau Subiectul III",
    )
    numar_cerinta: str = Field(
        ...,
        description="Eticheta / numărul cerinței (ex: '1', '2.b', 'Subiectul I.A.3')",
    )
    context_suport: Optional[str] = Field(
        default=None,
        description="Textul suport, fragmentul literar, tabelul de valori sau codul asociat",
    )
    cerinta_text: str = Field(
        ...,
        description="Enunțul integral al problemei sau al întrebării",
        min_length=3,
    )
    barem_text: str = Field(
        ...,
        description="Rezolvarea oficială și defalcarea etapelor de acordare a punctajului",
        min_length=3,
    )
    puncte: float = Field(
        ...,
        description="Numărul de puncte acordate conform baremului oficial",
        gt=0.0,
        le=100.0,
    )
    topic_curricular: str = Field(
        ...,
        description="Eticheta tematică curriculară (ex: Geometrie analitică, Teoria grafurilor)",
        min_length=2,
    )

    @field_validator("id")
    @classmethod
    def validate_id_format(cls, value: str) -> str:
        if not value.startswith("bac_"):
            raise ValueError(f"ID-ul trebuie să înceapă cu prefixul 'bac_': {value}")
        return value.lower()

    @field_validator("puncte")
    @classmethod
    def validate_puncte_reasonable(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("Punctajul trebuie să fie strict pozitiv.")
        return round(value, 2)


class DatasetSplit(BaseModel):
    """Metadate despre o colecție de instanțe BacItem."""

    name: str = Field(..., description="Numele split-ului: train, validation sau test")
    items_count: int = Field(..., description="Numărul total de itemi")
    subjects: List[str] = Field(default_factory=list, description="Discipline acoperite")
    years_range: tuple[int, int] = Field(..., description="Intervalul anilor (min, max)")


def load_jsonl(file_path: Union[str, Path]) -> List[BacItem]:
    """Încarcă o listă de instanțe BacItem dintr-un fișier JSONL."""
    path = Path(file_path)
    items: List[BacItem] = []
    with path.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line_str = line.strip()
            if not line_str:
                continue
            try:
                data = json.loads(line_str)
                items.append(BacItem.model_validate(data))
            except Exception as exc:
                raise ValueError(f"Eroare la parsarea liniei {line_num} din {path}: {exc}") from exc
    return items


def save_jsonl(items: List[BacItem], file_path: Union[str, Path]) -> None:
    """Salvează o listă de instanțe BacItem într-un fișier JSONL."""
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item.model_dump(), ensure_ascii=False) + "\n")


def stream_jsonl(file_path: Union[str, Path]) -> Generator[BacItem, None, None]:
    """Generează secvențial instanțe BacItem dintr-un fișier JSONL mare."""
    path = Path(file_path)
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if line_str:
                yield BacItem.model_validate_json(line_str)
