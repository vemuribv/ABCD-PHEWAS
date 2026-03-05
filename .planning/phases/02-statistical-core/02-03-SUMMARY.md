---
phase: 02-statistical-core
plan: 03
subsystem: statistical-engine
tags: [parallel, ProcessPoolExecutor, orchestrator, multi-cluster, PheWAS]

requires:
  - phase: 02-statistical-core-02
    provides: "test_single_variable, dispatch table, all test runners"
  - phase: 01-data-foundation
    provides: "PipelineResult dataclass with df, type_map"
provides:
  - "run_all_tests orchestrator function for end-to-end stat testing"
  - "Parallel execution via ProcessPoolExecutor"
  - "Shape assertion: n_variables * (n_clusters + 1) rows"
affects: [03-correction-visualization, cli, pipeline-integration]

tech-stack:
  added: [concurrent.futures.ProcessPoolExecutor]
  patterns: [picklable-args-wrapper, serial-debug-mode, shape-assertion]

key-files:
  created: []
  modified:
    - src/abcd_phewas/stat_engine.py
    - tests/test_stat_engine.py

key-decisions:
  - "Picklable tuple args for ProcessPoolExecutor (values.tolist() not DataFrame)"
  - "n_workers=1 serial mode for debugging; None for auto CPU count"
  - "Shape assertion with diagnostic logging of bad variable counts"

patterns-established:
  - "Wrapper function pattern: _test_variable_wrapper unpacks tuple for pool workers"
  - "Error isolation: per-variable exception catching returns NaN row, never crashes pool"

requirements-completed: [STAT-04, STAT-05, STAT-06]

duration: 10min
completed: 2026-03-05
---

# Phase 2 Plan 03: run_all_tests Orchestrator Summary

**Parallel stat engine orchestrator with shape assertion, supporting 2-to-8 cluster configs via ProcessPoolExecutor**

## Performance

- **Duration:** 10 min
- **Started:** 2026-03-05T10:08:33Z
- **Completed:** 2026-03-05T10:18:23Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- run_all_tests function wires PipelineResult into full stat testing across all variables
- ProcessPoolExecutor parallelization with picklable args wrapper
- Shape assertion enforces n_variables * (n_clusters + 1) rows with diagnostic error messages
- Full test suite green: 117 tests (Phase 1 + Phase 2) with zero regressions
- STAT-04/05 (correction) explicitly deferred to Phase 3 -- no correction columns present
- STAT-06 (multi-cluster) validated end-to-end with 2 and 8 cluster configs

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: run_all_tests failing tests** - `ba3ec72` (test)
2. **Task 1 GREEN: run_all_tests implementation** - `5773290` (feat)
3. **Task 2: Full suite validation** - no changes needed, all 117 tests pass

_Note: TDD task had RED and GREEN commits. No refactor needed._

## Files Created/Modified
- `src/abcd_phewas/stat_engine.py` - Added _test_variable_wrapper and run_all_tests orchestrator
- `tests/test_stat_engine.py` - Added 6 integration tests for run_all_tests (shape, columns, parallel, assertion)

## Decisions Made
- Picklable tuple args for ProcessPoolExecutor: pass values.tolist() instead of DataFrame/Series to avoid pickle overhead
- n_workers=1 for serial/debug mode, None delegates to os.cpu_count()
- Shape assertion includes diagnostic logging of which variables produced wrong row counts

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 2 (Statistical Core) is now complete
- run_all_tests returns raw p-values DataFrame ready for Phase 3 correction (FDR + Bonferroni)
- Result DataFrame has the 12-column contract for downstream plotting
- STAT-04/05 (multiple testing correction) deferred to Phase 3 as planned

---
*Phase: 02-statistical-core*
*Completed: 2026-03-05*

## Self-Check: PASSED
- All source files exist
- All commits verified (ba3ec72, 5773290)
- 117 tests pass with zero regressions
