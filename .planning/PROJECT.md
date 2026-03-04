# ABCD PheWAS: Pubertal Trajectory Cluster Characterization

## What This Is

A Python-based PheWAS (Phenome-Wide Association Study) pipeline that characterizes pubertal maturation trajectory clusters identified by CRLI deep multivariate time series clustering. Given cluster assignments and a phenotype file with thousands of ABCD variables, it systematically tests whether any phenotype variables are differentially enriched or depleted in each cluster, producing publication-quality visualizations.

## Core Value

Discover the phenotypic "character" of each pubertal trajectory cluster — what makes each cluster distinctive across thousands of variables spanning neurocognitive, mental health, physical health, and other domains.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Load cluster assignments (subject IDs + cluster labels) and a single-timepoint phenotype file
- [ ] Handle mixed variable types: binary, categorical, ordinal, and continuous
- [ ] Apply appropriate statistical tests per variable type (e.g., chi-square/Fisher for binary/categorical, Kruskal-Wallis/ANOVA for continuous/ordinal)
- [ ] One-vs-rest comparison: test each cluster against all other subjects pooled
- [ ] Global test: test whether each variable differs across any clusters
- [ ] Support 2-8 clusters
- [ ] Multiple comparison correction with both FDR (Benjamini-Hochberg) and Bonferroni
- [ ] Map phenotype variables to ABCD data dictionary domains for grouping
- [ ] Manhattan-style PheWAS plot: -log10(p) by variable, colored by domain
- [ ] Heatmap visualization: clusters x significant variables, showing effect direction and significance
- [ ] Run separately for males and females (sex-stratified upstream)
- [ ] Support running on different timepoints (baseline, latest available) as separate PheWAS analyses
- [ ] Output results tables with effect sizes, p-values, corrected p-values, and domain labels
- [ ] Optional covariate adjustment (TBD — may add site/scanner or other confounders later)

### Out of Scope

- Upstream clustering (CRLI) — already done separately
- Longitudinal PheWAS (analyzing phenotype change over time) — single timepoint per run
- Merging phenotype variables across timepoints — each timepoint analyzed independently
- Causal inference — this is associational/descriptive

## Context

- **Dataset:** ABCD Study (Adolescent Brain Cognitive Development)
- **Upstream:** CRLI (deep MVTS clustering) on pubertal development measures (PDS, hormones) with age in months as the time axis
- **Stratification:** Separate male and female models upstream, so clusters are sex-specific
- **Age awareness:** Clusters are derived from age-indexed trajectories, so age is encoded in cluster identity
- **Phenotype scale:** 3,000+ variables across multiple ABCD domains
- **Domain mapping:** Variable-to-domain mapping available via ABCD data dictionary table names

## Constraints

- **Language:** Python
- **Cluster count:** 2-8 clusters per sex
- **Input format:** Cluster file (subject ID + cluster label), phenotype file (subject ID + thousands of columns)
- **No sex/age covariates:** Clusters already encode these — adjusting would remove the signal

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| One-vs-rest as primary comparison | Answers "what defines this cluster" directly | — Pending |
| No age/sex covariate adjustment | Clusters are defined by age-indexed pubertal trajectories, stratified by sex | — Pending |
| Both FDR and Bonferroni correction | Show liberal and conservative thresholds on same plots | — Pending |
| Domain grouping from ABCD dictionary | Natural grouping for Manhattan plot x-axis | — Pending |

---
*Last updated: 2026-03-04 after initialization*
