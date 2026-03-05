---
phase: 01-data-foundation
plan: 02
subsystem: data
tags: [scipy, numpy, pandas, pyyaml, pytest, preprocessing, domain-mapping, pipeline]

# Dependency graph
requires:
  - phase: 01-data-foundation
    plan: 01
    provides: "loader.py, type_detector.py, PipelineConfig, VarType enum, config/domain_mapping.yaml, conftest.py"
provides:
  - "preprocessor.py: two-pass preprocessing (scipy skewness check, mean-based winsorization, rank-based INT, z-score) with transformation log"
  - "domain_mapper.py: regex-based domain assignment from YAML config, case-insensitive, first-match-wins"
  - "pipeline.py: PipelineResult dataclass + run_pipeline() orchestrating all 12 stages in correct order"
  - "44 new tests (18 preprocessor + 19 domain mapper + 7 pipeline) — 75 total passing at 97% coverage"
affects:
  - "02-statistical-tests (uses run_pipeline output: preprocessed df, type_map, domain_map)"
  - "03-visualization (uses domain_map colors for Manhattan plot domain axis)"
  - "04-reporting (uses transformation_log and skipped_vars for data quality report)"

# Tech tracking
tech-stack:
  added:
    - "scipy.stats.skew(bias=True) for skewness matching R's default estimator"
    - "scipy.stats.rankdata (average ties) + norm.ppf for rank-based INT matching R qnorm"
    - "re.search with re.IGNORECASE for case-insensitive domain regex matching"
  patterns:
    - "Two-pass preprocessing: skewness -> winsorize -> re-check -> INT if still skewed, z-score otherwise"
    - "Mean-based winsorization (mean ± n_sd*std, ddof=1) matching R DescTools::Winsorize"
    - "Dataclass PipelineResult as single return object for the full pipeline"
    - "12-stage pipeline with explicit ordering enforced by code comments and tests"
    - "Logger.debug per-match in domain_mapper (addresses regex order sensitivity debugging)"

key-files:
  created:
    - "src/abcd_phewas/preprocessor.py"
    - "src/abcd_phewas/domain_mapper.py"
    - "src/abcd_phewas/pipeline.py"
    - "tests/test_preprocessor.py"
    - "tests/test_domain_mapper.py"
    - "tests/test_pipeline.py"
  modified: []

key-decisions:
  - "Use lognormal distribution for test_two_pass_int: exponential(2.0) drops below skew threshold after winsorization; lognormal stays skewed"
  - "Mean-based winsorization bounds computed from the original array (including outliers): matches R's DescTools behavior where minval/maxval are derived from the same data"
  - "Sentinel replacement (Stage 2) before type detection (Stage 7): enforced by ordering and validated by test_pipeline_ordering_sentinel_before_type_detection"
  - "Missingness computed before min-n filter (Stage 5 before Stage 6): users can see why variables were skipped"
  - "PipelineResult uses @dataclass with field(default_factory=list) for mutable defaults"

patterns-established:
  - "Pipeline stage ordering: load -> sentinel replace -> blocklist -> pheno_cols -> missingness -> min-n filter -> type detect -> overrides -> preprocess -> domain config -> domain assign -> log"
  - "TDD workflow confirmed: RED (import error) -> GREEN (all tests pass) for each module"
  - "Domain assignment: iterate YAML order, first regex match wins, Other/Unclassified fallback"

requirements-completed: [DATA-05, DOMN-01, DOMN-02]

# Metrics
duration: 6min
completed: 2026-03-05
---

# Phase 1 Plan 02: Data Foundation (Preprocessing + Domain Mapper + Pipeline) Summary

**Two-pass preprocessing pipeline (scipy INT + mean-based winsorization matching R reference), regex domain mapper (8 ABCD domains from YAML), and 12-stage run_pipeline() orchestrator returning a complete PipelineResult**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-05T00:28:20Z
- **Completed:** 2026-03-05T00:34:06Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- preprocessor.py implements DATA-05: two-pass pipeline — scipy.stats.skew(bias=True) for skewness check, mean-based winsorization (ddof=1, matches R DescTools::Winsorize), rank-based INT via rankdata + norm.ppf (matches R qnorm), z-score with ddof=1 (matches R scale()); transformation log records each column's path
- domain_mapper.py implements DOMN-01/02: case-insensitive regex matching from domain_mapping.yaml, first-match-wins ordering, Other/Unclassified fallback with "#AAAAAA", DEBUG logging per match
- pipeline.py wires all stages: 12-stage run_pipeline() returning PipelineResult (df, type_map, domain_map, transformation_log, missingness, skipped_vars, unclassified_vars); sentinel replacement enforced before type detection
- 75 tests passing (44 new), 97% coverage across all 7 modules

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement two-pass preprocessor module** - `f2c3838` (feat)
2. **Task 2: Implement domain mapper module** - `bd68cf9` (feat)
3. **Task 3: Wire pipeline orchestrator and integration tests** - `a473e2f` (feat)

