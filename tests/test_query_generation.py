"""
Tests for PubMed query generation correctness.

Run with:
    .venv/bin/pytest tests/test_query_generation.py -v
"""
import re
import subprocess
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PubMedScraper import PubMedScraper
from scripts.run_review_pubmed_search import SEARCH_TERMS


PYTHON = os.path.join(os.path.dirname(__file__), "..", ".venv", "bin", "python")
RUNNER  = os.path.join(os.path.dirname(__file__), "..", "scripts", "run_review_pubmed_search.py")

EXPECTED_KEYS = [
    "CORE_AGE_AGING_MODELS",
    "MATURATION_ADULTLIKE",
    "DRUG_PREDICTION_TOXICITY",
    "ENGINEERING_KNOBS_AGEFOCUSED",
    "AGE_RELEVANT_ENDPOINTS_AGEFOCUSED",
]

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
# 1. EXPECTED KEYS
# ══════════════════════════════════════════════════════════════════════════════

class TestExpectedKeys:
    """Exactly these 5 keys must be present in SEARCH_TERMS."""

    @pytest.mark.parametrize("key", EXPECTED_KEYS)
    def test_key_exists(self, key):
        assert key in SEARCH_TERMS, f"Missing key: {key}"

    @pytest.mark.parametrize("key", EXPECTED_KEYS)
    def test_value_is_single_element_list(self, key):
        val = SEARCH_TERMS[key]
        assert isinstance(val, list) and len(val) == 1, (
            f"[{key}] Value must be a 1-element list, got: {val!r}"
        )

    def test_no_bare_broad_keys(self):
        """BROAD variants are no longer used; only AGEFOCUSED."""
        for key in SEARCH_TERMS:
            assert not key.endswith("_BROAD"), (
                f"Unexpected BROAD key found: {key}. Only AGEFOCUSED variants are used."
            )


# ══════════════════════════════════════════════════════════════════════════════
# 2. DATE FORMAT
# ══════════════════════════════════════════════════════════════════════════════

class TestDateFormat:
    """The date clause must NOT be quoted; PubMed expects (YYYY:YYYY[dp])."""

    @pytest.mark.parametrize("key", EXPECTED_KEYS)
    def test_no_quotes_around_date(self, key):
        q = get_search_string(key, 2020)
        assert '"2020:2020[dp]"' not in q, (
            f"[{key}] Date clause must not be quoted. Got: ...{q[-80:]}..."
        )

    @pytest.mark.parametrize("key", EXPECTED_KEYS)
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
# 3. FIELD TAG — must use [tiab], not [Title/Abstract]
# ══════════════════════════════════════════════════════════════════════════════

class TestFieldTag:
    """All content terms must use [tiab], not the verbose [Title/Abstract]."""

    @pytest.mark.parametrize("key", EXPECTED_KEYS)
    def test_uses_tiab_not_long_form(self, key):
        q = SEARCH_TERMS[key][0]
        assert "[Title/Abstract]" not in q, (
            f"[{key}] Must use [tiab] not [Title/Abstract]"
        )

    @pytest.mark.parametrize("key", EXPECTED_KEYS)
    def test_tiab_present(self, key):
        q = SEARCH_TERMS[key][0]
        assert "[tiab]" in q, f"[{key}] No [tiab] tag found in query"


# ══════════════════════════════════════════════════════════════════════════════
# 4. EHT CONSTRAINED FORM
# ══════════════════════════════════════════════════════════════════════════════

class TestEHTConstraint:
    """EHT[tiab] must appear only in a constrained (AND'd) form."""

    EHT_STANDALONE = re.compile(
        r"(?:^|\bOR\s+)\(?EHT\[tiab\]\)?(?:\s+OR\b|\s*\)|\s*$)",
        re.IGNORECASE,
    )
    EHT_CONSTRAINED = re.compile(r"EHT\[tiab\]\s+AND\s+\(", re.IGNORECASE)

    @pytest.mark.parametrize("key", EXPECTED_KEYS)
    def test_eht_not_standalone(self, key):
        q = SEARCH_TERMS[key][0]
        assert not self.EHT_STANDALONE.search(q), (
            f"[{key}] Standalone 'EHT[tiab]' found. "
            "Wrap as: (EHT[tiab] AND (heart[tiab] OR cardiac[tiab] OR myocard*[tiab]))"
        )

    def test_eht_has_cardiac_qualifier(self):
        q = SEARCH_TERMS["CORE_AGE_AGING_MODELS"][0]
        if "EHT[tiab]" in q:
            assert self.EHT_CONSTRAINED.search(q)
            assert re.search(r"heart|cardiac|myocard", q, re.IGNORECASE)


# ══════════════════════════════════════════════════════════════════════════════
# 5. PLATFORM BLOCK — comprehensive model synonyms
# ══════════════════════════════════════════════════════════════════════════════

PLATFORM_REQUIRED = [
    "engineered heart tissue",
    "heart-on-a-chip",
    "heart on a chip",
    "cardiac organoid",
    "cardiac spheroid",
    "microphysiological",
    "organ-on-a-chip",
    "organ on a chip",
    "hipsc",
    "ipsc",
]

class TestPlatformBlock:
    """PLATFORM_TIAB synonyms must appear in every query (all share the same block)."""

    @pytest.mark.parametrize("term", PLATFORM_REQUIRED)
    @pytest.mark.parametrize("key", EXPECTED_KEYS)
    def test_platform_term_present(self, key, term):
        q = SEARCH_TERMS[key][0].lower()
        assert term.lower() in q, (
            f"[{key}] Missing platform synonym: '{term}'"
        )


