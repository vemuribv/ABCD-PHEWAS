# Roadmap: ABCD PheWAS Cluster Characterization

## Overview

The pipeline is built in four stages that mirror its data flow. Phase 1 establishes a clean, typed, domain-labeled DataFrame — every downstream step depends on variable type classification being done once before any test runs. Phase 2 builds and validates the statistical engine with unit tests on synthetic data, producing a raw p-value table. Phase 3 applies global multiple comparison correction and generates the publication-quality outputs. Phase 4 wires everything into a sex-stratified, multi-timepoint CLI that can run the full pipeline end-to-end.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Data Foundation** - Clean, typed, domain-labeled DataFrame with CRLI blocklist and sentinel values handled
- [ ] **Phase 2: Statistical Core** - Test engine with all variable types, one-vs-rest + global omnibus, effect sizes, raw p-values
- [ ] **Phase 3: Correction and Outputs** - Global FDR/Bonferroni correction, results CSV, publication-quality Manhattan plots
- [ ] **Phase 4: Pipeline Orchestration** - Sex-stratified, multi-timepoint CLI that runs the full pipeline end-to-end

## Phase Details

### Phase 1: Data Foundation
**Goal**: A validated, typed, domain-labeled DataFrame is ready for statistical testing, with CRLI variables blocked and ABCD sentinels removed
**Depends on**: Nothing (first phase)
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, DOMN-01, DOMN-02
**Success Criteria** (what must be TRUE):
  1. Loading a cluster file and phenotype file produces a merged DataFrame with only subjects present in both files
  2. Every column is assigned exactly one variable type (binary, categorical, ordinal, or continuous) without manual labeling
  3. ABCD sentinel values (-999, 777, 999) are treated as missing, not as numeric or categorical values
  4. Variables in the CRLI blocklist are absent from the DataFrame before any test runs
  5. Every variable has a domain label; no variable has a NULL domain (unmatched variables receive "Other/Unclassified")
**Plans**: 2 plans
Plans:
- [ ] 01-01-PLAN.md — Project scaffold, data loader, and variable type detector
- [ ] 01-02-PLAN.md — Preprocessor, domain mapper, and pipeline orchestrator

### Phase 2: Statistical Core
**Goal**: Per-variable test results (one-vs-rest per cluster + global omnibus) with raw p-values and effect sizes, validated on synthetic data before running on ABCD
**Depends on**: Phase 1
**Requirements**: STAT-01, STAT-02, STAT-03, STAT-04, STAT-05, STAT-06
**Success Criteria** (what must be TRUE):
  1. Unit tests on synthetic data covering all four variable types pass before any ABCD data is processed
  2. Each variable receives the correct test: Kruskal-Wallis for continuous/ordinal, chi-square or Fisher's exact for binary/categorical
  3. Running on a 2-cluster and an 8-cluster assignment file both produce valid results without code changes
  4. Effect sizes (Cohen's d for continuous, Cramer's V for categorical) are present for all (variable, cluster) pairs, not just significant ones
  5. The raw p-value array length equals n_variables × (n_clusters + 1), confirmed by assertion before correction
**Plans**: TBD

### Phase 3: Correction and Outputs
**Goal**: Final corrected results table and publication-quality plots are produced from the raw p-value array
**Depends on**: Phase 2
**Requirements**: OUTP-01, OUTP-02, OUTP-03
**Success Criteria** (what must be TRUE):
  1. Results CSV contains one row per (variable, cluster) pair with FDR-BH q-value, Bonferroni p-value, effect size, CI, n per group, and missingness rate
  2. Manhattan plot renders for each one-vs-rest cluster comparison: domain-colored x-axis, FDR and Bonferroni threshold lines, directional markers, non-overlapping labels on significant hits at 300 DPI
  3. Global omnibus Manhattan plot renders showing which variables differ across any cluster
**Plans**: TBD

### Phase 4: Pipeline Orchestration
**Goal**: A single command runs the full pipeline for a given sex stratum and timepoint, producing all outputs in an organized directory
**Depends on**: Phase 3
**Requirements**: PIPE-01, PIPE-02, PIPE-03
**Success Criteria** (what must be TRUE):
  1. Running the pipeline with male and female cluster files separately produces independent, non-overlapping output directories
  2. Running the pipeline with baseline and follow-up phenotype files produces two complete sets of results without code changes
  3. The results README documents sibling non-independence as a known limitation with sample statistics (n subjects, n families, n sibling pairs)
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Data Foundation | 0/2 | Planning complete | - |
| 2. Statistical Core | 0/TBD | Not started | - |
| 3. Correction and Outputs | 0/TBD | Not started | - |
| 4. Pipeline Orchestration | 0/TBD | Not started | - |
