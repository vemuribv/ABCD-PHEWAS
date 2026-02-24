"""Data loading and preprocessing for the ABCD Cluster-Based PheWAS Pipeline.

Faithfully ports the R preprocessing pipeline from PheWAS Analyses Resub5.Rmd:
  1. Load Excel/CSV phenotype file and assign column dtypes by positional range
  2. Compute skewness (matches psych::describe skew with bias=False)
  3. Winsorize skewed continuous columns at mean ± n_sd * SD
  4. Inverse-normal-transform (INT) columns still skewed after winsorizing
  5. Z-score all continuous columns (ddof=1 to match R's scale())
  6. Load cluster labels CSV and merge with phenotype data
  7. Sex filtering and k-1 cluster dummy creation
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import norm

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Data loading
# --------------------------------------------------------------------------- #

def load_phenotype_data(
    filepath: str,
    continuous_col_range: tuple[int, int],
    binary_col_range: tuple[int, int],
    subject_id_col: str = "subjectkey",
) -> pd.DataFrame:
    """Load an ABCD phenotype file and assign column dtypes by positional range.

    Mirrors R:
        PheWAS_baseline[, c(1:4, 20, 671:1291)] <- lapply(..., as.factor)
        PheWAS_baseline[, c(5:19, 21:670)]       <- lapply(..., as.numeric)

    Parameters
    ----------
    filepath : str
        Path to an .xlsx or .csv file.
    continuous_col_range : tuple[int, int]
        (first_col, last_col) — 0-based, inclusive, for continuous phenotypes.
    binary_col_range : tuple[int, int]
        (first_col, last_col) — 0-based, inclusive, for binary/categorical phenotypes.
    subject_id_col : str
        Name of the subject identifier column.

    Returns
    -------
    pd.DataFrame
        Loaded data with continuous columns as float64 and binary columns as
        pandas Categorical (object dtype).
    """
    fp = Path(filepath)
    if fp.suffix in (".xlsx", ".xls"):
        df = pd.read_excel(filepath, dtype=str)
    else:
        df = pd.read_csv(filepath, dtype=str, low_memory=False)

    logger.info("Loaded %d rows × %d cols from %s", len(df), len(df.columns), filepath)

    # Replace empty strings and literal "NA" with np.nan
    df.replace({"": np.nan, "NA": np.nan, "N/A": np.nan}, inplace=True)

    cont_start, cont_end = continuous_col_range
    bin_start, bin_end = binary_col_range

    # Convert continuous columns to float
    cont_cols = df.columns[cont_start: cont_end + 1].tolist()
    for col in cont_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Binary/categorical columns stay as object (string categories)
    # No explicit conversion needed — they remain as strings/NaN

    logger.info(
        "Column types assigned: %d continuous [%d:%d], %d binary [%d:%d]",
        len(cont_cols), cont_start, cont_end,
        len(df.columns[bin_start: bin_end + 1]), bin_start, bin_end,
    )

    return df


# --------------------------------------------------------------------------- #
# Skewness
# --------------------------------------------------------------------------- #

def compute_skewness(df: pd.DataFrame, col_names: list[str]) -> pd.Series:
    """Compute skewness for each column.

    Uses scipy.stats.skew with bias=False to match R's psych::describe skew.

    Parameters
    ----------
    df : pd.DataFrame
    col_names : list[str]

    Returns
    -------
    pd.Series indexed by column name.
    """
    skews = {}
    for col in col_names:
        vals = df[col].dropna().values
        if len(vals) < 3:
            skews[col] = np.nan
        else:
            skews[col] = float(stats.skew(vals, bias=False))
    return pd.Series(skews)


def identify_skewed_columns(
    skewness: pd.Series,
    threshold: float = 1.96,
) -> list[str]:
    """Return column names where |skewness| > threshold.

    Mirrors R: skewed <- descbase[descbase$skew > 1.96 | descbase$skew < -1.96, ]
    """
    return list(skewness[skewness.abs() > threshold].index)


# --------------------------------------------------------------------------- #
# Transformations
# --------------------------------------------------------------------------- #

def winsorize_column(series: pd.Series, n_sd: float = 3.0) -> pd.Series:
    """Winsorize to mean ± n_sd * SD, ignoring NaN.

    Mirrors R: Winsorize(x, minval=mean(x, na.rm=T) - 3*sd(x, na.rm=T),
                                maxval=mean(x, na.rm=T) + 3*sd(x, na.rm=T))
    """
    mu = series.mean(skipna=True)
    sigma = series.std(skipna=True, ddof=1)
    if sigma == 0 or np.isnan(sigma):
        return series.copy()
    lower = mu - n_sd * sigma
    upper = mu + n_sd * sigma
    return series.clip(lower=lower, upper=upper)


def inverse_normal_transform(series: pd.Series) -> pd.Series:
    """Rank-based inverse normal transformation (INT).

    Exact port of R:
        qnorm((rank(x, na.last="keep") - 0.5) / sum(!is.na(x)))

    NaN positions remain NaN after transformation.
    """
    valid_mask = series.notna()
    n_valid = valid_mask.sum()
    if n_valid < 2:
        return series.copy().astype(float)

    # rank with average ties, keeping NaN positions as NaN
    ranked = series[valid_mask].rank(method="average")
    transformed = norm.ppf((ranked - 0.5) / n_valid)

    result = series.copy().astype(float)
    result[valid_mask] = transformed
    return result


def zscore_column(series: pd.Series) -> pd.Series:
    """Z-score standardisation using ddof=1 to match R's scale().

    NaN positions remain NaN.
    """
    mu = series.mean(skipna=True)
    sigma = series.std(skipna=True, ddof=1)
    if sigma == 0 or np.isnan(sigma):
        return series - mu  # return zero-centred if no variance
    return (series - mu) / sigma


# --------------------------------------------------------------------------- #
# Full preprocessing pipeline
# --------------------------------------------------------------------------- #

def preprocess_continuous_phenotypes(
    df: pd.DataFrame,
    continuous_cols: list[str],
    skew_threshold: float = 1.96,
    winsorize_sd: float = 3.0,
) -> pd.DataFrame:
    """Apply the full R preprocessing pipeline to continuous phenotypes.

    Pipeline (mirrors PheWAS Analyses Resub5.Rmd lines ~84–265):
    1. Compute skewness on all continuous columns.
    2. Winsorize highly skewed columns (|skew| > skew_threshold).
    3. Re-check skewness after winsorizing.
    4. Apply INT to columns still highly skewed.
    5. Z-score all continuous columns.

    Parameters
    ----------
    df : pd.DataFrame
    continuous_cols : list[str]
        Column names of continuous phenotypes to transform.
    skew_threshold : float
        |skew| threshold for flagging a column as highly skewed (default 1.96).
    winsorize_sd : float
        Number of SDs for winsorizing bounds (default 3.0).

    Returns
    -------
    pd.DataFrame with continuous columns transformed in-place (copy returned).
    """
    result = df.copy()

    # Step 1: initial skewness
    skewness = compute_skewness(result, continuous_cols)
    skewed_cols = identify_skewed_columns(skewness, skew_threshold)
    logger.info(
        "%d / %d continuous columns initially skewed (|skew| > %.2f)",
        len(skewed_cols), len(continuous_cols), skew_threshold,
    )

    # Step 2: winsorize
    for col in skewed_cols:
        result[col] = winsorize_column(result[col], winsorize_sd)

    # Step 3: re-check skewness after winsorizing
    skewness_post = compute_skewness(result, skewed_cols)
    still_skewed = identify_skewed_columns(skewness_post, skew_threshold)
    logger.info(
        "%d columns still skewed after winsorizing — applying INT",
        len(still_skewed),
    )

    # Step 4: INT for still-skewed
    for col in still_skewed:
        result[col] = inverse_normal_transform(result[col])

    # Step 5: z-score all continuous columns
    for col in continuous_cols:
        result[col] = zscore_column(result[col])

    logger.info("Continuous preprocessing complete.")
    return result


# --------------------------------------------------------------------------- #
# Cluster labels
# --------------------------------------------------------------------------- #

def load_cluster_labels(
    filepath: str,
    subject_id_col: str = "subjectkey",
    cluster_col: str = "cluster",
) -> pd.DataFrame:
    """Load a CSV with subject IDs and cluster assignments.

    Parameters
    ----------
    filepath : str
        Path to the cluster labels CSV.
    subject_id_col : str
        Column containing the subject identifier (must match phenotype data).
    cluster_col : str
        Column containing the cluster label (e.g., "0", "1", "2").

    Returns
    -------
    pd.DataFrame with exactly [subject_id_col, cluster_col].
    """
    df = pd.read_csv(filepath, dtype={subject_id_col: str, cluster_col: str})
    missing = [c for c in (subject_id_col, cluster_col) if c not in df.columns]
    if missing:
        raise ValueError(
            f"Cluster file is missing required columns: {missing}. "
            f"Available columns: {list(df.columns)}"
        )
    df = df[[subject_id_col, cluster_col]].copy()
    df[cluster_col] = df[cluster_col].astype(str).str.strip()
    logger.info(
        "Loaded %d cluster labels from %s (clusters: %s)",
        len(df), filepath, sorted(df[cluster_col].unique()),
    )
    return df


def merge_clusters(
    phenotype_df: pd.DataFrame,
    cluster_df: pd.DataFrame,
    subject_id_col: str = "subjectkey",
) -> pd.DataFrame:
    """Inner-join phenotype data with cluster labels on subject_id_col.

    Logs subject count before and after to flag unexpected drops.
    """
    n_before = len(phenotype_df)
    merged = phenotype_df.merge(cluster_df, on=subject_id_col, how="inner")
    n_after = len(merged)
    if n_after < n_before:
        logger.warning(
            "Merge dropped %d subjects (phenotype n=%d → merged n=%d). "
            "Check that subject IDs match between files.",
            n_before - n_after, n_before, n_after,
        )
    else:
        logger.info(
            "Merged cluster labels: n=%d subjects retained.", n_after
        )
    return merged


# --------------------------------------------------------------------------- #
# Sex stratification
# --------------------------------------------------------------------------- #

def filter_by_sex(
    df: pd.DataFrame,
    sex_col: str,
    sex_stratum: str,
    male_value: str = "1",
    female_value: str = "2",
) -> pd.DataFrame:
    """Filter DataFrame to a single sex stratum.

    Parameters
    ----------
    df : pd.DataFrame
    sex_col : str
    sex_stratum : str
        One of "all", "male", "female".
    male_value : str
        Value in sex_col indicating male subjects.
    female_value : str
        Value in sex_col indicating female subjects.

    Returns
    -------
    Filtered (or unfiltered) copy of df.
    """
    if sex_stratum == "all":
        logger.info("Sex stratum: all (n=%d)", len(df))
        return df.copy()

    sex_series = df[sex_col].astype(str).str.strip()
    if sex_stratum == "male":
        filtered = df[sex_series == male_value].copy()
    elif sex_stratum == "female":
        filtered = df[sex_series == female_value].copy()
    else:
        raise ValueError(
            f"sex_stratum must be 'all', 'male', or 'female'. Got: '{sex_stratum}'"
        )

    logger.info("Sex stratum: %s → n=%d", sex_stratum, len(filtered))
    return filtered


# --------------------------------------------------------------------------- #
# Cluster dummy coding
# --------------------------------------------------------------------------- #

def create_cluster_dummies(
    df: pd.DataFrame,
    cluster_col: str = "cluster",
    reference_cluster: Optional[str] = None,
) -> tuple[pd.DataFrame, list[str], str]:
    """Create k-1 binary dummy variables for cluster membership.

    The reference cluster is dropped (it becomes the baseline / intercept).
    Dummy columns are named ``cluster_<label>`` (e.g., ``cluster_2``).

    Parameters
    ----------
    df : pd.DataFrame
        Must contain cluster_col.
    cluster_col : str
    reference_cluster : Optional[str]
        If None, the first label in sorted order is used (deterministic).

    Returns
    -------
    df_with_dummies : pd.DataFrame
        Original df plus k-1 dummy columns.
    dummy_col_names : list[str]
        Names of the dummy columns in sorted order.
    reference_cluster : str
        The cluster label used as the reference / baseline.
    """
    cluster_labels = sorted(df[cluster_col].astype(str).unique().tolist())
    if reference_cluster is None:
        reference_cluster = cluster_labels[0]
    reference_cluster = str(reference_cluster)

    if reference_cluster not in cluster_labels:
        raise ValueError(
            f"reference_cluster '{reference_cluster}' not found in cluster labels: "
            f"{cluster_labels}"
        )

    non_ref = [c for c in cluster_labels if c != reference_cluster]
    df = df.copy()
    dummy_col_names: list[str] = []
    for label in non_ref:
        col_name = f"cluster_{label}"
        df[col_name] = (df[cluster_col].astype(str) == label).astype(int)
        dummy_col_names.append(col_name)

    logger.info(
        "Cluster dummies created: reference='%s', contrasts=%s",
        reference_cluster, dummy_col_names,
    )
    return df, dummy_col_names, reference_cluster
