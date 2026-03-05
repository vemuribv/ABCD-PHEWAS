"""Two-pass preprocessing pipeline for continuous variables (DATA-05).

Pipeline per continuous variable:
1. Compute initial skewness (scipy.stats.skew with bias=True).
2. If |skew| > skew_threshold: winsorize (mean-based, n_sd * std bounds).
3. Re-check skewness on winsorized array.
4. If still skewed (|skew| > skew_threshold): apply rank-based INT.
   Else: apply z-score.

Non-continuous variables (ORDINAL, BINARY, CATEGORICAL) pass through unmodified.

R reference: PheWAS Analyses Resub5.Rmd — winsorization uses DescTools::Winsorize
with minval/maxval (mean-based), INT uses qnorm((rank(x, na.last="keep")-0.5)/sum(!is.na(x))).
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from scipy.stats import norm, rankdata
from scipy.stats import skew as _scipy_skew_fn

from abcd_phewas.type_detector import VarType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


def _scipy_skew(arr: np.ndarray) -> float:
    """Compute skewness using scipy.stats.skew(bias=True) on non-NaN values.

    Returns 0.0 if fewer than 3 non-NaN values (undefined skewness).
    Matches R's default skewness estimator.
    """
    valid = arr[~np.isnan(arr)]
    if len(valid) < 3:
        return 0.0
    return float(_scipy_skew_fn(valid, bias=True))


def winsorize_mean_sd(arr: np.ndarray, n_sd: float = 3.0) -> np.ndarray:
    """Mean-based winsorization: clip values to [mean - n_sd*std, mean + n_sd*std].

    Parameters
    ----------
    arr:
        Input array (may contain NaN).
    n_sd:
        Number of standard deviations for clipping bounds. Default: 3.0.

    Returns
    -------
    np.ndarray
        Array with outliers clipped. NaN positions preserved.

    Notes
    -----
    Matches R's DescTools::Winsorize(x, minval=mean-3*sd, maxval=mean+3*sd).
    Uses ddof=1 to match R's sd() function.
    """
    result = arr.copy().astype(float)
    valid = arr[~np.isnan(arr)]
    if len(valid) < 2:
        return result
    mean = float(np.nanmean(arr))
    std = float(np.nanstd(arr, ddof=1))
    if std == 0:
        return result
    lower = mean - n_sd * std
    upper = mean + n_sd * std
    mask = ~np.isnan(result)
    result[mask] = np.clip(result[mask], lower, upper)
    return result


def rank_based_int(arr: np.ndarray) -> np.ndarray:
    """Rank-based inverse normal transformation (INT).

    For each non-NaN value, compute the average rank, then transform to
    normal quantiles via:  norm.ppf((rank - 0.5) / n)

    Parameters
    ----------
    arr:
        Input array (may contain NaN).

    Returns
    -------
    np.ndarray
        INT-transformed array. NaN positions preserved.

    Notes
    -----
    Matches R:  qnorm((rank(x, na.last="keep") - 0.5) / sum(!is.na(x)))
    Uses average ranks (ties.method="average") matching R's default rank().
    """
    result = np.full_like(arr, np.nan, dtype=float)
    nan_mask = np.isnan(arr)
    valid_indices = np.where(~nan_mask)[0]
    valid_vals = arr[valid_indices]
    n = len(valid_vals)
    if n == 0:
        return result
    ranks = rankdata(valid_vals, method="average")  # average ties, matches R default
    transformed = norm.ppf((ranks - 0.5) / n)
    result[valid_indices] = transformed
    return result


def z_score(arr: np.ndarray) -> np.ndarray:
    """Z-score standardization: (arr - mean) / std with ddof=1.

    Parameters
    ----------
    arr:
        Input array (may contain NaN).

    Returns
    -------
    np.ndarray
        Standardized array. NaN positions preserved.
        If std == 0 (constant array), returns zeros.

    Notes
    -----
    Uses ddof=1 to match R's scale() function.
    """
    result = np.full_like(arr, np.nan, dtype=float)
    nan_mask = np.isnan(arr)
    valid_indices = np.where(~nan_mask)[0]
    if len(valid_indices) == 0:
        return result
    mean = float(np.nanmean(arr))
    std = float(np.nanstd(arr, ddof=1))
    if std == 0:
        result[valid_indices] = 0.0
    else:
        result[valid_indices] = (arr[valid_indices] - mean) / std
    return result


# ---------------------------------------------------------------------------
# Two-pass pipeline for a single continuous variable
# ---------------------------------------------------------------------------


def preprocess_continuous_column(
    arr: np.ndarray,
    col_name: str,
    skew_threshold: float = 1.96,
    winsor_n_sd: float = 3.0,
) -> tuple[np.ndarray, dict]:
    """Two-pass preprocessing for one continuous variable.

    Pass 1 — assess initial skewness.
    Pass 2 — if skewed: winsorize, re-assess; apply INT or z-score.
             if not skewed: z-score directly.

    Parameters
    ----------
    arr:
        1-D NumPy array for the column (float, may contain NaN).
    col_name:
        Variable name (for the transformation log).
    skew_threshold:
        Absolute skewness threshold for triggering winsorization and INT.
    winsor_n_sd:
        SD bounds for mean-based winsorization.

    Returns
    -------
    tuple[np.ndarray, dict]
        (transformed_array, log_dict)

    Log dict keys:
        variable, skew_initial, winsorized, skew_post_winsor, int_applied, z_scored
    """
    arr = np.asarray(arr, dtype=float)
    skew_initial = _scipy_skew(arr)

    log: dict = {
        "variable": col_name,
        "skew_initial": skew_initial,
        "winsorized": False,
        "skew_post_winsor": None,
        "int_applied": False,
        "z_scored": False,
    }

    if abs(skew_initial) > skew_threshold:
        # Pass 1: winsorize
        arr = winsorize_mean_sd(arr, n_sd=winsor_n_sd)
        log["winsorized"] = True
        skew_post = _scipy_skew(arr)
        log["skew_post_winsor"] = skew_post

        if abs(skew_post) > skew_threshold:
            # Still skewed: apply INT
            arr = rank_based_int(arr)
            log["int_applied"] = True
            logger.debug(
                "Column %s: INT applied (skew_initial=%.3f, skew_post_winsor=%.3f)",
                col_name,
                skew_initial,
                skew_post,
            )
        else:
            # Winsorization resolved skew: z-score
            arr = z_score(arr)
            log["z_scored"] = True
            logger.debug(
                "Column %s: z-scored after winsorization (skew_initial=%.3f -> %.3f)",
                col_name,
                skew_initial,
                skew_post,
            )
    else:
        # Not skewed: z-score directly
        arr = z_score(arr)
        log["z_scored"] = True
        logger.debug(
            "Column %s: z-scored directly (skew_initial=%.3f)",
            col_name,
            skew_initial,
        )

    return arr, log


# ---------------------------------------------------------------------------
# DataFrame-level preprocessing
# ---------------------------------------------------------------------------


def preprocess_dataframe(
    df: pd.DataFrame,
    type_map: dict[str, VarType],
    pheno_cols: list[str],
    config,  # PipelineConfig — avoid circular import, use duck typing
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Preprocess all continuous columns; leave ORDINAL/BINARY/CATEGORICAL unchanged.

    Parameters
    ----------
    df:
        Full merged DataFrame (subjects x variables).
    type_map:
        Mapping of column name -> VarType for all phenotype columns.
    pheno_cols:
        List of phenotype column names to consider. Others are ignored.
    config:
        PipelineConfig instance (reads skew_threshold and winsor_n_sd).

    Returns
    -------
    tuple[pd.DataFrame, pd.DataFrame]
        (modified_df, transformation_log_df)
        - modified_df: same columns, continuous ones are transformed in-place
        - transformation_log_df: one row per continuous variable with log columns
    """
    result_df = df.copy()
    logs = []

    for col in pheno_cols:
        if col not in type_map:
            continue
        vtype = type_map[col]
        if vtype != VarType.CONTINUOUS:
            # Ordinal, binary, categorical: pass through unchanged
            continue

        arr = result_df[col].to_numpy(dtype=float)
        transformed, log = preprocess_continuous_column(
            arr,
            col_name=col,
            skew_threshold=config.skew_threshold,
            winsor_n_sd=config.winsor_n_sd,
        )
        result_df[col] = transformed
        logs.append(log)

    log_df = pd.DataFrame(logs) if logs else pd.DataFrame(
        columns=[
            "variable", "skew_initial", "winsorized", "skew_post_winsor",
            "int_applied", "z_scored",
        ]
    )
    return result_df, log_df
