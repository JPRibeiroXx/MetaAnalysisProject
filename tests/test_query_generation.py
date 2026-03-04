"""
Tests for PubMed query generation correctness.

Run with:
    .venv/bin/pytest tests/test_query_generation.py -v
"""
import re
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PubMedScraper import PubMedScraper
from scripts.run_review_pubmed_search import SEARCH_TERMS


# ── helpers ────────────────────────────────────────────────────────────────────

def get_search_string(query_key: str, year: int, increment: int = 1) -> str:
    """Return the fully assembled PubMed query string for one key + year."""
    scraper = PubMedScraper({query_key: SEARCH_TERMS[query_key]})
    end = year + increment
    scraper.generate_queries(year, end, increment)
    ss = scraper.generate_search_strings()
    if increment == 1:
        key = f"{query_key}_{year}"
    else:
        key = f"{query_key}_{year}_{year + increment - 1}"
    return ss[key][0]


# ══════════════════════════════════════════════════════════════════════════════
# 1. DATE FORMAT
# ══════════════════════════════════════════════════════════════════════════════

class TestDateFormat:
    """The date clause must NOT be quoted; PubMed expects (YYYY:YYYY[dp])."""

    @pytest.mark.parametrize("key", list(SEARCH_TERMS.keys()))
    def test_no_quotes_around_date(self, key):
        q = get_search_string(key, 2020)
        assert '"2020:2020[dp]"' not in q, (
            f"[{key}] Date clause must not be quoted. Got: ...{q[-80:]}..."
        )

    @pytest.mark.parametrize("key", list(SEARCH_TERMS.keys()))
    def test_date_in_parens_no_quotes(self, key):
        q = get_search_string(key, 2020)
        assert "(2020:2020[dp])" in q, (
            f"[{key}] Expected '(2020:2020[dp])' in query. Got: ...{q[-80:]}..."
        )

    def test_date_format_multi_year_increment(self):
        scraper = PubMedScraper({"Q": SEARCH_TERMS["CORE_AGE_AGING_MODELS"]})
        scraper.generate_queries(2014, 2017, 2)
        ss = scraper.generate_search_strings()
        q = ss["Q_2014_2015"][0]
        assert '"2014:2015[dp]"' not in q
        assert "(2014:2015[dp])" in q


# ══════════════════════════════════════════════════════════════════════════════
# 2. EHT CONSTRAINED FORM
# ══════════════════════════════════════════════════════════════════════════════

class TestEHTConstraint:
    """EHT[Title/Abstract] must appear only in a constrained form (AND'd with
    a cardiac context), never as a bare standalone OR-term."""

    EHT_STANDALONE = re.compile(
        r"(?:^|\bOR\s+)\(?EHT\[Title/Abstract\]\)?(?:\s+OR\b|\s*\)|\s*$)",
        re.IGNORECASE,
    )

    EHT_CONSTRAINED = re.compile(
        r"EHT\[Title/Abstract\]\s+AND\s+\(",
        re.IGNORECASE,
    )

    @pytest.mark.parametrize("key", list(SEARCH_TERMS.keys()))
    def test_eht_not_standalone(self, key):
        q = SEARCH_TERMS[key][0]
        assert not self.EHT_STANDALONE.search(q), (
            f"[{key}] Standalone 'EHT[Title/Abstract]' found. "
            "Wrap it as: (EHT[Title/Abstract] AND (heart... OR cardiac... OR myocard*...))"
        )

    @pytest.mark.parametrize("key", ["CORE_AGE_AGING_MODELS"])
    def test_eht_has_cardiac_qualifier(self, key):
        q = SEARCH_TERMS[key][0]
        if "EHT[Title/Abstract]" in q:
            assert self.EHT_CONSTRAINED.search(q), (
                f"[{key}] EHT must be followed by 'AND (' cardiac qualifier"
            )
            assert re.search(r"heart|cardiac|myocard", q, re.IGNORECASE), (
                f"[{key}] EHT constrained form must include heart/cardiac/myocard*"
            )


# ══════════════════════════════════════════════════════════════════════════════
# 3. BROAD vs AGE-FOCUSED VARIANTS
# ══════════════════════════════════════════════════════════════════════════════

