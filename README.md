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
│   ├── sample.jsonl        # 50 real sample records (Math, CS, Romanian Literature)
│   └── raw/                # Downloaded exam PDFs (ignored by git)
├── src/
│   ├── crawler.py          # Download & extract utility for edu.ro & Wayback Machine
│   ├── parser.py           # PDF text extractor, noise cleaner, and section splitter
│   ├── models.py           # Pydantic v2 schemas (BacItem) and JSONL I/O helpers
│   ├── baseline.py         # TF-IDF + LinearSVC baseline classifier with interactive CLI
│   └── stats.py            # Dataset profiling and descriptive statistics utility
├── tests/
│   └── test_pipeline.py    # Automated unit test suite (Pydantic, regex, ML baseline)
├── pyproject.toml          # Modern Python packaging and tool configuration
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

The repository includes 50 real records across 2024–2025 exam sessions:

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

The crawler queries official CNPEE endpoints (`subiecte<year>.edu.ro`), downloads discipline archives, and extracts matching statement and rubric pairs to `data/raw/<year>/`:

```bash
# Default: download 2024 core disciplines (Matematica, Informatica, Romana)
python -m src.crawler

# Multi-year crawl (e.g. 2024 and 2025):
python -m src.crawler --years 2024 2025

# Target specific disciplines:
python -m src.crawler --years 2024 --disciplines Matematica Informatica
```

### 3. Parsing and Structuring Exam Pairs (`src/parser.py`)

Recursively scans `data/raw/` for statement and rubric PDF pairs, strips administrative boilerplate (institutional headers, ministry notices, timing rules), extracts discipline-specific exercises with official grading criteria, and validates records via Pydantic v2:

```bash
# Parse all downloaded PDFs in data/raw/ and export to data/sample.jsonl
python -m src.parser

# Or target a specific folder:
python -m src.parser --raw-dir data/raw/2024
```

### 4. Dataset Profiling & Statistics (`src/stats.py`)

Computes descriptive statistics, discipline breakdown, and NLP text complexity metrics:

```bash
python -m src.stats
```

### 5. Running the Validation Baseline (`src/baseline.py`)

Trains a TF-IDF + LinearSVC baseline classifier on the dataset to demonstrate downstream discipline and curricular classification (as defined in `docs/data-proposal.md` Section 5):

```bash
# Run standard test suite
python -m src.baseline

# Or classify any custom question interactively on the fly:
python -m src.baseline --predict "Calculați derivata funcției f(x) = e^x + x^2."
```

### 6. Running Automated Tests

Run the full automated unit test suite covering schema validation, regex noise cleaning, and classifier accuracy:

```bash
python -m unittest discover tests
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
