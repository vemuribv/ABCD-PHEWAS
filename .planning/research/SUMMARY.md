# Project Research Summary

**Project:** ABCD PheWAS Cluster Characterization Pipeline
**Domain:** Phenome-Wide Association Study (PheWAS) — Python research pipeline for pubertal trajectory cluster characterization
**Researched:** 2026-03-04
**Confidence:** HIGH

## Executive Summary

This project is a batch research pipeline that characterizes pubertal trajectory clusters (derived from CRLI) by testing their associations across 3,000+ ABCD Study phenotype variables. Expert PheWAS pipelines of this type follow a linear, staged architecture: load and validate inputs, classify variables, run statistical tests, apply global multiple comparison correction, assemble results, then generate visualizations. The key design decisions are: (1) non-parametric tests (Kruskal-Wallis and chi-square/Fisher) over regression models, since the exposure is categorical and there are no random effects to model; (2) a one-vs-rest per-cluster framing rather than a single global test; and (3) correction applied globally across all tests simultaneously, not per-cluster or per-domain. No existing Python PheWAS library (pyPheWAS, PYPE) handles ABCD-style mixed phenotype arrays — a custom dispatcher is required.

The recommended stack is Python 3.11 with pandas 3.x, scipy, statsmodels, seaborn/matplotlib, and pingouin for effect sizes. This combination covers all required tests natively and has verified version compatibility as of 2026-03. The pipeline architecture separates data loading, classification, testing, correction, and visualization into independent modules with clean data contracts, which makes each stage independently testable and replaceable.

The dominant risks are methodological rather than technical. The most critical is circular analysis: pubertal variables used to construct CRLI clusters must be explicitly blocked from the PheWAS phenotype matrix before any tests run. A close second is ABCD family structure (21% of subjects have enrolled siblings) — violating test independence inflates false positive rates. Both risks have clear prevention strategies that must be baked into Phase 1 data loading, before any statistical logic is written.

---

## Key Findings

### Recommended Stack

