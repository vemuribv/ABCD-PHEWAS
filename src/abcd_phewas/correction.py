"""Multiple comparison correction for PheWAS results.

Applies FDR Benjamini-Hochberg and Bonferroni corrections at two levels:
1. Global: separately for omnibus and one_vs_rest test families.
2. Within-domain: separately for each (comparison_type, domain) pair.

Pure function: DataFrame in, augmented DataFrame out (copy, not in-place).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from statsmodels.stats.multitest import multipletests

# Correction column names added to the output DataFrame
CORRECTION_COLS = ["fdr_q_global", "bonf_p_global", "fdr_q_domain", "bonf_p_domain"]


def apply_corrections(df: pd.DataFrame) -> pd.DataFrame:
    """Apply FDR-BH and Bonferroni corrections to p-values.

    Corrections are applied separately for omnibus and one_vs_rest families
    (global level), and further within each (comparison_type, domain) pair
    (domain level).

    Parameters
    ----------
    df:
        DataFrame with at least columns: comparison_type, p_value, domain.
        Rows with NaN p_value are excluded from correction and remain NaN.

    Returns
    -------
    pd.DataFrame
        Copy of input with 4 new columns: fdr_q_global, bonf_p_global,
        fdr_q_domain, bonf_p_domain.
    """
    df = df.copy()

    # Initialize correction columns as NaN
    for col in CORRECTION_COLS:
        df[col] = np.nan

    # --- Global corrections: omnibus and OVR as separate families ---
    for comp_type in ["omnibus", "one_vs_rest"]:
        mask = df["comparison_type"] == comp_type
        if mask.sum() == 0:
            continue

        pvals = df.loc[mask, "p_value"].values
        valid = ~np.isnan(pvals)

        if valid.sum() == 0:
            continue

        _, fdr_q, _, _ = multipletests(pvals[valid], method="fdr_bh")
        _, bonf_p, _, _ = multipletests(pvals[valid], method="bonferroni")

        # Map corrected values back to original indices (only valid rows)
        idx = df.index[mask][valid]
        df.loc[idx, "fdr_q_global"] = fdr_q
        df.loc[idx, "bonf_p_global"] = bonf_p

    # --- Within-domain corrections: per (comparison_type, domain) pair ---
    for comp_type in ["omnibus", "one_vs_rest"]:
        for domain in df["domain"].unique():
            mask = (df["comparison_type"] == comp_type) & (df["domain"] == domain)
            if mask.sum() == 0:
                continue

            pvals = df.loc[mask, "p_value"].values
            valid = ~np.isnan(pvals)

            # Need at least 2 valid p-values for meaningful correction
            if valid.sum() < 2:
                continue

            _, fdr_q, _, _ = multipletests(pvals[valid], method="fdr_bh")
            _, bonf_p, _, _ = multipletests(pvals[valid], method="bonferroni")

            idx = df.index[mask][valid]
            df.loc[idx, "fdr_q_domain"] = fdr_q
            df.loc[idx, "bonf_p_domain"] = bonf_p

    return df
