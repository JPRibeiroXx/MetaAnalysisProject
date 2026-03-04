#!/usr/bin/env python3
"""
Reproduce the original plots with new query data:
  1. #Papers_2000_to_2026.png  — KDE density (left) + line count (right), one line per query group
  2. Euler_Diagram.png          — 5-set UpSet plot showing keyword intersection across query groups

Uses raw JSONL counts (not deduped master) for accurate per-year-per-group numbers.
Computes set intersections by normalized title across all raw JSONL.
"""

import os
import re
import sys
import unicodedata

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import seaborn as sns
from venn import venn

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

ROOT = os.path.dirname(os.path.dirname(__file__))
JSON_DIR = os.path.join(ROOT, "json_files")
IMAGES = os.path.join(ROOT, "images")

REVIEW_GROUPS = [
    "CORE_AGE_AGING_MODELS",
    "MATURATION_ADULTLIKE",
    "ENGINEERING_KNOBS",
    "AGE_RELEVANT_ENDPOINTS",
    "DRUG_PREDICTION_TOXICITY",
]

# Short labels for axes / legend
SHORT = {
    "CORE_AGE_AGING_MODELS":    "Core Age/Aging",
    "MATURATION_ADULTLIKE":     "Maturation",
    "ENGINEERING_KNOBS":        "Eng. Knobs",
    "AGE_RELEVANT_ENDPOINTS":   "Endpoints",
    "DRUG_PREDICTION_TOXICITY": "Drug/Tox",
}

