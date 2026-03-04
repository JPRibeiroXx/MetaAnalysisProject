#!/usr/bin/env python3
"""
PubMed scraper for the cardiac aging review:
  "Age as a design variable: building cardiac models that predict clinical outcomes"

Query architecture
------------------
Shared building blocks are assembled into SEARCH_TERMS so queries stay DRY and
easy to audit.  Each value is a ONE-element list so paperscraper doesn't OR-split
the boolean logic — it passes the string through as a single term block, which
gets wrapped in parens and AND-ed with the year date filter.

Search scope (--search-scope)
-----------------------------
* tiab (default): [Title/Abstract] — title and abstract only (precise, fewer hits).
* tw: [tw] Text Word — title, abstract, MeSH terms, keywords, and other indexed fields
  (broader recall, more hits, possible noise).
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PubMedScraper import PubMedScraper

# ── Shared building blocks ─────────────────────────────────────────────────────

# Full cardiac-model synonym block (used in every query that has a model filter)
_MODEL = (
    '("engineered heart tissue"[Title/Abstract]'
    ' OR (EHT[Title/Abstract] AND (heart[Title/Abstract] OR cardiac[Title/Abstract] OR myocard*[Title/Abstract]))'
    ' OR "heart-on-a-chip"[Title/Abstract]'
    ' OR "cardiac microphysiological system"[Title/Abstract]'
    ' OR "microphysiological system"[Title/Abstract]'
    ' OR MPS[Title/Abstract]'
    ' OR "organ-on-a-chip"[Title/Abstract]'
    ' OR "cardiac organoid"[Title/Abstract]'
    ' OR "cardiac spheroid"[Title/Abstract]'
    ' OR "3D cardiac"[Title/Abstract]'
    ' OR hiPSC-CM[Title/Abstract]'
    ' OR "iPSC-derived cardiomyocyte"[Title/Abstract])'
)

# Age / senescence block (standard, used in CORE and AGEFOCUSED variants)
_AGE = (
    '(aging[Title/Abstract] OR aged[Title/Abstract]'
    ' OR senescence[Title/Abstract]'
    ' OR "cellular senescence"[Title/Abstract]'
    ' OR maturation[Title/Abstract]'
    ' OR "adult-like"[Title/Abstract])'
)

# Age block extended with inflammaging / age-related (used in CORE query)
_AGE_EXTENDED = (
    '(aging[Title/Abstract] OR aged[Title/Abstract]'
    ' OR senescence[Title/Abstract]'
    ' OR "cellular senescence"[Title/Abstract]'
    ' OR "inflammaging"[Title/Abstract]'
    ' OR "age-related"[Title/Abstract])'
)

# Engineering-knob interventions block
_KNOBS = (
    '("electrical stimulation"[Title/Abstract]'
    ' OR pacing[Title/Abstract]'
    ' OR "mechanical loading"[Title/Abstract]'
    ' OR stretch[Title/Abstract]'
    ' OR preload[Title/Abstract]'
    ' OR afterload[Title/Abstract]'
    ' OR "substrate stiffness"[Title/Abstract]'
    ' OR anisotropy[Title/Abstract]'
    ' OR alignment[Title/Abstract]'
    ' OR "co-culture"[Title/Abstract])'
)

# Age-relevant functional / structural endpoints block (with MEA / FPD added)
_ENDPOINTS = (
    '(fibrosis[Title/Abstract]'
    ' OR "matrix stiffness"[Title/Abstract]'
    ' OR "beta-adrenergic"[Title/Abstract]'
    ' OR isoproterenol[Title/Abstract]'
    ' OR mitochondria[Title/Abstract]'
    ' OR metabolism[Title/Abstract]'
    ' OR "action potential duration"[Title/Abstract]'
    ' OR "field potential duration"[Title/Abstract]'
    ' OR "multi-electrode array"[Title/Abstract]'
    ' OR MEA[Title/Abstract]'
    ' OR arrhythmia[Title/Abstract]'
    ' OR "calcium transient"[Title/Abstract]'
    ' OR contractility[Title/Abstract]'
    ' OR force[Title/Abstract])'
)

# Placeholder used in all blocks; substituted by get_search_terms(scope)
_F = "[Title/Abstract]"


def _sub_scope(s: str, field: str) -> str:
    return s.replace("[Title/Abstract]", field)


def get_search_terms(scope: str = "tiab") -> dict[str, list[str]]:
    """
    Return SEARCH_TERMS with the given PubMed field tag.
    scope: "tiab" → [tiab] Title/Abstract (default, precise).
           "tw"   → [tw] Text Word (title, abstract, MeSH, keywords — broader).
    """
    f = "[tiab]" if scope == "tiab" else "[tw]"
    model = _sub_scope(_MODEL, f)
    age = _sub_scope(_AGE, f)
    age_ext = _sub_scope(_AGE_EXTENDED, f)
    knobs = _sub_scope(_KNOBS, f)
    endpoints = _sub_scope(_ENDPOINTS, f)

    mat_block = _sub_scope(
        '((hiPSC-CM[Title/Abstract]'
        ' OR "iPSC-derived cardiomyocyte"[Title/Abstract]'
        ' OR "engineered heart tissue"[Title/Abstract]'
        ' OR "heart-on-a-chip"[Title/Abstract]'
        ' OR "microphysiological system"[Title/Abstract]'
        ' OR MPS[Title/Abstract]'
        ' OR "organ-on-a-chip"[Title/Abstract])'
        ' AND (maturation[Title/Abstract]'
        ' OR "adult-like"[Title/Abstract]'
        ' OR "metabolic maturation"[Title/Abstract]'
        ' OR "structural maturation"[Title/Abstract]'
        ' OR "functional maturation"[Title/Abstract]))',
        f,
    )
    drug_block = _sub_scope(
        '(("engineered heart tissue"[Title/Abstract]'
        ' OR "heart-on-a-chip"[Title/Abstract]'
        ' OR "cardiac microphysiological system"[Title/Abstract]'
        ' OR "microphysiological system"[Title/Abstract]'
        ' OR MPS[Title/Abstract]'
        ' OR "organ-on-a-chip"[Title/Abstract]'
        ' OR hiPSC-CM[Title/Abstract])'
        ' AND (cardiotoxicity[Title/Abstract]'
        ' OR "drug-induced cardiotoxicity"[Title/Abstract]'
        ' OR proarrhythmia[Title/Abstract]'
        ' OR "QT prolongation"[Title/Abstract]'
        ' OR torsades[Title/Abstract]'
        ' OR "drug screening"[Title/Abstract])'
        ' AND (predict*[Title/Abstract]'
        ' OR translational[Title/Abstract]'
        ' OR "clinical"[Title/Abstract]))',
        f,
    )

    return {
        "CORE_AGE_AGING_MODELS": [f'({model} AND {age_ext})'],
        "MATURATION_ADULTLIKE": [mat_block],
        "ENGINEERING_KNOBS_BROAD": [f'({model} AND {knobs})'],
        "ENGINEERING_KNOBS_AGEFOCUSED": [f'({model} AND {knobs} AND {age})'],
        "AGE_RELEVANT_ENDPOINTS_BROAD": [f'({model} AND {endpoints})'],
        "AGE_RELEVANT_ENDPOINTS_AGEFOCUSED": [f'({model} AND {endpoints} AND {age})'],
        "DRUG_PREDICTION_TOXICITY": [drug_block],
    }


# Default: Title/Abstract. Use get_search_terms("tw") for Text Word (broader).
SEARCH_TERMS: dict[str, list[str]] = get_search_terms("tiab")


def main():
    parser = argparse.ArgumentParser(
        description="Scrape PubMed for the cardiac aging review."
    )
    parser.add_argument("--start-year", type=int, default=2000)
    parser.add_argument(
        "--end-year",
        type=int,
        default=2027,
        help="Exclusive upper bound (e.g. 2027 to include 2026). Default: 2027",
    )
    parser.add_argument("--increment", type=int, default=1)
    parser.add_argument("--outdir", default="./json_files")
    parser.add_argument(
        "--search-scope",
        choices=["tiab", "tw"],
        default="tiab",
        help="tiab = Title/Abstract only (precise). tw = Text Word (incl. MeSH, keywords — broader recall).",
    )
    args = parser.parse_args()

    terms = get_search_terms(args.search_scope)
    print(
        f"Running {len(terms)} queries from {args.start_year} "
        f"to {args.end_year - 1} (exclusive end={args.end_year}), "
        f"increment={args.increment}"
    )
    print(f"Output directory: {args.outdir}")
    print(f"Search scope: {args.search_scope} ({'Title/Abstract' if args.search_scope == 'tiab' else 'Text Word (MeSH, keywords, etc.)'})\n")

    scraper = PubMedScraper(terms)
    queries = scraper.generate_queries(args.start_year, args.end_year, args.increment)
    print(f"Generated {len(queries)} query-year combinations.")
    scraper.scrape_pubmed(output_dir=args.outdir)


if __name__ == "__main__":
    main()
