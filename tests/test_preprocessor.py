"""Tests for the two-pass preprocessing pipeline (DATA-05).

Tests cover:
- Two-pass logic: skewed -> winsorize -> re-check -> INT or z-score
- Ordinal and binary passthrough
- winsorize_mean_sd: mean-based bounds
- rank_based_int: normal quantile transform
- NaN handling throughout
- Transformation log contents
"""

import numpy as np
import pandas as pd
import pytest
from scipy.stats import skew as scipy_skew

from abcd_phewas.config import PipelineConfig
from abcd_phewas.preprocessor import (
    preprocess_continuous_column,
    preprocess_dataframe,
    rank_based_int,
    winsorize_mean_sd,
    z_score,
)
from abcd_phewas.type_detector import VarType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_config(**kwargs) -> PipelineConfig:
    defaults = dict(
        cluster_path="dummy.csv",
        phenotype_path="dummy.csv",
        skew_threshold=1.96,
        winsor_n_sd=3.0,
    )
    defaults.update(kwargs)
    return PipelineConfig(**defaults)


# ---------------------------------------------------------------------------
# winsorize_mean_sd
# ---------------------------------------------------------------------------

def test_winsorize_mean_sd_clips_outliers():
    """Values beyond mean ± 3 SD are clipped to those bounds."""
    rng = np.random.default_rng(0)
    arr = rng.normal(0, 1, size=200).astype(float)
    # Inject extreme outliers
    arr[0] = 100.0
    arr[1] = -100.0
    result = winsorize_mean_sd(arr, n_sd=3.0)
    mean = np.nanmean(arr)
    std = np.nanstd(arr, ddof=1)
    upper = mean + 3.0 * std
    lower = mean - 3.0 * std
    assert np.all(result[~np.isnan(result)] <= upper + 1e-9)
    assert np.all(result[~np.isnan(result)] >= lower - 1e-9)
    # Original outliers are clipped (both now equal to the clipping bound, not 100/-100)
    assert result[0] == pytest.approx(upper, abs=1e-9)
    assert result[1] == pytest.approx(lower, abs=1e-9)


def test_winsorize_mean_sd_preserves_nan():
    """NaN positions are unchanged after winsorization."""
    arr = np.array([1.0, np.nan, 3.0, np.nan, 5.0])
    result = winsorize_mean_sd(arr, n_sd=3.0)
    assert np.isnan(result[1])
    assert np.isnan(result[3])


def test_winsorize_mean_sd_preserves_inliers():
    """Values within bounds are unchanged."""
    arr = np.array([0.0, 1.0, 2.0, 3.0, 4.0], dtype=float)
    result = winsorize_mean_sd(arr, n_sd=10.0)
    np.testing.assert_allclose(result, arr)


# ---------------------------------------------------------------------------
# rank_based_int
# ---------------------------------------------------------------------------

def test_rank_based_int_normal_quantiles():
    """INT of 1..n produces normal quantile values matching scipy.stats.norm.ppf."""
    from scipy.stats import norm
    n = 20
    arr = np.arange(1.0, n + 1)  # already ranked
    result = rank_based_int(arr)
    expected = norm.ppf((np.arange(1.0, n + 1) - 0.5) / n)
    np.testing.assert_allclose(result, expected, atol=1e-10)


def test_rank_based_int_preserves_nan():
    """NaN positions are unchanged after INT."""
    arr = np.array([1.0, np.nan, 3.0, np.nan, 5.0])
    result = rank_based_int(arr)
    assert np.isnan(result[1])
    assert np.isnan(result[3])
    # Non-NaN values are finite
    assert np.all(np.isfinite(result[~np.isnan(result)]))


def test_rank_based_int_output_near_normal():
    """Large INT output has mean ~0 and values span expected quantile range."""
    rng = np.random.default_rng(7)
    arr = rng.exponential(2.0, size=1000).astype(float)
    result = rank_based_int(arr)
    assert abs(np.nanmean(result)) < 0.05
    assert np.nanmin(result) < -2.5
    assert np.nanmax(result) > 2.5


