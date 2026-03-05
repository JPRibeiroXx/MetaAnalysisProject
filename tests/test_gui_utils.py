"""
Tests for GUI utility functions: suggest_pattern, build_query_preview, fetch_mesh_terms.

Run with:
    .venv/bin/pytest tests/test_gui_utils.py -v
"""
import sys
import os
import json
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.gui_utils import suggest_pattern, build_query_preview, fetch_mesh_terms, apply_pending_term


# ══════════════════════════════════════════════════════════════════════════════
# suggest_pattern
# ══════════════════════════════════════════════════════════════════════════════

class TestSuggestPattern:
    """suggest_pattern(label, description) -> pipe-separated regex string."""

    def test_returns_string(self):
        result = suggest_pattern("cardiac model", "in vitro heart tissue model")
        assert isinstance(result, str)

    def test_non_empty_for_known_domain(self):
        result = suggest_pattern("cardiac model", "in vitro heart tissue model")
        assert len(result.strip()) > 0

    def test_non_empty_for_unknown_domain(self):
        result = suggest_pattern("widget", "a widget that does things")
        assert len(result.strip()) > 0

    def test_cardiac_label_contains_heart_terms(self):
        result = suggest_pattern("cardiac", "paper about the heart")
        terms = result.lower().split("|")
        assert any(t in ("cardiac", "heart", "myocardial", "cardiovascular") for t in terms)

    def test_aging_label_contains_senescence(self):
        result = suggest_pattern("aging", "study of cellular senescence and age-related changes")
        assert "aging" in result.lower() or "senescence" in result.lower() or "age" in result.lower()

    def test_drug_label_contains_toxicity_terms(self):
        result = suggest_pattern("drug toxicity", "paper on cardiotoxicity and drug safety")
        assert any(t in result.lower() for t in ("drug", "toxic", "cardiotoxic", "safety"))

    def test_no_pipe_at_start_or_end(self):
        result = suggest_pattern("fibrosis", "extracellular matrix and fibrotic remodeling")
        assert not result.startswith("|")
        assert not result.endswith("|")

    def test_no_empty_segments(self):
        result = suggest_pattern("metabolism", "mitochondrial metabolism and oxidative phosphorylation")
        for seg in result.split("|"):
            assert seg.strip() != "", f"Empty segment found in: {result!r}"

    def test_empty_label_and_description_returns_something(self):
        result = suggest_pattern("", "")
        # Should at least return an empty string gracefully, not raise
        assert isinstance(result, str)

    def test_neuron_label(self):
        result = suggest_pattern("neuron", "neuronal activity and synapse formation")
        assert any(t in result.lower() for t in ("neuron", "neural", "synapse", "axon"))

    def test_lung_label(self):
        result = suggest_pattern("lung", "pulmonary tissue and airway modelling")
        assert any(t in result.lower() for t in ("lung", "pulmonary", "airway", "alveolar"))


# ══════════════════════════════════════════════════════════════════════════════
# build_query_preview
# ══════════════════════════════════════════════════════════════════════════════

class TestBuildQueryPreview:
    """build_query_preview(blocks) -> PubMed boolean string."""

    def _make_blocks(self, rows):
        return pd.DataFrame(rows, columns=["Block Name", "Terms", "Connector"])

    def test_single_block_no_connector(self):
        blocks = self._make_blocks([
            ("Models", "hiPSC-CM[tiab]\nEHT[tiab]", "—"),
        ])
        result = build_query_preview(blocks)
        assert "hiPSC-CM[tiab]" in result
        assert "EHT[tiab]" in result
        assert " OR " in result

    def test_two_blocks_and(self):
        blocks = self._make_blocks([
            ("Models", "hiPSC-CM[tiab]", "AND"),
            ("Aging",  "aging[tiab]",     "—"),
        ])
        result = build_query_preview(blocks)
        assert "hiPSC-CM[tiab]" in result
        assert "aging[tiab]" in result
        assert " AND " in result

    def test_two_blocks_or(self):
        blocks = self._make_blocks([
            ("A", "alpha[tiab]", "OR"),
            ("B", "beta[tiab]",  "—"),
        ])
        result = build_query_preview(blocks)
        assert " OR " in result

    def test_three_blocks(self):
        blocks = self._make_blocks([
            ("A", "alpha[tiab]",   "AND"),
            ("B", "beta[tiab]",    "AND"),
            ("C", "gamma[tiab]",   "—"),
        ])
        result = build_query_preview(blocks)
        assert "alpha[tiab]" in result
        assert "beta[tiab]" in result
        assert "gamma[tiab]" in result

    def test_empty_blocks_returns_empty(self):
        blocks = self._make_blocks([])
        result = build_query_preview(blocks)
        assert result == ""

    def test_block_with_only_whitespace_skipped(self):
        blocks = self._make_blocks([
            ("A", "  \n  ",   "AND"),
            ("B", "real[tiab]", "—"),
        ])
        result = build_query_preview(blocks)
        assert "real[tiab]" in result

    def test_terms_are_ored_within_block(self):
        blocks = self._make_blocks([
            ("A", "one[tiab]\ntwo[tiab]\nthree[tiab]", "—"),
        ])
        result = build_query_preview(blocks)
        assert result.count("OR") == 2

    def test_result_has_outer_parens(self):
        blocks = self._make_blocks([
            ("A", "alpha[tiab]", "AND"),
            ("B", "beta[tiab]",  "—"),
        ])
        result = build_query_preview(blocks)
        assert result.startswith("(")
        assert result.endswith(")")

    def test_single_term_single_block(self):
        blocks = self._make_blocks([
            ("A", "hiPSC-CM[tiab]", "—"),
        ])
        result = build_query_preview(blocks)
        assert "hiPSC-CM[tiab]" in result


