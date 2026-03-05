# Requirements: ABCD PheWAS Cluster Characterization

**Defined:** 2026-03-04
**Core Value:** Discover the phenotypic "character" of each pubertal trajectory cluster — what makes each cluster distinctive across thousands of variables.

## v1 Requirements

### Data Foundation

- [x] **DATA-01**: Load cluster assignments (subject ID + cluster label) and single-timepoint phenotype file
- [x] **DATA-02**: Auto-detect variable types: binary, categorical, ordinal, continuous
- [x] **DATA-03**: Handle missing data with per-variable NA exclusion and missingness rate reporting
- [x] **DATA-04**: Skip variables with <10 non-missing subjects in any comparison group
- [x] **DATA-05**: Apply skewness check, winsorization (mean +/- 3 SD), and rank-based INT to skewed continuous variables (|skew| > 1.96); z-score non-skewed continuous variables

### Domain Mapping

- [x] **DOMN-01**: Assign phenotype variables to ABCD domains using configurable regex mapping
- [x] **DOMN-02**: Preserve existing 8-domain structure and color palette from current R codebase

### Statistical Testing

- [x] **STAT-01**: One-vs-rest comparison per cluster: Kruskal-Wallis for continuous/ordinal, chi-square/Fisher for binary/categorical
- [x] **STAT-02**: Global omnibus test per variable across all clusters
- [x] **STAT-03**: Effect sizes: Cohen's d (continuous), Cramer's V (binary/categorical)
- [ ] **STAT-04**: Global FDR (Benjamini-Hochberg) and Bonferroni correction across all tests
- [ ] **STAT-05**: Within-domain FDR and Bonferroni correction
- [x] **STAT-06**: Support 2-8 clusters

### Output

- [ ] **OUTP-01**: Results CSV with variable, domain, test type, statistic, p-value, FDR q, Bonferroni p, effect size, CI, cluster label, n per group, missingness rate
- [ ] **OUTP-02**: Manhattan-style PheWAS plot per cluster (one-vs-rest) with domain colors, FDR/Bonferroni threshold lines, direction markers, labels on significant hits
- [ ] **OUTP-03**: Global Manhattan plot (omnibus test results)

### Pipeline

- [ ] **PIPE-01**: Run separately for males and females
- [ ] **PIPE-02**: Support running on different timepoints as separate analyses
- [ ] **PIPE-03**: Document sibling non-independence as a known limitation (keep all subjects)

## v2 Requirements

### Visualization

- **VIS-01**: Heatmap of clusters x significant variables with effect size fill and domain grouping
- **VIS-02**: Volcano plot (effect size vs -log10(p)) per cluster
- **VIS-03**: Summary statistics table per cluster for significant variables

### Preprocessing

- **PREP-01**: Preprocessing report documenting which variables received which transformation

### Advanced

- **ADV-01**: Configurable covariate adjustment (site/scanner) via residualization
- **ADV-02**: CRLI input variable blocklist to prevent circular analysis
- **ADV-03**: One-per-family subsetting option for sensitivity analysis

## Out of Scope

| Feature | Reason |
|---------|--------|
| Mixed-effects models (lmer/glmer) | Clusters are categorical grouping, not regression predictor; KW/chi-square are appropriate and 100x faster |
| Causal inference / mediation | Explicitly associational/descriptive analysis |
| Interactive web dashboard | Publication-quality static plots are the correct output |
| Longitudinal PheWAS | Each timepoint analyzed independently by design |
| Phenotype imputation (MICE) | Interpretation ambiguity; listwise deletion per variable is standard |
| Automatic normality-based test selection | Double-dipping inflates type I error; test choice based on variable type, not normality test |
| Mobile app / real-time analysis | Batch pipeline on fixed ABCD snapshot |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DATA-01 | Phase 1 | Complete |
| DATA-02 | Phase 1 | Complete |
| DATA-03 | Phase 1 | Complete |
| DATA-04 | Phase 1 | Complete |
| DATA-05 | Phase 1 | Complete |
| DOMN-01 | Phase 1 | Complete |
| DOMN-02 | Phase 1 | Complete |
| STAT-01 | Phase 2 | Complete |
| STAT-02 | Phase 2 | Complete |
| STAT-03 | Phase 2 | Complete |
| STAT-04 | Phase 2 | Pending |
| STAT-05 | Phase 2 | Pending |
| STAT-06 | Phase 2 | Complete |
| OUTP-01 | Phase 3 | Pending |
| OUTP-02 | Phase 3 | Pending |
| OUTP-03 | Phase 3 | Pending |
| PIPE-01 | Phase 4 | Pending |
| PIPE-02 | Phase 4 | Pending |
| PIPE-03 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 19 total
- Mapped to phases: 19
- Unmapped: 0

---
*Requirements defined: 2026-03-04*
*Last updated: 2026-03-04 after roadmap creation*
