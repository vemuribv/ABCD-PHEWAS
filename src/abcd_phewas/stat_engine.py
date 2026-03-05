"""Statistical test engine: dispatch, test runners, and result assembly.

Phase 2, Plan 02: Core computation module that determines the test statistic,
p-value, effect size, and CIs for every (variable, cluster) pair.

Dispatch table maps (VarType, ComparisonType) -> runner function.
Each runner returns a standardised result dict with 12 columns.
"""
from __future__ import annotations

import logging
import warnings
from concurrent.futures import ProcessPoolExecutor
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency, fisher_exact, kruskal, mannwhitneyu

from abcd_phewas.effect_sizes import (
    bootstrap_ci,
    cohens_d,
    cramers_v,
    epsilon_squared,
    monte_carlo_chi_square,
    rank_biserial,
)
from abcd_phewas.type_detector import VarType


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ComparisonType(str, Enum):
    """Whether this row is an omnibus test or a one-vs-rest comparison."""

    OMNIBUS = "omnibus"
    ONE_VS_REST = "one_vs_rest"


# ---------------------------------------------------------------------------
# Result row factory
# ---------------------------------------------------------------------------


def make_result_row(
    variable: str,
    comparison_type: str,
    cluster_label,
    test_used: str,
    statistic: float,
    p_value: float,
    effect_size: float,
    effect_size_type: str,
    ci_lower: float,
    ci_upper: float,
    n_target: int,
    n_rest,
) -> dict:
    """Build a standardised result dict with the 12 required columns."""
    return {
        "variable": variable,
        "comparison_type": comparison_type,
        "cluster_label": cluster_label,
        "test_used": test_used,
        "statistic": statistic,
        "p_value": p_value,
        "effect_size": effect_size,
        "effect_size_type": effect_size_type,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "n_target": n_target,
        "n_rest": n_rest,
    }


# ---------------------------------------------------------------------------
# NaN result row (for degenerate / insufficient data)
# ---------------------------------------------------------------------------


def _nan_result(
    variable: str,
    comparison_type: str,
    cluster_label,
    test_used: str,
    effect_size_type: str,
    n_target: int,
    n_rest,
) -> dict:
    return make_result_row(
        variable=variable,
        comparison_type=comparison_type,
        cluster_label=cluster_label,
        test_used=test_used,
        statistic=float("nan"),
        p_value=float("nan"),
        effect_size=float("nan"),
        effect_size_type=effect_size_type,
        ci_lower=float("nan"),
        ci_upper=float("nan"),
        n_target=n_target,
        n_rest=n_rest,
    )


# ---------------------------------------------------------------------------
# Omnibus: Kruskal-Wallis (continuous / ordinal)
# ---------------------------------------------------------------------------


def run_kruskal_wallis(
    variable: str,
    groups_dict: dict,
    var_type: VarType,
    random_state: Optional[int] = None,
) -> dict:
    """Kruskal-Wallis omnibus test across all clusters.

    Parameters
    ----------
    variable : str
        Variable name.
    groups_dict : dict
        {cluster_label: np.ndarray of values} -- NaN already dropped per group.
    var_type : VarType
        CONTINUOUS or ORDINAL.
    random_state : int or None
        Unused (kept for dispatch signature consistency).
    """
    # Drop NaN within each group and filter to groups with >= 2 obs
    clean_groups = {}
    for label, vals in groups_dict.items():
        arr = np.asarray(vals, dtype=float)
        arr = arr[~np.isnan(arr)]
        if len(arr) >= 2:
            clean_groups[label] = arr

    n_total = sum(len(g) for g in clean_groups.values())

    if len(clean_groups) < 2:
        return _nan_result(
            variable, ComparisonType.OMNIBUS.value, None,
            "kruskal_wallis", "epsilon_squared", n_total, None,
        )

    arrays = list(clean_groups.values())
    h_stat, p_val = kruskal(*arrays)
    es = epsilon_squared(h_stat, n_total)

    # Bootstrap CI for epsilon_squared on omnibus is not standard;
    # report NaN CI for omnibus (CIs are for one-vs-rest per CONTEXT.md pattern)
    return make_result_row(
        variable=variable,
        comparison_type=ComparisonType.OMNIBUS.value,
        cluster_label=None,
        test_used="kruskal_wallis",
        statistic=float(h_stat),
        p_value=float(p_val),
        effect_size=float(es),
        effect_size_type="epsilon_squared",
        ci_lower=float("nan"),
        ci_upper=float("nan"),
        n_target=n_total,
        n_rest=None,
    )


# ---------------------------------------------------------------------------
# Omnibus: Chi-square (binary / categorical)
# ---------------------------------------------------------------------------