# ---------------------------------------------------------------------------
# z_score
# ---------------------------------------------------------------------------

def test_z_score_mean_zero_std_one():
    rng = np.random.default_rng(42)
    arr = rng.normal(50, 10, size=100).astype(float)
    result = z_score(arr)
    assert abs(np.nanmean(result)) < 1e-10
    assert abs(np.nanstd(result, ddof=1) - 1.0) < 1e-10


def test_z_score_constant_returns_zeros():
    """Constant array (std == 0) returns all zeros."""
    arr = np.full(10, 5.0)
    result = z_score(arr)
    np.testing.assert_array_equal(result, np.zeros(10))


def test_z_score_preserves_nan():
    arr = np.array([1.0, np.nan, 3.0])
    result = z_score(arr)
    assert np.isnan(result[1])


# ---------------------------------------------------------------------------
# preprocess_continuous_column (two-pass pipeline)
# ---------------------------------------------------------------------------

def test_two_pass_int():
    """Highly skewed array: winsorize -> still skewed -> INT applied.

    Uses lognormal distribution which stays highly skewed even after winsorization.
    """
    rng = np.random.default_rng(0)
    arr = np.exp(rng.normal(0, 2, size=500)).astype(float)
    # Confirm input is highly skewed
    initial_skew = abs(scipy_skew(arr[~np.isnan(arr)], bias=True))
    assert initial_skew > 1.96, f"Expected high skew, got {initial_skew}"

    result, log = preprocess_continuous_column(arr, "test_var", skew_threshold=1.96)

    assert log["variable"] == "test_var"
    assert abs(log["skew_initial"]) > 1.96
    assert log["winsorized"] is True
    assert log["int_applied"] is True
    assert log["z_scored"] is False
    # INT output should be approximately normal
    assert abs(np.nanmean(result)) < 0.1


def test_two_pass_zscore():
    """Moderately skewed array: winsorize -> no longer skewed -> z-scored.

    Construct array that is skewed before winsorization but not after.
    Uses a normal base array with a single extreme outlier (creates high skew
    that winsorization resolves by clipping that one value).
    """
    rng = np.random.default_rng(5)
    # Normal array + one extreme outlier to create initial high skew
    arr = rng.normal(0, 1, size=200).astype(float)
    arr[0] = 15.0  # single extreme outlier: causes high skew, resolved by winsorization
    initial_skew = scipy_skew(arr, bias=True)
    assert abs(initial_skew) > 1.96, f"Need initial |skew| > 1.96, got {initial_skew}"

    result, log = preprocess_continuous_column(arr, "mod_skew", skew_threshold=1.96)

    assert log["winsorized"] is True
    assert abs(log["skew_post_winsor"]) <= 1.96, (
        f"Expected |post-winsor skew| <= 1.96 after clipping outliers, "
        f"got {log['skew_post_winsor']}"
    )
    assert log["int_applied"] is False
    assert log["z_scored"] is True
    # z-scored output mean ~0
    assert abs(np.nanmean(result)) < 0.1


def test_non_skewed_zscore():
    """Non-skewed array: no winsorization -> z-scored directly."""
    rng = np.random.default_rng(10)
    arr = rng.normal(100, 15, size=200).astype(float)
    initial_skew = abs(scipy_skew(arr, bias=True))
    assert initial_skew <= 1.96, f"Expected non-skewed input, got |skew|={initial_skew}"

    result, log = preprocess_continuous_column(arr, "normal_var", skew_threshold=1.96)

    assert log["winsorized"] is False
    assert log["int_applied"] is False
    assert log["z_scored"] is True
    assert abs(np.nanmean(result)) < 0.1
    assert abs(np.nanstd(result, ddof=1) - 1.0) < 0.05


