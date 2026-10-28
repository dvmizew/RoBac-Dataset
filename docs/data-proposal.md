# Propunere Dataset: Subiecte și Bareme Bacalaureat România (RoBac-Eval)

**Echipa:** Radu Daniel-Dumitru, Godeanu Victor, Iorga Iustin-Nicolae, Petcu Andreea-Elena  
**Depozit GitHub:** [RoBac-Dataset](https://github.com/dvmizew/RoBac-Dataset)  
**Eșantion date reale (20 înregistrări):** [`data/sample.jsonl`](../data/sample.jsonl)

---

## 1. De ce acest dataset?

### La ce e bun și cine l-ar folosi?
**RoBac-Eval** este un set de date structurat ce reunește subiectele oficiale și baremele de corectare de la Examenul Național de Bacalaureat (2015–2024), aliniind fiecare cerință cu pașii oficiali de rezolvare și punctajul aferent.

Publicul țintă și cazurile de utilizare:
1. **Cercetători în Procesarea Limbajului Natural (NLP / LLM):** Benchmark riguros pentru evaluarea capacității modelelor de limbaj (atât multilingve, cât și dedicate limbii române) pe raționament științific secvențial (multi-step reasoning în matematică), înțelegerea codului (C++/pseudocod) și sinteză literară.
2. **Dezvoltatori de platforme EdTech & Tutoriat Inteligent:** Antrenarea asistenților educaționali virtuali capabili să explice rezolvări și să ofere feedback structurat elevilor pe baza baremului oficial.
3. **Profesori și elevi:** Crearea de instrumente de căutare semantică avansată pentru identificarea problemelor similare din anii precedenți după competențe, nu doar după cuvinte cheie exacte.

### Ce aduce în plus față de ce există deja? De ce nu ajunge un set existent?
În prezent, **nu există niciun dataset NLP deschis dedicat curriculumului național liceal din România**.
- **Corpusurile românești existente (LiRo benchmark, Ro-STS, CoNLL-Ro):** Se concentrează exclusiv pe sarcini generale (clasificare de știri, recenzii de produse, recunoaștere de entități numite din presă). Niciunul nu abordează raționamentul curricular, formulele matematice sau analiza de cod.
- **De ce nu este suficient formatul existent al datelor?** Subiectele oficiale sunt publicate de Ministerul Educației exclusiv ca fișiere PDF destinate tiparului:
  1. *Enunțurile și baremele sunt în fișiere PDF separate*, neexistând o legătură programatică între o cerință și rezolvarea ei.
  2. *Zgomot instituțional ridicat:* Paginile conțin antete repetate, instrucțiuni administrative și pauze arbitrare de rând.
  3. *Lipsa adnotărilor tematice:* Exercițiile nu sunt etichetate curricular (ex. „Analiză matematică - Integrale definite”, „Grafuri - Arbori”).

---

## 2. Surse de Date, Licență și Dimensiune

- **Sursă și Link oficial:** Arhiva publică oficială a Ministerului Educației / CNPEE: [http://subiecte.edu.ro](http://subiecte.edu.ro) (sesiunile 2015–2024: Iunie-Iulie, August-Septembrie, Simulare, Modele oficiale).
- **Cadrul legal și Licență:** 
  - Datele primare sunt informații de interes public conform **Legii nr. 544/2001** și sunt exceptate de la protecția dreptului de autor conform **Legii nr. 8/1996 (art. 9 lit. b)**.
  - Setul de date procesat, structurat și adnotat este distribuit sub licența liberă **Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)**.
  - Codul pipeline-ului de achiziție și parsare este licențiat sub **MIT License**.
- **Dimensiune aproximativă:**
  - **~250+ fișiere PDF** descărcate (subiecte + bareme).
  - **3.000 – 4.500 de înregistrări structurate unice** (itemi de examen) acoperind 3 discipline reprezentative: *Matematică*, *Informatică*, *Limba și literatura română*.
  - Volum pe disc: ~150 MB fișiere PDF brute; ~15–25 MB fișier final JSONL.

---

## 3. Date Sensibile și Confidențialitate

- **Conțin datele informații personale (PII)?** **NU.** Setul conține strict enunțurile oficiale de examen și grilele de corectare stabilite la nivel național înainte de desfășurarea probelor. Nu conține nume de elevi, lucrări scrise, CNP-uri, note individuale sau date despre unitățile școlare.
- **Politica privind datele brute (Git hygiene):** Fișierele PDF brute nu se urcă pe depozitul GitHub; directorul `data/raw/` și fișierele `*.pdf` sunt excluse explicit prin `.gitignore`. Se versionază exclusiv codul și fișierele de date structurate (`.jsonl`).
- **Curățarea zgomotului:** Pipeline-ul aplică filtre regex pentru a elimina antetele instituționale și numerele de pagină fără valoare semantică.

---

## 4. Schema Datelor și Exemple

Fiecare înregistrare reprezintă un exercițiu sau o cerință unică aliniată cu secvența corespunzătoare din baremul oficial.

### 4.1 Tabelul Câmpurilor

| Câmp | Tip | Descriere |
| :--- | :--- | :--- |
| `id` | `string` | Identificator unic (`bac_{an}_{sesiune}_{materie}_{profil}_{sectiune}_{cerinta}`) |
| `an` | `integer` | Anul sesiunii (ex: `2024`) |
| `sesiune` | `string` | Sesiunea (`iunie-iulie`, `simulare`, `modele`, `august-septembrie`) |
| `materie` | `string` | Disciplina de examen (`Matematica`, `Informatica`, `Limba si literatura romana`) |
| `profil` | `string` | Profilul de studiu (`mate-info`, `stiinte-ale-naturii`, `tehnologic`, `filologie`) |
| `sectiune` | `string` | Secțiunea (`Subiectul I`, `Subiectul II`, `Subiectul III`) |
| `numar_cerinta` | `string` | Numărul cerinței (ex: `1`, `2.a`, `Subiectul I.A.1`) |
| `context_suport` | `string / null` | Text suport, fragment literar sau cod pseudocod asociat cerinței |
| `cerinta_text` | `string` | Enunțul complet al problemei sau al întrebării |
| `barem_text` | `string` | Soluția oficială, etapele de rezolvare și detalierea punctajului |
| `puncte` | `float` | Punctajul oficial alocat (ex: `5.0`, `10.0`, `30.0`) |
| `topic_curricular` | `string` | Categoria tematică curriculară (ex: `Algebră - Matrice`, `Grafuri - Arbori`) |

### 4.2 Definiție Pydantic v2

```python
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class BacItem(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., description="ID unic compus: bac_{an}_{sesiune}_{materie}_{cerinta}")
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

### 4.3 Exemple Reale

#### Exemplul 1: Matematică (Analiză Matematică, 2024)
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

#### Exemplul 2: Informatică (Eficiență Algoritmică C++, 2024)
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

#### Exemplul 3: Limba și Literatura Română (Text Argumentativ, 2024)
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

## 5. Validarea Utilității Datasetului

Pentru a demonstra utilitatea practică și științifică a setului de date, vom implementa două sarcini concrete:

1. **Clasificare Tematică Curriculară Automată:**
   - Antrenarea unui model care primește enunțul exercițiului și prezice automat tema din programă (`topic_curricular`).
   - Se va compara o linie de bază clasică (**TF-IDF + Logistic Regression / LinearSVC**) cu un model Transformer dedicat limbii române (**Romanian-BERT** / **RoRoBERTa**).
   - Metrici: Macro F1-score și Accuracy evaluate pe un set de testare temporal out-of-distribution (anii 2023–2024).

2. **Motor de Căutare Semantică pentru Exerciții (Semantic Retrieval):**
   - Construirea unui motor de căutare vectorial bazat pe sentence embeddings (`multilingual-e5` sau Ro-BERT) care să permită unui elev sau profesor să introducă un enunț și să primească instantaneu probleme similare rezolvate din anii anteriori, depășind limitările căutării lexicale simple.

---

## 6. Eșantion din Datele Reale

Un set reprezentativ de **20 de înregistrări reale** (provenite din sesiunile 2023–2024) este disponibil direct în depozit la calea:  
👉 [`data/sample.jsonl`](../data/sample.jsonl)

Fiecare linie din fișier respectă întocmai schema Pydantic și conține date reale verificate pentru Matematică, Informatică și Limba Română.