## Files Created/Modified

- `src/abcd_phewas/preprocessor.py` - winsorize_mean_sd, rank_based_int, z_score, preprocess_continuous_column (two-pass), preprocess_dataframe
- `src/abcd_phewas/domain_mapper.py` - load_domain_config, assign_domain (regex, IGNORECASE), assign_all_domains
- `src/abcd_phewas/pipeline.py` - PipelineResult dataclass, run_pipeline (12 stages, correct ordering)
- `tests/test_preprocessor.py` - 18 tests: two-pass paths, NaN handling, ordinal/binary passthrough, transformation log
- `tests/test_domain_mapper.py` - 19 tests: all 8 domains, case-insensitivity, first-match-wins, unclassified
- `tests/test_pipeline.py` - 7 integration tests: structure, sentinel ordering, skipped vars, end-to-end

## Decisions Made

- **Lognormal for INT test:** The plan suggested exponential(2.0) for testing the INT branch, but this distribution drops below the 1.96 skew threshold after winsorization. Used lognormal (exp(normal(0,2))) instead — stays highly skewed post-winsorization as needed.
- **Winsorization bounds from original array:** Mean/std computed on the array including outliers (matches R DescTools behavior). This means bounds are wider than if outliers were excluded — appropriate because the function is descriptive of the actual data distribution.
- **Missingness before min-n filter:** Stage ordering ensures missingness is recorded for ALL phenotype columns, including those that will be skipped. Users can see why variables were excluded.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test data selection for test_two_pass_int and test_two_pass_zscore**
- **Found during:** Task 1 (TDD GREEN phase)
- **Issue:** Plan's suggested test data (exponential, 5 outliers) did not produce the expected behavior. Exponential(2.0, n=500) dropped below 1.96 skew after winsorization (post-winsor skew: 1.28). Five outliers at 12.0 also remained skewed post-winsorization (skew: 2.38). Both produced incorrect test behavior.
- **Fix:** Used lognormal for the INT branch test; used single large outlier (15.0) for the z-score-after-winsorize branch test. Verified actual distribution behavior with diagnostic prints before finalizing.
- **Files modified:** `tests/test_preprocessor.py`
- **Verification:** Both tests now pass with correct branch routing confirmed in transformation log
- **Committed in:** `f2c3838` (Task 1 commit)

**2. [Rule 1 - Bug] Fixed test_winsorize_mean_sd_clips_outliers assertion**
- **Found during:** Task 1
- **Issue:** Test asserted `result[0] < 10.0` but injecting outlier=100.0 inflates the mean, making the clipping bound ~30 (not <10). The core assertion (`<= upper + 1e-9`) was already correct.
- **Fix:** Changed assertion to verify clipped value equals the computed upper bound (`pytest.approx(upper, abs=1e-9)`).
- **Files modified:** `tests/test_preprocessor.py`
- **Verification:** Test passes, correctly validates that clipping happens to the bound
- **Committed in:** `f2c3838` (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (2 test data bugs, Rule 1)
**Impact on plan:** Both fixes ensure tests correctly validate the specified behavior. No scope creep.

## Issues Encountered

- Distribution selection for TDD: plan-level test suggestions must account for how winsorization interacts with each distribution's tail behavior. Exponential and normal+outliers combinations do not reliably preserve the skewed/not-skewed split needed to test each branch.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Full Phase 1 goal is met: load -> sentinel -> blocklist -> type detect -> preprocess -> domain map all wired and tested
- run_pipeline() is the primary entry point for Phase 2 (statistical tests)
- PipelineResult provides all outputs Phase 2 needs: preprocessed df, type_map (for selecting test type), domain_map (for grouping), skipped_vars (for excluding)
- All blockers from STATE.md still apply to later phases (CRLI blocklist variable names, cluster file format, family structure) — these are data dependencies confirmed as out-of-scope for Phase 1

## Self-Check: PASSED

- All 6 source/test files confirmed present on disk
- All 3 task commits confirmed in git log (f2c3838, bd68cf9, a473e2f)
- 75 tests passing, 97% coverage verified

---
*Phase: 01-data-foundation*
*Completed: 2026-03-05*
