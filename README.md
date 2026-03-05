# MetaAnalysisProject

A PubMed literature-review pipeline with a Streamlit GUI.
Search, deduplicate, tag, screen, and visualise papers — all from one interface.

---

## Repository layout

```
MetaAnalysisProject/
├── app.py                  Streamlit GUI (main entry point)
├── requirements.txt
├── core/
│   ├── scraper.py          PubMedScraper class
│   └── processing.py       DataFrameProcessor class
├── utils/
│   └── gui_utils.py        Pure helpers (MeSH lookup, query builder, regex suggest)
├── scripts/
│   ├── run_review_pubmed_search.py   CLI: run the PubMed scrape
│   ├── build_review_master_table.py  CLI: build master + screening CSVs
│   ├── plot_review_figures.py        CLI: generate figures from CSVs
│   └── export_pubmed_queries_csv.py  CLI: export all queries to CSV
└── tests/
    ├── test_query_generation.py
    └── test_gui_utils.py
```

---

## Setup — macOS / Linux

```bash
git clone https://github.com/JPRibeiroXx/MetaAnalysisProject.git
cd MetaAnalysisProject

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

## Setup — Windows

```powershell
git clone https://github.com/JPRibeiroXx/MetaAnalysisProject.git
cd MetaAnalysisProject

python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt
```

> If `python` is not found try `py -3` or install Python 3.10+ from [python.org](https://www.python.org/downloads/).

---

## Run the GUI

```bash
# macOS / Linux
source .venv/bin/activate
streamlit run app.py

# Windows
.venv\Scripts\activate
streamlit run app.py
```

Opens at `http://localhost:8501`.

---

## CLI Quick Start

### Step 1 — Scrape PubMed

```bash
python3 scripts/run_review_pubmed_search.py \
    --start-year 2000 --end-year 2027 --increment 1
```

Results saved as JSONL into `./json_files/`.

Optional flags:

| Flag | Default | Description |
|------|---------|-------------|
| `--start-year` | 2000 | First year (inclusive) |
| `--end-year` | 2027 | Exclusive upper bound (2027 → includes 2026) |
| `--increment` | 1 | Year chunk size — keep at 1 for broad queries (PubMed 10 k cap) |
| `--outdir` | `./json_files` | Output directory |
| `--search-scope` | `tiab` | `tiab` = Title/Abstract, `tw` = Text Word |

### Step 2 — Build master table

```bash
python3 scripts/build_review_master_table.py
```

Outputs in `./exported_dfs/`:

| File | Contents |
|------|----------|
| `review_master.csv` | All deduplicated records + tags |
| `review_screening.csv` | `keep_for_manual_screening == True` subset |
| `review_screening.xlsx` | Same, formatted for manual curation |

---

## Run tests

```bash
# macOS / Linux
.venv/bin/pytest tests/ -v

# Windows
.venv\Scripts\pytest tests\ -v
```

---

## Contact

- **Email**: [jpribeiro99@hotmail.com](mailto:jpribeiro99@hotmail.com)
- **GitHub**: [JPRibeiroXx](https://github.com/JPRibeiroXx)
