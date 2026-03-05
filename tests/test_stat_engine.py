"""Tests for the statistical test engine (stat_engine.py).

Covers: dispatch table, all test runner functions, sparse fallback chain,
multi-cluster support, NaN handling, and result row completeness.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from abcd_phewas.type_detector import VarType


# ---------------------------------------------------------------------------
# Required result columns (from CONTEXT.md locked decision)
# ---------------------------------------------------------------------------
REQUIRED_COLUMNS = {
    "variable",
    "comparison_type",
    "cluster_label",
    "test_used",
    "statistic",
    "p_value",
    "effect_size",
    "effect_size_type",
    "ci_lower",
    "ci_upper",
    "n_target",
    "n_rest",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _groups_dict(df: pd.DataFrame, col: str) -> dict[int | str, np.ndarray]:
    """Build groups_dict {cluster_label: values_array} from fixture df."""
    groups = {}
    for label in sorted(df["cluster"].unique()):
        mask = df["cluster"] == label
        groups[label] = df.loc[mask, col].values
    return groups


# ---------------------------------------------------------------------------
# Test: ComparisonType enum
# ---------------------------------------------------------------------------


class TestComparisonType:
    def test_enum_values(self):
        from abcd_phewas.stat_engine import ComparisonType

        assert ComparisonType.OMNIBUS == "omnibus"
        assert ComparisonType.ONE_VS_REST == "one_vs_rest"


# ---------------------------------------------------------------------------
# Test: make_result_row
# ---------------------------------------------------------------------------


class TestMakeResultRow:
    def test_all_columns_present(self):
        from abcd_phewas.stat_engine import make_result_row

        row = make_result_row(
            variable="test_var",
            comparison_type="omnibus",
            cluster_label=None,
            test_used="kruskal_wallis",
            statistic=10.5,
            p_value=0.001,
            effect_size=0.05,
            effect_size_type="epsilon_squared",
            ci_lower=0.01,
            ci_upper=0.10,
            n_target=100,
            n_rest=None,
        )
        assert set(row.keys()) == REQUIRED_COLUMNS


# ---------------------------------------------------------------------------
# Test: Omnibus tests
# ---------------------------------------------------------------------------


class TestOmnibus:
    def test_omnibus_continuous(self, two_cluster_data):
        from abcd_phewas.stat_engine import run_kruskal_wallis

        groups = _groups_dict(two_cluster_data, "cont_pheno")
        result = run_kruskal_wallis("cont_pheno", groups, VarType.CONTINUOUS)
        assert result["test_used"] == "kruskal_wallis"
        assert result["comparison_type"] == "omnibus"
        assert result["effect_size_type"] == "epsilon_squared"
        assert result["p_value"] < 0.05  # known strong effect
        assert 0.0 <= result["effect_size"] <= 1.0

    def test_omnibus_binary(self, two_cluster_data):
        from abcd_phewas.stat_engine import run_chi_square_omnibus

        table = pd.crosstab(
            two_cluster_data["cluster"], two_cluster_data["binary_pheno"]
        ).values
        result = run_chi_square_omnibus("binary_pheno", table, VarType.BINARY)
        assert result["test_used"] == "chi_square"
        assert result["comparison_type"] == "omnibus"
        assert result["effect_size_type"] == "cramers_v"
        assert result["p_value"] < 0.05


# ---------------------------------------------------------------------------
# Test: One-vs-rest tests
# ---------------------------------------------------------------------------


class TestOneVsRest:
    def test_one_vs_rest_continuous(self, two_cluster_data):
        from abcd_phewas.stat_engine import run_mann_whitney

        mask = two_cluster_data["cluster"] == 1
        target = two_cluster_data.loc[mask, "cont_pheno"].values
        rest = two_cluster_data.loc[~mask, "cont_pheno"].values
        result = run_mann_whitney(
            "cont_pheno", target, rest, cluster_label=1,
            var_type=VarType.CONTINUOUS, random_state=42,
        )
        assert result["test_used"] == "mann_whitney"
        assert result["comparison_type"] == "one_vs_rest"
        assert result["effect_size_type"] == "cohens_d"
        assert result["p_value"] < 0.05

    def test_one_vs_rest_ordinal(self, two_cluster_data):
        from abcd_phewas.stat_engine import run_mann_whitney

        mask = two_cluster_data["cluster"] == 1
        target = two_cluster_data.loc[mask, "ordinal_pheno"].values.astype(float)
        rest = two_cluster_data.loc[~mask, "ordinal_pheno"].values.astype(float)
        result = run_mann_whitney(
            "ordinal_pheno", target, rest, cluster_label=1,
            var_type=VarType.ORDINAL, random_state=42,
        )
        assert result["test_used"] == "mann_whitney"
        assert result["effect_size_type"] == "rank_biserial"

    def test_one_vs_rest_binary(self, two_cluster_data):
        from abcd_phewas.stat_engine import run_chi_square_pairwise

        mask = two_cluster_data["cluster"] == 1
        target = two_cluster_data.loc[mask, "binary_pheno"].values
        rest = two_cluster_data.loc[~mask, "binary_pheno"].values
        result = run_chi_square_pairwise(
            "binary_pheno", target, rest, cluster_label=1,
            var_type=VarType.BINARY, random_state=42,
        )
        assert result["comparison_type"] == "one_vs_rest"
        assert result["test_used"] in ("chi_square", "fisher_exact")
        assert result["effect_size_type"] == "cramers_v"


# ---------------------------------------------------------------------------
# Test: Sparse fallback chain
# ---------------------------------------------------------------------------


class TestSparseFallback:
    def test_fisher_fallback(self, sparse_contingency_2x2):
        """Sparse 2x2 table -> Fisher's exact test."""
        from abcd_phewas.stat_engine import run_chi_square_pairwise

        # Build target/rest arrays from the contingency table
        # Row 0 = target, Row 1 = rest; Col 0 = category 0, Col 1 = category 1
        target = np.array(
            [0] * sparse_contingency_2x2[0, 0] + [1] * sparse_contingency_2x2[0, 1]
        )
        rest = np.array(
            [0] * sparse_contingency_2x2[1, 0] + [1] * sparse_contingency_2x2[1, 1]
        )
        result = run_chi_square_pairwise(
            "sparse_var", target, rest, cluster_label="sparse",
            var_type=VarType.BINARY, random_state=42,
        )
        assert result["test_used"] == "fisher_exact"

    def test_monte_carlo_fallback(self, sparse_contingency_3x3):
        """Sparse >2x2 table -> Monte Carlo simulated chi-square."""
        from abcd_phewas.stat_engine import run_chi_square_pairwise

        # Build target (row 0) / rest (rows 1+2) arrays from 3x3 table
        # 3 categories: 0, 1, 2
        target = np.array(
            [0] * sparse_contingency_3x3[0, 0]
            + [1] * sparse_contingency_3x3[0, 1]
            + [2] * sparse_contingency_3x3[0, 2]
        )
        rest_rows = sparse_contingency_3x3[1:, :].sum(axis=0)
        rest = np.array(
            [0] * rest_rows[0] + [1] * rest_rows[1] + [2] * rest_rows[2]
        )
        result = run_chi_square_pairwise(
            "sparse_var", target, rest, cluster_label="sparse",
            var_type=VarType.CATEGORICAL, random_state=42,
        )
        assert result["test_used"] == "chi_square_simulated"


