#!/usr/bin/env python3
"""
Export all actual PubMed queries used for the review into a CSV.

Output:
  exported_dfs/pubmed_queries_YYYY_YYYY.csv

Columns:
  - query_group  (e.g. CORE_AGE_AGING_MODELS)
  - year         (int, publication year)
  - query_name   (internal key, e.g. CORE_AGE_AGING_MODELS_2000)
  - pubmed_query (full string as sent to PubMed)
"""

import argparse
import os
import sys
import re
import csv

# Allow importing from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PubMedScraper import PubMedScraper  # type: ignore
from scripts.run_review_pubmed_search import get_search_terms  # type: ignore


def parse_group_and_year(query_name: str) -> tuple[str, int]:
    """
    PubMedScraper.generate_queries names:
      - increment == 1:  f'{key}_{year}'
      - increment > 1:   f'{key}_{start}_{end}'
    We only use increment == 1 here.
    """
    m = re.search(r"_(\d{4})$", query_name)
    if not m:
        raise ValueError(f"Could not parse year from query_name={query_name!r}")
    year = int(m.group(1))
    group = query_name[: m.start()]
    return group, year


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export all PubMed queries used for the cardiac aging review."
    )
    parser.add_argument(
        "--start-year",
        type=int,
        default=2000,
        help="First year (inclusive). Default: 2000",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=2027,
        help="Exclusive upper bound for years (same convention as scraper). "
        "Default: 2027 (covers 2000–2026).",
    )
    parser.add_argument(
        "--increment",
        type=int,
        default=1,
        help="Year increment (must match what was used for scraping). Default: 1",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output CSV path. "
        "Default: exported_dfs/pubmed_queries_START_END-1.csv",
    )
    parser.add_argument(
        "--search-scope",
        choices=["tiab", "tw"],
        default="tiab",
        help="Same as scraper: tiab = Title/Abstract, tw = Text Word (broader).",
    )
    args = parser.parse_args()

    root = os.path.dirname(os.path.dirname(__file__))
    exported = os.path.join(root, "exported_dfs")
    os.makedirs(exported, exist_ok=True)

    if args.out is None:
        args.out = os.path.join(
            exported, f"pubmed_queries_{args.start_year}_{args.end_year - 1}.csv"
        )

    search_terms = get_search_terms(args.search_scope)
    scraper = PubMedScraper(search_terms)
    scraper.generate_queries(args.start_year, args.end_year, args.increment)
    search_strings = scraper.generate_search_strings()

    rows: list[dict[str, str | int]] = []
    for query_name, strings in sorted(search_strings.items()):
        if not strings:
            continue
        if len(strings) != 1:
            raise RuntimeError(
                f"Expected exactly one search string per query_name, got {len(strings)}"
            )
        pubmed_query = strings[0]
        group, year = parse_group_and_year(query_name)
        rows.append(
            {
                "query_group": group,
                "year": year,
                "query_name": query_name,
                "pubmed_query": pubmed_query,
            }
        )

    # Deterministic ordering: by group, then year
    rows.sort(key=lambda r: (str(r["query_group"]), int(r["year"])))  # type: ignore[arg-type]

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["query_group", "year", "query_name", "pubmed_query"]
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} queries to {args.out}")


if __name__ == "__main__":
    main()

