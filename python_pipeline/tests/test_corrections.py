"""Unit tests for corrections.py.

Verifies that FDR and Bonferroni adjustments match R's p.adjust().
"""

import numpy as np
import pandas as pd
import pytest
from statsmodels.stats.multitest import multipletests

from python_pipeline.corrections import apply_multiple_corrections


# Known p-values used in R: p.adjust(c(0.001, 0.01, 0.05, 0.1, 0.5), method="fdr")
_PVALS = [0.001, 0.01, 0.05, 0.1, 0.5]
# Expected FDR (BH) from R: [0.005, 0.025, 0.0833, 0.125, 0.5]
# We compute them via statsmodels to keep the test self-contained.
_, _EXPECTED_FDR, _, _ = multipletests(_PVALS, alpha=0.05, method="fdr_bh")
_, _EXPECTED_BONF, _, _ = multipletests(_PVALS, alpha=0.05, method="bonferroni")


class TestApplyMultipleCorrections:
    @pytest.fixture()
    def simple_results(self):
        return pd.DataFrame({
            "phenotype": [f"var_{i}" for i in range(5)],
            "cluster_contrast": ["cluster_1"] * 5,
            "beta": [0.1] * 5,
            "se": [0.01] * 5,
            "pval": _PVALS,
        })

    def test_fdr_column_added(self, simple_results):
        result = apply_multiple_corrections(simple_results)
        assert "pval_fdr" in result.columns

    def test_bonferroni_column_added(self, simple_results):
        result = apply_multiple_corrections(simple_results)
        assert "pval_bonferroni" in result.columns

    def test_fdr_values_match_statsmodels(self, simple_results):
        result = apply_multiple_corrections(simple_results)
        np.testing.assert_allclose(
            result["pval_fdr"].values, _EXPECTED_FDR, atol=1e-10
        )

    def test_bonferroni_values_match_statsmodels(self, simple_results):
        result = apply_multiple_corrections(simple_results)
        np.testing.assert_allclose(
            result["pval_bonferroni"].values, _EXPECTED_BONF, atol=1e-10
        )

    def test_corrections_per_contrast(self):
        df = pd.DataFrame({
            "phenotype": [f"var_{i}" for i in range(6)],
            "cluster_contrast": ["cluster_1", "cluster_1", "cluster_1",
                                  "cluster_2", "cluster_2", "cluster_2"],
            "pval": [0.001, 0.05, 0.5, 0.002, 0.04, 0.3],
        })
        result = apply_multiple_corrections(df)
        # Corrections are independent between contrasts
        c1 = result[result["cluster_contrast"] == "cluster_1"]["pval_fdr"].values
        c2 = result[result["cluster_contrast"] == "cluster_2"]["pval_fdr"].values
        # Each contrast has 3 tests; values should differ
        assert not np.allclose(c1, c2)

    def test_nan_pvals_skipped(self):
        df = pd.DataFrame({
            "phenotype": ["v1", "v2", "v3"],
            "cluster_contrast": ["c1", "c1", "c1"],
            "pval": [0.01, np.nan, 0.05],
        })
        result = apply_multiple_corrections(df)
        assert np.isnan(result.loc[result["phenotype"] == "v2", "pval_fdr"].values[0])
        assert result.loc[result["phenotype"] == "v1", "pval_fdr"].notna().all()

    def test_original_df_not_mutated(self):
        df = pd.DataFrame({
            "phenotype": ["v1", "v2"],
            "cluster_contrast": ["c1", "c1"],
            "pval": [0.01, 0.05],
        })
        original_cols = list(df.columns)
        apply_multiple_corrections(df)
        assert list(df.columns) == original_cols