# ---------------------------------------------------------------------------
# Test: test_single_variable row counts
# ---------------------------------------------------------------------------


class TestSingleVariable:
    def test_row_count_2_clusters(self, two_cluster_data):
        from abcd_phewas.stat_engine import test_single_variable

        rows = test_single_variable(
            "cont_pheno",
            two_cluster_data["cont_pheno"],
            two_cluster_data["cluster"],
            VarType.CONTINUOUS,
            random_state=42,
        )
        # 2 clusters -> 1 omnibus + 2 one-vs-rest = 3 rows
        assert len(rows) == 3
        comp_types = [r["comparison_type"] for r in rows]
        assert comp_types.count("omnibus") == 1
        assert comp_types.count("one_vs_rest") == 2

    def test_row_count_8_clusters(self, eight_cluster_data):
        from abcd_phewas.stat_engine import test_single_variable

        rows = test_single_variable(
            "cont_pheno",
            eight_cluster_data["cont_pheno"],
            eight_cluster_data["cluster"],
            VarType.CONTINUOUS,
            random_state=42,
        )
        # 8 clusters -> 1 omnibus + 8 one-vs-rest = 9 rows
        assert len(rows) == 9
        comp_types = [r["comparison_type"] for r in rows]
        assert comp_types.count("omnibus") == 1
        assert comp_types.count("one_vs_rest") == 8

    def test_binary_row_count_2_clusters(self, two_cluster_data):
        from abcd_phewas.stat_engine import test_single_variable

        rows = test_single_variable(
            "binary_pheno",
            two_cluster_data["binary_pheno"],
            two_cluster_data["cluster"],
            VarType.BINARY,
            random_state=42,
        )
        assert len(rows) == 3  # 1 omnibus + 2 one-vs-rest

    def test_categorical_row_count_8_clusters(self, eight_cluster_data):
        from abcd_phewas.stat_engine import test_single_variable

        rows = test_single_variable(
            "categ_pheno",
            eight_cluster_data["categ_pheno"],
            eight_cluster_data["cluster"],
            VarType.CATEGORICAL,
            random_state=42,
        )
        assert len(rows) == 9  # 1 omnibus + 8 one-vs-rest