# Colours that match the original style (matplotlib tab10 / distinct hues)
GROUP_COLORS = {
    "CORE_AGE_AGING_MODELS":    "#e377c2",   # pink
    "MATURATION_ADULTLIKE":     "#ff7f0e",   # orange
    "ENGINEERING_KNOBS":        "#2ca02c",   # green
    "AGE_RELEVANT_ENDPOINTS":   "#9467bd",   # purple
    "DRUG_PREDICTION_TOXICITY": "#1f77b4",   # blue
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_title(t: str) -> str:
    if not isinstance(t, str):
        return ""
    nfkd = unicodedata.normalize("NFKD", t)
    ascii_str = nfkd.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", ascii_str.lower())


def load_raw_per_group() -> dict[str, pd.DataFrame]:
    """Return {group: concatenated raw df} for each review group."""
    group_dfs: dict[str, list[pd.DataFrame]] = {g: [] for g in REVIEW_GROUPS}

    for fname in sorted(os.listdir(JSON_DIR)):
        if not fname.endswith(".jsonl"):
            continue
        for group in REVIEW_GROUPS:
            if fname.startswith(group):
                # Extract year from filename stem  e.g. ..._2024_PubMed
                m = re.search(r"_(\d{4})(?:_\d{4})?_PubMed", fname)
                if not m:
                    continue
                year = int(m.group(1))
                path = os.path.join(JSON_DIR, fname)
                try:
                    df = pd.read_json(path, lines=True)
                except Exception:
                    continue
                if df.empty:
                    continue
                df["_year"] = year
                df["query_group"] = group
                group_dfs[group].append(df)
                break

    result = {}
    for group, frames in group_dfs.items():
        if frames:
            result[group] = pd.concat(frames, ignore_index=True)
    return result


# ---------------------------------------------------------------------------
# Plot 1 — Papers per year (KDE + Line), matching original style
# ---------------------------------------------------------------------------

def plot_papers_per_year(group_dfs: dict[str, pd.DataFrame]):
    sns.set_theme(style="whitegrid", context="notebook", font_scale=1.05)

    # ---- Build per-year count table (raw, not deduped) ----
    records = []
    for group, df in group_dfs.items():
        for year, sub in df.groupby("_year"):
            records.append({"year": year, "query_group": group, "count": len(sub)})
    count_df = pd.DataFrame(records)

    # ---- Build per-paper row table for KDE (one row per paper) ----
    all_raw = pd.concat(group_dfs.values(), ignore_index=True)
    # parse date; prefer _year column already set
    kde_df = all_raw[["_year", "query_group"]].rename(columns={"_year": "year"})

    fig, axes = plt.subplots(1, 2, figsize=(18, 7))
    fig.suptitle("Number of Papers Published per Year (2000–2026)", fontsize=14, fontweight="bold")

    # ---- Left: KDE density ----
    ax0 = axes[0]
    for group in REVIEW_GROUPS:
        sub = kde_df[kde_df["query_group"] == group]["year"]
        if len(sub) < 3:
            continue
        sns.kdeplot(
            sub,
            ax=ax0,
            label=SHORT[group],
            color=GROUP_COLORS[group],
            linewidth=2,
        )
    ax0.set_title("Density Plot", fontsize=12)
    ax0.set_xlabel("Year")
    ax0.set_ylabel("Density")
    ax0.legend(title="Query", fontsize=9)
    ax0.xaxis.set_major_locator(mticker.MultipleLocator(5))

    # ---- Right: Line plot (raw counts per year) ----
    ax1 = axes[1]
    pivot = count_df.pivot_table(index="year", columns="query_group", values="count", fill_value=0)
    for group in REVIEW_GROUPS:
        if group not in pivot.columns:
            continue
        linestyle = "--" if group in ("MATURATION_ADULTLIKE", "DRUG_PREDICTION_TOXICITY") else "-"
        ax1.plot(
            pivot.index,
            pivot[group],
            label=SHORT[group],
            color=GROUP_COLORS[group],
            linewidth=2,
            linestyle=linestyle,
            marker=None,
        )
    ax1.set_title("Line Plot", fontsize=12)
    ax1.set_xlabel("Year")
    ax1.set_ylabel("Number of Papers")
    ax1.legend(title="Query", fontsize=9)
    ax1.xaxis.set_major_locator(mticker.MultipleLocator(5))

    plt.tight_layout()
    out_path = os.path.join(IMAGES, "#Papers_2000_to_2026.png")
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Saved → {out_path}")


# ---------------------------------------------------------------------------
# Plot 2 — Euler / intersection diagram (5-set Venn via venn package)
# ---------------------------------------------------------------------------

def plot_euler_diagram(group_dfs: dict[str, pd.DataFrame]):
    # Build per-group sets of normalized titles
    group_sets: dict[str, set[str]] = {}
    for group, df in group_dfs.items():
        titles = df["title"].apply(normalize_title)
        group_sets[group] = set(titles[titles != ""])

    # venn() takes {label: set_of_items}
    labelled = {SHORT[g]: group_sets[g] for g in REVIEW_GROUPS}

    fig, ax = plt.subplots(figsize=(14, 11))
    venn(labelled, ax=ax, fontsize=12)
    ax.set_title(
        "Keyword intersection in PubMed's titles and abstracts\n(2000–2026)",
        fontsize=14,
        fontweight="bold",
        pad=20,
    )

    out_path = os.path.join(IMAGES, "Euler_Diagram_2026.png")
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Saved → {out_path}")


# ---------------------------------------------------------------------------
# Also emit a simple pairwise-overlap table for reference
# ---------------------------------------------------------------------------

def print_overlap_table(group_dfs: dict[str, pd.DataFrame]):
    group_sets: dict[str, set[str]] = {}
    for group, df in group_dfs.items():
        titles = df["title"].apply(normalize_title)
        group_sets[group] = set(titles[titles != ""])

    print("\n--- Pairwise overlap (# shared papers by normalized title) ---")
    groups = list(group_sets.keys())
    header = f"{'':30s}" + "".join(f"{SHORT[g]:>18s}" for g in groups)
    print(header)
    for g1 in groups:
        row = f"{SHORT[g1]:30s}"
        for g2 in groups:
            n = len(group_sets[g1] & group_sets[g2])
            row += f"{n:>18d}"
        print(row)


def main():
    os.makedirs(IMAGES, exist_ok=True)
    print("Loading raw JSONL files …")
    group_dfs = load_raw_per_group()
    for g, df in group_dfs.items():
        print(f"  {SHORT[g]:<20s} {len(df):>5d} raw rows")

    plot_papers_per_year(group_dfs)
    plot_euler_diagram(group_dfs)
    print_overlap_table(group_dfs)


if __name__ == "__main__":
    main()
