# Codebase Structure

**Analysis Date:** 2025-03-02

## Directory Layout

```
python_pipeline/
├── __init__.py                 # Package version; minimal init
├── cli.py                      # Command-line interface and pipeline orchestration
├── config.py                   # PheWASConfig dataclass for runtime parameters
├── preprocessing.py            # Data loading, transformations, cluster setup
├── models.py                   # GLMM fitting via pymer4 (R/lme4 wrapper)
├── parallel.py                 # ProcessPoolExecutor dispatch with checkpoints
├── corrections.py              # FDR and Bonferroni corrections (per-contrast)
├── domains.py                  # Domain assignment (metadata + regex patterns)
├── visualizations.py           # Manhattan, forest, and stacked bar plots
├── utils.py                    # Logging, file I/O, validation helpers
├── configs/
│   ├── domains.yaml            # Domain definitions (name, color, regex patterns)
│   ├── phenotype_metadata.csv  # Variable → domain lookup (from Paul 2024)
│   ├── example_run.yaml        # Example configuration file (template)
│   ├── 1-s2.0-S088915912500145X-mmc1.xlsx         # Source: Genome-wide association meta-analysis
│   ├── 44220_2024_313_MOESM3_ESM.xlsx             # Source: Paul 2024 supplement
│   ├── domain_crosscheck.csv   # Domain consistency check output
│   └── phenotype_metadata.csv  # Built by build_phenotype_metadata.py
├── scripts/
│   ├── __init__.py
│   └── build_phenotype_metadata.py  # Script to generate phenotype_metadata.csv from Excel sources
└── tests/
    ├── __init__.py
    ├── test_preprocessing.py    # Tests for preprocessing transformations (54 total)
    ├── test_corrections.py      # Tests for FDR/Bonferroni corrections
    ├── test_domains.py          # Tests for domain assignment logic
    └── __pycache__/             # Compiled test cache
```

## Directory Purposes

**python_pipeline/ (root):**
- Purpose: Package container for all PheWAS pipeline code
- Contains: Core pipeline modules + config + tests
- Entry point: `python -m python_pipeline.cli --config <yaml> ...`

**python_pipeline/configs/:**
- Purpose: Configuration files and metadata sources
- Contains:
  - YAML config files (domains.yaml, example_run.yaml)
  - CSV metadata lookup (phenotype_metadata.csv)
  - Excel source files for domain/variable mapping
- Key files:
  - `domains.yaml` — authoritative domain definitions (8 domains + Unclassified)
  - `phenotype_metadata.csv` — variable → domain mapping (covers ~1200 phenotypes)
  - `example_run.yaml` — template config file with all parameters documented
- Generated/Not Committed: domain_crosscheck.csv (validation output)