def run_chi_square_omnibus(
    variable: str,
    contingency_table: np.ndarray,
    var_type: VarType,
    random_state: Optional[int] = None,
) -> dict:
    """Chi-square omnibus test on a KxL contingency table.

    No sparse fallback for omnibus (see plan justification).
    """
    table = np.asarray(contingency_table)

    # Remove all-zero rows and columns (Pitfall 1)
    row_mask = table.sum(axis=1) > 0
    col_mask = table.sum(axis=0) > 0
    table = table[row_mask][:, col_mask]

    n_total = int(table.sum())

    if table.shape[0] < 2 or table.shape[1] < 2:
        return _nan_result(
            variable, ComparisonType.OMNIBUS.value, None,
            "chi_square", "cramers_v", n_total, None,
        )

    chi2, p_val, _, _ = chi2_contingency(table, correction=False)
    es = cramers_v(table)

    return make_result_row(
        variable=variable,
        comparison_type=ComparisonType.OMNIBUS.value,
        cluster_label=None,
        test_used="chi_square",
        statistic=float(chi2),
        p_value=float(p_val),
        effect_size=float(es),
        effect_size_type="cramers_v",
        ci_lower=float("nan"),
        ci_upper=float("nan"),
        n_target=n_total,
        n_rest=None,
    )


# ---------------------------------------------------------------------------
# One-vs-rest: Mann-Whitney U (continuous / ordinal)
# ---------------------------------------------------------------------------


def run_mann_whitney(
    variable: str,
    target_values: np.ndarray,
    rest_values: np.ndarray,
    cluster_label,
    var_type: VarType,
    random_state: Optional[int] = None,
) -> dict:
    """Mann-Whitney U one-vs-rest test.

    Effect size: Cohen's d for CONTINUOUS, rank-biserial for ORDINAL.
    """
    target = np.asarray(target_values, dtype=float)
    rest = np.asarray(rest_values, dtype=float)

    # Drop NaN
    target = target[~np.isnan(target)]
    rest = rest[~np.isnan(rest)]

    n1, n2 = len(target), len(rest)

    # Determine effect size type based on var_type
    es_type = "cohens_d" if var_type == VarType.CONTINUOUS else "rank_biserial"

    if n1 < 2 or n2 < 2:
        return _nan_result(
            variable, ComparisonType.ONE_VS_REST.value, cluster_label,
            "mann_whitney", es_type, n1, n2,
        )

    u_stat, p_val = mannwhitneyu(target, rest, alternative="two-sided")

    if var_type == VarType.CONTINUOUS:
        es = cohens_d(target, rest)
        ci = bootstrap_ci(cohens_d, (target, rest), random_state=random_state)
    else:
        # Ordinal: rank-biserial
        es = rank_biserial(float(u_stat), n1, n2)
        ci = bootstrap_ci(
            lambda t, r: rank_biserial(
                float(mannwhitneyu(t, r, alternative="two-sided").statistic),
                len(t), len(r),
            ),
            (target, rest),
            random_state=random_state,
        )

    return make_result_row(
        variable=variable,
        comparison_type=ComparisonType.ONE_VS_REST.value,
        cluster_label=cluster_label,
        test_used="mann_whitney",
        statistic=float(u_stat),
        p_value=float(p_val),
        effect_size=float(es),
        effect_size_type=es_type,
        ci_lower=float(ci[0]),
        ci_upper=float(ci[1]),
        n_target=n1,
        n_rest=n2,
    )


# ---------------------------------------------------------------------------
# One-vs-rest: Chi-square / Fisher / Monte Carlo (binary / categorical)
# ---------------------------------------------------------------------------


