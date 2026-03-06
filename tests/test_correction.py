"""Tests for multiple comparison correction logic.

Covers:
- Global FDR-BH and Bonferroni with omnibus/OVR family separation
- NaN p-value passthrough
- Within-domain corrections per (comparison_type, domain) pair
- Edge cases: single-test domains, all-NaN domains, Bonferroni capping
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from statsmodels.stats.multitest import multipletests

from abcd_phewas.correction import apply_corrections


def _make_raw_df() -> pd.DataFrame:
    """Synthetic DataFrame mimicking run_all_tests output + domain column.

    3 domains, mix of omnibus and one_vs_rest rows, includes NaN p-values.
    """
    rows = [
        # --- Domain A: omnibus rows ---
        {"variable": "varA1", "comparison_type": "omnibus", "cluster_label": "all",
         "test_used": "kruskal", "statistic": 10.0, "p_value": 0.001,
         "effect_size": 0.1, "effect_size_type": "epsilon_sq",
         "ci_lower": np.nan, "ci_upper": np.nan, "n_target": 100, "n_rest": 400,
         "domain": "DomainA"},
        {"variable": "varA2", "comparison_type": "omnibus", "cluster_label": "all",
         "test_used": "kruskal", "statistic": 5.0, "p_value": 0.03,
         "effect_size": 0.05, "effect_size_type": "epsilon_sq",
         "ci_lower": np.nan, "ci_upper": np.nan, "n_target": 100, "n_rest": 400,
         "domain": "DomainA"},
        {"variable": "varA3", "comparison_type": "omnibus", "cluster_label": "all",
         "test_used": "kruskal", "statistic": 2.0, "p_value": 0.15,
         "effect_size": 0.02, "effect_size_type": "epsilon_sq",
         "ci_lower": np.nan, "ci_upper": np.nan, "n_target": 100, "n_rest": 400,
         "domain": "DomainA"},
        # --- Domain A: one_vs_rest rows ---
        {"variable": "varA1", "comparison_type": "one_vs_rest", "cluster_label": "C1",
         "test_used": "mannwhitney", "statistic": 8.0, "p_value": 0.005,
         "effect_size": 0.3, "effect_size_type": "rank_biserial",
         "ci_lower": 0.1, "ci_upper": 0.5, "n_target": 50, "n_rest": 450,
         "domain": "DomainA"},
        {"variable": "varA2", "comparison_type": "one_vs_rest", "cluster_label": "C1",
         "test_used": "mannwhitney", "statistic": 3.0, "p_value": 0.08,
         "effect_size": 0.1, "effect_size_type": "rank_biserial",
         "ci_lower": -0.05, "ci_upper": 0.25, "n_target": 50, "n_rest": 450,
         "domain": "DomainA"},
        # --- Domain B: omnibus rows ---
        {"variable": "varB1", "comparison_type": "omnibus", "cluster_label": "all",
         "test_used": "chi2", "statistic": 12.0, "p_value": 0.0005,
         "effect_size": 0.15, "effect_size_type": "cramers_v",
         "ci_lower": np.nan, "ci_upper": np.nan, "n_target": 100, "n_rest": 400,
         "domain": "DomainB"},
        {"variable": "varB2", "comparison_type": "omnibus", "cluster_label": "all",
         "test_used": "chi2", "statistic": 1.0, "p_value": np.nan,
         "effect_size": np.nan, "effect_size_type": "cramers_v",
         "ci_lower": np.nan, "ci_upper": np.nan, "n_target": 100, "n_rest": 400,
         "domain": "DomainB"},
        # --- Domain B: one_vs_rest rows ---
        {"variable": "varB1", "comparison_type": "one_vs_rest", "cluster_label": "C1",
         "test_used": "fisher", "statistic": 6.0, "p_value": 0.01,
         "effect_size": 0.2, "effect_size_type": "cramers_v",
         "ci_lower": 0.05, "ci_upper": 0.35, "n_target": 50, "n_rest": 450,
         "domain": "DomainB"},
        # --- Domain C: single omnibus test (edge case) ---
        {"variable": "varC1", "comparison_type": "omnibus", "cluster_label": "all",
         "test_used": "kruskal", "statistic": 7.0, "p_value": 0.02,
         "effect_size": 0.08, "effect_size_type": "epsilon_sq",
         "ci_lower": np.nan, "ci_upper": np.nan, "n_target": 100, "n_rest": 400,
         "domain": "DomainC"},
    ]
    return pd.DataFrame(rows)


class TestApplyCorrections:
    """Test apply_corrections() pure function."""

    def test_returns_four_new_columns(self):
        df = _make_raw_df()
        result = apply_corrections(df)
        expected_cols = {"fdr_q_global", "bonf_p_global", "fdr_q_domain", "bonf_p_domain"}
        assert expected_cols.issubset(set(result.columns))

    def test_does_not_modify_input(self):
        df = _make_raw_df()
        orig_cols = list(df.columns)
        _ = apply_corrections(df)
        assert list(df.columns) == orig_cols, "Input DataFrame should not be modified"

    def test_global_omnibus_family_separation(self):
        """Global FDR for omnibus rows should be computed from omnibus p-values only."""
        df = _make_raw_df()
        result = apply_corrections(df)

        # Extract omnibus rows with valid p-values
        omnibus_mask = (result["comparison_type"] == "omnibus") & result["p_value"].notna()
        omnibus_pvals = result.loc[omnibus_mask, "p_value"].values

        # Manually compute expected FDR for omnibus family
        _, expected_fdr, _, _ = multipletests(omnibus_pvals, method="fdr_bh")

        actual_fdr = result.loc[omnibus_mask, "fdr_q_global"].values
        np.testing.assert_array_almost_equal(actual_fdr, expected_fdr)

    def test_global_ovr_family_separation(self):
        """Global FDR for OVR rows should be computed from OVR p-values only."""
        df = _make_raw_df()
        result = apply_corrections(df)

        ovr_mask = result["comparison_type"] == "one_vs_rest"
        ovr_pvals = result.loc[ovr_mask, "p_value"].values

        _, expected_fdr, _, _ = multipletests(ovr_pvals, method="fdr_bh")
        actual_fdr = result.loc[ovr_mask, "fdr_q_global"].values
        np.testing.assert_array_almost_equal(actual_fdr, expected_fdr)

    def test_nan_pvalue_passthrough(self):
        """Rows with NaN p_value should have NaN in all 4 correction columns."""
        df = _make_raw_df()
        result = apply_corrections(df)

        nan_mask = result["p_value"].isna()
        assert nan_mask.sum() > 0, "Test data should include NaN p-values"

        for col in ["fdr_q_global", "bonf_p_global", "fdr_q_domain", "bonf_p_domain"]:
            assert result.loc[nan_mask, col].isna().all(), (
                f"NaN p-value rows should have NaN in {col}"
            )

    def test_within_domain_corrections(self):
        """Within-domain corrections should use only that domain's p-values."""
        df = _make_raw_df()
        result = apply_corrections(df)

        # DomainA omnibus has 3 valid p-values -- enough for domain correction
        domA_omni_mask = (
            (result["comparison_type"] == "omnibus")
            & (result["domain"] == "DomainA")
            & result["p_value"].notna()
        )
        domA_pvals = result.loc[domA_omni_mask, "p_value"].values
        assert len(domA_pvals) == 3

        _, expected_fdr_domain, _, _ = multipletests(domA_pvals, method="fdr_bh")
        actual_fdr_domain = result.loc[domA_omni_mask, "fdr_q_domain"].values
        np.testing.assert_array_almost_equal(actual_fdr_domain, expected_fdr_domain)

    def test_single_test_domain_gets_nan_domain_corrections(self):
        """Domain with only 1 valid p-value in a family gets NaN domain corrections."""
        df = _make_raw_df()
        result = apply_corrections(df)

        # DomainC has only 1 omnibus test
        domC_omni_mask = (
            (result["comparison_type"] == "omnibus")
            & (result["domain"] == "DomainC")
        )
        assert domC_omni_mask.sum() == 1

        row = result.loc[domC_omni_mask].iloc[0]
        assert pd.isna(row["fdr_q_domain"]), "Single-test domain should get NaN FDR domain"
        assert pd.isna(row["bonf_p_domain"]), "Single-test domain should get NaN Bonf domain"

    def test_bonferroni_capped_at_one(self):
        """Bonferroni-corrected p-values should never exceed 1.0."""
        df = _make_raw_df()
        result = apply_corrections(df)

        for col in ["bonf_p_global", "bonf_p_domain"]:
            valid = result[col].dropna()
            if len(valid) > 0:
                assert (valid <= 1.0).all(), f"{col} should be capped at 1.0"

    def test_fdr_monotonicity_within_family(self):
        """FDR q-values should be monotonically consistent with raw p-value ordering."""
        df = _make_raw_df()
        result = apply_corrections(df)

        # Check omnibus family
        omni = result[result["comparison_type"] == "omnibus"].dropna(subset=["p_value"])
        omni_sorted = omni.sort_values("p_value")
        fdr_vals = omni_sorted["fdr_q_global"].values

        # BH q-values: if p1 <= p2, then q1 <= q2
        for i in range(len(fdr_vals) - 1):
            assert fdr_vals[i] <= fdr_vals[i + 1] + 1e-12, (
                f"FDR q-values should be non-decreasing with p-value ordering: "
                f"q[{i}]={fdr_vals[i]} > q[{i+1}]={fdr_vals[i+1]}"
            )

    def test_global_bonferroni_values(self):
        """Global Bonferroni corrections should match manual computation."""
        df = _make_raw_df()
        result = apply_corrections(df)

        omnibus_mask = (result["comparison_type"] == "omnibus") & result["p_value"].notna()
        omnibus_pvals = result.loc[omnibus_mask, "p_value"].values

        _, expected_bonf, _, _ = multipletests(omnibus_pvals, method="bonferroni")
        actual_bonf = result.loc[omnibus_mask, "bonf_p_global"].values
        np.testing.assert_array_almost_equal(actual_bonf, expected_bonf)
