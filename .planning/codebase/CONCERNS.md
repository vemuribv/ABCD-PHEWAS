# Codebase Concerns

**Analysis Date:** 2026-03-02

## Tech Debt

**Missing error handling in binary phenotype validation:**
- Issue: Binary phenotypes are validated with hard-coded thresholds (n_pos < 5 or n_neg < 5) with no configurable flexibility or grace period.
- Files: `python_pipeline/models.py` (lines 350–356)
- Impact: Phenotypes with exactly 5 positive/negative cases are excluded silently; users cannot adjust threshold without modifying code.
- Fix approach: Add configurable `min_binary_counts` parameter to `PheWASConfig` and pass through the pipeline; log which phenotypes were filtered and why.

**Aggressive DataFrame copying reduces performance:**
- Issue: 16 `.copy()` calls throughout the pipeline create unnecessary memory overhead. For 5500 subjects × 1300 phenotypes, preprocessing creates 5+ full copies of the entire dataset.
- Files: `python_pipeline/preprocessing.py` (lines 216, 281, 345, 349, 351, 404), `python_pipeline/cli.py` (line 160), `python_pipeline/corrections.py` (line 50), `python_pipeline/visualizations.py` (lines 51, 123, 272, 359), `python_pipeline/domains.py` (line 198)
- Impact: Memory usage spikes during preprocessing and corrections; runtime increases linearly with dataset size; potential OOM on memory-constrained systems.
- Fix approach: Audit `.copy()` calls—many are defensive copies unnecessary for immutability. Replace with in-place operations where safe; use copy-on-write strategies (pandas 2.0+) for truly independent DataFrames.

**pymer4 import fallback is incomplete:**
- Issue: `models.py` lazily imports pymer4 and sets `_PYMER4_AVAILABLE` flag, but only used in conditional logging. Runtime functions still call `fit_continuous_model()` / `fit_binary_model()` which raise `RuntimeError` if pymer4 is missing.
- Files: `python_pipeline/models.py` (lines 40–47, 138–139, 181–182)
- Impact: Error message is cryptic when pymer4 is absent; users may not realize R/lme4 needs installation. The code supports testing without pymer4 but production runs silently fail mid-pipeline.
- Fix approach: Check `_PYMER4_AVAILABLE` in `run_single_phenotype()` before calling model fitting; provide clear error exit at pipeline start if running full analysis without pymer4.

**Checkpoint file is append-only, no deduplication:**
- Issue: `parallel.py` appends phenotype names on completion but does not deduplicate; if a phenotype is re-run, it appears twice in the checkpoint file. Loading the checkpoint creates a set, so it works correctly, but repeated runs pollute the file.
- Files: `python_pipeline/parallel.py` (lines 53–61)
- Impact: Checkpoint file grows without bound; becomes unreadable after hundreds of reruns; no clear record of which specific run completed each phenotype.
- Fix approach: Rewrite checkpoint as a timestamp-indexed JSON file `{phenotype: completion_timestamp}` instead of plain text; add `--reset-checkpoint` CLI flag to clear before re-run.

**No validation of column ranges against actual data:**
- Issue: `config.py` defines `continuous_col_range` and `binary_col_range` as free parameters with no runtime validation that the ranges match the actual Excel/CSV structure. Off-by-one errors silently select the wrong columns.
- Files: `python_pipeline/config.py` (lines 43–44), `python_pipeline/cli.py` (lines 172–177)
- Impact: User provides range `[20, 656]` expecting columns 20–656 (inclusive), but if the file only has 650 columns, the last 6 phenotypes are silently ignored. No warning issued.
- Fix approach: In `load_phenotype_data()`, validate that `cont_end + 1 <= len(df.columns)` and `bin_end + 1 <= len(df.columns)`; raise `ValueError` with file info if ranges exceed actual columns. Log the actual column headers selected.

**visualizations.py passes DataFrame to multiple plot functions with no cleanup:**
- Issue: Each plot function receives the same results DataFrame, makes a copy for processing, then returns. No explicit cleanup of matplotlib figures between calls; `plt.close(fig)` is called, but unused figure objects may accumulate in memory during large multi-contrast runs.
- Files: `python_pipeline/visualizations.py` (lines 228–229, 316–317), `python_pipeline/cli.py` (lines 318–342)
- Impact: Long runs with many contrasts (e.g., 10+ contrasts × 1300 phenotypes) may leak memory in matplotlib's internal cache; potential OOM on memory-limited systems.
- Fix approach: Add `plt.close('all')` after each contrast finishes plotting; consider wrapping plot functions in a context manager to guarantee cleanup.