The core pipeline runs on scipy (Kruskal-Wallis, chi-square, Fisher's exact), statsmodels (Benjamini-Hochberg and Bonferroni via `multipletests`), and pingouin (effect sizes). These three libraries together cover all required statistical operations. pandas 3.x with the pyarrow backend handles the wide phenotype DataFrame (3,000+ columns, ~10k subjects) without memory issues. Visualization uses matplotlib for Manhattan plots (domain-colored x-axis, custom significance lines) and seaborn for heatmaps (diverging palette, ordered rows/columns). The `adjustText` library prevents label collisions on Manhattan plots. No external PheWAS libraries are used — pyPheWAS is ICD-code specific, and PYPE assumes a continuous genotype predictor.

**Core technologies:**
- Python 3.11: runtime — 3.11 is the safest choice; 3.12 has minor statsmodels rough edges
- pandas 3.0.1: data loading and merging — pyarrow backend handles wide DataFrames efficiently; copy-on-write prevents silent mutation
- scipy 1.17.1: all statistical tests — authoritative source for kruskal, chi2_contingency, fisher_exact; 1.15+ added `false_discovery_control`
- statsmodels 0.14.6: multiple comparison correction — `multipletests` handles both FDR-BH and Bonferroni in one call
- pingouin 0.6.0: effect sizes — returns Cohen's d and eta-squared directly; use only for significant hits (too slow for full 3,000-variable loop)
- seaborn 0.13.2 + matplotlib 3.10.8: visualizations — heatmap and Manhattan plot; seaborn 0.13 confirmed compatible with matplotlib 3.10
- adjustText 1.3.0: non-overlapping labels on Manhattan plot — required for publication-quality output
- uv: package and environment management — 10-100x faster than pip/venv; use `uv venv` + `uv pip install`

### Expected Features

The pipeline's v1 scope is defined by what is required to produce a valid, reviewable, and publishable result. All table-stakes features must ship together — they are interdependent (variable type detection gates every downstream step). The existing ABCD R codebase provides domain names, color palette, preprocessing logic (skewness/winsorize/INT), and output format conventions that should be preserved for consistency.

**Must have (table stakes):**
- Variable type detection (binary/categorical/ordinal/continuous) — gates all test routing and effect size selection
- Missing data handling with NA sentinel detection — ABCD uses -999, 777, 999 sentinel codes that pandas will not auto-detect
- Continuous variable preprocessing: skewness check, winsorization (mean ± 3 SD), rank-based INT — established ABCD PheWAS precedent
- One-vs-rest Kruskal-Wallis and chi-square/Fisher per cluster — core research question
- Global omnibus Kruskal-Wallis/chi-square across all clusters — tests global null
- Effect sizes: Cohen's d (continuous), Cramer's V and odds ratio (binary/categorical) — p-values alone insufficient at N ~3,000
- FDR (Benjamini-Hochberg) and Bonferroni correction applied globally — both required; correction must span all variables and all clusters simultaneously
- Domain assignment via regex mapping (8 ABCD domains) — required for Manhattan plot ordering and interpretability
- CRLI input variable blocklist — circular analysis prevention; must run before any tests
- Results table CSV output (variable, domain, test_type, statistic, p_value, fdr_q, bonferroni_p, effect_size, ci_low, ci_high, cluster_label, n_cluster, n_rest, missingness_rate)
- Manhattan-style PheWAS plot per cluster (one-vs-rest) and global — canonical PheWAS output; must be publication quality at 300 DPI

**Should have (v1.x — after initial results validated):**
- Heatmap of significant results: clusters x significant variables, effect size fill with diverging palette — essential for papers with >2 clusters
- Within-domain FDR correction (in addition to global) — published ABCD PheWAS standard (PMC11383484)
- Preprocessing report documenting per-variable transformation decisions — required for methods section
- Summary statistics table per cluster for significant variables — required for supplementary tables
- Volcano plot (effect size vs -log10(p)) — standard complement to Manhattan plot

**Defer (v2+):**
- Covariate adjustment (site, scanner residualization) — defer until site effects are empirically assessed
- Configurable YAML/JSON domain mapping — defer until regex approach proves insufficient
- Neuroimaging domain expansion — defer until psychosocial PheWAS is validated

### Architecture Approach

The pipeline is a linear staged batch processor. Each stage produces a well-defined artifact consumed by the next. The dispatcher pattern routes each variable to the correct statistical test based on type, which is classified once on the full dataset before any tests run — never inside the test loop. All p-values from all tests (global and one-vs-rest across all clusters) are accumulated into a single flat list and corrected once, not per-cluster. Plots are generated last, as read-only consumers of the final corrected results table. The build order is: loader → classifier → correction module (can be built/tested in isolation) → global tests → one-vs-rest tests → effects → results assembler → Manhattan plot → heatmap.

**Major components:**
1. Data Loader (loader.py) — joins cluster assignments and phenotype file on subject ID; applies CRLI blocklist; validates sex stratum; detects sentinel values
2. Variable Classifier (classifier.py) — infers type per column (binary/categorical/ordinal/continuous); flags high-missingness variables; maps variables to ABCD domains via TSV lookup
3. Statistical Test Engine (tests/global_tests.py, tests/one_vs_rest.py) — dispatcher routes to correct test per type; collects results in tidy schema
4. Effect Size Calculator (effects.py) — Cohen's d, odds ratio, Cramer's V, eta-squared; called on all hits not just significant ones
5. Multiple Comparison Corrector (correction.py) — BH-FDR and Bonferroni applied once to full p-value array
6. Results Assembler (results.py) — merges all stats into tidy DataFrame; writes TSV
7. Manhattan Plotter (plots/manhattan.py) — domain-colored x-axis, -log10(p) y-axis, significance lines, direction markers, adjustText labels
8. Heatmap Generator (plots/heatmap.py) — significant variables x clusters, effect direction encoding, domain color bar

### Critical Pitfalls

1. **Circular analysis (double dipping)** — Test the phenotype matrix for any variable name overlapping with CRLI clustering inputs (PDS items, hormone variables). Apply a named blocklist in the data loader before any test runs. Grep output results for `pds`, `hormone`, `testosterone`, `estradiol`, `dhea` as a post-hoc check.

2. **Multiple comparison correction on wrong denominator** — FDR and Bonferroni must be applied to a flat array of ALL p-values (global tests + one-vs-rest for ALL clusters simultaneously). Per-cluster correction severely undercorrects. Add an assertion: `len(p_value_array) == n_variables * (n_clusters + 1)`.

3. **ABCD sentinel values treated as categories** — ABCD encodes missing data as -999, 777 (don't know), 999 (refused). Without explicit `na_values` in `read_csv`, these appear as a data category in chi-square tests. Load with explicit sentinel list; spot-check 5 known CBCL variables with 777/999 codes.

4. **ABCD family structure non-independence** — 21% of ABCD subjects have enrolled siblings, violating test independence assumptions. Decision required before building tests: permutation testing (preserving family structure) or one-sibling-per-family subsetting. This choice affects the entire pipeline architecture.

5. **Wrong test for variable type** — Applying parametric tests to ordinal/binary variables, or applying chi-square when expected cell counts are below 5. Implement and unit-test the test-selector with synthetic data covering all four variable types before running on ABCD data. For binary variables: switch to Fisher's exact when >20% of expected cells fall below 5 (not the old "any cell below 5" rule).

6. **Domain mapping gaps** — ABCD variables from derived files may not match dictionary table names. Assert zero NULL domain values before generating Manhattan plot. Assign unmatched variables to "Other/Unclassified" domain rather than dropping.

---

## Implications for Roadmap

Based on the dependency graph (variable type detection gates everything; domain mapping is independent; correction must see all p-values; plots must see final corrected results), a 4-phase structure is recommended:

### Phase 1: Data Foundation
**Rationale:** All statistical work depends on clean, correctly typed data. The CRLI blocklist and ABCD sentinel detection must be in place before any tests run — fixing these after statistical results exist requires a full rerun. This phase has no external dependencies and can be validated on real data before any statistical logic is written.
**Delivers:** Merged DataFrame with validated subject IDs, classified variable types, domain labels, sentinel-clean data, CRLI blocklist applied, sex stratum validated.
**Addresses features:** Variable type detection, missing data handling, domain assignment, CRLI input variable exclusion.
**Avoids pitfalls:** Circular analysis, missing data sentinels as categories, domain mapping gaps, sex column in phenotype matrix, subject ID type mismatch.
**Build order:** loader.py → classifier.py (with domain TSV) → data validation assertions.

### Phase 2: Statistical Core
**Rationale:** The test engine is the most complex and most testable component. Build and validate it with unit tests on synthetic data before running on ABCD. Includes preprocessing (skewness/winsorize/INT), the dispatcher, and effect size calculation — these are tightly coupled and should be built together.
**Delivers:** Per-variable test results (global + one-vs-rest for all clusters) with raw p-values and effect sizes in tidy schema. No correction yet — this phase produces the raw material for Phase 3.
**Addresses features:** Skewness-based preprocessing (winsorize + INT), one-vs-rest Kruskal-Wallis/chi-square/Fisher, global omnibus test, Cohen's d + Cramer's V effect sizes, minimum sample size guards.
**Avoids pitfalls:** Wrong test for variable type, effect size absent from outputs, low-prevalence binary variables, Fisher's exact performance trap (apply only when cell counts require it).
**Build order:** tests/global_tests.py → tests/one_vs_rest.py → effects.py.

### Phase 3: Correction and Results
**Rationale:** Correction must be applied after ALL tests are complete — it is a pure function over the full p-value array. This phase is short but statistically critical. Once results are written to TSV, the analysis is validatable before investing in visualization.
**Delivers:** Final results.tsv with FDR-BH and Bonferroni corrected values for all (variable, cluster) pairs. Reviewable intermediate output.
**Addresses features:** FDR (Benjamini-Hochberg) correction, Bonferroni correction, results table CSV output.
**Avoids pitfalls:** Correction on wrong denominator (assert array length), FDR correlation assumption (report both BH-FDR and Bonferroni; note FDR limitations in output headers).
**Build order:** correction.py → results.py.

### Phase 4: Visualization
**Rationale:** Plots are read-only consumers of the final results table. Building them last means they always reflect validated, corrected results. Manhattan plot is the canonical PheWAS output and should be completed before the heatmap.
**Delivers:** Publication-quality Manhattan plots (per-cluster + global), heatmap of significant variables across clusters, volcano plots (v1.x).
**Addresses features:** Manhattan-style PheWAS plot, effect direction markers (up/down triangles), domain color coding, FDR and Bonferroni threshold lines, adjustText labels on significant hits, heatmap (significant variables x clusters).
**Uses stack:** matplotlib 3.10.8 (Manhattan, custom x-axis), seaborn 0.13.2 (heatmap with `col_cluster=False, row_cluster=False`), adjustText 1.3.0 (label placement).
**Avoids pitfalls:** Generating plots before correction is complete; using seaborn.clustermap (which reorders clusters) instead of seaborn.heatmap.
**Build order:** plots/manhattan.py → plots/heatmap.py → plots/volcano.py (v1.x).

### Phase Ordering Rationale

- Data foundation must precede all statistical work because type classification must be done once on the full dataset. Re-classifying inside the test loop produces inconsistent types across cluster subsets.
- Statistical core precedes correction because correction operates on the complete p-value array. Writing tests in batches and correcting between batches is the most common FDR implementation error in PheWAS.
- Correction precedes visualization because plots require final corrected p-values. Generating Manhattan plots from raw p-values and re-running after correction is a common source of inconsistency between figures and tables.
- Phase 1 (data foundation) includes the CRLI blocklist check — this is deliberately first because circular analysis is unrecoverable without a full rerun and the cost is zero to prevent early.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 1 (Data Foundation):** ABCD family structure decision (permutation vs. one-sibling-per-family subsetting) requires reviewing the specific cluster assignment files to know how many families are split across clusters. This is ABCD-specific and worth a targeted investigation before building Phase 2.
- **Phase 2 (Statistical Core):** Family structure implementation — if permutation is chosen, the permutation architecture significantly changes how the test engine is built. Resolve the family structure decision in Phase 1 before building Phase 2.

Phases with standard patterns (skip additional research):
- **Phase 3 (Correction):** statsmodels `multipletests` is the established standard; implementation is a single function call with a well-defined interface.
- **Phase 4 (Visualization):** Manhattan plot and heatmap patterns are well-documented. seaborn.heatmap with `col_cluster=False, row_cluster=False` is the confirmed approach.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Versions verified via PyPI JSON API (2026-03-04); official docs confirmed function signatures and version compatibility |
| Features | HIGH | Table stakes derived from existing codebase + published ABCD PheWAS standards (PMC11383484); differentiators cross-validated against multiple ABCD PheWAS papers |
| Architecture | HIGH | Core pipeline pattern confirmed across PYPE, PheTK, R PheWAS package; dispatcher and tidy schema patterns are industry standard for mass-testing pipelines |
| Pitfalls | HIGH | 10 pitfalls with sources; ABCD-specific pitfalls (family structure, sentinel values, circular analysis) sourced from peer-reviewed ABCD methodology papers |

**Overall confidence:** HIGH

### Gaps to Address

- **Family structure decision:** Whether to use permutation testing (preserving family structure) or one-sibling-per-family subsetting has not been decided. This is the most significant open architectural question. Permutation requires significant additional infrastructure; subsetting is simpler but reduces sample size. Needs a decision before Phase 2 begins.
- **CRLI input variable list:** The exact set of variables used in CRLI cluster construction needs to be confirmed with the research team before building the blocklist. The blocklist is a named constant in the pipeline, not a computed value.
- **Cluster assignment file format:** The format of the cluster assignment file (CSV column names, subject ID format, number of clusters) needs to be confirmed before building loader.py. ARCHITECTURE.md assumes `src_subject_id` and a `cluster_label` column.
- **Domain mapping coverage:** The 8 domains from the existing R codebase need to be validated against the specific ABCD release being used. Domain TSV file (`data/domain_map.tsv`) will need manual curation for any variables not covered by the existing regex patterns.
- **Covariate adjustment decision (TBD in PROJECT.md):** Site/scanner effects need empirical assessment before deciding whether to implement covariate residualization. This is a Phase 1 question to answer by examining cluster distributions across sites.

---

## Sources

### Primary (HIGH confidence)
- PyPI JSON API (2026-03-04) — pandas 3.0.1, scipy 1.17.1, statsmodels 0.14.6, matplotlib 3.10.8, seaborn 0.13.2, pingouin 0.6.0, scikit-posthocs 0.12.0, adjustText 1.3.0
- SciPy 1.17 official docs — chi2_contingency, fisher_exact, kruskal signatures
- statsmodels 0.14/0.15 docs — multipletests interface and method options
- pyPheWAS documentation — confirmed ICD-code-only scope (negative finding)
- PMC11383484 (ABCD CRP PheWAS, 2024) — preprocessing standards, domain-specific correction, ABCD phenotype counts
- PMC9156875 (ABCD practical guide) — ABCD-specific missing data, family structure, covariate selection
- PMC2841687 (circular analysis / double dipping) — circular analysis methodology
- Existing codebase: `PheWAS Analyses Resub5.Rmd` — domain names, color palette, preprocessing pipeline, output format

### Secondary (MEDIUM confidence)
- PYPE paper (Cell Patterns, 2024) — statsmodels as standard for mass regression PheWAS in Python; pipeline architecture patterns
- PheTK (Bioinformatics, 2025) — large-scale biobank PheWAS architecture patterns
- Python Graph Gallery: Manhattan Plot with Matplotlib — domain-colored PheWAS Manhattan plot pattern
- ABCD Data Dictionary — table-name-based domain grouping as standard approach
- Wharton Penn within-domain correction paper — within-domain FDR correction rationale

### Tertiary (LOW confidence)
- PMC10309061 (LOAD genetic risk in ABCD) — Bonferroni/FDR usage patterns (context only)
- bioRxiv: scanner differences in ABCD — multi-site batch effects (context for covariate adjustment decision)

---
*Research completed: 2026-03-04*
*Ready for roadmap: yes*
