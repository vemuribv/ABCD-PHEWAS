---
status: complete
phase: 02-statistical-core
source: 02-01-SUMMARY.md, 02-02-SUMMARY.md, 02-03-SUMMARY.md
started: 2026-03-05T10:30:00Z
updated: 2026-03-05T11:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Effect Size Functions
expected: All six effect-size functions (cohens_d, rank_biserial, cramers_v, epsilon_squared, monte_carlo_chi_square, bootstrap_ci) import and return valid numeric results on synthetic data. bootstrap_ci returns a (low, high) tuple.
result: pass

### 2. Stat Engine Dispatch Table
expected: test_single_variable produces K+1 result rows (1 omnibus + K one-vs-rest) for a given variable. Each row has exactly 12 columns. First row is omnibus (Kruskal-Wallis), remaining are one-vs-rest (Mann-Whitney).
result: pass

### 3. Sparse Fallback Chain
expected: When a contingency table has expected cell counts < 5, the engine falls back to Fisher exact (2x2) or Monte Carlo chi-square (larger). The one-vs-rest row should use fisher_exact for sparse 2x2 tables.
result: pass

### 4. run_all_tests Orchestrator
expected: run_all_tests processes multiple variables from a PipelineResult and returns a DataFrame with n_variables * (n_clusters+1) rows and 12 columns. No NaN in p_value.
result: pass

### 5. Full Test Suite Green
expected: All 117+ tests pass with no failures or errors.
result: pass

## Summary

total: 5
passed: 5
issues: 0
pending: 0
skipped: 0

## Gaps

[none yet]
