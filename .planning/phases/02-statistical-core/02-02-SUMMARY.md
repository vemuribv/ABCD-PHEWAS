---
phase: 02-statistical-core
plan: 02
subsystem: statistics
tags: [stat-engine, kruskal-wallis, mann-whitney, chi-square, fisher-exact, dispatch-table]

# Dependency graph
requires:
  - phase: 01-data-foundation
    provides: "VarType enum for dispatch table keying"
  - phase: 02-statistical-core
    plan: 01
    provides: "cohens_d, rank_biserial, cramers_v, epsilon_squared, monte_carlo_chi_square, bootstrap_ci"
provides:
  - "ComparisonType enum (OMNIBUS, ONE_VS_REST)"
  - "make_result_row: standardized 12-column result dict factory"
  - "run_kruskal_wallis: omnibus test for continuous/ordinal"
  - "run_chi_square_omnibus: omnibus test for binary/categorical"
  - "run_mann_whitney: one-vs-rest for continuous/ordinal with effect size + CI"
  - "run_chi_square_pairwise: one-vs-rest with Fisher/Monte Carlo fallback chain"
  - "TEST_DISPATCH: 8-entry (VarType, ComparisonType) -> runner mapping"
  - "test_single_variable: produces K+1 result rows for one variable"
affects: [02-03-parallel-runner]

# Tech tracking
tech-stack:
  added: []
  patterns: [dispatch-table, sparse-fallback-chain, tdd-red-green]

key-files:
  created:
    - src/abcd_phewas/stat_engine.py
    - tests/test_stat_engine.py
  modified: []

key-decisions:
  - "No sparse fallback for omnibus KxL tables (full-sample cell counts virtually never < 5)"
  - "NaN CI for omnibus effect sizes (bootstrap CIs only for one-vs-rest comparisons)"
  - "Dispatch table uses (VarType, ComparisonType) tuple as key for O(1) lookup"

patterns-established:
  - "Dispatch table: (VarType, ComparisonType) -> runner function for extensible test selection"
  - "Result row contract: all test runners return dict with exactly 12 columns"
  - "Sparse fallback chain: expected<5 + 2x2->Fisher, expected<5 + >2x2->Monte Carlo, else->chi-square"

requirements-completed: [STAT-01, STAT-02, STAT-06]

# Metrics
duration: 5min
completed: 2026-03-05
---

# Phase 2 Plan 02: Statistical Test Engine Summary

**Dispatch-based stat engine with KW/MWU/chi-square/Fisher runners, sparse fallback chain, and standardized 12-column result rows for 2-to-8 cluster comparisons**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-05T10:01:18Z
- **Completed:** 2026-03-05T10:06:00Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 2

## Accomplishments
- Complete dispatch table mapping all 8 (VarType, ComparisonType) combinations to runner functions
- Sparse fallback chain verified: Fisher exact for 2x2, Monte Carlo for >2x2, standard chi-square otherwise
- test_single_variable produces correct K+1 rows for both 2-cluster and 8-cluster data
- All effect sizes computed for every pair (not just significant), with bootstrap CIs on one-vs-rest
- Full test suite remains green (111 tests: 94 previous + 17 new)

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing stat engine tests** - `9961b40` (test)
2. **Task 1 GREEN: Implement stat_engine.py** - `18a1113` (feat)

_TDD plan: RED committed failing tests, GREEN committed passing implementation._

## Files Created/Modified
- `src/abcd_phewas/stat_engine.py` - ComparisonType enum, 4 test runners, dispatch table, test_single_variable entry point
- `tests/test_stat_engine.py` - 17 unit tests covering dispatch, omnibus, one-vs-rest, fallbacks, multi-cluster, NaN handling

## Decisions Made
- No sparse fallback applied to omnibus KxL contingency tables (full-sample expected cell counts are safely above 5 for ABCD dataset sizes)
- Omnibus results report NaN for CI (bootstrap CIs only meaningful for one-vs-rest pairwise comparisons)
- Dispatch table keyed on (VarType, ComparisonType) tuple for clean O(1) test selection

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- stat_engine.py ready for Plan 03's parallel runner to call test_single_variable across 3,000+ variables
- All runner functions accept random_state for reproducible Monte Carlo and bootstrap operations
- Result rows conform to the 12-column contract for Phase 3 correction and output

## Self-Check: PASSED

- [x] src/abcd_phewas/stat_engine.py exists
- [x] tests/test_stat_engine.py exists
- [x] Commit 9961b40 found (RED)
- [x] Commit 18a1113 found (GREEN)
- [x] 111/111 tests pass

---
*Phase: 02-statistical-core*
*Completed: 2026-03-05*
