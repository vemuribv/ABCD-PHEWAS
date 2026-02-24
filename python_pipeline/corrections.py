"""Multiple-comparison corrections for PheWAS results.

Applies Benjamini-Hochberg FDR and Bonferroni corrections — one set of
corrections per cluster contrast — matching R's p.adjust() behaviour:

    p.adjust(Results$Pval, method = "fdr")
    p.adjust(Results$Pval, method = "bonferroni")
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from statsmodels.stats.multitest import multipletests

logger = logging.getLogger(__name__)


def apply_multiple_corrections(
    results_df: pd.DataFrame,
    pval_col: str = "pval",
    alpha: float = 0.05,
) -> pd.DataFrame:
    """Add FDR and Bonferroni adjusted p-values to a results DataFrame.

    Corrections are computed *within each cluster_contrast stratum* so that
    the number of tests in the multiple-comparison correction equals the
    number of phenotypes tested for that contrast — mirroring the R code's
    p.adjust() call on a single PRS's result table.

    Parameters
    ----------
    results_df : pd.DataFrame
        Must contain columns: ``pval_col`` and ``cluster_contrast``.
    pval_col : str
        Name of the raw p-value column.
    alpha : float
        Alpha level for multipletests (affects the ``reject`` output of
        multipletests but not the adjusted p-values themselves; kept for
        consistency with statsmodels API).

    Returns
    -------
    pd.DataFrame
        Input DataFrame with two new columns appended:
        ``pval_fdr`` (BH-adjusted) and ``pval_bonferroni``.
    """
    results_df = results_df.copy()
    results_df["pval_fdr"] = np.nan
    results_df["pval_bonferroni"] = np.nan

    if "cluster_contrast" not in results_df.columns:
        # No contrast column — apply corrections globally
        _apply_corrections_to_group(results_df, pval_col, alpha)
        return results_df

    for contrast, group_idx in results_df.groupby("cluster_contrast").groups.items():
        group = results_df.loc[group_idx]
        valid_mask = group[pval_col].notna()
        n_valid = valid_mask.sum()

        if n_valid == 0:
            continue

        pvals = group.loc[valid_mask, pval_col].values.astype(float)

        try:
            _, fdr_corrected, _, _ = multipletests(
                pvals, alpha=alpha, method="fdr_bh"
            )
            _, bonf_corrected, _, _ = multipletests(
                pvals, alpha=alpha, method="bonferroni"
            )
        except Exception as exc:
            logger.warning(
                "multipletests failed for contrast '%s': %s", contrast, exc
            )
            continue

        valid_positions = group.index[valid_mask]
        results_df.loc[valid_positions, "pval_fdr"] = fdr_corrected
        results_df.loc[valid_positions, "pval_bonferroni"] = bonf_corrected

        n_fdr_sig = (fdr_corrected < alpha).sum()
        n_bonf_sig = (bonf_corrected < alpha).sum()
        logger.info(
            "Contrast '%s': %d tests, %d FDR-sig, %d Bonferroni-sig",
            contrast, n_valid, n_fdr_sig, n_bonf_sig,
        )

    return results_df


def _apply_corrections_to_group(
    df: pd.DataFrame,
    pval_col: str,
    alpha: float,
) -> None:
    """Apply corrections in-place on a DataFrame without a contrast column."""
    valid_mask = df[pval_col].notna()
    pvals = df.loc[valid_mask, pval_col].values.astype(float)
    if len(pvals) == 0:
        return

    _, fdr_corrected, _, _ = multipletests(pvals, alpha=alpha, method="fdr_bh")
    _, bonf_corrected, _, _ = multipletests(pvals, alpha=alpha, method="bonferroni")

    df.loc[valid_mask, "pval_fdr"] = fdr_corrected
    df.loc[valid_mask, "pval_bonferroni"] = bonf_corrected