class TestVariants:
    """BROAD and AGEFOCUSED variants must both exist for KNOBS and ENDPOINTS."""

    @pytest.mark.parametrize("key", [
        "ENGINEERING_KNOBS_BROAD",
        "ENGINEERING_KNOBS_AGEFOCUSED",
        "AGE_RELEVANT_ENDPOINTS_BROAD",
        "AGE_RELEVANT_ENDPOINTS_AGEFOCUSED",
    ])
    def test_variant_exists(self, key):
        assert key in SEARCH_TERMS, f"Missing key: {key}"
        assert isinstance(SEARCH_TERMS[key], list) and len(SEARCH_TERMS[key]) == 1

    def test_old_unqualified_keys_removed(self):
        """The old bare ENGINEERING_KNOBS / AGE_RELEVANT_ENDPOINTS should no
        longer exist — they've been split into BROAD and AGEFOCUSED."""
        assert "ENGINEERING_KNOBS" not in SEARCH_TERMS, (
            "Bare ENGINEERING_KNOBS should be replaced by _BROAD/_AGEFOCUSED"
        )
        assert "AGE_RELEVANT_ENDPOINTS" not in SEARCH_TERMS, (
            "Bare AGE_RELEVANT_ENDPOINTS should be replaced by _BROAD/_AGEFOCUSED"
        )

    @pytest.mark.parametrize("key", [
        "ENGINEERING_KNOBS_AGEFOCUSED",
        "AGE_RELEVANT_ENDPOINTS_AGEFOCUSED",
    ])
    def test_agefocused_contains_age_terms(self, key):
        q = SEARCH_TERMS[key][0]
        age_terms = ["aging", "aged", "senescence", "maturation", "adult-like"]
        found = [t for t in age_terms if t in q.lower()]
        assert found, (
            f"[{key}] AGEFOCUSED must contain age/maturation terms. "
            f"None of {age_terms} found."
        )

    def test_broad_and_agefocused_differ(self):
        for prefix in ("ENGINEERING_KNOBS", "AGE_RELEVANT_ENDPOINTS"):
            broad = SEARCH_TERMS[f"{prefix}_BROAD"][0]
            agefocused = SEARCH_TERMS[f"{prefix}_AGEFOCUSED"][0]
            assert broad != agefocused, (
                f"{prefix}: BROAD and AGEFOCUSED must be different queries"
            )
            # AGEFOCUSED must be a strict superset (broader == fewer constraints)
            assert len(agefocused) > len(broad), (
                f"{prefix}: AGEFOCUSED should be longer (extra age constraint)"
            )


# ══════════════════════════════════════════════════════════════════════════════
# 4. MODEL BLOCK SYNONYMS
# ══════════════════════════════════════════════════════════════════════════════

MODEL_KEYS = [
    "CORE_AGE_AGING_MODELS",
    "MATURATION_ADULTLIKE",
    "ENGINEERING_KNOBS_BROAD",
    "ENGINEERING_KNOBS_AGEFOCUSED",
    "AGE_RELEVANT_ENDPOINTS_BROAD",
    "AGE_RELEVANT_ENDPOINTS_AGEFOCUSED",
    "DRUG_PREDICTION_TOXICITY",
]

class TestModelSynonyms:
    """MPS / organ-on-a-chip must appear in every query that has a model block."""

    @pytest.mark.parametrize("key", MODEL_KEYS)
    def test_mps_present(self, key):
        q = SEARCH_TERMS[key][0]
        assert "microphysiological" in q.lower() or "MPS" in q, (
            f"[{key}] Must contain 'microphysiological' or 'MPS'"
        )

    @pytest.mark.parametrize("key", MODEL_KEYS)
    def test_organ_on_chip_present(self, key):
        q = SEARCH_TERMS[key][0]
        assert "organ-on-a-chip" in q.lower(), (
            f"[{key}] Must contain 'organ-on-a-chip'"
        )


# ══════════════════════════════════════════════════════════════════════════════
# 5. ENDPOINT SYNONYMS (MEA / FPD)
# ══════════════════════════════════════════════════════════════════════════════

ENDPOINT_KEYS = [
    "AGE_RELEVANT_ENDPOINTS_BROAD",
    "AGE_RELEVANT_ENDPOINTS_AGEFOCUSED",
]

class TestEndpointSynonyms:
    """MEA and field potential duration (FPD) must appear in endpoint queries."""

    @pytest.mark.parametrize("key", ENDPOINT_KEYS)
    def test_mea_present(self, key):
        q = SEARCH_TERMS[key][0]
        assert "MEA" in q or "multi-electrode array" in q.lower(), (
            f"[{key}] Must contain 'MEA' or 'multi-electrode array'"
        )

    @pytest.mark.parametrize("key", ENDPOINT_KEYS)
    def test_fpd_present(self, key):
        q = SEARCH_TERMS[key][0]
        assert "field potential duration" in q.lower() or "FPD" in q, (
            f"[{key}] Must contain 'field potential duration' or 'FPD'"
        )
