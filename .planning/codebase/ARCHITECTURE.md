# Architecture

**Analysis Date:** 2025-03-02

## Pattern Overview

**Overall:** Layered pipeline architecture with clear separation between data loading, preprocessing, model fitting, statistical correction, and visualization stages.

**Key Characteristics:**
- **Linear orchestration**: Each stage depends on the output of the previous stage, managed centrally in `cli.py`
- **Parallel model fitting**: Individual phenotypes are distributed across worker processes using ProcessPoolExecutor (not threads, due to R/rpy2 constraints)
- **Configuration-driven**: All runtime parameters externalized to YAML with CLI overrides
- **Faithful R port**: Each layer closely mirrors the corresponding R code from `PheWAS Analyses Resub5.Rmd`
- **Checkpoint-based resumption**: Supports interrupted runs with phenotype-level granularity

## Layers

**Configuration & Orchestration (`config.py`, `cli.py`):**
- Purpose: Parse YAML config and CLI arguments; orchestrate the 10-stage pipeline
- Location: `python_pipeline/config.py`, `python_pipeline/cli.py`
- Contains: `PheWASConfig` dataclass, `build_parser()`, `run_pipeline()` orchestration
- Depends on: All downstream modules (preprocessing, models, corrections, domains, visualization)
- Used by: Entry point `main()` in `cli.py`
- Key flows: YAML loading → CLI override → validation → pipeline dispatch

**Data Loading & Preprocessing (`preprocessing.py`):**
- Purpose: Load Excel/CSV phenotype data, merge cluster labels, compute transformations (skewness detection, winsorizing, INT, z-scoring)
- Location: `python_pipeline/preprocessing.py`
- Contains: Functions for loading, filtering, cluster dummy creation, and the 5-step continuous phenotype transformation pipeline
- Depends on: pandas, numpy, scipy.stats
- Used by: `run_pipeline()` (Stage 1-4)
- Key functions:
  - `load_phenotype_data()` — reads Excel/CSV and assigns column types by positional range
  - `preprocess_continuous_phenotypes()` — applies skewness → winsorize → re-check → INT → zscore pipeline
  - `create_cluster_dummies()` — generates k-1 binary dummy variables for cluster contrasts
  - `filter_by_sex()` — stratifies to sex stratum

**Model Fitting (`models.py`):**
- Purpose: Define and fit linear mixed-effects models (via pymer4/R lme4) for each phenotype
- Location: `python_pipeline/models.py`
- Contains: Formula builders, continuous/binary model fitting functions, result extraction
- Depends on: pymer4, warnings suppression
- Used by: `parallel.py` (via `_worker()`) for parallel dispatch
- Key functions:
  - `build_formula()` — constructs lme4-style formula string
  - `fit_continuous_model()` — Lmer for continuous phenotypes
  - `fit_binary_model()` — Lmer with family='binomial' for binary phenotypes
  - `extract_cluster_results()` — extracts beta, SE, p-value per cluster contrast from pymer4 coefficients
  - `run_single_phenotype()` — unit of parallel work (returns k-1 ModelResult dicts per phenotype)

**Parallel Execution (`parallel.py`):**
- Purpose: Distribute phenotype fitting across worker processes with checkpoint support
- Location: `python_pipeline/parallel.py`
- Contains: ProcessPoolExecutor dispatch, checkpoint read/write, sequential fallback
- Depends on: concurrent.futures.ProcessPoolExecutor, pathlib
- Used by: `run_pipeline()` (Stage 6)
- Key functions:
  - `_load_checkpoint()` — loads set of completed phenotypes from checkpoint file
  - `_append_checkpoint()` — appends phenotype name after successful completion
  - `run_phewas_parallel()` — main dispatcher; returns flat list of ModelResults

**Statistical Corrections (`corrections.py`):**
- Purpose: Apply FDR (Benjamini-Hochberg) and Bonferroni corrections per cluster contrast
- Location: `python_pipeline/corrections.py`
- Contains: `apply_multiple_corrections()` with per-contrast stratification
- Depends on: statsmodels.stats.multitest
- Used by: `run_pipeline()` (Stage 7)
- Key behavior: Corrections computed *within each cluster_contrast* so the number of tests equals the number of phenotypes per contrast

