# Paper Scraping Project

Welcome to the **Paper Scraping Project**, designed to help researchers easily collect academic papers from various online sources using web scraping techniques.

## Overview
This project simplifies the process of gathering research papers for purposes such as:
- **Literature Review**
- **Data Analysis**
- **Scientific Research**

Whether you are compiling sources for a thesis, conducting a meta-analysis, or just researching a specific topic, this tool provides you with automated methods to collect and organize academic papers.

## Features
- **Automated Scraping**: Uses web scraping tools to automatically gather research papers from specified sources.
- **Customizable Queries**: Set search queries and filters to retrieve papers that match your research interests.
- **Data Extraction**: Extracts metadata like titles, authors, abstracts, and full-text content for further analysis.
- **Multiple Export Options**: Export the scraped data in formats such as **CSV**, **JSON**, or directly into a **database**.

## Getting Started

### 1. Clone the repository:
```bash
git clone https://github.com/JPRibeiroXx/MetaAnalysisProject.git
cd MetaAnalysisProject
```

### 2. Install the required dependencies:
```bash
pip install -r requirements.txt
```

---

## Cardiac Aging Review — Quick Start

**Review title:** *Age as a design variable: building cardiac models that predict clinical outcomes*

### Step 1 — Scrape PubMed

Runs 5 pre-defined boolean queries year-by-year (avoids the 10 000-record cap).
Results are saved as JSONL into `./json_files/`.

```bash
python3 scripts/run_review_pubmed_search.py --start-year 2000 --end-year 2027 --increment 1
```

Optional flags:
```
--start-year INT   First year to include (default: 2000)
--end-year   INT   Exclusive upper bound, e.g. 2027 to include 2026 (default: 2027)
--increment  INT   Year chunk size (default: 1)
--outdir     PATH  Where to write JSONL files (default: ./json_files)
```

### Step 2 — Build master screening table

Loads all JSONL files, deduplicates (PMID > DOI > normalized title), applies
boolean screening tags, and exports CSVs + XLSX.

```bash
python3 scripts/build_review_master_table.py
```

Outputs in `./exported_dfs/`:
| File | Contents |
|------|----------|
| `review_master.csv` | All deduplicated records + tags |
| `review_screening.csv` | `keep_for_manual_screening == True` subset |
| `review_screening.xlsx` | Same, formatted for manual curation |

**Screening logic:**
```
keep = tag_model AND tag_age AND (tag_endpoint OR tag_drug OR tag_knob)
```

Optional flags:
```
--json-dir PATH   JSONL source directory (default: ./json_files)
--out-dir  PATH   Output directory (default: ./exported_dfs)
```

## Installation

You can follow these simple steps to get the project up and running:

1. Clone the repository to your local machine using:
    ```bash
    git clone https://github.com/yourusername/paper-scraping-project.git
    ```

2. Install the necessary dependencies by running:
    ```bash
    pip install -r requirements.txt
    ```

3. Start the scraping process and follow the on-screen instructions to customize your search.

## Contributing

We welcome all contributions! To contribute:

1. Fork this repository.
2. Create a new branch for your feature:
   ```bash
   git checkout -b feature/yourfeature
   ```
3. Implement your changes and commit:
```bash
git commit -m 'Add new feature'
```
4. Push your branch:
```bash
git push origin feature/yourfeature
```
5. Open a Pull Request.

## License

This project is licensed under the **MIT License**. For more details, see the [LICENSE](LICENSE) file.

## Contact

Have questions or feedback? Feel free to reach out:

- **Email**: [jpribeiro99@hotmail.com](mailto:jpribeiro99@hotmail.com)
- **GitHub**: [JPRibeiroXx](https://github.com/JPRibeiroXx)

## Citations

If you use this project or its data in academic work, please consider citing the following articles:

```bibtex
@article{born2021trends,
  title={Trends in Deep Learning for Property-driven Drug Design},
  author={Born, Jannis and Manica, Matteo},
  journal={Current Medicinal Chemistry},
  volume={28},
  number={38},
  pages={7862--7886},
  year={2021},
  publisher={Bentham Science Publishers}
}

@article{born2021on,
  title={On the role of artificial intelligence in medical imaging of COVID-19},
  journal={Patterns},
  volume={2},
  number={6},
  pages={100269},
  year={2021},
  publisher={Elsevier}
}
```