**Metadata fallback to regex silently succeeds without warning:**
- Issue: If `phenotype_metadata.csv` is missing or empty, `load_phenotype_metadata()` returns `{}` and domain assignment falls back to regex matching without informing the user. No way to know if a phenotype was assigned by authoritative metadata or by regex guess.
- Files: `python_pipeline/domains.py` (lines 99–102, 147–154)
- Impact: User may assume all domains come from the published supplement (high confidence) when in fact 20%+ are regex-matched guesses. Reproducibility concern: different regex patterns in future versions may reassign phenotypes silently.
- Fix approach: Log a clear info message when metadata is missing, and add a `metadata_source` column to results CSV indicating `"published_metadata"` vs `"regex_pattern"` for each phenotype. Warn if >10% of phenotypes are regex-only.

## Known Bugs

**adjustText import is optional but may silently fail:**
- Symptoms: If `adjustText` package is installed but breaks at import (e.g., due to missing system dependencies like graphviz), the `try/except` block silently sets `_ADJUST_TEXT_AVAILABLE = False` without logging a warning.
- Files: `python_pipeline/visualizations.py` (lines 24–28)
- Trigger: Run with `pip install adjustText` but missing `graphviz` system library (Linux: `apt-get install graphviz`).
- Workaround: Labels will not be adjusted; they will overlap. Install graphviz or use `--log-level DEBUG` to see the actual import error.

**Cluster dummy variable names are non-deterministic if cluster labels contain spaces:**
- Symptoms: If cluster file contains labels like `"0 "` (trailing space), they are stripped in `load_cluster_labels()` but not before creating dummy names, leading to inconsistent column names between runs.
- Files: `python_pipeline/preprocessing.py` (line 282), `python_pipeline/preprocessing.py` (lines 407–408)
- Trigger: Cluster labels with leading/trailing whitespace or special characters.
- Workaround: Manually clean cluster CSV before running; validation could be added to reject non-alphanumeric labels.

**Sex-stratified analyses remove sex covariate but only after config validation:**
- Symptoms: If user specifies `sex` as a covariate and runs a sex-stratified analysis (e.g., `--sex-stratum female`), the code logs a removal message but this happens *after* config validation; if validation were stricter, the error would be caught earlier.
- Files: `python_pipeline/cli.py` (lines 405–412)
- Trigger: Run `python -m python_pipeline.cli --sex-stratum female` with `sex` in covariates.
- Workaround: Code handles it gracefully; improvement is defensive.

## Security Considerations

**Cluster file path is user-supplied with no existence check until load time:**
- Risk: User could specify `--cluster-file /etc/passwd` or other unintended files; no early validation.
- Files: `python_pipeline/cli.py` (lines 79–80), `python_pipeline/config.py` (line 26)
- Current mitigation: `load_cluster_labels()` will raise an error if the file doesn't contain expected columns.
- Recommendations: Add early existence check in `PheWASConfig.validate()` and print a warning if cluster file path looks suspicious (e.g., `/etc/`, `~`, absolute paths outside project).

**Environment variable handling is absent:**
- Risk: No secrets management; if future versions add API credentials, they might be hardcoded in YAML or committed to git.
- Files: N/A (not applicable currently)
- Current mitigation: All inputs are local files; no external APIs.
- Recommendations: If external services are added (e.g., cloud storage, API calls), use `os.getenv()` with required validation; document required env vars in README; add `.env.example`.

**Log files include full file paths and sensitive column names:**
- Risk: If logs are shared, they reveal data structure and file locations.
- Files: `python_pipeline/utils.py` (line 46), throughout CLI and preprocessing logging
- Current mitigation: Logs are written to stdout/stderr; no log file is created by default.
- Recommendations: When a log file is added, use log rotation and sanitize paths; mask database/file paths in logs if running in production.

## Performance Bottlenecks

**ProcessPoolExecutor serializes entire DataFrame to each worker:**
- Problem: Each worker receives a copy of the full preprocessed DataFrame (5500 rows × 1300+ cols) via pickle. With 8 workers, this is 8 × 40+ MB of data serialization overhead.
- Files: `python_pipeline/parallel.py` (lines 160–171)
- Cause: DataFrame is pickled in `_worker()` function signature for each submitted job.
- Improvement path: Consider memory-mapping or shared-memory approach (e.g., `multiprocessing.Manager().dict()` for read-only reference) or splitting the DataFrame by phenotype groups. For now, acceptable if n_workers ≤ 8.

**Visualizations iterate over every result row multiple times:**
- Problem: `plot_manhattan()` and `plot_forest()` sort, group, and filter the DataFrame separately; for 1300 phenotypes × 2–5 contrasts = 6500+ rows, this means 5+ full DataFrame iterations per contrast.
- Files: `python_pipeline/visualizations.py` (lines 123, 135, 154–157, 188–189, 268–272)
- Cause: Functional programming style; not grouped operations.
- Improvement path: Use `groupby()` and single-pass vectorized operations; compute all sorting/filtering once per contrast, then iterate results.

