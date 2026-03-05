# Phase 2: Statistical Core - Context

**Gathered:** 2026-03-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Per-variable statistical test engine producing raw p-values, effect sizes (with CIs), and test metadata for one-vs-rest cluster comparisons and global omnibus tests. Accepts Phase 1's PipelineResult (df, type_map, domain_map). Does NOT apply multiple comparison correction (that's Phase 3).

</domain>

<decisions>
## Implementation Decisions

### Omnibus vs One-vs-Rest Design
- KW across all K clusters IS the omnibus for continuous/ordinal variables (no separate omnibus KW)
- Chi-square across all K clusters IS the omnibus for binary/categorical variables
- One-vs-rest uses Mann-Whitney U for continuous/ordinal (target cluster vs pooled rest)
- One-vs-rest uses chi-square or Fisher's exact for binary/categorical (target vs rest contingency table)
- P-value count assertion: n_variables x (n_clusters + 1) where +1 is the omnibus

### Effect Size Coverage
- **Continuous one-vs-rest:** Cohen's d (target cluster vs pooled rest)
- **Ordinal one-vs-rest:** Rank-biserial correlation from Mann-Whitney U (directional, -1 to +1)
- **Binary/categorical one-vs-rest:** Cramer's V from 2xL contingency table
- **Continuous/ordinal omnibus:** Epsilon-squared (e^2) from Kruskal-Wallis (0 to 1)
- **Binary/categorical omnibus:** Cramer's V from KxL contingency table
- Confidence intervals computed in Phase 2 alongside effect sizes (bootstrap or analytic)

### Fisher's Exact Fallback Rules
- For 2x2 tables: use Fisher's exact when any expected cell count < 5 (Cochran's rule)
- For larger tables (>2x2) with sparse cells: chi-square with simulated p-value (Monte Carlo, like R's simulate.p.value=TRUE)
- Fisher's exact NOT used for tables larger than 2x2 (computational cost)

### Test Logging
- Results include a 'test_used' column: 'kruskal_wallis', 'mann_whitney', 'chi_square', 'fisher_exact', 'chi_square_simulated'
- Full transparency for methods section reporting

### Output Format
- Results DataFrame: one row per (variable, comparison) pair
- Columns: variable, comparison_type (omnibus/one_vs_rest), cluster_label, test_used, statistic, p_value, effect_size, effect_size_type, ci_lower, ci_upper, n_target, n_rest
- Easy to pass directly to Phase 3 for correction and output generation

### Correction Scope (Resolved)
- STAT-04 (global FDR/Bonferroni) and STAT-05 (within-domain FDR/Bonferroni) deferred to Phase 3
- Phase 2 produces raw p-values ONLY
- This resolves the roadmap/requirements discrepancy: Phase 2 = test engine, Phase 3 = correction + output

### Claude's Discretion
- Test engine module structure (single module vs split by test type)
- Synthetic data generation for unit tests
- Parallelization strategy for running tests across 3,000+ variables
- Bootstrap parameters (n_resamples for CIs)
- Exact Monte Carlo simulation parameters (n_replicates for simulated chi-square)

</decisions>

<specifics>
## Specific Ideas

- Unit tests on synthetic data must pass before any ABCD data is processed (success criteria #1)
- Must work unchanged for 2-cluster and 8-cluster assignments (success criteria #3)
- Effect sizes computed for ALL (variable, cluster) pairs, not just significant ones (success criteria #4)
- The R codebase (`PheWAS Analyses Resub5.Rmd`) serves as reference for test selection logic

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `VarType` enum (type_detector.py): BINARY, ORDINAL, CATEGORICAL, CONTINUOUS — drives test selection
- `PipelineResult` dataclass (pipeline.py): provides df, type_map, domain_map, missingness
- `PipelineConfig` dataclass (config.py): holds all configuration parameters

### Established Patterns
- Pipeline uses dataclass-based config and result objects
- Loguru for logging (type_detector.py), stdlib logging (pipeline.py) — mixed but functional
- Phase 1 code lives in `src/abcd_phewas/` package with tests in `tests/`

### Integration Points
- Input: `PipelineResult` from `run_pipeline()` — df has preprocessed phenotype columns, type_map classifies each
- Output: Results DataFrame consumed by Phase 3 for correction, CSV generation, and plotting
- Test engine should be callable independently (not only via full pipeline) for unit testing

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-statistical-core*
*Context gathered: 2026-03-05*
