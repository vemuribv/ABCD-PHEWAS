"""Results CSV assembly and writing.

Merges domain labels, missingness rates, and multiple comparison corrections
into a publication-ready 18-column results CSV sorted by raw p-value.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from abcd_phewas.correction import apply_corrections

# Required output column order (18 columns)
RESULT_COLUMNS = [
    "variable", "domain", "comparison_type", "cluster_label",
    "test_used", "statistic", "p_value", "effect_size",
    "effect_size_type", "ci_lower", "ci_upper", "n_target", "n_rest",
    "missingness_rate", "fdr_q_global", "bonf_p_global",
    "fdr_q_domain", "bonf_p_domain",
]


def assemble_results(
    raw_df: pd.DataFrame,
    domain_map: dict[str, tuple[str, str]],
    missingness: pd.DataFrame,
) -> pd.DataFrame:
    """Assemble final results DataFrame with corrections and metadata.

    Parameters
    ----------
    raw_df:
        12-column DataFrame from run_all_tests (variable, comparison_type,
        cluster_label, test_used, statistic, p_value, effect_size,
        effect_size_type, ci_lower, ci_upper, n_target, n_rest).
    domain_map:
        {variable_name: (domain_name, hex_color)} from PipelineResult.
    missingness:
        DataFrame with columns [variable, missingness_rate, ...] from
        PipelineResult.missingness.

    Returns
    -------
    pd.DataFrame
        18-column DataFrame sorted by p_value ascending.
    """
    df = raw_df.copy()

    # Add domain column from domain_map (default "Other/Unclassified")
    df["domain"] = df["variable"].map(
        lambda v: domain_map.get(v, ("Other/Unclassified", "#AAAAAA"))[0]
    )

    # Merge missingness_rate from missingness DataFrame
    miss_lookup = missingness.set_index("variable")["missingness_rate"].to_dict()
    df["missingness_rate"] = df["variable"].map(miss_lookup)

    # Apply FDR-BH and Bonferroni corrections (adds 4 columns)
    df = apply_corrections(df)

    # Sort by raw p_value ascending (most significant first)
    df = df.sort_values("p_value", ascending=True, na_position="last").reset_index(drop=True)

    # Reorder to the 18-column spec
    df = df[RESULT_COLUMNS]

    return df


def write_results_csv(df: pd.DataFrame, output_path: str) -> None:
    """Write results DataFrame to CSV.

    Parameters
    ----------
    df:
        Assembled results DataFrame (18 columns).
    output_path:
        File path for the output CSV.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
