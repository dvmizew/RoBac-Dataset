# RoBac-Eval

A structured dataset of Romanian National Baccalaureate (*Bacalaureat*) exam questions and official grading rubrics (2015–2024), parsed from PDF into JSONL format for NLP tasks, curricular topic classification, and semantic search.

The full project proposal is documented in [`docs/data-proposal.md`](docs/data-proposal.md).

### Team
- Radu Daniel-Dumitru
- Godeanu Victor
- Iorga Iustin-Nicolae
- Petcu Andreea-Elena

---

## Repository Structure

```text
├── docs/
│   └── data-proposal.md    # Detailed dataset proposal and specification
├── data/
│   ├── sample.jsonl        # 20 real sample records (Math, CS, Romanian Literature)
│   └── raw/                # Downloaded exam PDFs (ignored by git)
├── src/
│   ├── crawler.py          # Download & extract utility for subiecte.edu.ro
│   ├── parser.py           # PDF text extractor, noise cleaner, and section splitter
│   └── models.py           # Pydantic v2 schemas (BacItem) and JSONL I/O helpers
├── requirements.txt
└── .gitignore
```

---

## Installation

Requires Python 3.10+:

```bash
git clone https://github.com/dvmizew/RoBac-Dataset.git
cd RoBac-Dataset

python -m venv .venv
source .venv/bin/activate       # On Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

---

## Usage

### 1. Loading the Dataset (`data/sample.jsonl`)

The repository includes 20 real records from the 2023–2024 exam sessions:

```python
from src.models import load_jsonl

items = load_jsonl("data/sample.jsonl")
print(f"Loaded {len(items)} items")

item = items[0]
print(f"[{item.materie}] {item.sectiune} ex. {item.numar_cerinta} ({item.puncte}p)")
print("Question:", item.cerinta_text)
print("Rubric:", item.barem_text)
```

### 2. Crawling Official PDFs (`src/crawler.py`)

The crawler queries official CNPEE subdomains (`subiecte2024.edu.ro`, etc.), downloads discipline ZIP bundles, and extracts PDFs to `data/raw/<year>/<session>/<subject>/`:

```bash
# Download 2024 summer session Mathematics variants and rubrics
python -m src.crawler --years 2024 --sessions iunie-iulie --subjects Matematica --download
```

### 3. Parsing an Exam Pair (`src/parser.py`)

Extracts text via PyMuPDF / pdfplumber, strips administrative boilerplate, splits sections, and aligns problem statements with their official grading rubric:

```bash
python -m src.parser \
  --subject-pdf data/raw/2024/iunie-iulie/Matematica/E_c_matematica_M_mate-info_2024_var_10_LRO.pdf \
  --barem-pdf data/raw/2024/iunie-iulie/Matematica/E_c_matematica_M_mate-info_2024_bar_10_LRO.pdf \
  --year 2024 \
  --session iunie-iulie \
  --subject Matematica \
  --profile mate-info \
  --output-jsonl data/mate_2024_parsed.jsonl
```

---

## Record Schema

Each line in the `.jsonl` dataset represents a discrete exercise mapped to its official rubric breakdown:

```json
{
  "id": "bac_2024_iunie_matematica_mate_info_s3_ex2_a",
  "an": 2024,
  "sesiune": "iunie-iulie",
  "materie": "Matematica",
  "profil": "mate-info",
  "sectiune": "Subiectul III",
  "numar_cerinta": "2.a",
  "context_suport": "Se consideră funcția f: R -> R, f(x) = e^x / (e^x + 1).",
  "cerinta_text": "Arătați că integrala de la 0 la 1 din f(x) dx este egală cu ln((e + 1) / 2).",
  "barem_text": "f(x) = (e^x + 1)' / (e^x + 1) (2p); Integrala devine [ln(e^x + 1)] evaluată de la 0 la 1 (2p); ln(e + 1) - ln(1 + 1) = ln((e + 1) / 2) (1p).",
  "puncte": 5.0,
  "topic_curricular": "Analiză matematică - Integrale definite"
}
```

---

## License & Data Policy

- **Raw Exam PDFs:** Public domain government documents (Romanian Law 544/2001 and Law 8/1996 Art. 9).
- **Processed Dataset:** [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
- **Code:** MIT.
