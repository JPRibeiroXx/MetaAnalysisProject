#!/usr/bin/env python3
"""
PubMed scraper for the cardiac aging review:
  "Age as a design variable for predictive cardiac models."

Five query groups (all AGEFOCUSED, using [tiab]):
  CORE_AGE_AGING_MODELS
  MATURATION_ADULTLIKE
  DRUG_PREDICTION_TOXICITY
  ENGINEERING_KNOBS_AGEFOCUSED
  AGE_RELEVANT_ENDPOINTS_AGEFOCUSED

Date clause is always unquoted: AND (YYYY:YYYY[dp])
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PubMedScraper import PubMedScraper

# ── Shared building blocks (all use {f} as the field tag placeholder) ─────────

# Full cardiac-model platform block
_PLATFORM = (
    '('
    '"engineered heart tissue"[{f}]'
    ' OR "engineered cardiac tissue"[{f}]'
    ' OR "engineered myocardium"[{f}]'
    ' OR "bioengineered myocardium"[{f}]'
    ' OR "cardiac tissue engineering"[{f}]'
    ' OR (("3D"[{f}] OR "3-D"[{f}]) AND ("cardiac tissue"[{f}] OR myocard*[{f}]))'
    ' OR "cardiac microtissue"[{f}]'
    ' OR "cardiac microtissues"[{f}]'
    ' OR "cardiac spheroid"[{f}]'
    ' OR "cardiac spheroids"[{f}]'
    ' OR "cardiac organoid"[{f}]'
    ' OR "cardiac organoids"[{f}]'
    ' OR "heart organoid"[{f}]'
    ' OR "heart organoids"[{f}]'
    ' OR "heart-on-a-chip"[{f}]'
    ' OR "heart on a chip"[{f}]'
    ' OR "myocardium-on-a-chip"[{f}]'
    ' OR "myocardium on a chip"[{f}]'
    ' OR "microphysiological system"[{f}]'
    ' OR "microphysiological systems"[{f}]'
    ' OR "cardiac microphysiological system"[{f}]'
    ' OR "cardiac microphysiological systems"[{f}]'
    ' OR (("organ-on-a-chip"[{f}] OR "organ on a chip"[{f}]'
    '     OR "organs-on-chips"[{f}] OR "organ chips"[{f}])'
    '    AND (heart[{f}] OR cardiac[{f}] OR myocard*[{f}]))'
    ' OR ((hiPSC[{f}] OR iPSC[{f}] OR "induced pluripotent"[{f}])'
    '    AND (cardiomyocyte*[{f}] OR hiPSC-CM*[{f}] OR iPSC-CM*[{f}]))'
    ' OR (EHT[{f}] AND (heart[{f}] OR cardiac[{f}] OR myocard*[{f}]))'
    ')'
)

# Age / senescence block
_AGE_SENESCENCE = (
    '('
    'aging[{f}] OR ageing[{f}] OR aged[{f}]'
    ' OR "age-related"[{f}] OR "age associated"[{f}] OR "age-associated"[{f}]'
    ' OR senescence[{f}] OR senescent[{f}] OR "cellular senescence"[{f}]'
    ' OR SASP[{f}] OR "senescence-associated secretory phenotype"[{f}]'
    ' OR inflammaging[{f}]'
    ' OR "accelerated aging"[{f}] OR "premature aging"[{f}] OR progeroid[{f}]'
    ' OR "stress-induced premature senescence"[{f}] OR SIPS[{f}]'
    ' OR senolytic*[{f}] OR senomorphic*[{f}]'
    ')'
)

# Maturation / adult-like block
_MATURATION = (
    '('
    'maturation[{f}] OR mature[{f}] OR matured[{f}]'
    ' OR "cardiomyocyte maturation"[{f}]'
    ' OR "adult-like"[{f}] OR adultlike[{f}] OR "adult phenotype"[{f}]'
    ' OR "metabolic maturation"[{f}]'
    ' OR "structural maturation"[{f}]'
    ' OR "functional maturation"[{f}]'
    ' OR "electrophysiological maturation"[{f}]'
    ' OR "postnatal maturation"[{f}]'
    ')'
)

# Age OR maturation combined (used in AGEFOCUSED queries)
_AGE_OR_MATURATION = (
    '('
    '(aging[{f}] OR ageing[{f}] OR aged[{f}]'
    ' OR senescence[{f}] OR "cellular senescence"[{f}] OR inflammaging[{f}])'
    ' OR'
    ' (maturation[{f}] OR "adult-like"[{f}] OR adultlike[{f}]'
    ' OR "cardiomyocyte maturation"[{f}])'
    ')'
)

# Engineering knobs block
_KNOBS = (
    '('
    '"electrical stimulation"[{f}] OR "electrical pacing"[{f}]'
    ' OR pacing[{f}] OR paced[{f}]'
    ' OR "mechanical loading"[{f}] OR stretch[{f}] OR stretching[{f}]'
    ' OR "cyclic stretch"[{f}]'
    ' OR preload[{f}] OR afterload[{f}] OR "mechanical stress"[{f}]'
    ' OR "substrate stiffness"[{f}] OR "matrix stiffness"[{f}]'
    ' OR stiffness[{f}] OR "young\'s modulus"[{f}]'
    ' OR alignment[{f}] OR aligned[{f}] OR anisotropy[{f}] OR anisotropic[{f}]'
    ' OR micropattern*[{f}] OR nanotopograph*[{f}]'
    ' OR perfusion[{f}] OR perfused[{f}] OR microfluidic*[{f}]'
    ' OR flow[{f}] OR "shear stress"[{f}]'
    ' OR "extracellular matrix"[{f}] OR ECM[{f}]'
    ' OR "decellularized matrix"[{f}] OR "decellularized extracellular matrix"[{f}]'
    ' OR "co-culture"[{f}] OR coculture[{f}] OR "tri-culture"[{f}]'
    ' OR "cardiac fibroblast"[{f}] OR "cardiac fibroblasts"[{f}]'
    ' OR endothelial*[{f}] OR macrophage*[{f}]'
    ' OR bioreactor*[{f}]'
    ')'
)

# Age-relevant functional / structural endpoints block
_ENDPOINTS = (
    '('
    'contractility[{f}] OR "twitch force"[{f}] OR force[{f}]'
    ' OR "active tension"[{f}] OR "passive tension"[{f}]'
    ' OR electrophysiology[{f}] OR "action potential"[{f}]'
    ' OR "action potential duration"[{f}] OR APD[{f}]'
    ' OR "field potential duration"[{f}] OR FPD[{f}]'
    ' OR "multi-electrode array"[{f}] OR MEA[{f}]'
    ' OR arrhythmia*[{f}] OR proarrhythmia*[{f}]'
    ' OR "QT prolongation"[{f}] OR torsade*[{f}]'
    ' OR "calcium transient"[{f}] OR "calcium transients"[{f}]'
    ' OR "calcium handling"[{f}] OR "Ca2+ transient"[{f}] OR "Ca2+ transients"[{f}]'
    ' OR mitochondria*[{f}] OR metabolism[{f}]'
    ' OR "oxidative phosphorylation"[{f}] OR "fatty acid oxidation"[{f}]'
    ' OR fibrosis[{f}] OR collagen[{f}]'
    ' OR "matrix stiffness"[{f}] OR "extracellular matrix"[{f}] OR ECM[{f}]'
    ' OR "beta-adrenergic"[{f}] OR "β-adrenergic"[{f}]'
    ' OR adrenergic[{f}] OR isoproterenol[{f}]'
    ')'
)

# Drug / translational block
_DRUG_TRANSLATION = (
    '('
    'cardiotoxicity[{f}] OR "drug-induced cardiotoxicity"[{f}]'
    ' OR "drug induced cardiotoxicity"[{f}]'
    ' OR "safety pharmacology"[{f}] OR "cardiac safety"[{f}]'
    ' OR proarrhythmia*[{f}] OR "QT prolongation"[{f}] OR torsade*[{f}]'
    ' OR hERG[{f}] OR IKr[{f}]'
    ' OR "drug screening"[{f}] OR "toxicity testing"[{f}]'
    ' OR "predictive toxicology"[{f}]'
    ')'
)

_DRUG_TRANSLATIONAL_CONTEXT = (
    '('
    'predict*[{f}] OR translational[{f}] OR clinical[{f}]'
    ' OR "clinical outcome"[{f}] OR "clinical outcomes"[{f}]'
    ')'
)


def _build(template: str, f: str) -> str:
    return template.replace("{f}", f)


def get_search_terms(scope: str = "tiab") -> dict[str, list[str]]:
    """
    Build all 5 SEARCH_TERMS with the given PubMed field tag.
      scope='tiab' → [tiab]  (Title/Abstract — precise, default)
      scope='tw'   → [tw]    (Text Word — title, abstract, MeSH, keywords)
    """
    f = "tiab" if scope == "tiab" else "tw"

    platform = _build(_PLATFORM, f)
    age      = _build(_AGE_SENESCENCE, f)
    mat      = _build(_MATURATION, f)
    age_or_m = _build(_AGE_OR_MATURATION, f)
    knobs    = _build(_KNOBS, f)
    eps      = _build(_ENDPOINTS, f)
    drug     = _build(_DRUG_TRANSLATION, f)
    drug_ctx = _build(_DRUG_TRANSLATIONAL_CONTEXT, f)

    return {
        "CORE_AGE_AGING_MODELS": [
            f"({platform} AND {age})"
        ],
        "MATURATION_ADULTLIKE": [
            f"({platform} AND {mat})"
        ],
        "DRUG_PREDICTION_TOXICITY": [
            f"({platform} AND {drug} AND {drug_ctx})"
        ],
        "ENGINEERING_KNOBS_AGEFOCUSED": [
            f"({platform} AND {knobs} AND {age_or_m})"
        ],
        "AGE_RELEVANT_ENDPOINTS_AGEFOCUSED": [
            f"({platform} AND {eps} AND {age_or_m})"
        ],
    }


# Default export used by tests and other scripts
SEARCH_TERMS: dict[str, list[str]] = get_search_terms("tiab")


def main() -> None:
    parser = argparse.ArgumentParser(
        description='PubMed scraper — "Age as a design variable for predictive cardiac models."'
    )
    parser.add_argument("--start-year", type=int, default=2000)
    parser.add_argument(
        "--end-year", type=int, default=2027,
        help="Exclusive upper bound (e.g. 2027 → includes 2026). Default: 2027",
    )
    parser.add_argument("--increment", type=int, default=1)
    parser.add_argument("--outdir", default="./json_files")
    parser.add_argument(
        "--search-scope", choices=["tiab", "tw"], default="tiab",
        help="tiab = Title/Abstract (precise). tw = Text Word (broader, incl. MeSH).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print 3 example queries per group and exit without scraping.",
    )
    args = parser.parse_args()

    terms = get_search_terms(args.search_scope)

    if args.dry_run:
        print(f"DRY RUN — scope={args.search_scope}, "
              f"years {args.start_year}–{args.end_year - 1}, "
              f"increment={args.increment}\n")
        scraper = PubMedScraper(terms)
        scraper.generate_queries(args.start_year, args.end_year, args.increment)
        ss = scraper.generate_search_strings()
        shown: dict[str, int] = {}
        for qkey, queries in ss.items():
            # Extract group name (everything before last _YYYY or _YYYY_YYYY)
            import re
            group = re.sub(r"_\d{4}(_\d{4})?$", "", qkey)
            if shown.get(group, 0) >= 3:
                continue
            shown[group] = shown.get(group, 0) + 1
            print(f"[{group}]  key={qkey}")
            print(f"  {queries[0]}\n")
        return

    print(
        f"Running {len(terms)} queries: "
        f"{args.start_year}–{args.end_year - 1} "
        f"(exclusive end={args.end_year}), increment={args.increment}, "
        f"scope={args.search_scope}"
    )
    os.makedirs(args.outdir, exist_ok=True)
    scraper = PubMedScraper(terms)
    scraper.generate_queries(args.start_year, args.end_year, args.increment)
    print(f"Generated {len(scraper.generate_search_strings())} query-year combinations.")
    scraper.scrape_pubmed(output_dir=args.outdir)


if __name__ == "__main__":
    main()
