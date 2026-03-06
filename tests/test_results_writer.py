"""Tests for results CSV assembly and writing.

Covers:
- Domain column merge from domain_map dict
- Missingness rate merge from missingness DataFrame
- Unrecognized variables get "Other/Unclassified" domain
- Output has exactly 18 columns in required order
- Output sorted by p_value ascending
- write_results_csv round-trip through pandas
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from abcd_phewas.results_writer import assemble_results, write_results_csv

# The 18 required columns in order
REQUIRED_COLUMNS = [
    "variable", "domain", "comparison_type", "cluster_label",
    "test_used", "statistic", "p_value", "effect_size",
    "effect_size_type", "ci_lower", "ci_upper", "n_target", "n_rest",
    "missingness_rate", "fdr_q_global", "bonf_p_global",
    "fdr_q_domain", "bonf_p_domain",
]


def _make_raw_df() -> pd.DataFrame:
    """Synthetic 12-column DataFrame from run_all_tests."""
    rows = [
        {"variable": "var1", "comparison_type": "omnibus", "cluster_label": "all",
         "test_used": "kruskal", "statistic": 10.0, "p_value": 0.05,
         "effect_size": 0.1, "effect_size_type": "epsilon_sq",
         "ci_lower": np.nan, "ci_upper": np.nan, "n_target": 100, "n_rest": 400},
        {"variable": "var2", "comparison_type": "omnibus", "cluster_label": "all",
         "test_used": "chi2", "statistic": 15.0, "p_value": 0.001,
         "effect_size": 0.2, "effect_size_type": "cramers_v",
         "ci_lower": np.nan, "ci_upper": np.nan, "n_target": 100, "n_rest": 400},
        {"variable": "var1", "comparison_type": "one_vs_rest", "cluster_label": "C1",
         "test_used": "mannwhitney", "statistic": 8.0, "p_value": 0.02,
         "effect_size": 0.3, "effect_size_type": "rank_biserial",
         "ci_lower": 0.1, "ci_upper": 0.5, "n_target": 50, "n_rest": 450},
        {"variable": "var3", "comparison_type": "omnibus", "cluster_label": "all",
         "test_used": "kruskal", "statistic": 3.0, "p_value": 0.10,
         "effect_size": 0.03, "effect_size_type": "epsilon_sq",
         "ci_lower": np.nan, "ci_upper": np.nan, "n_target": 100, "n_rest": 400},
    ]
    return pd.DataFrame(rows)


def _make_domain_map() -> dict:
    """Domain map: var1 and var2 are known, var3 is not."""
    return {
        "var1": ("Neurocognition", "#FF0000"),
        "var2": ("Mental Health", "#00FF00"),
        # var3 intentionally missing -> should default to "Other/Unclassified"
    }


def _make_missingness() -> pd.DataFrame:
    """Missingness DataFrame with variable, missingness_rate columns."""
    return pd.DataFrame({
        "variable": ["var1", "var2", "var3"],
        "missingness_rate": [0.05, 0.10, 0.02],
        "n_missing": [25, 50, 10],
        "n_total": [500, 500, 500],
    })


class TestAssembleResults:
    """Test assemble_results() function."""

    def test_output_has_18_columns(self):
        result = assemble_results(_make_raw_df(), _make_domain_map(), _make_missingness())
        assert list(result.columns) == REQUIRED_COLUMNS

    def test_domain_merge_known_variable(self):
        result = assemble_results(_make_raw_df(), _make_domain_map(), _make_missingness())
        var1_domains = result.loc[result["variable"] == "var1", "domain"].unique()
        assert len(var1_domains) == 1
        assert var1_domains[0] == "Neurocognition"

    def test_domain_merge_unknown_variable_gets_other(self):
        result = assemble_results(_make_raw_df(), _make_domain_map(), _make_missingness())
        var3_domain = result.loc[result["variable"] == "var3", "domain"].iloc[0]
        assert var3_domain == "Other/Unclassified"

    def test_missingness_merge(self):
        result = assemble_results(_make_raw_df(), _make_domain_map(), _make_missingness())
        var2_miss = result.loc[result["variable"] == "var2", "missingness_rate"].iloc[0]
        assert var2_miss == pytest.approx(0.10)

    def test_sorted_by_p_value_ascending(self):
        result = assemble_results(_make_raw_df(), _make_domain_map(), _make_missingness())
        pvals = result["p_value"].values
        # Verify non-decreasing order
        for i in range(len(pvals) - 1):
            assert pvals[i] <= pvals[i + 1], (
                f"Results not sorted by p_value: p[{i}]={pvals[i]} > p[{i+1}]={pvals[i+1]}"
            )

    def test_first_row_has_smallest_p_value(self):
        result = assemble_results(_make_raw_df(), _make_domain_map(), _make_missingness())
        assert result.iloc[0]["p_value"] == pytest.approx(0.001)


class TestWriteResultsCsv:
    """Test write_results_csv() function."""

    def test_round_trip(self, tmp_path):
        df = assemble_results(_make_raw_df(), _make_domain_map(), _make_missingness())
        out_path = tmp_path / "results.csv"
        write_results_csv(df, str(out_path))

        # Read back and verify
        loaded = pd.read_csv(out_path)
        assert loaded.shape == df.shape
        assert list(loaded.columns) == list(df.columns)

    def test_csv_file_exists(self, tmp_path):
        df = assemble_results(_make_raw_df(), _make_domain_map(), _make_missingness())
        out_path = tmp_path / "results.csv"
        write_results_csv(df, str(out_path))
        assert out_path.exists()
        assert out_path.stat().st_size > 0
