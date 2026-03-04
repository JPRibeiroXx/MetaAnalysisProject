#!/usr/bin/env python3
"""
Generate figures for the cardiac aging review from the master/screening tables.

Reads:
  exported_dfs/review_master.csv
  exported_dfs/review_screening.csv

Writes PNGs into:
  images/
"""

import os

import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt


ROOT = os.path.dirname(os.path.dirname(__file__))
EXPORTED = os.path.join(ROOT, "exported_dfs")
IMAGES = os.path.join(ROOT, "images")


def load_data():
    master_path = os.path.join(EXPORTED, "review_master.csv")
    screening_path = os.path.join(EXPORTED, "review_screening.csv")

    master = pd.read_csv(master_path)
    screening = pd.read_csv(screening_path)

    # Parse dates and add year for grouping
    master["date"] = pd.to_datetime(master["date"], errors="coerce")
    screening["date"] = pd.to_datetime(screening["date"], errors="coerce")

    master["year"] = master["date"].dt.year
    screening["year"] = screening["date"].dt.year

    return master, screening


def setup_style():
    sns.set_theme(style="whitegrid", context="talk")


def plot_papers_per_year_by_group(master: pd.DataFrame):
    """
    Fig 1 idea:
    Number of papers per year, broken down by query_group (lineplot).
    """
    df = (
        master
        .dropna(subset=["year"])
        .groupby(["year", "query_group"])
        .size()
        .reset_index(name="count")
    )

    plt.figure(figsize=(14, 7))
    sns.lineplot(
        data=df,
        x="year",
        y="count",
        hue="query_group",
        marker="o",
    )
    plt.title("Number of papers per year by query group")
    plt.xlabel("Year")
    plt.ylabel("Number of papers")
    plt.tight_layout()

    out_path = os.path.join(IMAGES, "papers_per_year_by_group.png")
    plt.savefig(out_path, dpi=300)
    plt.close()


def plot_total_by_group(master: pd.DataFrame):
    """
    Fig 2 idea:
    Total number of papers per query_group across all years (barplot).
    """
    df = (
        master
        .groupby("query_group")
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )

    plt.figure(figsize=(8, 6))
    sns.barplot(data=df, x="count", y="query_group", palette="viridis")
    plt.title("Total number of papers per query group (2000–2026)")
    plt.xlabel("Number of papers")
    plt.ylabel("Query group")
    plt.tight_layout()

    out_path = os.path.join(IMAGES, "total_papers_by_group.png")
    plt.savefig(out_path, dpi=300)
    plt.close()


def plot_screened_fraction_by_year(master: pd.DataFrame):
    """
    Fig 3 idea:
    Fraction of all papers that pass keep_for_manual_screening per year.
    """
    df = master.dropna(subset=["year"]).copy()
    df["keep_for_manual_screening"] = df["keep_for_manual_screening"].astype(bool)

    yearly = (
        df.groupby("year")
        .agg(
            total=("title", "size"),
            kept=("keep_for_manual_screening", "sum"),
        )
        .reset_index()
    )
    yearly["fraction_kept"] = yearly["kept"] / yearly["total"]

    fig, ax1 = plt.subplots(figsize=(14, 7))

    sns.barplot(data=yearly, x="year", y="total", color="#d0d7e2", ax=ax1)
    ax1.set_ylabel("Total papers")
    ax1.set_xlabel("Year")

    ax2 = ax1.twinx()
    sns.lineplot(
        data=yearly,
        x="year",
        y="fraction_kept",
        marker="o",
        color="#d62728",
        ax=ax2,
    )
    ax2.set_ylabel("Fraction kept for manual screening")
    ax2.set_ylim(0, 1)

    plt.title("Total papers and screening fraction per year")
    fig.tight_layout()

    out_path = os.path.join(IMAGES, "screened_fraction_by_year.png")
    plt.savefig(out_path, dpi=300)
    plt.close()


def plot_tag_cooccurrence_heatmap(screening: pd.DataFrame):
    """
    Fig 4 idea:
    Tag co-occurrence heatmap among the screening set
    (tag_model, tag_age, tag_knob, tag_endpoint, tag_drug).
    """
    tag_cols = ["tag_model", "tag_age", "tag_knob", "tag_endpoint", "tag_drug"]
    tags = screening[tag_cols].astype(bool)

    # Compute co-occurrence matrix: P(A and B) over the screening set
    n = len(tags)
    co_matrix = pd.DataFrame(
        index=tag_cols,
        columns=tag_cols,
        dtype=float,
    )
    for a in tag_cols:
        for b in tag_cols:
            co_matrix.loc[a, b] = (tags[a] & tags[b]).sum() / n

    plt.figure(figsize=(8, 6))
    sns.heatmap(
        co_matrix,
        annot=True,
        fmt=".2f",
        cmap="mako",
        vmin=0,
        vmax=1,
    )
    plt.title("Tag co-occurrence (fraction of screening set)")
    plt.tight_layout()

    out_path = os.path.join(IMAGES, "tag_cooccurrence_heatmap.png")
    plt.savefig(out_path, dpi=300)
    plt.close()


def plot_tag_counts_by_group(screening: pd.DataFrame):
    """
    Fig 5 idea:
    For the screened-in set, how often each tag appears within each query_group.
    """
    tag_cols = ["tag_model", "tag_age", "tag_knob", "tag_endpoint", "tag_drug"]
    df = screening.copy()
    df[tag_cols] = df[tag_cols].astype(bool)

    # Melt tags to long format for easier plotting
    tag_long = df.melt(
        id_vars=["query_group"],
        value_vars=tag_cols,
        var_name="tag",
        value_name="present",
    )
    tag_long = tag_long[tag_long["present"]]

    counts = (
        tag_long.groupby(["query_group", "tag"])
        .size()
        .reset_index(name="count")
    )

    plt.figure(figsize=(12, 7))
    sns.barplot(
        data=counts,
        x="query_group",
        y="count",
        hue="tag",
    )
    plt.title("Tag counts within screened-in set, by query group")
    plt.xlabel("Query group")
    plt.ylabel("Count in screened-in set")
    plt.xticks(rotation=20)
    plt.tight_layout()

    out_path = os.path.join(IMAGES, "tag_counts_by_group.png")
    plt.savefig(out_path, dpi=300)
    plt.close()


def main():
    os.makedirs(IMAGES, exist_ok=True)
    setup_style()
    master, screening = load_data()

    plot_papers_per_year_by_group(master)
    plot_total_by_group(master)
    plot_screened_fraction_by_year(master)
    plot_tag_cooccurrence_heatmap(screening)
    plot_tag_counts_by_group(screening)


if __name__ == "__main__":
    main()

