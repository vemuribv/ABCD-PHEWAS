"""Command-line interface and pipeline orchestration.

Usage examples:

  # Full pipeline run
  python -m python_pipeline.cli \\
      --config python_pipeline/configs/example_run.yaml \\
      --timepoint baseline \\
      --sex-stratum female \\
      --phenotype-file data/FINAL_PHEWAS_baseline_n5556.xlsx \\
      --cluster-file data/cluster_labels.csv \\
      --output-dir results/baseline_female/ \\
      --n-workers 8

  # Resume an interrupted run
  python -m python_pipeline.cli \\
      --config python_pipeline/configs/example_run.yaml \\
      --timepoint baseline \\
      --sex-stratum female \\
      --checkpoint-file results/baseline_female/checkpoint.txt

  # Re-generate plots from existing results CSV
  python -m python_pipeline.cli \\
      --config python_pipeline/configs/example_run.yaml \\
      --timepoint baseline \\
      --plots-only \\
      --results-csv results/baseline_female/phewas_results_baseline_female_ref0.csv
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

from .config import PheWASConfig
from .corrections import apply_multiple_corrections
from .domains import assign_domains_to_results, get_domain_order, load_domain_config
from .models import run_single_phenotype
from .parallel import run_phewas_parallel
from .preprocessing import (
    create_cluster_dummies,
    filter_by_sex,
    load_cluster_labels,
    load_phenotype_data,
    merge_clusters,
    preprocess_continuous_phenotypes,
)
from .utils import make_output_suffix, setup_logging, validate_required_columns, write_results
from .visualizations import plot_forest, plot_manhattan, plot_stacked_bar

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Argument parser
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="abcd-phewas",
        description="Cluster-based PheWAS pipeline for ABCD puberty trajectory data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Config
    p.add_argument(
        "--config", required=True,
        help="Path to YAML config file (required).",
    )

    # Overrides for key config fields
    p.add_argument("--phenotype-file", default=None,
                   help="Override phenotype_file from config.")
    p.add_argument("--cluster-file", default=None,
                   help="Override cluster_file from config.")
    p.add_argument("--output-dir", default=None,
                   help="Override output_dir from config.")
    p.add_argument(
        "--sex-stratum", choices=["all", "male", "female"], default=None,
        help="Sex stratum to analyse ('all', 'male', or 'female').",
    )
    p.add_argument("--n-workers", type=int, default=None,
                   help="Number of parallel worker processes.")
    p.add_argument("--reference-cluster", default=None,
                   help="Cluster label to use as the reference (intercept).")

    # Analysis metadata
    p.add_argument(
        "--timepoint",
        choices=["baseline", "followup"],
        required=True,
        help="Timepoint label: 'baseline' or 'followup'. Used in output filenames.",
    )

    # Optional modes
    p.add_argument(
        "--skip-preprocess", action="store_true",
        help=(
            "Load a pre-saved transformed CSV (skips skew/winsor/INT/zscore). "
            "Requires phenotype_file to point to the already-transformed CSV."
        ),
    )
    p.add_argument(
        "--checkpoint-file", default=None,
        help="Plain-text checkpoint file for resumable runs.",
    )
    p.add_argument(
        "--plots-only", action="store_true",
        help="Skip model fitting; generate plots from an existing results CSV.",
    )
    p.add_argument(
        "--results-csv", default=None,
        help="For --plots-only: path to existing combined results CSV.",
    )

    # Logging
    p.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO).",
    )

    return p


# --------------------------------------------------------------------------- #
# Main pipeline
# --------------------------------------------------------------------------- #

def run_pipeline(cfg: PheWASConfig, args: argparse.Namespace) -> None:
    """Orchestrate the full PheWAS pipeline.

    Stages:
    1.  Load & preprocess phenotype data
    2.  Load & merge cluster labels
    3.  Filter by sex stratum
    4.  Create k-1 cluster dummy variables
    5.  Identify continuous vs. binary phenotype columns
    6.  Run GLMM in parallel for all phenotypes
    7.  Apply FDR + Bonferroni corrections (per contrast)
    8.  Assign domain labels
    9.  Write results CSVs
    10. Generate visualisations
    """
    out = Path(cfg.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Stage 1: Load + preprocess phenotype data
    # ------------------------------------------------------------------ #
    logger.info("=== Stage 1: Load + preprocess phenotype data ===")
    if args.skip_preprocess:
        logger.info("--skip-preprocess: loading pre-transformed CSV.")
        df = pd.read_csv(cfg.phenotype_file, low_memory=False)
    else:
        df = load_phenotype_data(
            cfg.phenotype_file,
            continuous_col_range=tuple(cfg.continuous_col_range),
            binary_col_range=tuple(cfg.binary_col_range),
            subject_id_col=cfg.subject_id_col,
        )

    all_cols = list(df.columns)
    cont_start, cont_end = cfg.continuous_col_range
    bin_start, bin_end = cfg.binary_col_range
    cont_cols = all_cols[cont_start: cont_end + 1]
    bin_cols = all_cols[bin_start: bin_end + 1]

    # Filter to columns that actually exist (guards against off-by-one ranges)
    cont_cols = [c for c in cont_cols if c in df.columns]
    bin_cols = [c for c in bin_cols if c in df.columns]

    if not args.skip_preprocess:
        df = preprocess_continuous_phenotypes(
            df,
            continuous_cols=cont_cols,
            skew_threshold=cfg.skew_threshold,
            winsorize_sd=cfg.winsorize_sd,
        )

    # ------------------------------------------------------------------ #
    # Stage 2: Load + merge cluster labels
    # ------------------------------------------------------------------ #
    logger.info("=== Stage 2: Merge cluster labels ===")
    cluster_df = load_cluster_labels(
        cfg.cluster_file,
        subject_id_col=cfg.subject_id_col,
        cluster_col=cfg.cluster_col,
    )
    df = merge_clusters(df, cluster_df, subject_id_col=cfg.subject_id_col)

    # ------------------------------------------------------------------ #
    # Stage 3: Sex stratification
    # ------------------------------------------------------------------ #
    logger.info("=== Stage 3: Sex stratification (%s) ===", cfg.sex_stratum)
    df = filter_by_sex(
        df,
        sex_col=cfg.sex_col,
        sex_stratum=cfg.sex_stratum,
        male_value=cfg.sex_col_male_value,
        female_value=cfg.sex_col_female_value,
    )

    # ------------------------------------------------------------------ #
    # Stage 4: Cluster dummy variables
    # ------------------------------------------------------------------ #
    logger.info("=== Stage 4: Create cluster dummy variables ===")
    df, dummy_cols, reference_cluster = create_cluster_dummies(
        df,
        cluster_col=cfg.cluster_col,
        reference_cluster=cfg.reference_cluster,
    )

    # ------------------------------------------------------------------ #
    # Stage 5: Identify phenotype sets
    # ------------------------------------------------------------------ #
    logger.info("=== Stage 5: Identify phenotype columns ===")
    phenotype_cols = cont_cols + bin_cols
    binary_set = set(bin_cols)

    logger.info(
        "%d continuous + %d binary = %d total phenotypes",
        len(cont_cols), len(bin_cols), len(phenotype_cols),
    )

    run_kwargs = dict(
        cluster_dummy_cols=dummy_cols,
        covariates=cfg.covariates,
        site_id_col=cfg.site_id_col,
        family_id_col=cfg.family_id_col,
        include_family_re=True,
        optimizer=cfg.optimizer,
        max_iterations=cfg.max_iterations,
    )

    # ------------------------------------------------------------------ #
    # Stage 6: Parallel GLMM fitting
    # ------------------------------------------------------------------ #
    logger.info(
        "=== Stage 6: Parallel GLMM (%d phenotypes × %d contrasts, %d workers) ===",
        len(phenotype_cols), len(dummy_cols), cfg.n_workers,
    )
    raw_results = run_phewas_parallel(
        df=df,
        phenotype_cols=phenotype_cols,
        binary_cols=binary_set,
        run_single_fn=run_single_phenotype,
        run_single_kwargs=run_kwargs,
        n_workers=cfg.n_workers,
        checkpoint_file=args.checkpoint_file,
    )
    results_df = pd.DataFrame(raw_results)

    if results_df.empty:
        logger.warning("No results produced — exiting.")
        return

    # Add metadata columns
    results_df["timepoint"] = args.timepoint
    results_df["sex_stratum"] = cfg.sex_stratum
    results_df["reference_cluster"] = reference_cluster

    # ------------------------------------------------------------------ #
    # Stage 7: Multiple-comparison corrections
    # ------------------------------------------------------------------ #
    logger.info("=== Stage 7: Multiple-comparison corrections ===")
    results_df = apply_multiple_corrections(results_df)

    # ------------------------------------------------------------------ #
    # Stage 8: Domain assignment
    # ------------------------------------------------------------------ #
    logger.info("=== Stage 8: Domain assignment ===")
    domain_specs = load_domain_config(cfg.domain_config_file)
    results_df = assign_domains_to_results(results_df, domain_specs)

    # ------------------------------------------------------------------ #
    # Stage 9: Write results CSVs
    # ------------------------------------------------------------------ #
    logger.info("=== Stage 9: Write results ===")
    suffix = make_output_suffix(args.timepoint, cfg.sex_stratum, reference_cluster)

    combined_path = str(out / f"phewas_results_{suffix}.csv")
    write_results(results_df, combined_path)

    for contrast in dummy_cols:
        sub = results_df[results_df["cluster_contrast"] == contrast]
        write_results(sub, str(out / f"phewas_{contrast}_{suffix}.csv"))

    # ------------------------------------------------------------------ #
    # Stage 10: Visualisations
    # ------------------------------------------------------------------ #
    _generate_plots(results_df, dummy_cols, domain_specs, cfg, args, suffix, out)

    logger.info("=== Pipeline complete. Outputs in %s ===", cfg.output_dir)


def _generate_plots(
    results_df: pd.DataFrame,
    dummy_cols: list[str],
    domain_specs: list[dict],
    cfg: PheWASConfig,
    args: argparse.Namespace,
    suffix: str,
    out: Path,
) -> None:
    """Generate all visualisations (Stage 10)."""
    logger.info("=== Stage 10: Visualisations ===")

    for contrast in dummy_cols:
        sub = results_df[results_df["cluster_contrast"] == contrast]
        if sub.empty:
            continue

        plot_manhattan(
            sub,
            cluster_contrast=contrast,
            domain_specs=domain_specs,
            output_path=str(out / f"manhattan_{contrast}_{suffix}.png"),
            title=f"Cluster PheWAS ({args.timepoint})",
            subtitle=f"Sex stratum: {cfg.sex_stratum}  |  Reference cluster: {sub['reference_cluster'].iloc[0]}",
        )

        plot_forest(
            sub,
            cluster_contrast=contrast,
            output_path=str(out / f"forest_{contrast}_{suffix}.png"),
        )

    plot_stacked_bar(
        results_df,
        domain_specs=domain_specs,
        output_path=str(out / f"stacked_bar_{suffix}.png"),
    )


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(args.log_level)

    # Load config
    cfg = PheWASConfig.from_yaml(args.config)

    # Apply CLI overrides
    if args.phenotype_file:
        cfg.phenotype_file = args.phenotype_file
    if args.cluster_file:
        cfg.cluster_file = args.cluster_file
    if args.output_dir:
        cfg.output_dir = args.output_dir
    if args.sex_stratum:
        cfg.sex_stratum = args.sex_stratum
    if args.n_workers is not None:
        cfg.n_workers = args.n_workers
    if args.reference_cluster:
        cfg.reference_cluster = args.reference_cluster

    if args.plots_only:
        if not args.results_csv:
            logger.error("--plots-only requires --results-csv.")
            sys.exit(1)
        if not cfg.output_dir:
            logger.error("--plots-only requires output_dir to be set.")
            sys.exit(1)

        logger.info("--plots-only mode: loading %s", args.results_csv)
        results_df = pd.read_csv(args.results_csv)
        domain_specs = load_domain_config(cfg.domain_config_file)

        # Re-add domain assignment if missing
        if "domain" not in results_df.columns:
            results_df = assign_domains_to_results(results_df, domain_specs)

        dummy_cols = sorted(
            results_df["cluster_contrast"].dropna().unique().tolist()
        )
        suffix = Path(args.results_csv).stem
        out = Path(cfg.output_dir)
        out.mkdir(parents=True, exist_ok=True)

        # Recover reference cluster from results if available
        ref_col = results_df.get("reference_cluster", pd.Series(["unknown"]))
        reference_cluster = str(ref_col.iloc[0]) if len(ref_col) else "unknown"

        _generate_plots(results_df, dummy_cols, domain_specs, cfg, args, suffix, out)
    else:
        cfg.validate()

        # Auto-remove sex covariate in sex-stratified analyses (constant column
        # causes singular design matrix)
        if cfg.sex_stratum != "all" and cfg.sex_col in cfg.covariates:
            cfg.covariates = [c for c in cfg.covariates if c != cfg.sex_col]
            logger.info(
                "Removed '%s' from covariates (sex-stratified analysis).",
                cfg.sex_col,
            )

        run_pipeline(cfg, args)


if __name__ == "__main__":
    main()