**Domain Assignment (`domains.py`):**
- Purpose: Map phenotype names to domains via two-layer lookup (metadata CSV → regex patterns)
- Location: `python_pipeline/domains.py`
- Contains: YAML config loader, metadata CSV loader, domain assignment logic with year-suffix stripping
- Depends on: yaml, pandas, regex
- Used by: `run_pipeline()` (Stage 8) and `cli.py` (--plots-only mode)
- Key functions:
  - `load_domain_config()` — loads domain definitions from domains.yaml
  - `load_phenotype_metadata()` — loads variable → domain lookup from phenotype_metadata.csv
  - `assign_domain()` — applies two-layer lookup (exact metadata → suffix-stripped metadata → regex)
  - `assign_domains_to_results()` — adds domain, domain_color, phenotype_description columns to results

**Visualizations (`visualizations.py`):**
- Purpose: Generate Manhattan plots, forest plots, and stacked bar charts
- Location: `python_pipeline/visualizations.py`
- Contains: Three main plot functions with matplotlib backend set to 'Agg' for parallel safety
- Depends on: matplotlib, numpy, pandas, adjustText (optional)
- Used by: `run_pipeline()` (Stage 10) and `cli.py` (--plots-only mode)
- Key functions: `plot_manhattan()`, `plot_forest()`, `plot_stacked_bar()`

**Utilities (`utils.py`):**
- Purpose: Shared helpers for logging, file I/O, validation
- Location: `python_pipeline/utils.py`
- Contains: `setup_logging()`, `write_results()`, `make_output_suffix()`, `validate_required_columns()`
- Depends on: logging, pathlib, pandas
- Used by: Multiple modules for logging configuration and result writing

## Data Flow

**Full Pipeline (10 Stages):**

1. **Load & Preprocess Phenotype Data** (`preprocessing.load_phenotype_data`, `preprocessing.preprocess_continuous_phenotypes`)
   - Input: Excel/CSV phenotype file (columns assigned by positional range)
   - Transformations: Skewness detection → Winsorizing (mean ± 3σ) → INT (rank-based inverse normal) → Z-scoring
   - Output: DataFrame with continuous columns standardized and normalized

2. **Merge Cluster Labels** (`preprocessing.load_cluster_labels`, `preprocessing.merge_clusters`)
   - Input: Cluster CSV with (subject_id, cluster) pairs; phenotype DataFrame
   - Process: Inner join on subject_id
   - Output: DataFrame with cluster column added

3. **Sex Stratification** (`preprocessing.filter_by_sex`)
   - Input: Cluster-merged DataFrame; sex_stratum from config
   - Process: Filter to male/female/all based on sex_col values
   - Output: Filtered DataFrame

4. **Create Cluster Dummy Variables** (`preprocessing.create_cluster_dummies`)
   - Input: Stratified DataFrame; cluster column
   - Process: Generate k-1 binary dummy columns (reference cluster dropped)
   - Output: DataFrame with cluster_0, cluster_1, ... columns

5. **Identify Phenotype Sets** (in `cli.py`)
   - Input: Config column ranges; processed DataFrame
   - Process: Extract continuous and binary phenotype column names
   - Output: Lists of phenotype names; binary_set for model type selection

6. **Parallel GLMM Fitting** (`parallel.run_phewas_parallel`)
   - Input: Fully preprocessed DataFrame; phenotype_cols; cluster_dummy_cols; covariates
   - Process: For each phenotype:
     - Build lme4 formula with cluster dummies + covariates + random intercepts (site, family)
     - Fit Lmer (continuous) or Lmer + family='binomial' (binary)
     - Extract beta, SE, p-value for each cluster dummy
   - Output: Flat list of ModelResult dicts (k-1 rows per phenotype)

7. **Multiple-Comparison Corrections** (`corrections.apply_multiple_corrections`)
   - Input: Raw results DataFrame with pval column; stratified by cluster_contrast
   - Process: Within each contrast, apply FDR (Benjamini-Hochberg) and Bonferroni
   - Output: Results with pval_fdr and pval_bonferroni columns

