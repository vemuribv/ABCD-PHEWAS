# Pitfalls Research

**Domain:** PheWAS / Phenome-Wide Association Study — cluster characterization pipeline (ABCD Study)
**Researched:** 2026-03-04
**Confidence:** HIGH (multiple peer-reviewed sources, ABCD-specific literature confirmed)

---

## Critical Pitfalls

### Pitfall 1: Circular Analysis — Testing Variables That Informed Cluster Construction

**What goes wrong:**
If any phenotype variables in the PheWAS were used (directly or indirectly) to construct the CRLI clusters upstream, then testing them for association with clusters is circular. p-values will be inflated and significance will be spurious. Known in neuroimaging as "double dipping."

**Why it happens:**
The CRLI clusters use pubertal development scores (PDS) and hormone measurements. PDS items and hormone-derived variables may overlap with ABCD phenotype columns in the PheWAS file. Researchers load the phenotype file without cross-checking whether any column was an input to clustering.

**How to avoid:**
Before running any statistical tests, explicitly list all variables that were inputs (direct or transformed) to the CRLI clustering. Create a blocklist. Filter those columns out of the PheWAS phenotype matrix entirely before testing. Document the exclusion in the pipeline with a clearly labeled step.

**Warning signs:**
- Variables named with "pds", "hormone", "testosterone", "estradiol", "dhea", or similar strings appearing in results
- Clustering input variables showing astronomically low p-values (e.g., p < 1e-100) — often the first sign of double-dipping
- Any phenotype that was used to compute cluster membership showing association with clusters

**Phase to address:**
Data loading / preprocessing phase — the exclusion blocklist must be applied before any statistical tests run.

---

### Pitfall 2: Wrong Statistical Test for Variable Type

**What goes wrong:**
Applying a parametric test (ANOVA, t-test) to ordinal or binary variables, or applying chi-square when expected cell counts are too small. Produces invalid p-values. Conversely, applying Kruskal-Wallis to a truly continuous, normally distributed variable wastes statistical power.

**Why it happens:**
Automated pipelines often default to a single test type. With 3,000+ variables of mixed types, manual inspection is impractical. Variable type metadata from the ABCD data dictionary is often trusted without validation against actual column distributions.

**How to avoid:**
Implement a type-detection step that validates each variable's actual distribution against its declared type:
- Binary (0/1 or exactly 2 levels): chi-square if expected cell counts >= 5, otherwise Fisher's exact test
- Categorical (nominal, >2 unordered levels): chi-square, Fisher's exact for sparse
- Ordinal (ordered levels, not truly continuous): Kruskal-Wallis (nonparametric rank test)
- Continuous: Kruskal-Wallis for non-normal, one-way ANOVA for normal (Shapiro-Wilk or similar check)

Apply Fisher's exact test when >20% of expected cells fall below 5 (not just any cell below 5 — that is the overly conservative old rule).

**Warning signs:**
- Variables declared as "ordinal" being tested with ANOVA (treating ordinal scores as continuous means assuming equal intervals between levels, which is invalid)
- Chi-square warning about low expected cell counts appearing in output but being ignored
- Binary variables with >95% zeros (near-zero prevalence) receiving chi-square instead of Fisher's exact

**Phase to address:**
Statistical testing core — build the test-selector as the first component; validate it on synthetic data with known ground truth before running on ABCD data.

---

### Pitfall 3: Ignoring Low-Prevalence Binary Variables

**What goes wrong:**
Binary phenotypes with very few positive cases (e.g., a rare diagnosis with only 15 out of 3,000 subjects) are included in the PheWAS. They have near-zero statistical power, but they still consume one slot in the multiple testing correction denominator. This inflates the correction burden for all other variables without contributing meaningful results.

**Why it happens:**
Loading all columns from the phenotype file without a minimum prevalence filter. The ABCD study has rare clinical events (certain diagnoses, medication use) that are present in the file but have insufficient case counts for meaningful testing.

**How to avoid:**
Apply a minimum case filter before testing binary variables. Standard PheWAS practice recommends at least 20-50 cases (some papers use 200 for adequate power). For this project with ~3,000 subjects split across 2-8 clusters, a one-vs-rest comparison splits the cohort further — minimum cases per group (not just overall) should be checked. Log excluded variables clearly in output.

**Warning signs:**
- Binary variable column sums below 20 in the full cohort
- Expected cell counts below 1 in any cell of the one-vs-rest contingency table
- Fisher's exact test running on variables with 3-5 total cases (technically possible, but meaningless biologically)

