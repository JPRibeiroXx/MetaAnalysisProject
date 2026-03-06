#!/usr/bin/env python3
"""
Build a deduplicated master screening table from all JSONL files in json_files/.

Outputs:
  exported_dfs/review_master.csv        — all deduplicated records with tags
  exported_dfs/review_screening.csv     — records where keep_for_manual_screening == True
  exported_dfs/review_screening.xlsx    — same, formatted for manual review (if openpyxl is available)
"""

import argparse
import os
import re
import sys
import unicodedata

import pandas as pd

# Allow running from either scripts/ or repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Tag regex patterns (case-insensitive, search title + abstract)
# ---------------------------------------------------------------------------
TAG_PATTERNS = {
    "tag_model": (
        r"engineered heart tissue|engineered cardiac tissue|engineered myocardium"
        r"|cardiac tissue engineering|cardiac microtissue|cardiac spheroid|cardiac organoid"
        r"|heart organoid|heart-on-a-chip|heart on a chip|myocardium-on-a-chip"
        r"|microphysiological system|organ-on-a-chip|organ on a chip|organs-on-chips"
        r"|hiPSC-CM|iPSC-CM|hiPSC|iPSC|induced pluripotent.*cardiomyocyte"
        r"|EHT"
    ),
    "tag_age": (
        r"\baging\b|\baged\b|ageing|age-related|age-associated|senescen"
        r"|SASP|inflammaging|progeroid|senolytic|premature aging|accelerated aging"
    ),
    "tag_maturation": (
        r"\bmaturation\b|\bmature\b|adult-like|adultlike|adult phenotype"
        r"|cardiomyocyte maturation|metabolic maturation|structural maturation"
        r"|functional maturation|postnatal maturation"
    ),
    "tag_knob": (
        r"electrical stimulation|electrical pacing|\bpacing\b"
        r"|mechanical loading|\bstretch\b|cyclic stretch"
        r"|preload|afterload|mechanical stress"
        r"|substrate stiffness|matrix stiffness|\bstiffness\b"
        r"|alignment|anisotropy|micropattern|nanotopograph"
        r"|perfusion|microfluidic|\bflow\b|shear stress"
        r"|extracellular matrix|\bECM\b|decellularized"
        r"|co-culture|coculture|tri-culture"
        r"|bioreactor"
    ),
    "tag_endpoint": (
        r"contractility|twitch force|\bforce\b|active tension|passive tension"
        r"|electrophysiology|action potential|action potential duration|\bAPD\b"
        r"|field potential duration|\bFPD\b|multi-electrode array|\bMEA\b"
        r"|arrhythmia|proarrhythmia|QT prolongation|torsade"
        r"|calcium transient|calcium handling|Ca2\+ transient"
        r"|mitochondria|metabolism|oxidative phosphorylation|fatty acid oxidation"
        r"|fibrosis|collagen|beta-adrenergic|adrenergic|isoproterenol"
    ),
    "tag_drug": (
        r"cardiotoxicity|drug-induced cardiotoxicity|safety pharmacology|cardiac safety"
        r"|proarrhythmia|QT prolongation|torsade|hERG|IKr"
        r"|drug screening|toxicity testing|predictive toxicology"
    ),
}


def normalize_title(title: str) -> str:
    """Lowercase, strip accents and non-alphanumeric chars for fuzzy dedup."""
    if not isinstance(title, str):
        return ""
    nfkd = unicodedata.normalize("NFKD", title)
    ascii_str = nfkd.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", ascii_str.lower())


def extract_query_group(stem: str) -> str:
    """
    Given a file stem like 'CORE_AGE_AGING_MODELS_2000_PubMed' or
    'CORE_AGE_AGING_MODELS_2000_2001_PubMed', return 'CORE_AGE_AGING_MODELS'.
    Strategy: strip '_PubMed' suffix, then strip trailing _DIGITS(_DIGITS)?.
    """
    stem = re.sub(r"_PubMed$", "", stem)
    stem = re.sub(r"_\d{4}(_\d{4})?$", "", stem)
    return stem


def load_all_jsonl(json_dir: str, prefix: str = "") -> pd.DataFrame:
    files = [
        f for f in os.listdir(json_dir)
        if f.endswith(".jsonl") and (not prefix or f.startswith(prefix))
    ]
    if not files:
        if prefix:
            return pd.DataFrame()
        print(f"No .jsonl files found in {json_dir}. Run the scraper first.")
        sys.exit(1)

    frames = []
    for fname in sorted(files):
        path = os.path.join(json_dir, fname)
        try:
            df = pd.read_json(path, lines=True)
        except Exception as e:
            print(f"  [WARN] Could not read {fname}: {e}")
            continue
        stem = os.path.splitext(fname)[0]
        df["query_file"] = stem
        df["query_group"] = extract_query_group(stem)
        frames.append(df)
        print(f"  Loaded {len(df):>5} rows from {fname}")

    return pd.concat(frames, ignore_index=True)


def deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    """
    Deduplicate preferring:  pmid  >  doi  >  normalized_title
    Keeps the first occurrence (earliest file loaded alphabetically).
    """
    original = len(df)

    # Normalize helper columns
    df["_norm_title"] = df["title"].apply(normalize_title)

    # Coerce pmid/doi to string for safe comparison
    for col in ("pmid", "doi"):
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().replace({"nan": "", "None": ""})

    # Step 1: dedup by PMID (non-empty)
    if "pmid" in df.columns:
        mask_has_pmid = df["pmid"].ne("")
        df_pmid = df[mask_has_pmid].drop_duplicates(subset="pmid", keep="first")
        df_no_pmid = df[~mask_has_pmid]
    else:
        df_pmid = pd.DataFrame(columns=df.columns)
        df_no_pmid = df

    # Step 2: dedup remaining by DOI
    if "doi" in df_no_pmid.columns:
        mask_has_doi = df_no_pmid["doi"].ne("")
        df_doi = df_no_pmid[mask_has_doi].drop_duplicates(subset="doi", keep="first")
        df_nodoi = df_no_pmid[~mask_has_doi]
    else:
        df_doi = pd.DataFrame(columns=df.columns)
        df_nodoi = df_no_pmid

    # Step 3: dedup remaining by normalized title
    df_title = df_nodoi.drop_duplicates(subset="_norm_title", keep="first")

    deduped = pd.concat([df_pmid, df_doi, df_title], ignore_index=True)
    deduped = deduped.drop(columns=["_norm_title"], errors="ignore")

    print(f"\nDeduplication: {original} → {len(deduped)} records")
    return deduped


def apply_tags(df: pd.DataFrame) -> pd.DataFrame:
    # Combine title + abstract into a single search field
    title = df["title"].fillna("").astype(str)
    abstract = df.get("abstract", pd.Series([""] * len(df))).fillna("").astype(str)
    text = title + " " + abstract

    for tag, pattern in TAG_PATTERNS.items():
        df[tag] = text.str.contains(pattern, case=False, regex=True)

    df["keep_for_manual_screening"] = (
        df["tag_model"]
        & (df["tag_age"] | df["tag_maturation"])
        & (df["tag_endpoint"] | df["tag_drug"] | df["tag_knob"])
    )
    return df


def main():
    parser = argparse.ArgumentParser(
        description="Build master screening table from scraped JSONL files."
    )
    parser.add_argument(
        "--json-dir",
        default="./json_files",
        help="Directory containing .jsonl files (default: ./json_files)",
    )
    parser.add_argument(
        "--out-dir",
        default="./exported_dfs",
        help="Directory to write output CSVs/XLSX (default: ./exported_dfs)",
    )
    parser.add_argument(
        "--prefix",
        default="",
        help=(
            "Only load JSONL files whose names start with this prefix. "
            "Useful to avoid mixing in old files from previous runs. "
            "E.g. --prefix CORE or leave empty to load all."
        ),
    )
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    review_prefixes = (
        "CORE_AGE_AGING_MODELS",
        "MATURATION_ADULTLIKE",
        "DRUG_PREDICTION_TOXICITY",
        "ENGINEERING_KNOBS_AGEFOCUSED",
        "AGE_RELEVANT_ENDPOINTS_AGEFOCUSED",
    )

    print(f"Loading JSONL files from: {args.json_dir}")
    if args.prefix:
        df = load_all_jsonl(args.json_dir, prefix=args.prefix)
    else:
        # Default: only load the 5 review queries to avoid picking up unrelated files
        import itertools
        frames = []
        for pfx in review_prefixes:
            partial = load_all_jsonl(args.json_dir, prefix=pfx)
            if partial is not None and len(partial):
                frames.append(partial)
        if not frames:
            print("No review JSONL files found. Run the scraper first.")
            sys.exit(1)
        df = pd.concat(frames, ignore_index=True)

    df = deduplicate(df)
    df = apply_tags(df)

    # Sort by year descending for easier browsing, then title
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.sort_values("date", ascending=False, na_position="last")

    master_path = os.path.join(args.out_dir, "review_master.csv")
    df.to_csv(master_path, index=False)
    print(f"\nMaster table  → {master_path}  ({len(df)} records)")

    screening = df[df["keep_for_manual_screening"]]
    screen_csv = os.path.join(args.out_dir, "review_screening.csv")
    screening.to_csv(screen_csv, index=False)
    print(f"Screening CSV → {screen_csv}  ({len(screening)} records)")

    # Optional XLSX
    screen_xlsx = os.path.join(args.out_dir, "review_screening.xlsx")
    try:
        with pd.ExcelWriter(screen_xlsx, engine="openpyxl") as writer:
            screening.to_excel(writer, index=False, sheet_name="Screening")
            # Auto-fit column widths (approximate)
            ws = writer.sheets["Screening"]
            for col in ws.columns:
                max_len = max(
                    (len(str(cell.value)) for cell in col if cell.value), default=10
                )
                ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 60)
        print(f"Screening XLSX→ {screen_xlsx}  ({len(screening)} records)")
    except ImportError:
        print("openpyxl not installed — skipping XLSX export. Run: pip install openpyxl")

    # Summary
    print("\n--- Tag summary (keep_for_manual_screening subset) ---")
    tag_cols = [c for c in df.columns if c.startswith("tag_")]
    for col in tag_cols:
        n = df[col].sum()
        print(f"  {col:<30} {n:>5} / {len(df)}")
    print(f"  {'keep_for_manual_screening':<30} {df['keep_for_manual_screening'].sum():>5} / {len(df)}")

    print("\n--- Records per query_group ---")
    print(df["query_group"].value_counts().to_string())


if __name__ == "__main__":
    main()
