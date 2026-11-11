"""PDF extraction, noise cleaning, and dataset structuring pipeline.

Processes Romanian National Baccalaureate exam statement and rubric PDFs,
cleans administrative and institutional boilerplate, parses exercises across
Mathematics, Computer Science, and Romanian Literature, validates records
via Pydantic v2 (BacItem), and exports the dataset to JSONL.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pymupdf

from src.models import BacItem, load_jsonl, save_jsonl

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("RoBac.Parser")

INSTITUTIONAL_NOISE_PATTERNS = [
    r"(?m)^\s*Ministerul\s+Educa[țt]iei.*$",
    r"(?m)^\s*Centrul\s+Na[țt]ional\s+de\s+Politici\s+[șs]i\s+Evaluare\s+[îi]n\s+Educa[țt]ie.*$",
    r"(?m)^\s*Centrul\s+Na[țt]ional\s+de\s+Evaluare\s+[șs]i\s+Examinare.*$",
    r"(?m)^\s*Centrul\s+Na[țt]ional\s+pentru\s+Curriculum\s+[șs]i\s+Evaluare.*$",
    r"(?m)^\s*Examenul\s+na[țt]ional\s+de\s+bacalaureat.*$",
    r"(?m)^\s*Prob[ăa]\s+scris[ăa]\s+.*$",
    r"(?m)^\s*Varianta\s+\d+.*$",
    r"(?m)^\s*Barem\s+de\s+evaluare.*$",
    r"(?m)^\s*BAREM\s+DE\s+EVALUARE.*$",
    r"(?m)^\s*Filier[ăa]\s+.*$",
    r"(?m)^\s*Pagina\s+\d+\s+din\s+\d+.*$",
    r"(?m)^\s*Proba\s+E\.\s*[a-d]\).*",
    r"(?m)^\s*•\s*Toate\s+subiectele.*$",
    r"(?m)^\s*•\s*Pentru\s+orice\s+solu.*$",
    r"(?m)^\s*•\s*Nu\s+se\s+acord.*$",
    r"(?m)^\s*•\s*Timpul\s+de\s+lucru.*$",
    r"(?m)^\s*•\s*Se\s+acord[ăa]\s+zece\s+puncte.*$",
    r"(?m)^\s*•\s*Identificatorii\s+utilizați.*$",
    r"(?m)^\s*•\s*În\s+grafurile\s+din\s+cerințe.*$",
]

CURRICULAR_TOPICS_MATE = {
    "1": "Algebră - Numere complexe și logaritmi",
    "2": "Algebră - Funcții și ecuații",
    "3": "Algebră - Ecuații exponențiale și iraționale",
    "4": "Combinatorică - Submulțimi și probabilități",
    "5": "Geometrie analitică - Vectori și drepte în plan",
    "6": "Trigonometrie - Relații în triunghi",
}


def clean_institutional_noise(text: str) -> str:
    """Strip institutional headers, footers, control characters, and notices."""
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    for pat in INSTITUTIONAL_NOISE_PATTERNS:
        cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE)
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", cleaned).strip()


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract raw text from PDF using PyMuPDF and strip noise."""
    doc = pymupdf.open(pdf_path)
    text = "\n".join(doc[i].get_text("text") for i in range(len(doc)))
    doc.close()
    return clean_institutional_noise(text)


def infer_metadata(var_path: Path) -> dict[str, str | int]:
    """Infer exam metadata (year, session, discipline, profile) from path and filename."""
    name_low = var_path.name.lower()
    path_low = str(var_path).lower()

    year = 2024
    if var_path.parent.name.isdigit():
        year = int(var_path.parent.name)
    else:
        ym = re.search(r"\b(20\d\d)\b", name_low)
        if ym:
            year = int(ym.group(1))

    if "matematica" in name_low or "e_c_" in name_low:
        materie = "Matematica"
    elif "informatica" in name_low or "e_d_" in name_low:
        materie = "Informatica"
    elif "romana" in name_low or "llr" in name_low or "e_a_" in name_low:
        materie = "Limba si literatura romana"
    else:
        materie = "General"

    if "mate-info" in name_low or "sp_mi" in name_low:
        profil = "mate-info"
    elif "tehn" in name_low:
        profil = "tehnologic"
    elif "stiinte" in name_low or "sn" in name_low:
        profil = "stiinte-ale-naturii"
    elif "real" in name_low:
        profil = "real"
    else:
        profil = "mate-info"

    if "simulare" in path_low:
        sesiune = "simulare"
    elif "modele" in path_low or ("var_01" in name_low and year >= 2025):
        sesiune = "modele"
    elif "special" in path_low:
        sesiune = "sesiunea-speciala"
    elif "toamna" in path_low or "august" in path_low:
        sesiune = "august-septembrie"
    else:
        sesiune = "iunie-iulie"

    return {"an": year, "sesiune": sesiune, "materie": materie, "profil": profil}


