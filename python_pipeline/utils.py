"""Shared utilities for the ABCD Cluster-Based PheWAS Pipeline."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pandas as pd


def setup_logging(level: str = "INFO") -> None:
    """Configure the root logger with timestamp, level, and module name.

    Parameters
    ----------
    level : str
        One of "DEBUG", "INFO", "WARNING", "ERROR".
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,  # override any existing handlers
    )


def write_results(
    results_df: pd.DataFrame,
    output_path: str,
    sep: str = ",",
) -> None:
    """Write a results DataFrame to CSV, creating parent directories as needed.

    Parameters
    ----------
    results_df : pd.DataFrame
    output_path : str
        Destination file path.
    sep : str
        Delimiter (default comma).
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    results_df.to_csv(output_path, index=False, sep=sep)
    logging.getLogger(__name__).info("Wrote %d rows to %s", len(results_df), output_path)


def make_output_suffix(timepoint: str, sex_stratum: str, reference_cluster: str) -> str:
    """Build a consistent filename suffix from analysis parameters.

    Example: "baseline_female_ref0"
    """
    ref_clean = str(reference_cluster).replace(" ", "_")
    return f"{timepoint}_{sex_stratum}_ref{ref_clean}"


def validate_required_columns(
    df: pd.DataFrame,
    required: list[str],
    context: str = "",
) -> None:
    """Raise ValueError if any required column is missing from df.

    Parameters
    ----------
    df : pd.DataFrame
    required : list[str]
    context : str
        Short description for the error message (e.g., "phenotype data").
    """
    missing = [c for c in required if c not in df.columns]
    if missing:
        label = f" ({context})" if context else ""
        raise ValueError(
            f"DataFrame{label} is missing required columns: {missing}.\n"
            f"Available columns (first 30): {list(df.columns[:30])}"
        )
