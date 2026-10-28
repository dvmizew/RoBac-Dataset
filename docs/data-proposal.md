# Dataset Proposal: Romanian Baccalaureate Exams and Rubrics (RoBac-Eval)

**Team:** Radu Daniel-Dumitru, Godeanu Victor, Iorga Iustin-Nicolae, Petcu Andreea-Elena  
**Repository:** [https://github.com/dvmizew/RoBac-Dataset](https://github.com/dvmizew/RoBac-Dataset)  
**Sample Data (20 real items):** [`data/sample.jsonl`](../data/sample.jsonl)

---

## 1. Why This Dataset?

### Utility and Target Users
**RoBac-Eval** is a structured dataset pairing official Romanian National Baccalaureate (*Bacalaureat*) exam problems with their official step-by-step grading rubrics (*bareme*) from 2015 to 2024, standardized into JSONL format.

Primary users and use cases:
1. **NLP and LLM Researchers:** Benchmarking Romanian language models on sequential multi-step reasoning (high school mathematics), code understanding (C++ algorithms and pseudocode), and literary text comprehension/essay evaluation.
2. **EdTech Developers:** Building automated tutoring and assessment tools that provide granular, rubric-aligned feedback to students rather than ungrounded free-form answers.
3. **Teachers and Students:** Semantic search systems capable of retrieving past exam exercises by targeted skill or mathematical concept, rather than brittle keyword matching.

### Value Over Existing Datasets & Why Raw PDFs Fall Short
Currently, **there is no public Romanian NLP dataset covering the national high school STEM or literature curriculum**:
- Existing Romanian NLP benchmarks (LiRo, Ro-STS, CoNLL-Ro) focus on general-domain tasks: news categorization, sentiment analysis of commercial product reviews, or standard named entity recognition. None feature mathematical formulations, algorithmic problem solving, or rubric step mapping.
- The Ministry of Education distributes exam papers exclusively as print-oriented PDFs:
  1. *Statements and rubrics are published in separate PDF documents*, with no machine-readable linkage between a prompt and its grading steps.
  2. *High formatting noise:* PDFs contain repeated administrative headers, institutional boilerplate, and inconsistent text flow around mathematical formulas.
  3. *No curricular metadata:* Questions lack standardized topic tags (e.g., "Calculus - Definite Integrals", "Graph Theory - Trees").

---

## 2. Data Sources, License, and Size

- **Source:** Official public archives of the Ministry of Education / CNPEE: [http://subiecte.edu.ro](http://subiecte.edu.ro) (2015–2024 exam years across main summer sessions, autumn sessions, simulations, and official sample variants).
- **Legal Framework & Licensing:**
  - Raw exam materials are public interest documents under Romanian Law 544/2001 and are exempt from copyright under Romanian Copyright Law 8/1996 (Art. 9 lit. b).
  - The processed, aligned, and annotated dataset is released under the **Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)** license.
  - The crawler and parsing pipeline code is released under the **MIT License**.
- **Approximate Size:**
  - **250+ PDF files** downloaded (statements + corresponding rubrics).
  - **3,000 – 4,500 structured items** across Mathematics, Computer Science, and Romanian Literature.
  - Storage footprint: ~150 MB raw PDFs (kept locally); ~15–25 MB final `.jsonl` files.

---

## 3. Sensitive Data and Privacy

- **Personally Identifiable Information (PII):** **None.** The dataset contains only nationwide official exam statements and pre-established grading rubrics. It contains no student submissions, grades, school affiliations, or personal records.
- **Git Hygiene:** Raw PDF binaries are never committed to GitHub. The `data/raw/` folder and `*.pdf` files are ignored via `.gitignore`. Only source code, metadata, and JSONL data files are tracked.
- **Noise Cleansing:** Text extraction filters out institutional headers (*"Ministerul Educației"*, *"Centrul Național de Politici și Evaluare în Educație"*), exam timing rules, and page numbering.

---

## 4. Data Schema and Examples

Each JSONL record represents an individual problem or sub-question mapped to its official grading breakdown.

### 4.1 Schema Fields

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | `string` | Unique identifier (`bac_{year}_{session}_{subject}_{profile}_{section}_{num}`) |
| `an` | `integer` | Calendar year of the exam (e.g., `2024`) |
| `sesiune` | `string` | Session name (`iunie-iulie`, `simulare`, `modele`, `august-septembrie`) |
| `materie` | `string` | Exam subject (`Matematica`, `Informatica`, `Limba si literatura romana`) |
| `profil` | `string` | Track/specialization (`mate-info`, `stiinte-ale-naturii`, `tehnologic`, `filologie`) |
| `sectiune` | `string` | Exam section (`Subiectul I`, `Subiectul II`, `Subiectul III`) |
| `numar_cerinta` | `string` | Exercise number or label (e.g., `1`, `2.a`, `Subiectul I.A.1`) |
| `context_suport` | `string / null` | Optional passage, pseudocode block, or reading support text |
| `cerinta_text` | `string` | Full problem statement |
| `barem_text` | `string` | Official grading criteria, solution steps, and point distribution |
| `puncte` | `float` | Allocated points according to rubric (e.g., `5.0`, `10.0`, `30.0`) |
| `topic_curricular` | `string` | Curricular classification label (e.g., `Analiză matematică - Integrale definite`) |

### 4.2 Pydantic v2 Schema

```python
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class BacItem(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., description="Unique ID: bac_{year}_{session}_{subject}_{num}")
    an: int = Field(..., ge=2015, le=2024)
    sesiune: str
    materie: str
    profil: str
    sectiune: str
    numar_cerinta: str
    context_suport: Optional[str] = None
    cerinta_text: str
    barem_text: str
    puncte: float
    topic_curricular: str
```

### 4.3 Concrete Examples

#### Example 1: Mathematics (Calculus - Mate-Info, 2024)
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

#### Example 2: Computer Science (Algorithm Efficiency - C++, 2024)
```json
{
  "id": "bac_2024_iunie_informatica_mate_info_s3_ex3",
  "an": 2024,
  "sesiune": "iunie-iulie",
  "materie": "Informatica",
  "profil": "mate-info",
  "sectiune": "Subiectul III",
  "numar_cerinta": "3",
  "context_suport": "Fișierul bac.txt conține pe prima linie cel mult 10^6 numere naturale din intervalul [0, 100]. Numerele sunt separate prin câte un spațiu.",
  "cerinta_text": "Se cere să se afișeze pe ecran, în ordine descrescătoare, numerele distincte care apar de cel puțin două ori în fișier. Proiectați un algoritm eficient din punctul de vedere al timpului de executare și al memoriei utilizate. Descrieți algoritmul și scrieți programul C/C++.",
  "barem_text": "Descrierea clară a metodei bazate pe vector de frecvență de dimensiune constantă 101, complexitate O(N) timp și O(1) memorie auxiliară (2p); Utilizarea corectă a fișierului și citirea valorilor (2p); Actualizarea vectorului de frecvență (2p); Parcurgerea descrescătoare de la 100 la 0 și afișarea elementelor cu frecvență >= 2 (3p); Respectarea restricțiilor de eficiență (1p).",
  "puncte": 10.0,
  "topic_curricular": "Eficiența algoritmilor - Vectori de frecvență"
}
```

#### Example 3: Romanian Literature (Argumentative Writing, 2024)
```json
{
  "id": "bac_2024_iunie_romana_real_s1_b",
  "an": 2024,
  "sesiune": "iunie-iulie",
  "materie": "Limba si literatura romana",
  "profil": "mate-info",
  "sectiune": "Subiectul I",
  "numar_cerinta": "Subiectul I.B",
  "context_suport": null,
  "cerinta_text": "Redactează un text de minimum 150 de cuvinte, în care să argumentezi dacă perseverența este sau nu o calitate definitorie pentru atingerea performanței într-un domeniu, raportându-te atât la experiența personală sau culturală, cât și la fragmentul extras din volumul 'Amintiri de la Junimea' de George Panu.",
  "barem_text": "Formularea tezei / ipotezei - 2p; Dezvoltarea primului argument raportat la textul suport - 4p; Dezvoltarea celui de-al doilea argument raportat la experiența personală/culturală - 4p; Formularea concluziei adecvate - 2p; Respectarea normelor de coerență, ortografie și punctuație - 4p; Încadrarea în limita minimă de 150 de cuvinte - 4p.",
  "puncte": 20.0,
  "topic_curricular": "Redactare - Text argumentativ"
}
```

---

## 5. Validation Plan

We will demonstrate the dataset's utility through two downstream tasks:

1. **Curricular Topic Classification:**
   - Automatically predicting the `topic_curricular` field from the exercise text (`cerinta_text` + `context_suport`).
   - Comparing a standard baseline (TF-IDF + Logistic Regression / LinearSVC) against fine-tuned Romanian Transformer models (`Romanian-BERT` / `RoRoBERTa`).
   - Evaluated on a temporal out-of-distribution split (training on 2015–2022, testing on 2023–2024).

2. **Semantic Similarity Search for Exam Problems:**
   - Building a dense vector retrieval index using sentence embeddings (`multilingual-e5` or Ro-BERT).
   - Allows users to query a problem formulation and retrieve structurally similar past exam questions, benchmarked against lexical search (BM25).

---

## 6. Real Data Sample

A verifiable sample of **20 real items** from 2023–2024 exam sessions is included directly in the repository at:  
[`data/sample.jsonl`](../data/sample.jsonl)