8. **Domain Assignment** (`domains.assign_domains_to_results`)
   - Input: Corrected results DataFrame; domain YAML config
   - Process: For each phenotype, lookup via metadata CSV (exact → suffix-stripped) then regex patterns
   - Output: Results with domain, domain_color, phenotype_description columns

9. **Write Results CSVs** (`utils.write_results`)
   - Input: Combined results DataFrame; per-contrast subsets
   - Output: `phewas_results_<suffix>.csv` and `phewas_<contrast>_<suffix>.csv` files

10. **Generate Visualizations** (`visualizations.plot_manhattan`, `plot_forest`, `plot_stacked_bar`)
    - Input: Results DataFrame; domain specs
    - Output: PNG plots (Manhattan, forest, stacked bar) per contrast

**State Management:**

- **Data state**: Progressive enrichment of phenotype DataFrame through stages (columns added: cluster dummies, standardized phenotypes)
- **Results state**: Sparse ModelResult dicts accumulated from parallel workers, then merged into single DataFrame and progressively enriched (corrections → domains → written to disk)
- **Checkpoint state**: Persisted set of completed phenotype names (one per line in checkpoint file); read at start to skip already-processed phenotypes

## Key Abstractions

**PheWASConfig:**
- Purpose: Single source of truth for all runtime parameters (files, column ranges, covariates, thresholds, parallelism)
- Pattern: Dataclass with `from_yaml()` class method; can be overridden by CLI flags
- File: `python_pipeline/config.py`

**ModelResult:**
- Purpose: Type alias for dict[str, Any]; represents one model coefficient result (phenotype × cluster contrast)
- Fields: phenotype, cluster_contrast, beta, se, pval, converged, warning
- File: `python_pipeline/models.py`

**DomainSpec:**
- Purpose: Type alias for dict; represents one domain definition from YAML
- Fields: name, color, include_patterns (list of regexes), exclude_patterns (list of regexes)
- File: `python_pipeline/domains.py`

**Processing Pipeline Functions:**
- All transformation functions (winsorize, INT, zscore) are pure: take pd.Series, return pd.Series
- Cluster dummy creation returns (modified_df, dummy_col_names, reference_cluster) tuple
- Model fitting returns Optional[pymer4.Lmer] (None on failure, logged as debug)
- Result extraction returns list[ModelResult] (k-1 rows per phenotype)

## Entry Points

**CLI Entry Point:**
- Location: `python_pipeline/cli.py:main()`
- Invocation: `python -m python_pipeline.cli --config <yaml> --timepoint <timepoint> [--sex-stratum <stratum>] [--output-dir <dir>] ...`
- Responsibilities:
  - Parse arguments via `build_parser()`
  - Load config from YAML via `PheWASConfig.from_yaml()`
  - Apply CLI overrides (phenotype_file, cluster_file, output_dir, sex_stratum, n_workers, reference_cluster)
  - Route to either:
    - `run_pipeline()` (full run) after validation
    - Plots-only path (load results CSV, regenerate visualizations)
  - Setup logging via `utils.setup_logging()`

**Alternative Entry Point (Plots Only):**
- Invocation: `python -m python_pipeline.cli --config <yaml> --plots-only --results-csv <csv> --output-dir <dir>`
- Flow: Load results CSV → Assign domains (if missing) → Generate plots
- Use case: Regenerating plots without re-fitting models

## Error Handling

**Strategy:** Graceful degradation with detailed logging.

**Patterns:**

- **Preprocessing errors:** Logged at debug level; execution continues (e.g., missing columns filtered out, NaN values handled)
- **Model fitting failures:** Return NaN-filled ModelResult with converged=False and reason in warning field; logged at debug level
- **Parallel worker failures:** Caught in `as_completed()` loop; logged at error level; execution continues to process remaining phenotypes
- **Configuration errors:** Raised as ValueError with detailed message before pipeline starts (validated in `cfg.validate()` or CLI parsing)
- **I/O errors:** Checkpoint and result writing failures caught and logged at warning level; pipeline continues

**No user-facing exceptions** propagate from model fitting or corrections; all critical errors are caught and logged.

---

*Architecture analysis: 2025-03-02*
