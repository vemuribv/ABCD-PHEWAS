---
phase: 03-correction-and-outputs
plan: 01
subsystem: statistical-correction
tags: [fdr, bonferroni, multipletests, statsmodels, csv-assembly]

# Dependency graph
requires:
  - phase: 02-statistical-core
    provides: "run_all_tests() 12-column DataFrame with p-values"
  - phase: 01-data-foundation
    provides: "PipelineResult with domain_map and missingness"
provides:
  - "apply_corrections() pure function adding 4 correction columns"
  - "assemble_results() merging domain, missingness, corrections into 18-column output"
  - "write_results_csv() for publication-ready CSV output"
affects: [03-02-PLAN, 04-cli-integration]

# Tech tracking
tech-stack:
  added: [statsmodels>=0.14]
  patterns: [pure-function-correction, family-separated-fdr]

key-files:
  created:
    - src/abcd_phewas/correction.py
    - src/abcd_phewas/results_writer.py
    - tests/test_correction.py
    - tests/test_results_writer.py
  modified:
    - pyproject.toml

key-decisions:
  - "multipletests from statsmodels for both FDR-BH and Bonferroni (consistent API, capping at 1.0)"
  - "Domain groups with < 2 valid p-values get NaN domain corrections (no meaningful correction possible)"

patterns-established:
  - "Pure function correction: DataFrame in, augmented DataFrame out (copy, not in-place)"
  - "Family separation: omnibus and one_vs_rest corrected independently at global and domain levels"

requirements-completed: [OUTP-01]

# Metrics
duration: 7min
completed: 2026-03-06
---

# Phase 3 Plan 01: Multiple Comparison Correction and Results CSV Summary

**FDR-BH and Bonferroni correction with omnibus/OVR family separation via statsmodels multipletests, plus 18-column results CSV assembly with domain and missingness merges**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-06T02:38:41Z
- **Completed:** 2026-03-06T02:46:27Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- apply_corrections() pure function applying global and within-domain FDR-BH and Bonferroni corrections with proper omnibus/OVR family separation
- assemble_results() merging domain labels from domain_map, missingness rates, and all 4 correction columns into the 18-column publication spec
- write_results_csv() for CSV output sorted by raw p-value ascending
- 18 new tests (10 correction + 8 results_writer), full suite at 135 tests green

## Task Commits

Each task was committed atomically:

1. **Task 1: correction.py -- apply FDR-BH and Bonferroni corrections** - `24ac8e8` (feat)
2. **Task 2: results_writer.py -- assemble and write final CSV** - `79c5b39` (feat)

_Both tasks followed TDD: RED (failing tests) -> GREEN (implementation passes)_

## Files Created/Modified
- `src/abcd_phewas/correction.py` - Pure function applying 4 correction columns (fdr_q_global, bonf_p_global, fdr_q_domain, bonf_p_domain)
- `src/abcd_phewas/results_writer.py` - assemble_results() and write_results_csv() for 18-column CSV output
- `tests/test_correction.py` - 10 tests covering family separation, NaN handling, domain grouping, capping, monotonicity
- `tests/test_results_writer.py` - 8 tests covering column spec, domain/missingness merge, sort order, CSV round-trip
- `pyproject.toml` - Added statsmodels>=0.14 dependency

## Decisions Made
- Used statsmodels multipletests for both FDR-BH and Bonferroni (consistent API, handles capping at 1.0, NaN exclusion)
- Domain groups with fewer than 2 valid p-values get NaN domain corrections (single-test domains cannot be meaningfully corrected)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- correction.py and results_writer.py ready for Manhattan plotting module (Plan 02)
- apply_corrections() can be called standalone or through assemble_results()
- Full test suite green at 135 tests

## Self-Check: PASSED

- All 4 source/test files verified on disk
- Both task commits (24ac8e8, 79c5b39) verified in git log
- 135 tests green, no regressions

---
*Phase: 03-correction-and-outputs*
*Completed: 2026-03-06*