**python_pipeline/scripts/:**
- Purpose: Standalone utilities for pipeline setup (not part of main pipeline)
- Contains: `build_phenotype_metadata.py` — generates phenotype_metadata.csv from Excel sources
- When to run: Before first pipeline run (if metadata doesn't exist)

**python_pipeline/tests/:**
- Purpose: Unit tests validating preprocessing and statistical correctness
- Contains:
  - `test_preprocessing.py` — 40+ tests for transformations (winsorize, INT, zscore, skewness, dummies, sex filter)
  - `test_corrections.py` — tests for FDR/Bonferroni per-contrast corrections
  - `test_domains.py` — tests for domain assignment (metadata lookup, regex patterns, year-suffix stripping)
- Coverage: Does NOT require pymer4/R installed (models are mocked in tests)
- Run: `python -m pytest python_pipeline/tests/ -v` (all 54 tests pass)

## Key File Locations

**Entry Points:**
- `python_pipeline/cli.py:main()` — Command-line entry point; calls `run_pipeline()` or plots-only path
- `python_pipeline/cli.py:run_pipeline()` — Orchestrates 10-stage pipeline

**Configuration:**
- `python_pipeline/config.py:PheWASConfig` — Dataclass holding all runtime parameters
- `python_pipeline/configs/example_run.yaml` — Template config file
- `python_pipeline/configs/domains.yaml` — Domain regex patterns and colors
- `python_pipeline/configs/phenotype_metadata.csv` — Variable → domain authoritative lookup

**Core Logic:**
- `python_pipeline/preprocessing.py` — Load, transform, cluster setup (5-stage transformation)
- `python_pipeline/models.py` — Formula building, Lmer/GLMER fitting, result extraction
- `python_pipeline/parallel.py` — ProcessPoolExecutor dispatch and checkpoint resumption
- `python_pipeline/corrections.py` — FDR and Bonferroni per-contrast corrections
- `python_pipeline/domains.py` — Domain lookup (metadata + regex)
- `python_pipeline/visualizations.py` — Manhattan, forest, stacked bar plots
- `python_pipeline/utils.py` — Logging, file I/O, validation

**Testing:**
- `python_pipeline/tests/test_preprocessing.py` — 40+ transformation tests
- `python_pipeline/tests/test_corrections.py` — Multiple-comparison correction tests
- `python_pipeline/tests/test_domains.py` — Domain assignment tests

## Naming Conventions

**Files:**
- Core modules: `lowercase_with_underscores.py` (e.g., `preprocessing.py`, `models.py`)
- Tests: `test_<module>.py` (e.g., `test_preprocessing.py`)
- Config files: `descriptive_name.yaml` or `descriptive_name.csv` (e.g., `example_run.yaml`, `phenotype_metadata.csv`)
- Scripts: `action_noun.py` (e.g., `build_phenotype_metadata.py`)

**Directories:**
- Package container: `python_pipeline/`
- Config directory: `configs/`
- Test directory: `tests/`
- Scripts directory: `scripts/`

**Functions:**
- Main pipeline entry: `main()`, `run_pipeline()`
- Data loaders: `load_<thing>()` (e.g., `load_phenotype_data()`)
- Processors: `<action>_<noun>()` (e.g., `winsorize_column()`, `create_cluster_dummies()`)
- Helpers starting with `_`: Private/internal functions (e.g., `_failed_result()`, `_worker()`)
- Builders: `build_<thing>()` (e.g., `build_formula()`, `build_parser()`)

**Variables:**
- DataFrames: `df`, `results_df`, `phenotype_df`, `cluster_df`
- Series: `series`, `skewness`, `ranked`
- Lists: `phenotype_cols`, `cont_cols`, `bin_cols`, `dummy_cols`
- Sets: `binary_set`, `binary_cols` (when passed as set)
- Config objects: `cfg` (PheWASConfig instance)
- Paths: Use pathlib.Path; variable names: `output_path`, `filepath`

## Where to Add New Code

**New Feature (e.g., new analysis metric):**
- Primary code: `python_pipeline/<new_module>.py`
- Tests: `python_pipeline/tests/test_<new_module>.py`
- Integration: Import and call from `cli.py:run_pipeline()` (insert at appropriate stage)
- Configuration: Add new fields to `config.py:PheWASConfig` if user-configurable

**New Visualization Type:**
- Implementation: Add function to `python_pipeline/visualizations.py`
- Pattern: Match signature of existing plot functions (results_df, domain_specs, output_path, etc.)
- Matplotlib backend: Already set to 'Agg' at module load; safe for parallel workers
- Call from: `cli.py:_generate_plots()` (Stage 10)

**New Preprocessing Transformation:**
- Implementation: Add function to `python_pipeline/preprocessing.py`
- Pattern: Pure function on pd.Series; returns pd.Series (same shape as input, NaN positions preserved)
- Integration: Call from `preprocess_continuous_phenotypes()` pipeline
- Tests: Add test cases in `python_pipeline/tests/test_preprocessing.py` verifying against R equivalents

**New Domain or Domain Pattern:**
- Edit: `python_pipeline/configs/domains.yaml`
- Format: Add entry to `domain_order` list with name, color (hex), include_patterns (list of regexes), exclude_patterns (list)
- Rebuild metadata: Run `python -m python_pipeline.scripts.build_phenotype_metadata` if variables need domain reassignment

**Configuration File Changes:**
- For new runtime parameters: Add field to `config.py:PheWASConfig` with default; update `config.validate()` if validation needed
- For new input file requirements: Add field to PheWASConfig and document in `example_run.yaml`
- CLI flag mapping: Update `cli.py:build_parser()` to add `--flag` argument; add override in `main()` (see sex_stratum, n_workers pattern)

**Test for New Module:**
- Location: `python_pipeline/tests/test_<module>.py`
- Fixtures: Use small synthetic DataFrames/Series (not dependent on pymer4 or R)
- Run: `python -m pytest python_pipeline/tests/test_<module>.py -v`
- Mocking: If calling R-dependent code (models.py), mock `pymer4.models.Lmer` (already done in test suite)

## Special Directories

**python_pipeline/configs/:**
- Purpose: Configuration sources (not code)
- Generated: `phenotype_metadata.csv` is generated by `scripts/build_phenotype_metadata.py`; should be committed after generation
- Not Committed: `domain_crosscheck.csv` (transient validation output)

**python_pipeline/tests/:**
- Purpose: Unit tests
- Generated: `__pycache__/` (compiled bytecode, in .gitignore)
- Committed: All `.py` test files
- Independence: Tests can run WITHOUT pymer4/R installed (models mocked)

**python_pipeline/scripts/:**
- Purpose: One-off setup utilities
- Generated: Outputs of scripts (e.g., phenotype_metadata.csv)
- Not part of main pipeline: Run manually before first pipeline execution

## Import Patterns

**Within python_pipeline:**
- Absolute imports: `from python_pipeline.preprocessing import load_phenotype_data`
- Relative imports (within tests): `from python_pipeline.preprocessing import ...`
- Mock imports (tests): Mock `pymer4.models.Lmer` to avoid R dependency

**External dependencies:**
- Data: pandas, numpy, scipy (scientific stack)
- Statistics: statsmodels (multipletests for corrections)
- Configuration: yaml, pyyaml
- Visualization: matplotlib, numpy, adjustText (optional, with graceful fallback)
- Models: pymer4 (lazy import in models.py; warns if unavailable)
- CLI: argparse (stdlib)
- Logging: logging (stdlib), pathlib (stdlib)

## Configuration as Code

**YAML Config Files:**
- `python_pipeline/configs/example_run.yaml` — Comprehensive template with inline comments
- `python_pipeline/configs/domains.yaml` — Domain definitions (regex patterns, colors)
- Usage: Load via `PheWASConfig.from_yaml(path)` in CLI

**Default Values:**
- Defined in `config.py:PheWASConfig` dataclass fields
- Applied when fields absent from YAML
- Overridable via CLI flags

**Column Range Specification:**
- Config fields: `continuous_col_range` (list of 2 ints: [start, end], 0-indexed, inclusive)
- Interpretation: Mirrors R's positional indexing; matches pandas iloc semantics
- Example: `[20, 656]` → columns at indices 20 through 656 (inclusive)
- Default: Matches FINAL_PHEWAS_baseline_n5556.xlsx structure

---

*Structure analysis: 2025-03-02*
