# Phase 1: Data Foundation - Context

**Gathered:** 2026-03-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Clean, typed, domain-labeled DataFrame ready for statistical testing, with CRLI variables blocked and ABCD sentinels removed. Loads cluster assignments and a single-timepoint phenotype file, auto-detects variable types, applies preprocessing transformations, and assigns domain labels.

</domain>

<decisions>
## Implementation Decisions

### Variable Type Detection
- Auto-detect using unique value count: ≤10 unique values = categorical, >10 = continuous
- Binary: exactly 2 unique non-NA values
- Ordinal: ≤10 unique values AND values are sequential integers (e.g., 1,2,3,4,5 Likert scales)
- Nominal categorical: ≤10 unique values but NOT sequential integers
- No data dictionary required — pure heuristic approach

### Input File Formats
- Both cluster assignments and phenotype data are CSV files
- Column names for subject ID and cluster label are configurable (not hardcoded)
- Phenotype file is a single wide CSV: one subject ID column + thousands of phenotype columns
- CRLI blocklist: plain text file with one variable name per line

### Domain Mapping
- Map variables to ABCD domains using table name prefixes (e.g., cbcl_ → Mental Health, nihtbx_ → Neurocognition)
- 8 domains and their color palette to be extracted from the existing R codebase during research
- Prefix-to-domain mapping stored in an external YAML or JSON config file (editable without code changes)
- Unclassified variables: show on plots as "Other" domain in neutral color AND generate a report listing unclassified variable names for manual review

### Preprocessing Pipeline
- Two-pass approach matching the R codebase:
  1. Check skewness (|skew| > 1.96)
  2. Winsorize skewed variables (mean ± 3 SD)
  3. Re-check skewness after winsorization
  4. Apply rank-based inverse normal transformation (INT) only to variables still skewed after winsorization
  5. Z-score non-skewed continuous variables
- Ordinal variables: no preprocessing (kept raw) — Kruskal-Wallis is rank-based, normalization unnecessary
- Full transformation log: CSV report documenting each variable's preprocessing path (e.g., "nihtbx_flanker: skewed → winsorized → still skewed → INT applied")
- Configurable sentinel value list: defaults to [-999, 777, 999], extendable via config for instrument-specific codes (e.g., -1 = "don't know", 888 = "refused")

### Claude's Discretion
- Python project structure (module layout, package naming)
- Specific pandas/numpy implementation patterns
- Logging framework and verbosity levels
- Unit test structure and synthetic data generation approach
- Memory optimization for 3,000+ column DataFrames

</decisions>

<specifics>
## Specific Ideas

- Two-pass preprocessing must reproduce the R pipeline's behavior (skewness → winsorize → re-check → INT if still skewed)
- The existing R code (`PheWAS Analyses Resub5.Rmd`) serves as the reference implementation for preprocessing logic
- Transformation log is important for manuscript methods section and reproducibility

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `PheWAS Analyses Resub5.Rmd`: R reference implementation with preprocessing logic, domain structure, and visualization patterns
- No existing Python code — greenfield Python project

### Established Patterns
- R code uses hardcoded column ranges for type assignment — Python version replaces this with auto-detection
- R code uses Excel input — Python version uses CSV
- R code uses `RNOmni` for INT, `DescTools::Winsorize` for winsorization — Python equivalents needed
- R code uses `psych::describe` for skewness — Python equivalent: `scipy.stats.skew`

### Integration Points
- Cluster assignment file comes from upstream CRLI pipeline (separate project)
- Phenotype file comes from ABCD data release (pre-existing)
- Output DataFrame feeds directly into Phase 2 (Statistical Core)

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-data-foundation*
*Context gathered: 2026-03-04*
