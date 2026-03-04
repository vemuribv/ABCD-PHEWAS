# Feature Research

**Domain:** PheWAS cluster characterization pipeline (ABCD Study, pubertal trajectory clusters)
**Researched:** 2026-03-04
**Confidence:** HIGH for table stakes; MEDIUM for differentiators (patterns from published ABCD PheWAS literature and existing codebase)

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features the analysis cannot be considered complete without. Missing any of these means the output cannot be published or trusted.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Variable type detection and routing | Different tests required for binary, categorical, ordinal, continuous variables; wrong test = invalid statistics | MEDIUM | Existing ABCD Rmd uses lmer (continuous) vs glmer-binomial (binary). New pipeline should use Kruskal-Wallis (continuous/ordinal) and chi-square/Fisher (binary/categorical) for non-parametric cluster comparison, since there are no random effects to model |
| One-vs-rest statistical tests per cluster | Core research question: "what defines this cluster vs all others?"; without this the analysis is uninterpretable | HIGH | For each cluster k: subjects in k vs all others pooled. Run per-variable test for each cluster. K tests per variable. |
| Global omnibus test per variable | Required to identify variables that differ across *any* cluster, independent of one-vs-rest | MEDIUM | Kruskal-Wallis (continuous/ordinal), chi-square (binary/categorical) across all cluster groups simultaneously |
| FDR correction (Benjamini-Hochberg) | Standard in ABCD PheWAS publications; controls false discovery at 5% across 3000+ tests | LOW | Apply globally across all variables and all cluster comparisons. The existing ABCD Rmd uses `p.adjust(method="fdr")` |
| Bonferroni correction | Conservative threshold shown alongside FDR; required in publication to demonstrate robustness of top hits | LOW | Apply globally. Show both thresholds on plots simultaneously |
| Effect size reporting | p-values alone are insufficient; Cohen's d (continuous) and Cramer's V or odds ratio (binary/categorical) required for publication | MEDIUM | Continuous: Cohen's d = mean difference / pooled SD. Binary: odds ratio + Cramer's V. Include confidence intervals. |
| Results table output (CSV) | All downstream analysis (manual review, supplementary tables) requires machine-readable output | LOW | Columns: variable, domain, test_type, statistic, p_value, fdr_q, bonferroni_p, effect_size, ci_low, ci_high, cluster_label, n_cluster, n_rest, missingness_rate |
| Domain assignment from ABCD data dictionary | The x-axis grouping of the Manhattan plot and the interpretive scaffold of the analysis; without domains the results are a wall of variable names | MEDIUM | Existing Rmd uses regex pattern matching on variable name prefixes (e.g., `ksad`, `cbcl` → Child Mental Health; `nihtbx`, `RAVLT` → Cognition). 8 domains identified in existing code: Cognition, Screen Time, Demographics, Substance, Culture/Environment, Physical Health, Family Mental Health, Child Mental Health |
| Manhattan-style PheWAS plot | The canonical PheWAS output; expected by any reviewer of ABCD PheWAS work | MEDIUM | x-axis: variables ordered by domain (not chromosome position). y-axis: -log10(p). Points colored by domain. FDR and Bonferroni threshold lines. Direction indicator (up/down triangle). Labels on FDR-significant hits. One plot per cluster (one-vs-rest), plus one global plot. |
| Missing data handling | ABCD variables have substantial missingness; analysis must not silently include samples with NA values or crash on all-NA columns | MEDIUM | Per-variable: exclude subjects with NA for that variable. Report missingness rate per variable. Skip variables below minimum N threshold (e.g., <50 non-missing per group). |
| Minimum sample size guards | Sparse cells break chi-square; Fisher is needed when expected cell counts are <5; skipping variables with insufficient data prevents spurious results | MEDIUM | For binary: if any expected cell count <5, switch to Fisher's exact. Skip variable entirely if any comparison group has <10 subjects |

---

### Differentiators (Competitive Advantage)

