"""Pipeline orchestrator: wires all stages into an end-to-end pipeline.

Stage order (enforced — must not be reordered):
1. load_and_merge          — load and inner-join cluster + phenotype CSVs
2. replace_sentinels       — replace -999/777/999 with NaN BEFORE type detection
3. apply_crli_blocklist    — drop CRLI-blocked columns
4. get_pheno_cols          — identify phenotype columns
5. compute_missingness     — missingness rates (after sentinels replaced)
6. filter_low_n_vars       — remove variables with < min_n per group
7. detect_all_types        — classify each variable (BINARY/ORDINAL/CATEGORICAL/CONTINUOUS)
8. apply_overrides         — apply user-supplied type overrides from CSV
9. preprocess_dataframe    — two-pass preprocessing for CONTINUOUS columns
10. load_domain_config     — load regex domain patterns from YAML
11. assign_all_domains     — assign each variable to a domain
12. log summary and return PipelineResult

The sentinel replacement step (2) MUST precede type detection (7) to ensure
that variables with -999 sentinels are correctly classified (not contaminated by
non-data values inflating unique counts). Tests enforce this ordering.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

from abcd_phewas.config import PipelineConfig
from abcd_phewas.domain_mapper import assign_all_domains, load_domain_config
from abcd_phewas.loader import (
    apply_crli_blocklist,
    compute_missingness,
    get_pheno_cols,
    has_enough_data,
    load_and_merge,
    replace_sentinels,
)
from abcd_phewas.preprocessor import preprocess_dataframe
from abcd_phewas.type_detector import VarType, apply_overrides, detect_all_types

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Complete output from run_pipeline.

    Attributes
    ----------
    df:
        Merged, sentinel-cleaned, preprocessed DataFrame.
        One row per subject, columns include subject_col, cluster_col, and
        all non-skipped, non-blocked phenotype variables.
    type_map:
        {variable_name: VarType} for all variables that passed the min-n filter.
    domain_map:
        {variable_name: (domain_name, hex_color)} for all non-skipped variables.
    transformation_log:
        DataFrame with one row per continuous variable documenting the
        preprocessing path taken (winsorized, int_applied, z_scored, etc.).
    missingness:
        DataFrame with missingness rates for all phenotype columns (computed
        before min-n filtering — includes skipped variables).
    skipped_vars:
        List of variable names excluded due to insufficient data per group
        (< min_n_per_group non-missing observations in at least one cluster).
    unclassified_vars:
        List of variable names that did not match any domain regex pattern
        (assigned to Other/Unclassified). Subset of domain_map keys.
    """

    df: pd.DataFrame
    type_map: dict[str, VarType]
    domain_map: dict[str, tuple[str, str]]
    transformation_log: pd.DataFrame
    missingness: pd.DataFrame
    skipped_vars: list[str] = field(default_factory=list)
    unclassified_vars: list[str] = field(default_factory=list)


def run_pipeline(config: PipelineConfig) -> PipelineResult:
    """Execute the full ABCD PheWAS preprocessing pipeline.

    Parameters
    ----------
    config:
        PipelineConfig dataclass with all pipeline parameters.

    Returns
    -------
    PipelineResult
        Complete pipeline outputs including preprocessed DataFrame, type map,
        domain map, transformation log, missingness rates, and skipped/
        unclassified variable lists.
    """
    # --- Stage 1: Load and merge ---
    logger.info("Stage 1: Loading and merging cluster + phenotype CSVs")
    df = load_and_merge(config)

    # --- Stage 2: Replace sentinels ---
    # CRITICAL: sentinel replacement MUST precede type detection.
    # Sentinel values like -999 inflate unique counts and corrupt type detection.
    logger.info("Stage 2: Replacing sentinel values with NaN")
    df = replace_sentinels(df, config.sentinels, config.subject_col, config.cluster_col)

    # --- Stage 3: Apply CRLI blocklist ---
    logger.info("Stage 3: Applying CRLI blocklist")
    df = apply_crli_blocklist(df, config.blocklist_path)

    # --- Stage 4: Identify phenotype columns ---
    pheno_cols = get_pheno_cols(df, config.subject_col, config.cluster_col)
    logger.info("Stage 4: Identified %d phenotype columns", len(pheno_cols))

    # --- Stage 5: Compute missingness ---
    # Done on all pheno_cols (including those that will be skipped by min-n filter)
    # so users can see why variables were dropped.
    logger.info("Stage 5: Computing missingness rates")
    missingness = compute_missingness(df, pheno_cols)

    # --- Stage 6: Filter low-n variables ---
    logger.info("Stage 6: Filtering low-n variables (min_n_per_group=%d)", config.min_n_per_group)
    skipped_vars: list[str] = []
    active_cols: list[str] = []
    for col in pheno_cols:
        if has_enough_data(df[col], df[config.cluster_col], config.min_n_per_group):
            active_cols.append(col)
        else:
            skipped_vars.append(col)
            logger.debug("Skipping '%s': insufficient data per cluster group", col)

    logger.info(
        "Skipped %d variables (insufficient data); %d remaining",
        len(skipped_vars),
        len(active_cols),
    )

    # --- Stage 7: Detect variable types ---
    # Runs AFTER sentinel replacement (Stage 2) — correct type detection
    # requires sentinels to already be NaN.
    logger.info("Stage 7: Detecting variable types for %d columns", len(active_cols))
    type_map = detect_all_types(df, active_cols)

    # --- Stage 8: Apply user overrides ---
    logger.info("Stage 8: Applying type overrides")
    type_map = apply_overrides(type_map, config.override_path)

    # --- Stage 9: Preprocess continuous columns ---
    logger.info("Stage 9: Preprocessing continuous columns (two-pass)")
    df, transformation_log = preprocess_dataframe(df, type_map, active_cols, config)

    # --- Stage 10: Load domain config ---
    logger.info("Stage 10: Loading domain config from %s", config.domain_config_path)
    domain_config = load_domain_config(config.domain_config_path)

    # --- Stage 11: Assign domains ---
    logger.info("Stage 11: Assigning domains to %d variables", len(active_cols))
    domain_map, unclassified_vars = assign_all_domains(active_cols, domain_config)

    # --- Stage 12: Log summary ---
    type_counts = {vt: sum(1 for v in type_map.values() if v == vt) for vt in VarType}
    logger.info(
        "Pipeline complete. Variables: %d binary, %d ordinal, %d categorical, %d continuous | "
        "%d skipped | %d unclassified",
        type_counts[VarType.BINARY],
        type_counts[VarType.ORDINAL],
        type_counts[VarType.CATEGORICAL],
        type_counts[VarType.CONTINUOUS],
        len(skipped_vars),
        len(unclassified_vars),
    )

    return PipelineResult(
        df=df,
        type_map=type_map,
        domain_map=domain_map,
        transformation_log=transformation_log,
        missingness=missingness,
        skipped_vars=skipped_vars,
        unclassified_vars=unclassified_vars,
    )