# ══════════════════════════════════════════════════════════════════════════════
# 6. AGE BLOCK — comprehensive senescence / aging terms
# ══════════════════════════════════════════════════════════════════════════════

AGE_REQUIRED = ["aging", "senescence", "inflammaging", "sasp", "senolytic", "progeroid"]

class TestAgeBlock:
    """CORE and AGEFOCUSED queries must carry the full AGE_SENESCENCE block."""

    @pytest.mark.parametrize("term", AGE_REQUIRED)
    def test_age_term_in_core(self, term):
        q = SEARCH_TERMS["CORE_AGE_AGING_MODELS"][0].lower()
        assert term.lower() in q, (
            f"[CORE_AGE_AGING_MODELS] Missing age term: '{term}'"
        )

    @pytest.mark.parametrize("key", [
        "ENGINEERING_KNOBS_AGEFOCUSED",
        "AGE_RELEVANT_ENDPOINTS_AGEFOCUSED",
    ])
    def test_agefocused_contains_age_terms(self, key):
        q = SEARCH_TERMS[key][0].lower()
        found = [t for t in ["aging", "aged", "senescence", "maturation"] if t in q]
        assert found, f"[{key}] No age/maturation terms found"


# ══════════════════════════════════════════════════════════════════════════════
# 7. MATURATION BLOCK
# ══════════════════════════════════════════════════════════════════════════════

class TestMaturationBlock:
    MAT_REQUIRED = ["maturation", "adult-like", "metabolic maturation", "cardiomyocyte maturation"]

    @pytest.mark.parametrize("term", MAT_REQUIRED)
    def test_maturation_term_present(self, term):
        q = SEARCH_TERMS["MATURATION_ADULTLIKE"][0].lower()
        assert term.lower() in q, (
            f"[MATURATION_ADULTLIKE] Missing maturation term: '{term}'"
        )


# ══════════════════════════════════════════════════════════════════════════════
# 8. ENDPOINT BLOCK — MEA / FPD / electrophysiology
# ══════════════════════════════════════════════════════════════════════════════

class TestEndpointBlock:
    @pytest.mark.parametrize("key", [
        "AGE_RELEVANT_ENDPOINTS_AGEFOCUSED",
    ])
    def test_mea_present(self, key):
        q = SEARCH_TERMS[key][0]
        assert "MEA" in q or "multi-electrode array" in q.lower(), (
            f"[{key}] Must contain MEA or multi-electrode array"
        )

    @pytest.mark.parametrize("key", [
        "AGE_RELEVANT_ENDPOINTS_AGEFOCUSED",
    ])
    def test_fpd_present(self, key):
        q = SEARCH_TERMS[key][0]
        assert "field potential duration" in q.lower() or "FPD" in q, (
            f"[{key}] Must contain 'field potential duration' or 'FPD'"
        )

    def test_calcium_handling_present(self):
        q = SEARCH_TERMS["AGE_RELEVANT_ENDPOINTS_AGEFOCUSED"][0].lower()
        assert "calcium" in q, "Missing calcium terms in endpoint block"

    def test_contractility_present(self):
        q = SEARCH_TERMS["AGE_RELEVANT_ENDPOINTS_AGEFOCUSED"][0].lower()
        assert "contractility" in q


# ══════════════════════════════════════════════════════════════════════════════
# 9. DRUG BLOCK — translational / safety pharmacology terms
# ══════════════════════════════════════════════════════════════════════════════

class TestDrugBlock:
    DRUG_REQUIRED = ["cardiotoxicity", "proarrhythmia", "qt prolongation", "herg", "predict"]

    @pytest.mark.parametrize("term", DRUG_REQUIRED)
    def test_drug_term_present(self, term):
        q = SEARCH_TERMS["DRUG_PREDICTION_TOXICITY"][0].lower()
        assert term.lower() in q, (
            f"[DRUG_PREDICTION_TOXICITY] Missing term: '{term}'"
        )


# ══════════════════════════════════════════════════════════════════════════════
# 10. DRY-RUN FLAG
# ══════════════════════════════════════════════════════════════════════════════

class TestDryRun:
    """--dry-run must print queries and exit 0 without hitting PubMed."""

    def test_dry_run_exits_zero(self):
        result = subprocess.run(
            [sys.executable, RUNNER,
             "--start-year", "2000", "--end-year", "2003", "--increment", "1", "--dry-run"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"dry-run exited {result.returncode}:\n{result.stderr}"

    def test_dry_run_shows_queries(self):
        result = subprocess.run(
            [sys.executable, RUNNER,
             "--start-year", "2000", "--end-year", "2003", "--increment", "1", "--dry-run"],
            capture_output=True, text=True,
        )
        out = result.stdout
        assert "2000:2000[dp]" in out, (
            f"--dry-run output must show date clause without quotes.\nGot:\n{out}"
        )
        assert '"2000:2000[dp]"' not in out, (
            f"--dry-run output must NOT quote the date clause.\nGot:\n{out}"
        )

    def test_dry_run_shows_all_groups(self):
        result = subprocess.run(
            [sys.executable, RUNNER,
             "--start-year", "2020", "--end-year", "2022", "--increment", "1", "--dry-run"],
            capture_output=True, text=True,
        )
        for key in EXPECTED_KEYS:
            assert key in result.stdout, (
                f"--dry-run output should mention query group '{key}'"
            )