**Corrections applied per-contrast but no caching of skipped contrasts:**
- Problem: If a contrast has 0 results (all phenotypes failed to fit), `apply_multiple_corrections()` is still called with an empty DataFrame; minimal overhead but unnecessary.
- Files: `python_pipeline/cli.py` (line 273), `python_pipeline/corrections.py` (lines 54–93)
- Cause: No early check in `run_phewas_parallel()` to skip empty contrasts.
- Improvement path: Filter `results_df` to contrasts with > 0 rows before corrections; saves one function call per failed contrast.

**Parallel fallback to sequential mode is slow for debugging:**
- Problem: `--n-workers 1` runs sequentially but still goes through `ProcessPoolExecutor` initialization code (lines 160). For single-worker debugging, pure sequential is faster.
- Files: `python_pipeline/parallel.py` (lines 142–158)
- Cause: Sequential fallback is implemented but inside the if/else.
- Improvement path: Implement a true `n_workers=0` for pure sequential; rename current path to avoid confusion.

## Fragile Areas

**Formula string building in models.py is fragile to special characters:**
- Files: `python_pipeline/models.py` (lines 54–93)
- Why fragile: If a phenotype name or covariate contains `+`, `*`, `|`, or `~`, the formula string breaks. No validation of column names against R formula syntax.
- Safe modification: Call `build_formula()` with a test subset; wrap in try/except in `run_single_phenotype()`; add a column name validator that rejects illegal characters.
- Test coverage: No test of `build_formula()` with special characters in column names.

**Year-suffix regex in domains.py depends on consistent naming:**
- Files: `python_pipeline/domains.py` (lines 43–46)
- Why fragile: If ABCD changes naming convention (e.g., from `_3y` to `_y3`), the regex silently fails to strip and phenotypes from different waves are not matched to the same domain. No warning if nothing matches.
- Safe modification: Add a `_YEAR_SUFFIX_PATTERNS` list and iterate; log when a variable is *not* stripped so users can see unmatched patterns; add unit tests with real ABCD variable names from different waves.
- Test coverage: `test_domains.py` tests regex in isolation but not against real ABCD data.

**Skew threshold and winsorize SD are hardcoded defaults:**
- Files: `python_pipeline/config.py` (lines 49–50), `python_pipeline/preprocessing.py` (lines 190–191)
- Why fragile: These come from the R code but are not well-documented. If a user has different data characteristics (e.g., fewer extreme outliers), the defaults may over-transform. No sensitivity analysis.
- Safe modification: Add `--skew-threshold` and `--winsorize-sd` CLI flags; generate a preprocessing report (e.g., histogram of skewness before/after) showing which phenotypes were transformed.
- Test coverage: Preprocessing tests use small synthetic data; no tests with real ABCD data.

## Scaling Limits

**Parallel processing is limited by R session startup overhead:**
- Current capacity: ~1200 phenotypes with 2–5 contrasts = 5000 total model fits; with 8 workers, each worker runs ~625 models; takes ~2–4 hours on modern hardware.
- Limit: R/lme4 startup per worker takes ~3–5 seconds; so worker pool initialization can take 30–40 seconds total. With very large numbers of phenotypes (>5000) or contrasts (>10), init overhead becomes noticeable.
- Scaling path: Implement a persistent R subprocess pool (e.g., via `rpy2` context manager) to avoid repeated R initializations; or migrate to pure Python GLMM library (e.g., `statsmodels`) if results are comparable.

**DataFrame memory scales linearly with phenotype count:**
- Current capacity: 5500 subjects × 1300 phenotypes × 8 bytes (float64) = ~57 MB per DataFrame; with 5+ copies during preprocessing, peak memory ~300 MB.
- Limit: For >50,000 phenotypes or >50,000 subjects, memory approaches 1–2 GB; on a system with 4 GB RAM, this becomes constrained with OS overhead.
- Scaling path: Stream phenotypes from disk instead of loading all into memory; batch-load phenotypes in chunks of 100–200; write intermediate results to disk instead of accumulating in memory.

**Visualization generation scales quadratically with number of contrasts:**
- Current capacity: 1200 phenotypes × 3 contrasts = 3 plot sets (manhattan, forest, bar) = 6 PNG files; takes ~5 seconds total.
- Limit: With 10+ contrasts, generation time becomes >30 seconds and matplotlib memory grows linearly.
- Scaling path: Vectorize plot generation; generate plots in parallel (separate processes); use lower DPI for drafts; implement plot caching (hash input data, reuse PNG if unchanged).

## Dependencies at Risk