def test_transformation_log_keys():
    """Transformation log dict contains all required keys with correct types."""
    rng = np.random.default_rng(0)
    arr = rng.normal(0, 1, size=50).astype(float)
    _, log = preprocess_continuous_column(arr, "my_var")

    assert set(log.keys()) == {
        "variable",
        "skew_initial",
        "winsorized",
        "skew_post_winsor",
        "int_applied",
        "z_scored",
    }
    assert log["variable"] == "my_var"
    assert isinstance(log["skew_initial"], float)
    assert isinstance(log["winsorized"], bool)
    # skew_post_winsor is None if not winsorized, or float if winsorized
    assert log["skew_post_winsor"] is None or isinstance(log["skew_post_winsor"], float)
    assert isinstance(log["int_applied"], bool)
    assert isinstance(log["z_scored"], bool)


def test_nan_handling_preserves_positions():
    """NaN positions are preserved through the full two-pass pipeline."""
    rng = np.random.default_rng(3)
    # Highly skewed so we hit the INT branch
    arr = rng.exponential(2.0, size=100).astype(float)
    nan_mask = np.zeros(100, dtype=bool)
    nan_mask[[0, 10, 50, 99]] = True
    arr[nan_mask] = np.nan

    result, log = preprocess_continuous_column(arr, "nan_test")
    result_nan_mask = np.isnan(result)
    np.testing.assert_array_equal(result_nan_mask, nan_mask)


# ---------------------------------------------------------------------------
# preprocess_dataframe
# ---------------------------------------------------------------------------

def test_ordinal_passthrough():
    """Ordinal columns are not modified by preprocess_dataframe."""
    rng = np.random.default_rng(20)
    df = pd.DataFrame({
        "ordinal_col": rng.integers(1, 6, size=50).astype(float),
    })
    type_map = {"ordinal_col": VarType.ORDINAL}
    config = make_config()
    result_df, _ = preprocess_dataframe(df, type_map, ["ordinal_col"], config)
    pd.testing.assert_series_equal(result_df["ordinal_col"], df["ordinal_col"])


def test_binary_passthrough():
    """Binary columns are not modified by preprocess_dataframe."""
    rng = np.random.default_rng(21)
    df = pd.DataFrame({
        "binary_col": rng.integers(0, 2, size=50).astype(float),
    })
    type_map = {"binary_col": VarType.BINARY}
    config = make_config()
    result_df, _ = preprocess_dataframe(df, type_map, ["binary_col"], config)
    pd.testing.assert_series_equal(result_df["binary_col"], df["binary_col"])


def test_transformation_log_dataframe():
    """preprocess_dataframe returns a DataFrame with one row per continuous variable."""
    rng = np.random.default_rng(30)
    n = 100
    df = pd.DataFrame({
        "cont_a": rng.normal(0, 1, size=n),
        "cont_b": rng.exponential(2.0, size=n),
        "ordinal_x": rng.integers(1, 6, size=n).astype(float),
        "binary_y": rng.integers(0, 2, size=n).astype(float),
    })
    type_map = {
        "cont_a": VarType.CONTINUOUS,
        "cont_b": VarType.CONTINUOUS,
        "ordinal_x": VarType.ORDINAL,
        "binary_y": VarType.BINARY,
    }
    config = make_config()
    _, log_df = preprocess_dataframe(df, type_map, list(df.columns), config)

    assert isinstance(log_df, pd.DataFrame)
    # Only continuous columns in the log
    assert len(log_df) == 2
    assert set(log_df["variable"]) == {"cont_a", "cont_b"}
    # All required columns present
    required_cols = {
        "variable", "skew_initial", "winsorized", "skew_post_winsor",
        "int_applied", "z_scored",
    }
    assert required_cols.issubset(set(log_df.columns))


def test_preprocess_dataframe_continuous_modified():
    """Continuous columns ARE transformed (not equal to original) by preprocess_dataframe."""
    rng = np.random.default_rng(40)
    n = 100
    arr = rng.exponential(2.0, size=n)  # highly skewed
    df = pd.DataFrame({"cont_col": arr})
    type_map = {"cont_col": VarType.CONTINUOUS}
    config = make_config()
    result_df, _ = preprocess_dataframe(df, type_map, ["cont_col"], config)
    # Should be different from original
    assert not np.allclose(result_df["cont_col"].values, df["cont_col"].values)
