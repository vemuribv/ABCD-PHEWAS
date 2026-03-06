---
phase: 03-correction-and-outputs
plan: 02
subsystem: visualization
tags: [matplotlib, adjustText, manhattan-plot, phewas, 300dpi, domain-grouping]

# Dependency graph
requires:
  - phase: 03-correction-and-outputs
    provides: "apply_corrections() adding fdr_q_global, bonf_p_global, fdr_q_domain, bonf_p_domain columns"
  - phase: 01-data-foundation
    provides: "load_domain_config() for domain order and colors"
provides:
  - "manhattan_plot() for one-vs-rest cluster Manhattan plots with directional markers"
  - "omnibus_plot() for global omnibus Manhattan plots with circular markers"
affects: [04-pipeline-orchestration]

# Tech tracking
tech-stack:
  added: [matplotlib>=3.7, adjustText>=1.0]
  patterns: [domain-grouped-x-axis, directional-marker-encoding, threshold-line-overlay]

key-files:
  created:
    - src/abcd_phewas/plotter.py
    - tests/test_plotter.py
  modified:
    - pyproject.toml

key-decisions:
  - "adjustText for non-overlapping label placement with arrow connectors"
  - "Bonferroni-significant labels first (up to 20), supplemented by FDR-significant if fewer than 5 Bonferroni hits"
  - "n_tests for OVR threshold lines uses total OVR tests across all clusters (not per-cluster count)"

patterns-established:
  - "Agg backend forced at module level for headless PNG generation"
  - "Domain x-axis ordering from YAML config with gap=5 between domains and alternating gray bands"
  - "Directional encoding: upward triangle for positive effect size, downward for negative"

requirements-completed: [OUTP-02, OUTP-03]

# Metrics
duration: 3min
completed: 2026-03-06
---

# Phase 3 Plan 02: Manhattan Plot Module Summary

**Publication-quality Manhattan-style PheWAS plots with domain-grouped x-axis, directional triangle markers for OVR and circular markers for omnibus, FDR+Bonferroni threshold lines, and adjustText non-overlapping labels at 300 DPI**

## Performance

- **Duration:** 3 min (continuation from checkpoint approval)
- **Started:** 2026-03-06T03:08:21Z
- **Completed:** 2026-03-06T03:11:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- manhattan_plot() rendering one-vs-rest cluster comparisons with directional triangle markers (up=positive, down=negative effect size), domain-colored, with FDR and Bonferroni threshold lines
- omnibus_plot() rendering global omnibus results with circular markers, domain colors, and threshold lines
- Non-overlapping label placement via adjustText with arrow connectors on significant hits
- Domain-grouped x-axis with alternating gray background bands and configurable domain ordering from YAML
- 6 smoke tests verifying PNG output, 300 DPI, and graceful handling of no-significant-hits scenarios

## Task Commits

Each task was committed atomically:

1. **Task 1: plotter.py -- Manhattan plot functions with smoke tests** - `2db2c02` (feat)
2. **Task 2: Visual verification of Manhattan plots** - User approved (checkpoint:human-verify, no separate commit)

## Files Created/Modified
- `src/abcd_phewas/plotter.py` - manhattan_plot() and omnibus_plot() with helper functions for x-positioning, threshold lines, and label placement
- `tests/test_plotter.py` - 6 smoke tests covering OVR and omnibus plot generation, DPI verification, directional markers, and no-significant-hits edge case
- `pyproject.toml` - Added matplotlib>=3.7 and adjustText>=1.0 dependencies

## Decisions Made
- Used adjustText library for non-overlapping label placement (standard in genomics Manhattan plots)
- Label selection prioritizes Bonferroni-significant hits (up to 20), supplements with FDR-significant if fewer than 5 Bonferroni hits (ensures important hits are always labeled)
- OVR threshold lines use total OVR test count across all clusters as the correction family (consistent with global correction in Plan 01)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 3 complete: correction.py, results_writer.py, and plotter.py all ready for pipeline integration
- Phase 4 (Pipeline Orchestration) can wire these modules into the CLI runner
- Full test suite green at 141+ tests

## Self-Check: PASSED

- All 3 source/test files verified on disk (plotter.py, test_plotter.py, pyproject.toml)
- Task 1 commit (2db2c02) verified in git log
- Task 2 approved by user (checkpoint:human-verify)

---
*Phase: 03-correction-and-outputs*
*Completed: 2026-03-06*