def run_chi_square_pairwise(
    variable: str,
    target_values: np.ndarray,
    rest_values: np.ndarray,
    cluster_label,
    var_type: VarType,
    random_state: Optional[int] = None,
) -> dict:
    """Chi-square one-vs-rest with sparse fallback chain.

    Fallback: expected < 5 + 2x2 -> Fisher's exact,
              expected < 5 + >2x2 -> Monte Carlo simulated chi-square,
              else -> standard chi-square.
    """
    target = np.asarray(target_values)
    rest = np.asarray(rest_values)

    # Drop NaN (handle mixed types)
    if target.dtype.kind == 'f':
        target = target[~np.isnan(target)]
    if rest.dtype.kind == 'f':
        rest = rest[~np.isnan(rest)]

    n1, n2 = len(target), len(rest)

    if n1 < 1 or n2 < 1:
        return _nan_result(
            variable, ComparisonType.ONE_VS_REST.value, cluster_label,
            "chi_square", "cramers_v", n1, n2,
        )

    # Build 2xL contingency table
    all_vals = np.concatenate([target, rest])
    group_labels = np.array([0] * n1 + [1] * n2)
    ct = pd.crosstab(
        pd.Series(group_labels, name="group"),
        pd.Series(all_vals, name="value"),
    ).values

    # Remove all-zero rows/columns (Pitfall 1)
    row_mask = ct.sum(axis=1) > 0
    col_mask = ct.sum(axis=0) > 0
    ct = ct[row_mask][:, col_mask]

    if ct.shape[0] < 2 or ct.shape[1] < 1:
        return _nan_result(
            variable, ComparisonType.ONE_VS_REST.value, cluster_label,
            "chi_square", "cramers_v", n1, n2,
        )

    # Compute expected frequencies to check sparseness
    _, _, _, expected = chi2_contingency(ct, correction=False)
    is_sparse = (expected < 5).any()

    if is_sparse and ct.shape == (2, 2):
        # Fisher's exact test
        odds_ratio, p_val = fisher_exact(ct)
        test_used = "fisher_exact"
        statistic = float(odds_ratio)
    elif is_sparse and (ct.shape[0] > 2 or ct.shape[1] > 2):
        # Monte Carlo simulated chi-square
        rng = np.random.default_rng(random_state)
        chi2, _, _, _ = chi2_contingency(ct, correction=False)
        p_val = monte_carlo_chi_square(ct, n_replicates=10_000, rng=rng)
        test_used = "chi_square_simulated"
        statistic = float(chi2)
    else:
        # Standard chi-square
        chi2, p_val, _, _ = chi2_contingency(ct, correction=False)
        test_used = "chi_square"
        statistic = float(chi2)

    es = cramers_v(ct)

    # Bootstrap CI for Cramer's V
    ci = bootstrap_ci(
        lambda t, r: cramers_v(
            pd.crosstab(
                pd.Series(np.array([0] * len(t) + [1] * len(r))),
                pd.Series(np.concatenate([t, r])),
            ).values
        ),
        (target, rest),
        random_state=random_state,
    )

    return make_result_row(
        variable=variable,
        comparison_type=ComparisonType.ONE_VS_REST.value,
        cluster_label=cluster_label,
        test_used=test_used,
        statistic=statistic,
        p_value=float(p_val),
        effect_size=float(es),
        effect_size_type="cramers_v",
        ci_lower=float(ci[0]),
        ci_upper=float(ci[1]),
        n_target=n1,
        n_rest=n2,
    )


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

TEST_DISPATCH = {
    (VarType.CONTINUOUS, ComparisonType.OMNIBUS): run_kruskal_wallis,
    (VarType.ORDINAL, ComparisonType.OMNIBUS): run_kruskal_wallis,
    (VarType.BINARY, ComparisonType.OMNIBUS): run_chi_square_omnibus,
    (VarType.CATEGORICAL, ComparisonType.OMNIBUS): run_chi_square_omnibus,
    (VarType.CONTINUOUS, ComparisonType.ONE_VS_REST): run_mann_whitney,
    (VarType.ORDINAL, ComparisonType.ONE_VS_REST): run_mann_whitney,
    (VarType.BINARY, ComparisonType.ONE_VS_REST): run_chi_square_pairwise,
    (VarType.CATEGORICAL, ComparisonType.ONE_VS_REST): run_chi_square_pairwise,
}


# ---------------------------------------------------------------------------
# Main entry: test a single variable
# ---------------------------------------------------------------------------


def test_single_variable(
    variable: str,
    data_series: pd.Series,
    cluster_series: pd.Series,
    var_type: VarType,
    random_state: Optional[int] = None,
) -> list[dict]:
    """Run omnibus + one-vs-rest tests for a single variable.

    Parameters
    ----------
    variable : str
        Variable name.
    data_series : pd.Series
        Values for this variable (may contain NaN).
    cluster_series : pd.Series
        Cluster assignments aligned with data_series.
    var_type : VarType
        Detected variable type.
    random_state : int or None
        Seed for reproducibility of bootstrap and Monte Carlo.

    Returns
    -------
    list[dict]
        K+1 result dicts (1 omnibus + K one-vs-rest).
    """
    # Drop NaN from data (paired with cluster)
    mask = ~pd.isna(data_series)
    data = data_series[mask].reset_index(drop=True)
    clusters = cluster_series[mask].reset_index(drop=True)

    unique_labels = sorted(clusters.unique())
    results = []

    # --- Omnibus ---
    omnibus_runner = TEST_DISPATCH[(var_type, ComparisonType.OMNIBUS)]

    if var_type in (VarType.CONTINUOUS, VarType.ORDINAL):
        groups_dict = {}
        for label in unique_labels:
            groups_dict[label] = data[clusters == label].values
        omnibus_row = omnibus_runner(
            variable, groups_dict, var_type, random_state=random_state,
        )
    else:
        # Binary / categorical: build KxL contingency table
        ct = pd.crosstab(clusters, data).values
        omnibus_row = omnibus_runner(
            variable, ct, var_type, random_state=random_state,
        )

    results.append(omnibus_row)

    # --- One-vs-rest per cluster ---
    ovr_runner = TEST_DISPATCH[(var_type, ComparisonType.ONE_VS_REST)]

    for label in unique_labels:
        target_mask = clusters == label
        target_vals = data[target_mask].values
        rest_vals = data[~target_mask].values

        if var_type in (VarType.CONTINUOUS, VarType.ORDINAL):
            row = ovr_runner(
                variable, target_vals, rest_vals, cluster_label=label,
                var_type=var_type, random_state=random_state,
            )
        else:
            row = ovr_runner(
                variable, target_vals, rest_vals, cluster_label=label,
                var_type=var_type, random_state=random_state,
            )

        results.append(row)

    return results