**pymer4 depends on R installation and lme4 package:**
- Risk: R version incompatibility (e.g., R 3.6 vs R 4.2 have different lme4 APIs); lme4 installation may fail on some systems; rpy2 C extension requires R development headers.
- Impact: Installation requires system-level R setup; deployment to Docker/HPC requires `apt-get install r-base` + R package installation; cross-platform CI/CD is fragile.
- Migration plan: Consider switching to `statsmodels.formula.api.gee()` for generalized estimating equations (similar to GLMM but pure Python); benchmark against pymer4 on real ABCD data to ensure comparable estimates. Would break R dependency.

**adjustText is an optional, unmaintained dependency:**
- Risk: Package may not be compatible with future matplotlib versions; original author has archived the repo.
- Impact: If matplotlib 4.0+ breaks adjustText, plot labels will not be adjusted (overlap persists); no clear error message.
- Migration plan: Either pin matplotlib version; or replace adjustText with a pure matplotlib solution (e.g., `matplotlib.offsetbox.AnnotationBbox`); add fallback to non-adjusted labels with a note in the PNG.

**statsmodels.stats.multitest may change API:**
- Risk: `multipletests()` function signature or output format may change in future statsmodels versions.
- Impact: Code would break at runtime during corrections step; no backward compatibility guaranteed.
- Migration plan: Pin statsmodels version in `setup.py` or `requirements.txt`; wrap `multipletests()` call in a compatibility layer that handles version differences.

## Missing Critical Features

**No support for multi-site normalization / harmonization:**
- Problem: Site effects are modeled as random intercepts but not removed before analyses. If two sites have systematic differences (e.g., different scanner protocols), results may be site-biased.
- Blocks: Cross-site comparison and meta-analysis; generalization to external cohorts.
- Recommendation: Add optional `--harmonize-sites` flag using ComBat or similar; document assumptions about site effects.

**No support for covariates that vary by phenotype (e.g., age-specific norms):**
- Problem: All phenotypes use the same covariate set; in reality, some phenotypes require adjustment by age, others by pubertal status. Fixed effects model is inflexible.
- Blocks: Modeling phenotype-specific confounders; advanced analyses.
- Recommendation: Allow covariate specification per-domain in YAML config.

**No support for missing data imputation:**
- Problem: Phenotypes with >5% missing values are dropped or analyzed with complete-case deletion. No imputation strategy (e.g., mean, MICE).
- Blocks: Analyses on incomplete data; sensitivity to missingness patterns.
- Recommendation: Add `--imputation-method` CLI flag; consider `sklearn.impute.SimpleImputer` or `statsmodels.imputation.MICE`.

**No results caching or incremental output:**
- Problem: If a run is interrupted, all results are lost; must restart from the beginning. Checkpoint file helps but doesn't save partial results.
- Blocks: Fault-tolerant long-running analyses; iterative refinement.
- Recommendation: Implement `--save-intermediate` flag to write per-phenotype results to a results database (SQLite); resume reads from database.

## Test Coverage Gaps

**CLI integration tests are absent:**
- What's not tested: End-to-end pipeline from `main()` through file I/O and visualization. Unit tests only cover individual functions.
- Files: `python_pipeline/tests/` (no `test_cli.py`)
- Risk: Bugs in parameter passing, file I/O sequencing, or multi-stage interactions remain undetected.
- Priority: **High** — CLI is the user-facing interface; a broken CLI affects all users.

**Parallel execution is untested:**
- What's not tested: `run_phewas_parallel()` with multiple workers, checkpoint recovery, exception handling in worker processes.
- Files: `python_pipeline/parallel.py` (no tests)
- Risk: Race conditions, deadlocks, or checkpoint corruption could only be found by running real multi-worker jobs.
- Priority: **High** — Parallelism is the core performance feature; bugs are hard to reproduce.

**Visualization generation is untested:**
- What's not tested: Plot generation with edge cases (empty data, all phenotypes FDR-sig, missing domain colors, malformed domain specs).
- Files: `python_pipeline/visualizations.py` (no tests)
- Risk: PNG generation may crash silently during plots; missing error handling.
- Priority: **Medium** — Visualization failures are less critical than model fits but impact usability.

**Real ABCD data is never used in tests:**
- What's not tested: Preprocessing with actual ABCD data characteristics (skew distributions, real missing-ness patterns, actual column counts).
- Files: All test files use synthetic data
- Risk: Tests pass but production run fails on real data (e.g., if a real phenotype has zero variance, or if column ranges are off).
- Priority: **High** — The gap between synthetic and real data can mask production bugs.

**Configuration validation is incomplete:**
- What's not tested: Invalid YAML syntax, missing required fields in domain spec, invalid cluster labels, malformed column ranges.
- Files: `python_pipeline/config.py` (validation is minimal)
- Risk: User passes malformed config; cryptic error messages downstream.
- Priority: **Medium** — Config errors are user-facing but caught early; good error messages would help.

---

*Concerns audit: 2026-03-02*