def discover_exam_pairs(raw_dir: Path) -> list[tuple[Path, Path]]:
    """Recursively scan raw_dir for matching statement and rubric PDF pairs."""
    pairs: list[tuple[Path, Path]] = []
    statement_candidates = sorted(raw_dir.rglob("*_var_*.pdf"))

    for var_f in statement_candidates:
        parent = var_f.parent
        all_pdfs = {f.name.lower(): f for f in parent.glob("*.pdf")}
        name_low = var_f.name.lower()

        patterns = [
            name_low.replace("_var_", "_bar_"),
            re.sub(r"_[cpascal]+_var_", "_bar_", name_low),
            re.sub(r"_var_(\d+)", r"_bar_\1", name_low),
        ]
        match: Path | None = None
        for pat in patterns:
            if pat in all_pdfs:
                match = all_pdfs[pat]
                break

        if match:
            pairs.append((var_f, match))
        else:
            logger.warning("No rubric pair found for %s", var_f.relative_to(raw_dir))

    return pairs


def parse_matematica(
    var_text: str, bar_text: str, meta: dict[str, str | int]
) -> list[BacItem]:
    """Parse Mathematics Subiectul I exercises and official rubric steps."""
    items: list[BacItem] = []
    an = int(meta["an"])
    sesiune = str(meta["sesiune"])
    materie = str(meta["materie"])
    profil = str(meta["profil"])
    ses_slug = sesiune.split("-")[0]

    s1_var_m = re.search(
        r"SUBIECTUL\s+I.*?\n(?:\(.*?\))?(.*?)(?=SUBIECTUL\s+al|\Z)",
        var_text,
        re.DOTALL | re.IGNORECASE,
    )
    s1_bar_m = re.search(
        r"SUBIECTUL\s+I.*?\n(?:\(.*?\))?(.*?)(?=SUBIECTUL\s+al|\Z)",
        bar_text,
        re.DOTALL | re.IGNORECASE,
    )
    if not s1_var_m or not s1_bar_m:
        return items

    splits = list(
        re.compile(r"(?:(?:5p\s+)?(?:\n|^))\s*(\d+)\.\s+").finditer(s1_var_m.group(1))
    )
    b_splits = list(re.compile(r"(?:^|\n)\s*(\d+)\.\s+").finditer(s1_bar_m.group(1)))

    bar_items: dict[str, str] = {}
    for i, m in enumerate(b_splits):
        num = m.group(1)
        st = m.end()
        en = (
            b_splits[i + 1].start() if i + 1 < len(b_splits) else len(s1_bar_m.group(1))
        )
        bar_items[num] = s1_bar_m.group(1)[st:en].strip()

    for i, m in enumerate(splits):
        num = m.group(1)
        st = m.end()
        en = splits[i + 1].start() if i + 1 < len(splits) else len(s1_var_m.group(1))
        cerinta = s1_var_m.group(1)[st:en].strip()
        barem = bar_items.get(num, "Barem oficial conform ghidului CNPEE.")
        item_id = f"bac_{an}_{ses_slug}_matematica_{profil}_s1_ex{num}".lower()

        items.append(
            BacItem(
                id=item_id,
                an=an,
                sesiune=sesiune,
                materie=materie,
                profil=profil,
                sectiune="Subiectul I",
                numar_cerinta=num,
                context_suport=None,
                cerinta_text=cerinta,
                barem_text=barem,
                puncte=5.0,
                topic_curricular=CURRICULAR_TOPICS_MATE.get(num, "Algebră / Geometrie"),
            )
        )
    return items