**Phase to address:**
Data loading / preprocessing phase — minimum prevalence filter applied after type detection, before tests run.

---

### Pitfall 4: Multiple Comparison Correction Applied to Wrong Unit

**What goes wrong:**
The FDR/Bonferroni correction is applied to the wrong denominator — for example, applied per-cluster (one-vs-rest) rather than globally across all tests across all clusters and all variables. This dramatically undercorrects, producing false discoveries.

**Why it happens:**
With multiple clusters and multiple variables, it's tempting to run the correction separately within each cluster's results. Some tools do this by default. The correct approach is to pool all p-values (all variables x all clusters for one-vs-rest tests, plus global tests) and correct once.

**How to avoid:**
Collect all raw p-values from all one-vs-rest comparisons across all clusters and all variables into a single array. Apply BH-FDR and Bonferroni once to that full array. Report corrected q-values for each (variable, cluster) combination. For the global test (across all clusters), apply a separate correction to the global p-value set.

The project correctly plans both FDR and Bonferroni — ensure both are applied to the complete test pool, not per-cluster subsets.

**Warning signs:**
- An unusually large number of significant hits relative to what the literature shows for similar ABCD PheWAS studies
- Significance threshold appearing permissive (FDR q < 0.05 with hundreds of hits when Bonferroni threshold would give very few)
- Correction applied per-domain or per-cluster rather than globally

**Phase to address:**
Multiple comparison correction implementation — add an explicit assertion that the correction input array length equals (number of variables) x (number of one-vs-rest tests).

---

### Pitfall 5: Not Accounting for ABCD Family Structure (Sibling Non-Independence)

**What goes wrong:**
The ABCD Study contains siblings, twins, and other family members enrolled together. These participants are correlated (genetically and environmentally), violating the independence assumption of chi-square, Fisher's, and Kruskal-Wallis tests. False positive rates are elevated.

