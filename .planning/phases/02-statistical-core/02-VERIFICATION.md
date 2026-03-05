---
phase: 02-statistical-core
verified: 2026-03-05T11:00:00Z
status: passed
score: 5/5 success criteria verified
requirements_note: >
  STAT-04 and STAT-05 are listed under Phase 2 in ROADMAP.md but are explicitly
  deferred to Phase 3 by all three plans. Phase 2's goal says "raw p-values"
  and Phase 3's goal says "FDR/Bonferroni correction". The REQUIREMENTS.md
  traceability table incorrectly marks STAT-04/STAT-05 as Complete -- they
  should read "Deferred to Phase 3" until Phase 3 implements them.
  This is a documentation discrepancy, not a code gap.
---

# Phase 2: Statistical Core Verification Report

**Phase Goal:** Per-variable test results (one-vs-rest per cluster + global omnibus) with raw p-values and effect sizes, validated on synthetic data before running on ABCD
**Verified:** 2026-03-05
**Status:** passed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths (from ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Unit tests on synthetic data covering all four variable types pass before any ABCD data is processed | VERIFIED | 42 tests pass across test_effect_sizes.py and test_stat_engine.py; all use synthetic fixtures (two_cluster_data, eight_cluster_data); no ABCD data touched |
| 2 | Each variable receives the correct test: KW for continuous/ordinal, chi-square/Fisher for binary/categorical | VERIFIED | TEST_DISPATCH has 8 entries mapping all (VarType, ComparisonType) pairs; test_all_8_combinations asserts coverage; test_omnibus_continuous confirms KW, test_omnibus_binary confirms chi-square |
| 3 | Running on 2-cluster and 8-cluster both produce valid results without code changes | VERIFIED | test_run_all_tests_2_clusters (12 rows), test_run_all_tests_8_clusters (36 rows), test_row_count_2_clusters (3 rows), test_row_count_8_clusters (9 rows) all pass |
| 4 | Effect sizes (Cohen's d for continuous, Cramer's V for categorical) are present for all (variable, cluster) pairs, not just significant ones | VERIFIED | test_effect_sizes_not_nan iterates all 4 var types and asserts no NaN effect_size on any row; effect_size_type correctly set per var type |
| 5 | Raw p-value array length equals n_variables x (n_clusters + 1), confirmed by assertion before correction | VERIFIED | stat_engine.py lines 608-625 enforce AssertionError with diagnostic logging; test_result_shape_assertion_failure confirms the assertion fires |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/abcd_phewas/effect_sizes.py` | 6 functions: cohens_d, rank_biserial, cramers_v, epsilon_squared, monte_carlo_chi_square, bootstrap_ci | VERIFIED | 237 lines, all 6 functions present with docstrings and type hints |
| `tests/test_effect_sizes.py` | Unit tests with known-answer validation (min 100 lines) | VERIFIED | 242 lines, 19 tests across 7 test classes including cross-validation spot-checks |
| `src/abcd_phewas/stat_engine.py` | Dispatch table, 4 runners, test_single_variable, run_all_tests | VERIFIED | 633 lines, ComparisonType enum, make_result_row, run_kruskal_wallis, run_chi_square_omnibus, run_mann_whitney, run_chi_square_pairwise, TEST_DISPATCH (8 entries), test_single_variable, _test_variable_wrapper, run_all_tests |
| `tests/test_stat_engine.py` | Integration tests for dispatch, fallback, multi-cluster, run_all_tests (min 150 lines) | VERIFIED | 535 lines, 23 tests across 10 test classes |
| `tests/conftest.py` | Extended with two_cluster_data, eight_cluster_data, sparse table fixtures | VERIFIED | 196 lines, all 4 new fixtures present (two_cluster_data, eight_cluster_data, sparse_contingency_2x2, sparse_contingency_3x3) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| stat_engine.py | effect_sizes.py | `from abcd_phewas.effect_sizes import cohens_d, rank_biserial, cramers_v, epsilon_squared, monte_carlo_chi_square, bootstrap_ci` | WIRED | Line 21-28; all 6 functions imported and used in runner functions |
| stat_engine.py | type_detector.py | `from abcd_phewas.type_detector import VarType` | WIRED | Line 29; VarType used in dispatch table keys and runner signatures |
| stat_engine.py | pipeline.py | `PipelineResult` accepted by run_all_tests | WIRED | Line 546 accepts pipeline_result, accesses .df and .type_map; no direct import (duck typing) |
| stat_engine.py | concurrent.futures | `ProcessPoolExecutor` | WIRED | Line 13 import, line 599 usage in run_all_tests with executor.map |
| effect_sizes.py | scipy.stats | `bootstrap, chi2_contingency` | WIRED | Line 12 import, used in bootstrap_ci and monte_carlo_chi_square |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| STAT-01 | 02-02 | One-vs-rest comparison per cluster: KW for continuous/ordinal, chi-square/Fisher for binary/categorical | SATISFIED | run_mann_whitney (continuous/ordinal one-vs-rest), run_chi_square_pairwise (binary/categorical one-vs-rest) with Fisher fallback; dispatch table maps all types |
| STAT-02 | 02-02 | Global omnibus test per variable across all clusters | SATISFIED | run_kruskal_wallis (continuous/ordinal omnibus), run_chi_square_omnibus (binary/categorical omnibus); test_single_variable always produces omnibus row first |
| STAT-03 | 02-01 | Effect sizes: Cohen's d (continuous), Cramer's V (binary/categorical) | SATISFIED | cohens_d, cramers_v, rank_biserial, epsilon_squared all implemented with known-answer tests and cross-validation against scipy |
| STAT-04 | 02-03 (deferred) | Global FDR (BH) and Bonferroni correction | NOT IMPLEMENTED (by design) | Plan 02-03 explicitly states "STAT-04 and STAT-05 are NOT implemented here -- raw p-values only, no correction applied". test_run_all_tests_no_correction confirms no q_value or bonferroni_p columns. Phase 2 goal says "raw p-values". Correction belongs in Phase 3. |
| STAT-05 | 02-03 (deferred) | Within-domain FDR and Bonferroni correction | NOT IMPLEMENTED (by design) | Same as STAT-04. Deferred to Phase 3. |
| STAT-06 | 02-02, 02-03 | Support 2-8 clusters | SATISFIED | test_run_all_tests_2_clusters and test_run_all_tests_8_clusters both pass; test_single_variable produces K+1 rows for any K |

**Note on STAT-04/STAT-05:** These are assigned to Phase 2 in ROADMAP.md but explicitly deferred to Phase 3 by the plans. The Phase 2 goal says "raw p-values" and the Phase 3 goal says "FDR/Bonferroni correction". The REQUIREMENTS.md traceability table incorrectly marks them as "Complete". This should be corrected to "Deferred to Phase 3". Since the Phase 2 goal does NOT include correction, this is not a gap in Phase 2 goal achievement. However, the ROADMAP and REQUIREMENTS.md documentation should be updated.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none found) | - | - | - | No TODOs, FIXMEs, placeholders, empty implementations, or console.log patterns detected |

### Human Verification Required

None required. All Phase 2 deliverables are pure computation functions testable via automated tests. The 42 tests provide comprehensive coverage including known-answer validation, boundary conditions, cross-validation against scipy/statsmodels, and multi-cluster integration tests.

### Gaps Summary

No gaps found for Phase 2 goal achievement. All 5 ROADMAP success criteria are verified. All artifacts exist, are substantive, and are properly wired.

The only documentation issue is that STAT-04 and STAT-05 are listed under Phase 2 requirements in ROADMAP.md but are deferred to Phase 3. The REQUIREMENTS.md traceability table should be updated to reflect this deferral.

---

_Verified: 2026-03-05_
_Verifier: Claude (gsd-verifier)_