Features that elevate this from a working analysis to a publication-ready, reusable pipeline.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Heatmap of significant results across clusters | Shows the full pattern of cluster differences in a single figure; essential for papers with >2 clusters; allows readers to compare cluster profiles at a glance | MEDIUM | Rows: variables significant at FDR < 0.05 in any cluster. Columns: clusters. Cell fill: effect size (Cohen's d or log odds ratio), diverging color scale. Significance markers overlaid (*/**). Rows sorted by domain. seaborn or matplotlib with custom domain color bar on left. |
| Within-domain multiple testing correction | ABCD PheWAS publications (2024) apply Bonferroni corrections within each domain separately, not globally; domain-specific correction increases power within domains while controlling error properly | MEDIUM | Apply FDR within each domain separately in addition to the global FDR. Report both. Thresholds: global FDR/Bonf, domain-specific FDR/Bonf. Already done in published ABCD PheWAS work (PMC11383484). |
| Effect direction markers on Manhattan plot | Immediately communicates enrichment vs depletion without requiring the reader to look up the effect size table | LOW | Upward triangle = cluster enriched (higher than rest); downward triangle = depleted. Already implemented in existing ABCD Rmd. |
| Configurable domain mapping (YAML/JSON) | Hard-coded regex is brittle; a mapping file that can be updated as the ABCD data dictionary changes makes the pipeline reusable across timepoints and data releases | MEDIUM | Domain map: list of (domain_name, regex_patterns, color). Loaded at runtime. Allows adding neuroimaging domains, new ABCD variables, etc. without code changes. |
| Summary statistics table per cluster | Descriptive stats (mean, SD, median, prevalence) for each significant variable broken down by cluster; required for supplementary tables | LOW | Per significant variable: cluster k mean/SD or n/% vs rest mean/SD or n/%. Machine-readable and human-readable formats. |
| Preprocessing report | Documents per-variable transformation decisions (skewness, winsorization, rank normalization applied); allows reviewer to audit preprocessing choices | MEDIUM | Existing ABCD Rmd manually applies: skewness check (|skew| > 1.96), winsorization (mean ± 3 SD), rank-based inverse normal transformation (INT). Report which variables received each treatment. |
| Skewness-based preprocessing for continuous variables | Continuous variables with |skew| > 1.96 are winsorized then INT-transformed; this follows established ABCD precedent and improves test validity | MEDIUM | Existing Rmd implements this with psych::describe + DescTools::Winsorize + rank-based INT (RNOmni). Python equivalents: scipy.stats.skew, scipy.stats.mstats.winsorize, scipy.stats.rankdata + scipy.stats.norm.ppf. |
| Volcano plot (effect size vs -log10(p)) | Standard complement to Manhattan plot; shows both significance and effect magnitude; useful for identifying small-effect significant hits vs large-effect sub-threshold hits | LOW | One per cluster. x-axis: effect size (Cohen's d or log odds ratio). y-axis: -log10(p). Color by domain or significance status. |
| Cluster size and composition summary | Reports N per cluster, sex distribution (should be 100% one sex since stratified), and basic demographics; required for any publication methods section | LOW | Output: per-cluster N, age statistics of cluster members from phenotype file. |
| Configurable covariate adjustment | Optional site/scanner adjustment via linear regression residualization before testing; PROJECT.md marks this as TBD but likely needed if site effects are present | HIGH | Residualize each continuous variable on covariates (e.g., site, scanner) before testing. For binary: include as additional variable in logistic test. Flag: --covariates site_id scanner_id. Implement last. |

---

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem helpful but should be deliberately excluded from scope.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Mixed-effects models (lmer/glmer) for cluster comparison | Existing ABCD Rmd uses lmer/glmer with random effects for site and family; natural instinct to reuse | Clusters from CRLI are the grouping variable, not a fixed predictor in a regression. Site and family ID are not available as random effects in the cluster-characterization framing. Using lmer would require restructuring the problem as regression (cluster label → phenotype) which works but adds convergence failures, is slower by 100x for 3000 variables, and is unnecessary for a descriptive one-vs-rest comparison where Kruskal-Wallis/chi-square are the appropriate and standard tests | Use Kruskal-Wallis (continuous/ordinal) and chi-square/Fisher (binary/categorical) for cluster comparisons. These are non-parametric, assumption-light, and fast. |
| Causal inference / mediation analysis | Researchers may want to know if pubertal timing *causes* downstream phenotype differences | Out of scope by design (PROJECT.md). This analysis is explicitly associational/descriptive. Adding causal machinery would require upstream CRLI cluster definitions to have causal identification assumptions they don't have. | Stay descriptive. State in methods: "associations, not causal estimates." Longitudinal causal analysis is a separate project. |
| Interactive web dashboard | Tempting for exploratory review of 3000+ variables | Adds significant engineering overhead (Dash, Plotly, deployment) with minimal publication value. The pipeline is for a specific analysis, not a general-purpose exploration tool. | Static publication-quality plots (PNG/PDF, 300 DPI) are the correct output format. |
| Real-time / streaming analysis | Running tests as data arrives | Not applicable. Data is a fixed snapshot from ABCD. Analysis runs as a batch job. | Batch processing with progress reporting (tqdm) is sufficient. |
| Longitudinal PheWAS (phenotype change over time) | ABCD has multiple timepoints; might be tempting to test change scores | Out of scope by design. Each timepoint is an independent analysis. Merging timepoints introduces complex missing data patterns and conflates age effects with time effects. | Run the same pipeline separately on baseline and follow-up phenotype files. |
| Automated variable labeling via LLM | Existing Rmd loads `openai` library, suggesting someone considered GPT-based labeling | Adds API dependency, cost, rate limits, and non-reproducibility. ABCD variable names already have human-readable labels in the data dictionary. | Map variable names to labels using the ABCD data dictionary (available as a CSV/Excel lookup table). |
| Automatic test selection between parametric and non-parametric based on normality | Shapiro-Wilk or similar tests to choose between ANOVA and Kruskal-Wallis per variable | Double-dipping: testing normality and then choosing the test based on that result inflates type I error. | Always use Kruskal-Wallis for continuous/ordinal (it is nearly as powerful as ANOVA when n is large, and ABCD has n~5000), and chi-square/Fisher for binary/categorical. Decision is made on variable type, not on normality test result. |
| Phenotype imputation | Multiple imputation (MICE) for missing data | Adds substantial complexity and run time. Imputed values would be used in null hypothesis tests, making the interpretation ambiguous. | Listwise deletion per variable (each variable tested only in subjects with non-missing data). Report missingness rate. Exclude variables with >50% missingness. |

---

## Feature Dependencies

```
[Variable type detection]
    └──required by──> [Statistical testing (Kruskal-Wallis vs chi-square routing)]
    └──required by──> [Effect size reporting (Cohen's d vs odds ratio routing)]
    └──required by──> [Missing data handling (NA exclusion per variable)]

[Statistical testing]
    └──required by──> [FDR correction]
    └──required by──> [Bonferroni correction]
    └──required by──> [Results table output]

[Domain assignment]
    └──required by──> [Manhattan plot]
    └──required by──> [Heatmap (row ordering and color bar)]
    └──required by──> [Within-domain multiple testing correction]

[Results table output]
    └──required by──> [Manhattan plot]
    └──required by──> [Heatmap]
    └──required by──> [Volcano plot]
    └──required by──> [Summary statistics table]

[One-vs-rest testing]
    └──required by──> [Per-cluster Manhattan plot]
    └──required by──> [Heatmap (one column per cluster)]

[Global omnibus test]
    └──required by──> [Global Manhattan plot]

[Skewness-based preprocessing]
    └──enhances──> [Statistical testing] (reduces false positives from extreme outliers)
    └──feeds into──> [Preprocessing report]

[Configurable domain mapping]
    └──enhances──> [Domain assignment] (replaces hard-coded regex with configurable file)
    └──enables──> [Within-domain correction] (domain membership is explicit, not implicit)

[Covariate adjustment]
    └──conflicts with──> [Non-parametric testing] (residualization is a separate linear step that precedes the non-parametric test; must be implemented as pre-processing, not as model covariates)
```

### Dependency Notes

- **Variable type detection requires nothing**: It is the root of the dependency tree. It must be the first step in the analysis loop.
- **Domain assignment is independent of statistical testing**: Domain mapping can be loaded at startup from a config file and joined to results after testing.
- **Skewness-based preprocessing enhances statistical testing**: Apply only to continuous variables before running Kruskal-Wallis. Does not affect binary/categorical path.
- **Covariate adjustment conflicts with the non-parametric test framing**: If needed, implement as residualization (regress covariate out of continuous variable, test residuals with Kruskal-Wallis). Do not add covariates as parameters inside the test.
- **Within-domain correction requires domain assignment first**: You cannot compute domain-specific FDR until variables are assigned to domains.

---

## MVP Definition

### Launch With (v1)

Minimum needed to produce a valid, reviewable result.

- [ ] Variable type detection (binary, categorical, ordinal, continuous) — gating for all test routing
- [ ] Missing data handling with per-variable N reporting — prevents silent invalid tests
- [ ] Skewness check, winsorization, and rank-based INT for continuous variables — follows ABCD PheWAS precedent; without this, extreme skew inflates false positives
- [ ] One-vs-rest Kruskal-Wallis (continuous/ordinal) and chi-square/Fisher (binary/categorical) — the core analysis
- [ ] Global omnibus Kruskal-Wallis / chi-square — tests global null across all clusters
- [ ] Effect size: Cohen's d (continuous), Cramer's V (categorical/binary) — required for publication
- [ ] FDR (Benjamini-Hochberg) and Bonferroni correction — both required; established in field
- [ ] Domain assignment via configurable regex mapping — needed for Manhattan plot ordering and interpretability
- [ ] Results table CSV output (one row per variable per cluster) — all downstream work depends on this
- [ ] Manhattan-style PheWAS plot (one-vs-rest per cluster + global) — canonical output; must be publication quality (300 DPI, domain colors, threshold lines, direction markers, FDR-labeled hits)

### Add After Validation (v1.x)

Add once v1 produces a reviewable result and the domain mapping is validated.

- [ ] Heatmap (clusters x significant variables, effect size fill) — add after confirming which variables are significant; layout depends on number of hits
- [ ] Within-domain FDR correction — add when global results are in hand; requires deciding on domain boundary definitions
- [ ] Preprocessing report (which variables received which transformation) — add for methods section documentation
- [ ] Summary statistics table per cluster (mean/SD or n/% per significant variable) — add for supplementary tables
- [ ] Volcano plot (effect size vs significance) — add as a second visualization for significant variables

### Future Consideration (v2+)

Defer until v1 is validated and there is a clear need.

- [ ] Covariate adjustment (site, scanner) — defer until site effects are empirically assessed in the data; adding before knowing if it's needed introduces risk of over-correcting
- [ ] Configurable domain mapping file (YAML/JSON) — defer until the regex-based approach proves insufficient; premature abstraction
- [ ] Neuroimaging domain expansion — defer until the psychosocial PheWAS is validated; adds complexity and different variable structure

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Variable type detection | HIGH | MEDIUM | P1 |
| Missing data handling + N guards | HIGH | LOW | P1 |
| Continuous variable preprocessing (skewness, winsorize, INT) | HIGH | MEDIUM | P1 |
| One-vs-rest Kruskal-Wallis / chi-square | HIGH | MEDIUM | P1 |
| Global omnibus test | HIGH | LOW | P1 |
| Cohen's d + Cramer's V effect sizes | HIGH | MEDIUM | P1 |
| FDR + Bonferroni correction | HIGH | LOW | P1 |
| Domain assignment (regex-based) | HIGH | MEDIUM | P1 |
| Results table CSV output | HIGH | LOW | P1 |
| Manhattan plot (publication quality) | HIGH | MEDIUM | P1 |
| Heatmap (clusters x significant variables) | HIGH | MEDIUM | P2 |
| Within-domain FDR correction | MEDIUM | LOW | P2 |
| Preprocessing report | MEDIUM | LOW | P2 |
| Summary statistics per cluster | MEDIUM | LOW | P2 |
| Volcano plot | MEDIUM | LOW | P2 |
| Configurable domain mapping (YAML) | MEDIUM | LOW | P3 |
| Covariate adjustment | MEDIUM | HIGH | P3 |
| Neuroimaging domain expansion | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for launch — analysis is invalid or uninterpretable without it
- P2: Should have — required for publication-quality output; add after v1 is validated
- P3: Nice to have — useful for reusability or edge cases; defer

---

## Ecosystem Context

### Existing ABCD PheWAS Codebase (This Repo)

The existing `PheWAS Analyses Resub5.Rmd` is a genetic PRS PheWAS (not cluster-based), written in R. Key patterns observed and adapted:

- **Domain assignment**: 8 domains assigned by regex pattern matching on variable name prefixes (e.g., `ksad|cbcl` → Child Mental Health, `nihtbx|RAVLT` → Cognition). The domain names and color palette (darkorange1, lightseagreen, orchid3, lightskyblue, goldenrod1, seagreen, pink2, deepskyblue4) should be preserved for visual consistency.
- **Preprocessing**: skew > |1.96| triggers winsorization (mean ± 3 SD) then rank-based INT. Non-skewed continuous variables are z-scored only.
- **Tests**: lmer (continuous) and glmer-binomial (binary) used for the genetic PRS. The new pipeline replaces these with Kruskal-Wallis and chi-square, which are more appropriate for a categorical cluster exposure without random effects.
- **Output**: Beta, STE, Pval, FDR, Bonferroni per variable. Manhattan plot with direction triangles, FDR labels via `ggrepel`, Bonferroni threshold line.
- **Known domain gap**: The existing code uses ad hoc regex to assign domains and several variables required manual relocation (reshist, pds, medhx). The new pipeline should make domain assignment more systematic.

### Published ABCD PheWAS Standards (2024)

From PMC11383484 (CRP PheWAS in ABCD, 2024):
- 1,273 psychosocial + 1,104 neuroimaging phenotypes
- Preprocessing: ≥100 non-missing, winsorization (±3 SD), rank-based INT
- Mixed effects models with site/family ID as random effects (for genetic studies; not applicable here)
- Both Bonferroni and FDR corrections applied globally AND within each neuroimaging domain
- Figures: Manhattan plots + beta coefficient forest plots for significant hits

### What This Pipeline Changes

The cluster characterization pipeline differs from published ABCD genetic PheWAS in three key ways that drive feature decisions:

1. **Exposure is categorical (cluster label), not continuous (PRS)**: Requires group comparison tests (Kruskal-Wallis, chi-square) not regression. No random effects needed.
2. **One-vs-rest framing**: Not a single global test. K tests per variable (one per cluster). More plots, more correction rows.
3. **No sex/age covariates**: Clusters encode these by design. Adjusting would remove the signal.

---

## Sources

- Existing repo: `/Users/bhargav/ai-coding/ABCD-PHEWAS/PheWAS Analyses Resub5.Rmd` — domain structure, preprocessing pipeline, visualization patterns, output format (observed directly)
- [PMC11383484: ABCD CRP PheWAS 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC11383484/) — preprocessing standards, domain-specific correction, ABCD-specific phenotype counts (HIGH confidence)
- [pyPheWAS documentation](https://pyphewas.readthedocs.io/en/latest/phewas_tools.html) — Manhattan plot, volcano plot, effect size plot conventions (MEDIUM confidence)
- [R PheWAS package (PMC4133579)](https://pmc.ncbi.nlm.nih.gov/articles/PMC4133579/) — standard PheWAS feature set (FDR, Bonferroni, linear/logistic, chi-square, t-test options) (HIGH confidence)
- [PheWAS multiple testing — Wharton Penn paper](http://www-stat.wharton.upenn.edu/~tcai/paper/PheWAS-Multiple-Testing.pdf) — within-domain correction rationale (MEDIUM confidence)
- Existing ABCD PheWAS publications reviewed: PMC11383484 (2024 CRP), PMC10309061 (LOAD genetic risk in ABCD), ABCD PheWAS at WashU (2024) — domain structures and methods (HIGH confidence)

---
*Feature research for: ABCD PheWAS pubertal trajectory cluster characterization*
*Researched: 2026-03-04*