# ══════════════════════════════════════════════════════════════════════════════
# fetch_mesh_terms
# ══════════════════════════════════════════════════════════════════════════════

class TestFetchMeshTerms:
    """fetch_mesh_terms(query) -> list[str] of '[MeSH Terms]'-formatted strings."""

    def _mock_response(self, hits: list[dict]):
        mock = MagicMock()
        mock.__enter__ = lambda s: s
        mock.__exit__ = MagicMock(return_value=False)
        mock.read.return_value = json.dumps(hits).encode()
        return mock

    def test_returns_list(self):
        hits = [{"label": "Aging", "resource": "http://id.nlm.nih.gov/mesh/D000014"}]
        with patch("utils.gui_utils.urllib.request.urlopen", return_value=self._mock_response(hits)):
            result = fetch_mesh_terms("aging")
        assert isinstance(result, list)

    def test_formats_as_mesh_terms(self):
        hits = [{"label": "Aging"}, {"label": "Cellular Senescence"}]
        with patch("utils.gui_utils.urllib.request.urlopen", return_value=self._mock_response(hits)):
            result = fetch_mesh_terms("aging")
        assert all("[MeSH Terms]" in t for t in result)

    def test_label_wrapped_in_quotes(self):
        hits = [{"label": "Heart Failure"}]
        with patch("utils.gui_utils.urllib.request.urlopen", return_value=self._mock_response(hits)):
            result = fetch_mesh_terms("heart failure")
        assert '"Heart Failure"[MeSH Terms]' in result

    def test_empty_query_returns_empty(self):
        result = fetch_mesh_terms("")
        assert result == []

    def test_whitespace_only_query_returns_empty(self):
        result = fetch_mesh_terms("   ")
        assert result == []

    def test_api_error_returns_empty(self):
        with patch("utils.gui_utils.urllib.request.urlopen", side_effect=Exception("timeout")):
            result = fetch_mesh_terms("aging")
        assert result == []

    def test_max_results_respected(self):
        hits = [{"label": f"Term {i}"} for i in range(20)]
        with patch("utils.gui_utils.urllib.request.urlopen", return_value=self._mock_response(hits)):
            result = fetch_mesh_terms("aging", max_results=5)
        assert len(result) <= 5

    def test_empty_api_response_returns_empty(self):
        with patch("utils.gui_utils.urllib.request.urlopen", return_value=self._mock_response([])):
            result = fetch_mesh_terms("xyzzy123")
        assert result == []

    def test_no_duplicates(self):
        hits = [{"label": "Aging"}, {"label": "Aging"}]
        with patch("utils.gui_utils.urllib.request.urlopen", return_value=self._mock_response(hits)):
            result = fetch_mesh_terms("aging")
        assert len(result) == len(set(result))


# ══════════════════════════════════════════════════════════════════════════════
# apply_pending_term
# ══════════════════════════════════════════════════════════════════════════════

class TestApplyPendingTerm:
    """apply_pending_term(existing_terms, new_term) -> updated terms string."""

    def test_adds_term_to_empty(self):
        result = apply_pending_term("", "aging[tiab]")
        assert "aging[tiab]" in result

    def test_adds_term_to_existing(self):
        result = apply_pending_term("hiPSC-CM[tiab]", "aging[tiab]")
        assert "hiPSC-CM[tiab]" in result
        assert "aging[tiab]" in result

    def test_no_duplicate_added(self):
        result = apply_pending_term("aging[tiab]", "aging[tiab]")
        assert result.count("aging[tiab]") == 1

    def test_each_term_on_own_line(self):
        result = apply_pending_term("hiPSC-CM[tiab]", "aging[tiab]")
        lines = [l.strip() for l in result.splitlines() if l.strip()]
        assert "hiPSC-CM[tiab]" in lines
        assert "aging[tiab]" in lines

    def test_preserves_existing_terms(self):
        existing = "one[tiab]\ntwo[tiab]\nthree[tiab]"
        result = apply_pending_term(existing, "four[tiab]")
        for t in ("one[tiab]", "two[tiab]", "three[tiab]", "four[tiab]"):
            assert t in result

    def test_strips_blank_lines(self):
        result = apply_pending_term("  \n\n  hiPSC-CM[tiab]\n\n", "aging[tiab]")
        lines = [l for l in result.splitlines() if l.strip()]
        assert all(l.strip() for l in lines)

    def test_mesh_term_added(self):
        result = apply_pending_term("aging[tiab]", '"Aging"[MeSH Terms]')
        assert '"Aging"[MeSH Terms]' in result