def parse_informatica(
    var_text: str, bar_text: str, meta: dict[str, str | int]
) -> list[BacItem]:
    """Parse Computer Science Subiectul I multiple choice problems and rubric."""
    items: list[BacItem] = []
    an = int(meta["an"])
    sesiune = str(meta["sesiune"])
    materie = str(meta["materie"])
    profil = str(meta["profil"])
    ses_slug = sesiune.split("-")[0]

    s1_var_m = re.search(
        r"SUBIECTUL\s+I.*?\n(?:\(.*?\))?(.*?)(?=SUBIECTUL\s+al|\Z)",
        var_text,
        re.DOTALL | re.IGNORECASE,
    )
    s1_bar_m = re.search(
        r"SUBIECTUL\s+I.*?\n(?:\(.*?\))?(.*?)(?=SUBIECTUL\s+al|\Z)",
        bar_text,
        re.DOTALL | re.IGNORECASE,
    )
    if not s1_var_m or not s1_bar_m:
        return items

    bar_answers: dict[str, str] = {}
    for num, letter in re.findall(r"(\d+)\s*([a-d])", s1_bar_m.group(1), re.IGNORECASE):
        bar_answers[num] = f"Răspuns corect: {letter.lower()} (4 puncte)"

    splits = list(re.compile(r"(?:^|\n)\s*(\d+)\.\s+").finditer(s1_var_m.group(1)))
    for i, m in enumerate(splits):
        num = m.group(1)
        st = m.end()
        en = splits[i + 1].start() if i + 1 < len(splits) else len(s1_var_m.group(1))
        cerinta = s1_var_m.group(1)[st:en].strip()
        barem = bar_answers.get(
            num, "Răspuns corect conform baremului oficial (4 puncte)"
        )
        item_id = f"bac_{an}_{ses_slug}_informatica_{profil}_s1_ex{num}".lower()

        items.append(
            BacItem(
                id=item_id,
                an=an,
                sesiune=sesiune,
                materie=materie,
                profil=profil,
                sectiune="Subiectul I",
                numar_cerinta=num,
                context_suport=None,
                cerinta_text=cerinta,
                barem_text=barem,
                puncte=4.0,
                topic_curricular="Elemente de bază ale limbajului C/C++ și algoritmi",
            )
        )
    return items


def parse_romana(
    var_text: str, bar_text: str, meta: dict[str, str | int]
) -> list[BacItem]:
    """Parse Romanian Literature Subiectul I reading comprehension and essay prompts."""
    items: list[BacItem] = []
    an = int(meta["an"])
    sesiune = str(meta["sesiune"])
    materie = str(meta["materie"])
    profil = str(meta["profil"])
    ses_slug = sesiune.split("-")[0]

    ctx_m = re.search(
        r"Cite[şș]te urm[ăa]torul fragment:\s*(.*?)(?=A\.\s*Scrie pe foaia|\Z)",
        var_text,
        re.DOTALL | re.IGNORECASE,
    )
    context_text = ctx_m.group(1).strip() if ctx_m else None

    a_m = re.search(
        r"A\.\s*Scrie pe foaia de examen.*?\n(.*?)B\.\s*Redacteaz[ăa]",
        var_text,
        re.DOTALL | re.IGNORECASE,
    )
    bar_a_m = re.search(
        r"A\.\s*\(30\s+de\s+puncte\)(.*?)B\.\s*\(20\s+de\s+puncte\)",
        bar_text,
        re.DOTALL | re.IGNORECASE,
    )
    bar_items: dict[str, str] = {}
    if bar_a_m:
        b_splits = list(re.compile(r"(?:^|\n)\s*(\d+)\.\s+").finditer(bar_a_m.group(1)))
        for i, m in enumerate(b_splits):
            num = m.group(1)
            st = m.end()
            en = (
                b_splits[i + 1].start()
                if i + 1 < len(b_splits)
                else len(bar_a_m.group(1))
            )
            bar_items[num] = bar_a_m.group(1)[st:en].strip()

    if a_m:
        splits = list(re.compile(r"(?:^|\n)\s*(\d+)\.\s+").finditer(a_m.group(1)))
        for i, m in enumerate(splits):
            num = m.group(1)
            st = m.end()
            en = splits[i + 1].start() if i + 1 < len(splits) else len(a_m.group(1))
            cerinta = re.sub(
                r"\s*\d+\s+puncte\s*$", "", a_m.group(1)[st:en].strip()
            ).strip()
            barem = bar_items.get(num, "Barem oficial conform ghidului CNPEE.")
            item_id = f"bac_{an}_{ses_slug}_romana_{profil}_s1_a_ex{num}".lower()

            items.append(
                BacItem(
                    id=item_id,
                    an=an,
                    sesiune=sesiune,
                    materie=materie,
                    profil=profil,
                    sectiune="Subiectul I",
                    numar_cerinta=f"Subiectul I.A.{num}",
                    context_suport=context_text,
                    cerinta_text=cerinta,
                    barem_text=barem,
                    puncte=6.0,
                    topic_curricular="Înțelegerea textului literar/memorialistic",
                )
            )

    b_m = re.search(
        r"B\.\s*Redacteaz[ăa]\s+un\s+text.*?\n(.*?)(?=SUBIECTUL\s+al|\Z)",
        var_text,
        re.DOTALL | re.IGNORECASE,
    )
    bar_b_m = re.search(
        r"B\.\s*\(20\s+de\s+puncte\)(.*?)(?=SUBIECTUL\s+al|\Z)",
        bar_text,
        re.DOTALL | re.IGNORECASE,
    )
    if b_m:
        cerinta_b = b_m.group(1).strip()
        barem_b = (
            bar_b_m.group(1).strip()
            if bar_b_m
            else "Barem oficial pentru text argumentativ (20 puncte)."
        )
        item_id = f"bac_{an}_{ses_slug}_romana_{profil}_s1_b".lower()
        items.append(
            BacItem(
                id=item_id,
                an=an,
                sesiune=sesiune,
                materie=materie,
                profil=profil,
                sectiune="Subiectul I",
                numar_cerinta="Subiectul I.B",
                context_suport=None,
                cerinta_text=cerinta_b,
                barem_text=barem_b,
                puncte=20.0,
                topic_curricular="Redactare - Text argumentativ",
            )
        )

    return items


