"""loader.py: CSV loading, merging, sentinel replacement, CRLI blocking, and missingness.

Pipeline order (must be respected):
1. load_and_merge       — inner join cluster + phenotype CSVs
2. apply_crli_blocklist — drop blocked columns immediately
3. replace_sentinels    — replace sentinel values with NaN (BEFORE type detection)
4. compute_missingness  — missingness rates (AFTER sentinel replacement)
5. has_enough_data      — per-group non-missing count check
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from loguru import logger

from abcd_phewas.config import PipelineConfig


def load_and_merge(config: PipelineConfig) -> pd.DataFrame:
    """Load cluster assignments and phenotype CSV, inner-merge on subject_col.

    Parameters
    ----------
    config:
        PipelineConfig with cluster_path, phenotype_path, subject_col, cluster_col.

    Returns
    -------
    pd.DataFrame
        Inner-merged DataFrame: one row per subject present in both files.
        Contains subject_col, cluster_col, and all phenotype columns.
    """
    clusters = pd.read_csv(
        config.cluster_path,
        usecols=[config.subject_col, config.cluster_col],
    )
    pheno = pd.read_csv(config.phenotype_path)

    merged = pd.merge(clusters, pheno, on=config.subject_col, how="inner")
    logger.info(
        f"Loaded {len(clusters)} cluster rows, {len(pheno)} pheno rows; "
        f"inner merge yielded {len(merged)} subjects"
    )
    return merged


def replace_sentinels(
    df: pd.DataFrame,
    sentinels: list[int | float],
    subject_col: str,
    cluster_col: str,
) -> pd.DataFrame:
    """Replace sentinel values with NaN on all phenotype columns.

    The subject_col and cluster_col are intentionally excluded from replacement
    because cluster labels may legitimately use values that overlap with sentinels.

    Parameters
    ----------
    df:
        Merged DataFrame (output of load_and_merge).
    sentinels:
        List of values to treat as missing (e.g. [-999, 777, 999]).
    subject_col:
        Name of the subject ID column — never modified.
    cluster_col:
        Name of the cluster label column — never modified.

    Returns
    -------
    pd.DataFrame
        DataFrame with sentinels replaced by np.nan in phenotype columns.
    """
    pheno_cols = get_pheno_cols(df, subject_col, cluster_col)
    df = df.copy()
    df[pheno_cols] = df[pheno_cols].replace(sentinels, np.nan)
    logger.debug(
        f"Replaced sentinels {sentinels} with NaN in {len(pheno_cols)} phenotype columns"
    )
    return df


def apply_crli_blocklist(
    df: pd.DataFrame,
    blocklist_path: str | None,
) -> pd.DataFrame:
    """Drop columns listed in the CRLI blocklist file.

    The blocklist is a plain-text file with one variable name per line.
    Column names not present in the DataFrame are silently ignored.

    Parameters
    ----------
    df:
        DataFrame (typically right after load_and_merge).
    blocklist_path:
        Path to the blocklist text file, or None to skip this step.

    Returns
    -------
    pd.DataFrame
        DataFrame with blocked columns removed.
    """
    if blocklist_path is None:
        return df

    with open(blocklist_path) as f:
        blocked = {line.strip() for line in f if line.strip()}

    cols_to_drop = [c for c in df.columns if c in blocked]
    if cols_to_drop:
        logger.info(f"CRLI blocklist: dropping {len(cols_to_drop)} columns: {cols_to_drop}")
    else:
        logger.debug("CRLI blocklist loaded; no matching columns to drop")

    return df.drop(columns=cols_to_drop)


def compute_missingness(
    df: pd.DataFrame,
    pheno_cols: list[str],
) -> pd.DataFrame:
    """Compute per-variable missingness rates.

    IMPORTANT: Call this AFTER replace_sentinels so sentinels are counted as missing.

    Parameters
    ----------
    df:
        DataFrame with sentinel values already replaced by NaN.
    pheno_cols:
        List of phenotype column names to compute missingness for.

    Returns
    -------
    pd.DataFrame
        DataFrame with columns: [variable, missingness_rate, n_missing, n_total].
        One row per phenotype variable.
    """
    n_total = len(df)
    n_missing = df[pheno_cols].isna().sum()
    missingness_rate = n_missing / n_total

    result = pd.DataFrame({
        "variable": pheno_cols,
        "missingness_rate": missingness_rate.values,
        "n_missing": n_missing.values.astype(int),
        "n_total": n_total,
    })
    return result.reset_index(drop=True)


def has_enough_data(
    series: pd.Series,
    groups: pd.Series,
    min_n: int = 10,
) -> bool:
    """Check whether every cluster group has at least min_n non-missing observations.

    Parameters
    ----------
    series:
        Phenotype variable (may contain NaN).
    groups:
        Cluster group labels aligned with series.
    min_n:
        Minimum number of non-missing observations required per group.

    Returns
    -------
    bool
        True if every group has >= min_n non-missing observations; False otherwise.
    """
    for group in groups.unique():
        mask = groups == group
        n_valid = series[mask].notna().sum()
        if n_valid < min_n:
            return False
    return True


def get_pheno_cols(
    df: pd.DataFrame,
    subject_col: str,
    cluster_col: str,
) -> list[str]:
    """Return all column names except subject_col and cluster_col.

    Parameters
    ----------
    df:
        Merged DataFrame.
    subject_col:
        Name of the subject ID column.
    cluster_col:
        Name of the cluster label column.

    Returns
    -------
    list[str]
        Sorted list of phenotype column names.
    """
    exclude = {subject_col, cluster_col}
    return [c for c in df.columns if c not in exclude]