# ---------------------------------------------------------------------------
# Parallel wrapper for ProcessPoolExecutor
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)


def _test_variable_wrapper(args: tuple) -> list[dict]:
    """Unpack args tuple and call test_single_variable.

    ProcessPoolExecutor can't efficiently pickle DataFrames, so we pass
    raw values and reconstruct pd.Series inside each worker.

    Parameters
    ----------
    args : tuple
        (variable, data_values, cluster_values, var_type, random_state)

    Returns
    -------
    list[dict]
        Result rows from test_single_variable, or a single NaN row on error.
    """
    variable, data_values, cluster_values, var_type, random_state = args
    try:
        data_series = pd.Series(data_values)
        cluster_series = pd.Series(cluster_values)
        return test_single_variable(
            variable, data_series, cluster_series, var_type,
            random_state=random_state,
        )
    except Exception as exc:
        logger.warning("Error testing variable '%s': %s", variable, exc)
        return [_nan_result(
            variable=variable,
            comparison_type=ComparisonType.OMNIBUS.value,
            cluster_label=None,
            test_used="error",
            effect_size_type="none",
            n_target=0,
            n_rest=None,
        )]


# ---------------------------------------------------------------------------
# Main orchestrator: run all tests across all variables
# ---------------------------------------------------------------------------


def run_all_tests(
    pipeline_result,
    cluster_col: str = "cluster",
    n_workers: int | None = None,
    random_state: int = 42,
) -> pd.DataFrame:
    """Run omnibus + one-vs-rest tests for every variable in the pipeline result.

    Parameters
    ----------
    pipeline_result : PipelineResult
        Output from run_pipeline containing df, type_map, etc.
    cluster_col : str
        Name of the cluster column in pipeline_result.df.
    n_workers : int or None
        Number of parallel workers.  1 = serial (for debugging).
        None = let ProcessPoolExecutor decide (os.cpu_count()).
    random_state : int
        Seed for reproducibility of bootstrap and Monte Carlo.

    Returns
    -------
    pd.DataFrame
        Result table with one row per (variable, comparison) pair.
        Columns: variable, comparison_type, cluster_label, test_used,
        statistic, p_value, effect_size, effect_size_type,
        ci_lower, ci_upper, n_target, n_rest.

    Raises
    ------
    AssertionError
        If row count != n_variables * (n_clusters + 1).
    """
    df = pipeline_result.df
    type_map = pipeline_result.type_map
    variables = list(type_map.keys())
    n_variables = len(variables)
    cluster_series = df[cluster_col]
    n_clusters = cluster_series.nunique()

    # Prepare argument tuples (picklable values, not DataFrames)
    args_list = []
    for var in variables:
        args_list.append((
            var,
            df[var].values.tolist(),
            cluster_series.values.tolist(),
            type_map[var],
            random_state,
        ))

    # Execute: serial or parallel
    if n_workers == 1:
        all_results = list(map(_test_variable_wrapper, args_list))
    else:
        with ProcessPoolExecutor(max_workers=n_workers) as executor:
            all_results = list(executor.map(_test_variable_wrapper, args_list))

    # Flatten list of lists into single list of dicts
    rows = []
    for result_list in all_results:
        rows.extend(result_list)

    # Shape assertion
    expected_rows = n_variables * (n_clusters + 1)
    if len(rows) != expected_rows:
        # Log which variables produced wrong row counts
        var_counts = {}
        for row in rows:
            v = row["variable"]
            var_counts[v] = var_counts.get(v, 0) + 1
        bad_vars = {v: c for v, c in var_counts.items() if c != n_clusters + 1}
        logger.error(
            "Row count mismatch: expected %d, got %d. "
            "Variables with wrong counts: %s",
            expected_rows, len(rows), bad_vars,
        )
        raise AssertionError(
            f"Expected {expected_rows} rows ({n_variables} vars * "
            f"{n_clusters + 1} comparisons), got {len(rows)}. "
            f"Bad variables: {bad_vars}"
        )

    result_df = pd.DataFrame(rows)
    result_df = result_df.sort_values(
        ["variable", "comparison_type", "cluster_label"],
    ).reset_index(drop=True)

    return result_df