# ---------------------------------------------------------------------------
# Test: Result column completeness
# ---------------------------------------------------------------------------


class TestResultColumns:
    def test_all_12_columns_in_every_row(self, two_cluster_data):
        from abcd_phewas.stat_engine import test_single_variable

        for col, vtype in [
            ("cont_pheno", VarType.CONTINUOUS),
            ("binary_pheno", VarType.BINARY),
            ("ordinal_pheno", VarType.ORDINAL),
            ("categ_pheno", VarType.CATEGORICAL),
        ]:
            rows = test_single_variable(
                col,
                two_cluster_data[col],
                two_cluster_data["cluster"],
                vtype,
                random_state=42,
            )
            for i, row in enumerate(rows):
                assert set(row.keys()) == REQUIRED_COLUMNS, (
                    f"Row {i} for {col} ({vtype}) missing columns: "
                    f"{REQUIRED_COLUMNS - set(row.keys())}"
                )


# ---------------------------------------------------------------------------
# Test: Effect sizes computed for ALL pairs
# ---------------------------------------------------------------------------


class TestEffectSizesAllPairs:
    def test_effect_sizes_not_nan(self, two_cluster_data):
        """Effect sizes are computed for every one-vs-rest comparison."""
        from abcd_phewas.stat_engine import test_single_variable

        for col, vtype in [
            ("cont_pheno", VarType.CONTINUOUS),
            ("binary_pheno", VarType.BINARY),
            ("ordinal_pheno", VarType.ORDINAL),
            ("categ_pheno", VarType.CATEGORICAL),
        ]:
            rows = test_single_variable(
                col,
                two_cluster_data[col],
                two_cluster_data["cluster"],
                vtype,
                random_state=42,
            )
            for row in rows:
                assert not np.isnan(row["effect_size"]), (
                    f"effect_size is NaN for {col} ({vtype}) "
                    f"comparison={row['comparison_type']} cluster={row['cluster_label']}"
                )


# ---------------------------------------------------------------------------
# Test: NaN handling
# ---------------------------------------------------------------------------


class TestNanHandling:
    def test_nan_in_data_still_produces_results(self, two_cluster_data):
        """Variable with some NaN values still produces valid results."""
        from abcd_phewas.stat_engine import test_single_variable

        # Inject NaN into some rows
        data = two_cluster_data["cont_pheno"].copy()
        data.iloc[0] = np.nan
        data.iloc[10] = np.nan
        data.iloc[50] = np.nan

        rows = test_single_variable(
            "cont_pheno_with_nan",
            data,
            two_cluster_data["cluster"],
            VarType.CONTINUOUS,
            random_state=42,
        )
        assert len(rows) == 3  # still 1 omnibus + 2 one-vs-rest
        for row in rows:
            assert not np.isnan(row["p_value"])
            assert not np.isnan(row["statistic"])


# ---------------------------------------------------------------------------
# Test: Dispatch table coverage
# ---------------------------------------------------------------------------


class TestDispatchTable:
    def test_all_8_combinations(self):
        """Dispatch table has entries for all (VarType, ComparisonType) pairs."""
        from abcd_phewas.stat_engine import ComparisonType, TEST_DISPATCH

        for vt in VarType:
            for ct in ComparisonType:
                assert (vt, ct) in TEST_DISPATCH, (
                    f"Missing dispatch entry for ({vt}, {ct})"
                )
        assert len(TEST_DISPATCH) == 8