def parse_exam_pair(subiect_pdf: Path, barem_pdf: Path) -> list[BacItem]:
    """Route a discovered PDF pair to the corresponding discipline parser."""
    meta = infer_metadata(subiect_pdf)
    var_text = extract_pdf_text(subiect_pdf)
    bar_text = extract_pdf_text(barem_pdf)

    materie = meta["materie"]
    if materie == "Matematica":
        return parse_matematica(var_text, bar_text, meta)
    if materie == "Informatica":
        return parse_informatica(var_text, bar_text, meta)
    if materie == "Limba si literatura romana":
        return parse_romana(var_text, bar_text, meta)

    logger.warning("Discipline '%s' parser not configured.", materie)
    return []


DEFAULT_RAW_DIR = REPO_ROOT / "data/raw"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "data/sample.jsonl"


def run_pipeline(
    raw_dir: Path = DEFAULT_RAW_DIR,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> list[BacItem]:
    """Execute end-to-end discovery, parsing, validation, and export pipeline."""
    if not raw_dir.exists():
        raise FileNotFoundError(f"Raw directory does not exist: {raw_dir}")

    pairs = discover_exam_pairs(raw_dir)
    if not pairs:
        raise FileNotFoundError(
            f"No matching PDF pairs (*_var_*.pdf and *_bar_*.pdf) found under {raw_dir}."
        )

    logger.info("Discovered %d exam pairs across %s", len(pairs), raw_dir)

    all_parsed_items: list[BacItem] = []
    for var_p, bar_p in pairs:
        parsed = parse_exam_pair(var_p, bar_p)
        logger.info(
            "Extracted %d items from [%s / %s]",
            len(parsed),
            var_p.parent.name,
            var_p.name,
        )
        all_parsed_items.extend(parsed)

    item_map: dict[str, BacItem] = {}
    if output_path.exists():
        try:
            for it in load_jsonl(output_path):
                item_map[it.id] = it
        except (OSError, ValueError) as exc:
            logger.warning(
                "Could not read existing items from %s: %s", output_path, exc
            )

    for it in all_parsed_items:
        item_map[it.id] = it

    final_items = list(item_map.values())
    save_jsonl(final_items, output_path)
    logger.info(
        "Successfully exported %d validated BacItem records to %s",
        len(final_items),
        output_path,
    )
    return final_items


def main() -> None:
    parser = argparse.ArgumentParser(
        description="RoBac-Eval: PDF Extraction and Healing Parser"
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=DEFAULT_RAW_DIR,
        help="Root directory with raw exam PDFs (defaults to data/raw)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Output JSONL path (defaults to data/sample.jsonl)",
    )
    args = parser.parse_args()

    items = run_pipeline(raw_dir=args.raw_dir, output_path=args.output)
    print(f"\n[OK] Pipeline completed. Total records in {args.output}: {len(items)}")
    for it in items[:10]:
        print(f" - [{it.id}] ({it.puncte}p): {it.cerinta_text[:60]}...")
    if len(items) > 10:
        print(f"   ... and {len(items) - 10} more items.")


if __name__ == "__main__":
    main()
