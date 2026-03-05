---
phase: 02-statistical-core
plan: 01
subsystem: statistics
tags: [effect-size, cohens-d, cramers-v, bootstrap, monte-carlo, scipy]

# Dependency graph
requires:
  - phase: 01-data-foundation
    provides: "VarType enum for test-type selection; PipelineResult for downstream integration"
provides:
  - "cohens_d: pooled-SD Cohen's d for continuous one-vs-rest comparisons"
  - "rank_biserial: rank-biserial correlation from Mann-Whitney U"
  - "cramers_v: Cramer's V from contingency tables"
  - "epsilon_squared: epsilon-squared from Kruskal-Wallis H"
  - "monte_carlo_chi_square: simulated chi-square p-value for sparse tables"
  - "bootstrap_ci: percentile bootstrap CI wrapper for any effect-size function"
affects: [02-02-stat-engine, 02-03-parallel-runner]

# Tech tracking
tech-stack:
  added: []
  patterns: [tdd-red-green, pure-function-modules, known-answer-tests]

key-files:
  created:
    - src/abcd_phewas/effect_sizes.py
    - tests/test_effect_sizes.py
  modified:
    - tests/conftest.py

key-decisions:
  - "Percentile bootstrap (not BCa) to handle degenerate/constant data without error"
  - "Monte Carlo chi-square uses multinomial sampling with expected-frequency probabilities"
  - "bootstrap_ci passes statistic_fn directly with vectorized=False (scipy 1.13+ API)"
  - "Zero pooled SD in cohens_d returns 0.0 (not inf)"

patterns-established:
  - "Pure math functions: simple inputs (arrays/scalars) -> single return value"
  - "Known-answer tests: hand-calculated expected values for statistical functions"
  - "RNG injection: all stochastic functions accept numpy Generator for reproducibility"

requirements-completed: [STAT-03]

# Metrics
duration: 5min
completed: 2026-03-05
---

# Phase 2 Plan 01: Effect Sizes Summary

**Six validated effect-size functions (Cohen's d, rank-biserial, Cramer's V, epsilon-squared) plus Monte Carlo chi-square and bootstrap CI wrapper, all with known-answer TDD tests**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-05T09:44:24Z
- **Completed:** 2026-03-05T09:49:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- All 6 effect-size building blocks implemented and tested with known-answer validation
- Monte Carlo chi-square simulation reproduces scipy chi2 p-values within tolerance
- Bootstrap CI handles both normal and degenerate (constant) data gracefully
- Full test suite remains green (90 tests: 75 Phase 1 + 15 new)

## Task Commits

Each task was committed atomically:

1. **Task 1: Test fixtures and effect size unit tests (RED)** - `53078ac` (test)
2. **Task 2: Implement effect_sizes.py (GREEN)** - `0c1764e` (feat)

_TDD plan: RED committed failing tests, GREEN committed passing implementation._

## Files Created/Modified
- `src/abcd_phewas/effect_sizes.py` - All 6 exported functions: cohens_d, rank_biserial, cramers_v, epsilon_squared, monte_carlo_chi_square, bootstrap_ci
- `tests/test_effect_sizes.py` - 15 unit tests covering known values, boundary conditions, reproducibility, and degenerate data
- `tests/conftest.py` - Extended with two_cluster_data, eight_cluster_data, sparse_contingency_2x2, sparse_contingency_3x3 fixtures

## Decisions Made
- Used percentile bootstrap method (not BCa) because BCa fails on degenerate/constant data
- Monte Carlo chi-square generates random tables via multinomial sampling with expected-frequency cell probabilities, matching R's simulate.p.value approach
- scipy bootstrap called with vectorized=False so statistic_fn receives 1-D arrays directly (clean API for scipy 1.13)
- cohens_d returns 0.0 when pooled SD is zero (both groups constant) rather than raising or returning inf

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed bootstrap_ci wrapper for scipy 1.13 API**
- **Found during:** Task 2 (GREEN phase)
- **Issue:** Initial implementation wrapped statistic_fn with a custom axis-handling loop, but scipy 1.13 with vectorized=False passes 1-D arrays directly without axis parameter
- **Fix:** Removed custom wrapper, pass statistic_fn directly to scipy.stats.bootstrap
- **Files modified:** src/abcd_phewas/effect_sizes.py
- **Verification:** test_bootstrap_ci_normal_data and test_bootstrap_ci_degenerate both pass
- **Committed in:** 0c1764e (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Necessary fix for scipy API compatibility. No scope creep.

## Issues Encountered
None beyond the bootstrap API fix documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Effect size functions ready for Plan 02's stat engine to call per (variable, cluster) pair
- Fixtures (two_cluster_data, eight_cluster_data) available for stat engine integration tests
- All functions are pure (no state, no side effects) -- safe for parallel execution

## Self-Check: PASSED

- [x] src/abcd_phewas/effect_sizes.py exists
- [x] tests/test_effect_sizes.py exists
- [x] tests/conftest.py exists (modified)
- [x] Commit 53078ac found (RED)
- [x] Commit 0c1764e found (GREEN)
- [x] 90/90 tests pass

---
*Phase: 02-statistical-core*
*Completed: 2026-03-05*
