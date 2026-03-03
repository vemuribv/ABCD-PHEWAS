# Technology Stack

**Analysis Date:** 2026-03-02

## Languages

**Primary:**
- Python 3.10+ - Core pipeline implementation, GLMM fitting, preprocessing, visualization

## Runtime

**Environment:**
- Python 3.10 or later (specified in `pyproject.toml` as `requires-python = ">=3.10"`)

**Package Manager:**
- pip (via setuptools)
- Lockfile: Not tracked (dependencies specified in `pyproject.toml`)

## Frameworks

**Core Pipeline:**
- pymer4 0.8.x - Linear and generalized mixed-effects model fitting via R's lme4 (wraps Lmer/Glmer)
- pandas 2.0+ - Data loading, manipulation, preprocessing
- numpy 1.24+ - Numerical operations, array handling
- scipy 1.10+ - Statistical functions (skewness, inverse-normal transform)

**Testing:**
- pytest - Test framework and runner
- scipy.stats - Statistical validation in tests

**Data Processing:**
- statsmodels 0.14+ - Multiple testing corrections (multipletests)
- openpyxl 3.1+ - Excel file parsing (.xlsx support)
- PyYAML 6.0+ - YAML configuration loading

**Visualization:**
- matplotlib 3.7+ - Static plot generation (Manhattan, forest, stacked bar)
- adjustText 0.8+ - Label positioning for overlapping text in plots

## Key Dependencies

**Critical:**
- pymer4 0.8.x - REQUIRED: Bridges Python and R's lme4 for GLMM fitting
  - Requires R and R package `lme4` installed on system
  - Uses rpy2 internally for R-Python interface (NOT thread-safe)
  - Lazy-imported in `python_pipeline/models.py` to allow testing without R

**Infrastructure:**
- pandas 2.0+ - Data pipeline backbone (loading, merging, filtering, transformations)
- numpy 1.24+ - Numerical computations (Z-scoring, winsorizing, skewness)
- scipy 1.10+ - Inverse-normal transform (norm.ppf), skewness calculation (stats.skew)
- statsmodels 0.14+ - Multiple testing corrections (multipletests for BH, Bonferroni)
- openpyxl 3.1+ - Excel file I/O (.xlsx phenotype files)
- PyYAML 6.0+ - Configuration management (domain.yaml, example_run.yaml)
- matplotlib 3.7+ - Publication-quality plots (domain-colored Manhattan, forest plots)
- adjustText 0.8+ - Non-overlapping label placement in plots

## Configuration

**Environment:**
- Configuration via YAML files: `python_pipeline/configs/example_run.yaml` (can be customized)
- All config values are dataclass fields in `python_pipeline/config.py` (PheWASConfig)
- Supports both file-based and CLI-flag overrides (CLI flags take precedence)

**Build:**
- `pyproject.toml` - Single source of truth for dependencies, package metadata, scripts
- Entry point: `abcd-phewas` command (defined in `[project.scripts]`)

**Required Configuration Files:**
- `python_pipeline/configs/domains.yaml` - Phenotype-to-domain mapping via regex (bundled)
- `python_pipeline/configs/phenotype_metadata.csv` - Authoritative domain lookup (bundled)
- User must supply:
  - Phenotype data file (.xlsx or .csv with 1200+ phenotype columns)
  - Cluster labels CSV (subject_id, cluster columns)
  - Output directory path

## Platform Requirements

**Development:**
- Python 3.10+ installed
- R runtime + lme4 package (required by pymer4)
  - Note: pymer4 uses rpy2 which bridges Python ↔ R via C interface
  - R is NOT thread-safe; parallel processing uses ProcessPoolExecutor (separate processes, not threads)

**Production:**
- Same as development (R + lme4 must be available on cluster/server)
- Typical deployment: HPC cluster with parallel job submission
- I/O bound: reads large Excel files (1200+ phenotypes × 5000+ subjects)
- CPU bound: GLMM fitting via bobyqa optimizer (parallelized across phenotypes)

## Parallelism

**Concurrency Model:**
- `concurrent.futures.ProcessPoolExecutor` (NOT ThreadPoolExecutor)
- Reason: pymer4 calls R via rpy2; R's C internals are not thread-safe
- Each worker process has its own isolated R session
- Configurable via `n_workers` (default 4, recommend CPU cores - 1)
- Location: `python_pipeline/parallel.py`

**Resumable Execution:**
- Checkpoint file support: text file listing completed phenotypes (one per line)
- On start: reads checkpoint and skips already-completed phenotypes
- After each phenotype: appends its name to checkpoint file
- Location: `python_pipeline/parallel.py` (_load_checkpoint, _append_checkpoint)

---

*Stack analysis: 2026-03-02*