**Why it happens:**
ABCD data is treated as a simple random sample. The family ID variable exists in the dataset but is not commonly used in analyses that use standard non-parametric tests (chi-square, Kruskal-Wallis don't have built-in random effects).

**How to avoid:**
Two acceptable approaches:
1. **Retain all subjects, apply permutation-based p-values** where the permutation preserves family structure (shuffle cluster labels within families, not across families). This is the most statistically rigorous approach.
2. **One subject per family** — randomly select one sibling per family, reducing sample size but eliminating the dependency. Document which subjects were excluded.

Do not use mixed models here (they require the covariate-adjustment framework the project explicitly avoids). Permutation testing is the preferred approach.

**Warning signs:**
- Family ID variable (`rel_family_id` in ABCD) present in the dataset but unused in the analysis pipeline
- No acknowledgment of family structure in the statistical methods
- ABCD documentation mentions 21% of sample have siblings enrolled

**Phase to address:**
Statistical testing core — decide on family structure handling before building tests, as it affects the entire pipeline architecture (permutation vs. subsetting).

---

### Pitfall 6: FDR Correction Assumes Independent Tests, But Phenotypes Are Correlated

**What goes wrong:**
Standard Benjamini-Hochberg FDR assumes tests are independent (or at least positively correlated in a specific way). ABCD phenotypes are substantially correlated within domains (e.g., multiple CBCL subscales, multiple cognitive measures). This can cause BH-FDR to either undercontrol or overcontrol the false discovery rate depending on the correlation structure.

**Why it happens:**
BH-FDR is applied as a black box without considering the correlation structure of the 3,000+ phenotypes. Researchers treat the correction as infallible once applied.

**How to avoid:**
- Report both FDR and Bonferroni as the project already plans — the gap between them signals how much correlated structure exists
- Treat FDR results as exploratory / hypothesis-generating and Bonferroni as the confirmatory threshold
- Do not claim BH-FDR gives strict false discovery rate control in the presence of correlated tests — note this limitation explicitly in outputs
- Optionally apply Benjamini-Yekutieli (BY) procedure which is valid under arbitrary dependence (more conservative than BH)

**Warning signs:**
- Clustered significant hits — entire domains lighting up simultaneously (indicates correlation, not necessarily true independent signals)
- Many highly correlated variables (r > 0.8) both appearing as significant

**Phase to address:**
Multiple comparison correction implementation — and results interpretation / output tables (add a note column flagging correlated variable clusters).

---

### Pitfall 7: Missing Data Treated as Zero or Category Label

**What goes wrong:**
In ABCD data, missing values appear as NaN, empty strings, -999, 777 (don't know), 999 (refused), or other sentinel values depending on the variable. If these are not detected and stripped before testing, they appear as a category level in chi-square tests or distort continuous distributions. "Don't know" responses in particular correlate with demographics and create systematic bias.

**Why it happens:**
Loading ABCD phenotype files with pandas read_csv without explicitly specifying na_values. ABCD uses multiple sentinel values that pandas does not recognize as NaN by default (-999, 777, 999, etc.).

**How to avoid:**
Load all ABCD files with explicit na_values list including ABCD sentinel codes. Cross-reference with the ABCD data dictionary for each variable's coding scheme. Treat "don't know" (777) and "refused" (999) as NaN by default, but log how many were converted (large rates suggest the variable is unreliable for this cohort).

Apply a minimum valid-data threshold per variable: if >40% of subjects have missing data on a variable, flag it for exclusion or at minimum note it in output.

**Warning signs:**
- Categorical variables with a category labeled "-999" or "999" appearing in test results
- Variables showing unexpected distributions where one level contains a majority of subjects
- Chi-square degrees of freedom higher than expected for a binary variable (suggests a sentinel value was treated as a third category)

**Phase to address:**
Data loading / preprocessing phase — define the ABCD sentinel value list as a pipeline constant; validate with spot checks on known variables.

---

### Pitfall 8: Effect Size Not Reported Alongside p-values

**What goes wrong:**
The pipeline reports only p-values and corrected q-values. In a large cohort (N ~3,000), even trivially small effects reach statistical significance after FDR correction. Researchers interpret significant findings as biologically meaningful without assessing effect magnitude.

**Why it happens:**
PheWAS pipelines historically emphasized p-value thresholds. Reporting infrastructure is built around significance rather than effect. With 3,000+ tests the sheer number of results discourages per-variable effect size calculation.

**How to avoid:**
For every variable-cluster test, compute and store:
- Binary/categorical: Cramér's V or odds ratio (with CI) for one-vs-rest
- Continuous/ordinal: rank-biserial correlation (r) for Kruskal-Wallis, or Cohen's d for ANOVA
- Include effect size in all output tables
- In visualizations, encode effect size (e.g., point size in Manhattan plot, color saturation in heatmap) alongside significance

**Warning signs:**
- Output tables with only p-value and q-value columns (no effect size column)
- Heatmap showing only significance (binary pass/fail) rather than magnitude
- "Significant" associations with odds ratios of 1.02 being reported as findings

**Phase to address:**
Statistical testing core — compute effect size as part of the test function, not as an afterthought post-hoc.

---

### Pitfall 9: Domain Mapping Gaps Leave Variables Unclassified

**What goes wrong:**
The ABCD data dictionary table name is used as the domain label for Manhattan plot grouping. Variables not present in the dictionary, newly added variables, or variables from merged/derived files end up with NULL domain labels. These appear as an unlabeled cluster in the Manhattan plot, are often overlooked, and sometimes contain important findings.

**Why it happens:**
ABCD releases new variables and renames tables across releases. The dictionary mapping is treated as complete when it isn't. Derived variables (e.g., computed composite scores) may not have dictionary entries.

**How to avoid:**
After domain mapping, assert that zero variables have NULL domain. For any unmatched variables: first attempt fuzzy matching on column name prefixes (ABCD variables have instrument-prefix naming conventions like `cbcl_`, `nihtbx_`, `abcd_`). If still unmatched, assign to an "Other/Unclassified" domain rather than dropping. Log all unmatched variables.

**Warning signs:**
- Domain column with NULL or empty values in output tables
- Manhattan plot with a mysterious unlabeled cluster of points
- Variable count in output tables lower than variable count in phenotype input file

**Phase to address:**
Domain mapping / data loading phase — run the domain mapping step with an assertion before any statistical testing begins.

---

### Pitfall 10: Sex-Stratified Analysis Conflated with Sex as a Variable

**What goes wrong:**
The pipeline runs separately for males and females (sex-stratified upstream). Within each stratum, sex is not a meaningful covariate. However, developers may still include a `sex` column in the phenotype matrix being tested, either running the sex variable through the PheWAS (always significant by construction, since all values are the same) or accidentally merging male and female files before stratified analysis.

**Why it happens:**
The sex column is present in the ABCD phenotype file. It's easy to forget to drop it when the pipeline already assumes within-stratum execution. Similarly, when concatenating results from male and female runs, file handles may be swapped.

**How to avoid:**
Explicitly drop the sex column from the phenotype matrix at the start of each stratified run. Assert that all subjects in a given run have the same sex value (using the cluster assignment file, which is sex-specific). Include the sex stratum as a parameter in output filenames and all result tables.

**Warning signs:**
- Sex variable appearing as a significant finding in within-stratum PheWAS
- Output files with identical male/female result sets (suggests wrong file was loaded)
- N per cluster inconsistent with expected male/female split

**Phase to address:**
Data loading / preprocessing phase — add explicit sex column exclusion and stratum validation assertions.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hardcode variable type as "continuous" for all variables | Simplifies pipeline, gets results quickly | Invalid p-values for binary/ordinal variables; invalid multiple comparison correction denominator | Never — type detection is core to PheWAS validity |
| Apply correction per-cluster instead of globally | Easier to implement cluster-by-cluster | Severely undercorrected, false positive explosion | Never |
| Ignore family structure (treat N=3000 as independent) | No permutation overhead | Inflated Type I error; reviewers will flag this | Only acceptable for preliminary exploratory runs, never for final results |
| Skip effect size computation | Faster output | Scientifically incomplete; can't distinguish trivial from meaningful signals | Never for final results |
| Use variable column name alone (no dictionary lookup) for domain mapping | No dictionary dependency | Unmapped variables create unlabeled Manhattan plot clusters; may miss important domain patterns | Acceptable in early prototyping, must be resolved before visualization |
| Drop all variables with any missing data | Simplest null handling | Eliminates many valid variables with rare missingness; may disproportionately remove certain domains | Never — use per-variable threshold instead |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Running Fisher's exact test on all binary variables regardless of cell counts | Extremely slow — Fisher's is computationally expensive for large contingency tables | Apply chi-square when expected cells allow (>20% rule); use Fisher's only for sparse data | At N > 1000 with many binary variables — noticeable slowdown |
| Looping over 3,000+ variables in pure Python without vectorization | Test run takes hours | Batch tests using scipy vectorized calls; use numpy for contingency table construction | At ~500 variables loop becomes noticeably slow; at 3,000 it is prohibitively slow |
| Permutation testing with N=10,000 permutations per variable | Infeasible runtime at 3,000 variables | Use permutation only to validate parametric test calibration on a subsample; use parametric tests for full run | At 1,000+ variables, permutation per variable becomes minutes-to-hours |
| Loading full ABCD phenotype file into memory without column filtering | Memory spike on large releases | Filter to subjects with cluster assignments first, then load | At release sizes > 5GB with thousands of columns, pandas may exceed 16GB RAM |

---

## Data / Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| ABCD data dictionary join | Joining on full column name when dictionary uses instrument prefix only | Use prefix-based matching; ABCD columns follow `instrumentname_variablesuffix` pattern — strip suffix for table-level domain lookup |
| Cluster assignment file subject IDs | ABCD uses `src_subject_id` (string, with leading zeros) — treating as integer drops leading zeros | Always load subject IDs as strings; use string equality for joins |
| One-vs-rest group construction | Computing "rest" as all subjects rather than all subjects with valid cluster assignments | Filter to only subjects present in the cluster file before constructing rest group |
| ABCD release version mismatch | Column names and codings change across releases (e.g., 4.0 vs 5.1) | Store release version as a pipeline parameter; validate key column names exist before running |

---

## "Looks Done But Isn't" Checklist

- [ ] **Multiple comparison correction:** Verify the correction array length equals total number of tests across all clusters — not just one cluster's tests
- [ ] **Circular analysis exclusion:** Verify CRLI input variables are explicitly removed from phenotype matrix before any test — grep outputs for PDS/hormone variable names to confirm absence
- [ ] **Effect sizes in output:** Verify output CSV contains effect size column (Cramér's V / rank-biserial r) alongside p and q values
- [ ] **Domain mapping coverage:** Assert zero NULL domain labels in output before generating Manhattan plot
- [ ] **Missing data sentinels:** Spot-check 5 known ABCD variables for correct NA handling (e.g., a CBCL item with known 777/999 codes)
- [ ] **Sex stratum validation:** Assert all subjects in each run file have a single sex value; assert sex column absent from phenotype test matrix
- [ ] **Subject ID string type:** Assert cluster file subject IDs match phenotype file subject IDs after string join — report any unmatched IDs
- [ ] **Binary variable prevalence filter:** Verify excluded-variable log exists and lists all variables filtered for low prevalence, with their case counts
- [ ] **Minimum cell count enforcement:** Verify Fisher's exact test is triggered for any contingency table with expected cell < 5 (add a logged counter of how many variables triggered Fisher's)

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Circular analysis (CRLI inputs included in PheWAS) | LOW — if caught before publication | Add blocklist, re-run pipeline, regenerate all outputs; no data collection needed |
| Wrong statistical test applied | LOW — computational only | Fix test-selector logic, re-run; compare new vs. old results tables to verify changes are sensible |
| Multiple comparison correction on wrong denominator | LOW — computational only | Refactor correction step, re-run; expect more conservative results |
| Missing data sentinels not caught | MEDIUM — requires data audit | Audit phenotype file for all sentinel values per ABCD dictionary, update na_values list, re-run |
| Family structure ignored (non-independence) | MEDIUM-HIGH — requires permutation infrastructure | Add permutation testing (days of compute); or switch to one-sibling-per-family subsetting (re-run) |
| Effect sizes not computed | LOW | Add effect size functions, re-run tests; no statistical re-validation needed |
| Domain mapping gaps discovered after plots generated | LOW | Fix mapping, regenerate plots only |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Circular analysis — CRLI inputs in phenotype matrix | Data loading / preprocessing | Assert: none of the CRLI input column names appear in the filtered phenotype matrix |
| Wrong statistical test per variable type | Statistical testing core | Unit test test-selector on synthetic binary, categorical, ordinal, and continuous data with known expected tests |
| Low-prevalence binary variable inclusion | Data loading / preprocessing | Verify: excluded-variable log exists with case counts; spot-check 3 known rare variables |
| Multiple comparison correction on wrong denominator | Multiple comparison correction implementation | Assert: len(p_value_array) == n_variables x n_clusters for one-vs-rest pool |
| ABCD family structure non-independence | Statistical testing core | Document chosen approach (permutation or one-per-family subsetting); add family-ID-based assertion |
| FDR correlation assumption | Multiple comparison correction + results interpretation | Report both BH-FDR and Bonferroni; note FDR limitations in output table headers |
| Missing data sentinels as categories | Data loading / preprocessing | Spot-check 5 known ABCD variables with 777/999 codes; verify they appear as NaN in loaded dataframe |
| Effect size absent from outputs | Statistical testing core | Assert: all output tables contain at least one effect size column before any file is written |
| Domain mapping gaps | Domain mapping / data loading | Assert: zero NULL domain values before Manhattan plot generation |
| Sex column in within-stratum phenotype matrix | Data loading / preprocessing | Assert: sex column absent from test matrix; assert single sex value across all subjects in run |

---

## Sources

- [Current Scope and Challenges in Phenome-Wide Association Studies (PMC5846687)](https://pmc.ncbi.nlm.nih.gov/articles/PMC5846687/) — core PheWAS methodological review
- [The challenges, advantages and future of PheWAS (PMC3904236)](https://pmc.ncbi.nlm.nih.gov/articles/PMC3904236/) — covariate selection, multiple testing
- [A simulation study investigating power estimates in PheWAS (BMC Bioinformatics 2018)](https://bmcbioinformatics.biomedcentral.com/articles/10.1186/s12859-018-2135-0) — binary trait minimum case counts, power analysis
- [A practical guide for ABCD Study researchers (PMC9156875)](https://pmc.ncbi.nlm.nih.gov/articles/PMC9156875/) — ABCD-specific: missing data, family structure, covariate selection, outlier handling
- [Circular analysis in systems neuroscience: the dangers of double dipping (PMC2841687)](https://pmc.ncbi.nlm.nih.gov/articles/PMC2841687/) — circular analysis / double dipping
- [Chi-squared test and Fisher's exact test (PMC5426219)](https://pmc.ncbi.nlm.nih.gov/articles/PMC5426219/) — cell count thresholds, when to apply Fisher's
- [Best Practices for Binary and Ordinal Data Analyses (PMC8096648)](https://pmc.ncbi.nlm.nih.gov/articles/PMC8096648/) — ordinal vs. continuous test selection
- [A PheWAS of Genetic Risk for CRP in Children from the ABCD Study (PMC12264583)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12264583/) — ABCD-specific PheWAS example with 2,377 variables
- [A PheWAS of Late Onset AD Genetic Risk in ABCD Children (PMC10309061)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10309061/) — ABCD PheWAS example, Bonferroni/FDR usage
- [Detecting and harmonizing scanner differences in ABCD (bioRxiv)](https://www.biorxiv.org/content/10.1101/309260v1) — multi-site batch effects in ABCD
- [Missing data approaches for longitudinal neuroimaging in ABCD (bioRxiv)](https://www.biorxiv.org/content/10.1101/2024.06.12.598732v1.full) — ABCD missing data handling

---
*Pitfalls research for: PheWAS cluster characterization pipeline (ABCD Study)*
*Researched: 2026-03-04*
