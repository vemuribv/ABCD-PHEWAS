# Codebase Concerns

**Analysis Date:** 2026-03-04

## Tech Debt

**Template-based Script Generation with Hardcoded Placeholders:**
- Issue: Multiple R scripts use placeholder variables like "NUMBER" that require sed substitution to generate working scripts
- Files: `multi_GWAS_CD2.R`, `multi_GWAS_ind_Compulsive.R`, `multi_GWAS_ind_Internal.R`, `multi_GWAS_ind_Neurodev.R`, `multi_GWAS_ind_Psychotic.R`
- Impact: Error-prone manual script generation process; scripts cannot be executed directly; fragile sed replacement may fail silently with incorrect path substitutions; difficult to version control and debug individual execution
- Fix approach: Convert to parameterized functions that accept array indices as arguments rather than template substitution; store all scripts in a single parametrized runner or use dynamic path construction with Sys.getenv() or command-line arguments

**Temporary Generated Files Not Tracked:**
- Issue: Shell scripts generate temporary R files via sed but leave comments saying "you can delete these scripts after you're done" without automated cleanup
- Files: `multi_GWAS_CD2.sh`, `multi_GWAS_CD2_ind_Compulsive.sh`, `multi_GWAS_CD2_ind_Internal.sh`, `multi_GWAS_CD2_ind_Neurodev.sh`, `multi_GWAS_CD2_ind_Psychotic.sh`
- Impact: Manual cleanup burden; orphaned files accumulate; disk space waste; unclear whether deletion affects reproducibility
- Fix approach: Add cleanup trap in bash scripts to remove generated R files; or move temporary files to a designated temp directory that is cleaned on completion; or refactor to avoid generation entirely

**Hard-Coded File Paths Throughout Analysis:**
- Issue: Analysis paths are absolute or relative to specific directory structures without centralized configuration
- Files: `split_sumstats_CD2.R` (lines 9-10), `LDSC.R` (line 7-8), `cross_disorder_munge.R`, `multi_GWAS_CD2.R` (lines 8, 69, 73, 77, 81)
- Impact: Difficult to run analyses in different environments; scripts break when data is reorganized; no documentation of expected directory structure
- Fix approach: Create a config file or environment variables that define all data paths; use a setup function that validates required directories exist before analysis begins

**Uncommented Code and Disabled Functionality:**
- Issue: Large Rmd file contains multiple commented-out code blocks including API key exposure, package installation commands, and environment setup
- Files: `PheWAS Analyses Resub5.Rmd` (lines 30-66, line 61 with API key visible in comment)
- Impact: Code readability suffers; security risk if API keys are exposed in history; confusing for future users; commented code drifts out of sync with live code
- Fix approach: Remove all commented production code; use proper environment variable handling for secrets; document deprecated functionality in separate DEPRECATED.md file if needed

**Undefined Covariate Variables (C1-C10):**
- Issue: Models extensively use C1 through C10 covariates (principal components) but these are never explicitly created in accessible code sections
- Files: `PheWAS Analyses Resub5.Rmd` (lines 174, 189, 191, 193-215, 247, 290, 305-309)
- Impact: Reproducibility issue - unknown how C1-C10 are computed; difficult to understand covariate strategy; hard to verify correctness of analysis; new analysts cannot reproduce preprocessing
- Fix approach: Add explicit documentation chunk showing C1-C10 generation; create standalone script for covariate preprocessing; add validation checks to confirm covariates are properly centered/scaled

**Hard-Coded Sample Sizes and Phenotype Information:**
- Issue: Sample sizes and phenotype metadata are duplicated across multiple files rather than centralized
- Files: `CD_sumstats.R` (lines 3-10), `LDSC.R` (lines 1-6), `cross_disorder_munge.R` (lines 2-8)
- Impact: Version mismatch risk; manual updates required in multiple places; no single source of truth for study metadata; easy to introduce inconsistencies
- Fix approach: Create a single metadata file (CSV/JSON) containing N values, trait names, trait files; have all scripts read from this centralized source

## Known Bugs

**Model Specification Inconsistency:**
- Bug: Some independent factor models specify different SNP pathways than documented
- Files: `multi_GWAS_ind_Compulsive.R` (line 58-63 vs 18-21 base model)
- Symptoms: Independent factor models may not be truly independent due to pathway mixing; results could be confounded
- Trigger: Cross-reference model specifications between base model and independent models
- Workaround: Manually verify each model specification matches its intended design before running; check published methods section

**Missing Output in Some Models:**
- Bug: Some independent factor models generate fewer output files than expected
- Files: `multi_GWAS_ind_Compulsive.R` (outputs 3 files), `multi_GWAS_ind_Psychotic.R` (outputs 3 files) vs `multi_GWAS_ind_Neurodev.R` (outputs 5 files)
- Symptoms: Asymmetric results structure; confusion during result aggregation
- Trigger: Check number of output CSV files per model run
- Workaround: Document expected output counts per model type; create wrapper script to validate output completeness

## Security Considerations

**API Key Exposure in Source Code:**
- Risk: OpenAI API key appears in commented code in Rmd file
- Files: `PheWAS Analyses Resub5.Rmd` (line 61)
- Current mitigation: Key is commented out
- Recommendations: Remove API key from repository entirely; implement proper environment variable loading via .Renviron or Sys.getenv(); use credential managers for sensitive tokens; scan repository history and revoke exposed keys

**Missing Input Validation:**
- Risk: Scripts do not validate that required input files exist before processing
- Files: All R scripts that call load() or read.table()
- Current mitigation: None - job will crash at runtime
- Recommendations: Add file existence checks at script start; validate file formats and required columns; provide clear error messages for missing dependencies

## Performance Bottlenecks

**Sequential SNP Processing:**
- Problem: SNPs are split into sets of 6000 and processed sequentially through SLURM array jobs (0-914 sets = massive queue time)
- Files: `split_sumstats_CD2.R` (line 5), `multi_GWAS_CD2.sh` (line 9)
- Cause: Large genome-wide SNP set requires splitting; no batching of subsequent analyses
- Improvement path: Increase SNP set size (currently 6000) if memory allows; implement post-processing pipeline to aggregate results immediately as jobs complete rather than waiting for all to finish; consider alternative GWAS tools that support streaming analysis

**In-Memory Data Manipulation:**
- Problem: Large PheWAS dataset is fully loaded and manipulated in memory with repeated transformations
- Files: `PheWAS Analyses Resub5.Rmd` (lines 84-151, 19600-19656)
- Cause: Using R data.frame operations on full dataset; multiple pass transformations
- Improvement path: Use data.table or fst for faster serialization; implement row filtering early to reduce memory footprint; vectorize transformations; profile code to identify hot spots

**Repeated Model Fitting for Similar Outcomes:**
- Problem: Nearly identical lmer/glmer models run separately for each outcome variable with no code reuse
- Files: `PheWAS Analyses Resub5.Rmd` (multiple hundred similar model calls)
- Cause: Manual copy-paste of model specifications with minor variable changes
- Improvement path: Refactor into a function that accepts outcome variable name and model formula template; use mapply or purrr::map to apply function across all variables; consolidate repeated fixed effects specifications

## Fragile Areas

**Complex Data Transformation Pipeline:**
- Files: `PheWAS Analyses Resub5.Rmd` (lines 84-150)
- Why fragile: Multi-step transformation with magic column indices (1:4, 20, 671:1291, 21:670, etc.); no validation that transformations succeeded; relocation operations are positional; winsorization and inverse normal transformation depend on previous steps succeeding
- Safe modification: Document what each column range represents; add assertions after each major transformation to verify data integrity; extract transformation logic to separate functions with validation; use named column selection instead of indices
- Test coverage: No unit tests for data transformation; no validation that output data is in expected state

**SLURM Job Array Configuration:**
- Files: `multi_GWAS_CD2.sh` (line 9 with array=0-914)
- Why fragile: Array size (915) is hard-coded and must match actual SNP set count from `split_sumstats_CD2.R`; mismatch causes silent job failures; no validation that split completed successfully
- Safe modification: Have split script write array range to file; read this in bash script to dynamically set array bounds; add pre-flight check to verify all required input files exist before submitting array jobs
- Test coverage: No validation of SNP splits before submission; no error handling for mismatched array sizes

**Model Formula Strings as Characters:**
- Files: `multi_GWAS_CD2.R` (lines 18-61), all multi_GWAS_ind_*.R files
- Why fragile: Entire model specification as single string; no syntax checking until runtime; easy to introduce typos; factor structure inconsistencies hard to spot by inspection
- Safe modification: Parse model specifications from structured data (YAML/JSON); implement model validation function that checks all variables exist; use symbolic model building rather than string concatenation; store model definitions in separate configuration file
- Test coverage: No automated checking of model validity before submission to HPC queue

**Unclear Downstream Dependencies:**
- Files: Various files in pipeline (CD_sumstats.R → split_sumstats_CD2.R → multi_GWAS_CD2.R with inconsistent path references)
- Why fragile: File paths reference different split_sumstats directories (split_sumstats2 vs split_sumstats3); no clear documentation of which version to use; intermediate outputs have inconsistent naming
- Safe modification: Create a data lineage document; standardize all intermediate data locations; add version tags to intermediate files; create a main script that orchestrates entire pipeline with consistent paths
- Test coverage: No end-to-end tests; no validation that upstream script outputs match downstream script inputs

## Scaling Limits

**Single Reference File Dependency:**
- Current capacity: All analyses reference single shared LD reference (`reference.1000G.maf.0.005.txt`) and LDSC covariance matrix (`LDSCoutput_CD.RData`)
- Limit: Reference file must be pre-computed; any future phenotype additions require recomputing LDSC matrix; no modularity for adding new traits
- Scaling path: Implement per-phenotype reference caching; modularize LDSC computation to allow incremental updates; document reference file generation process; consider updating references with newer LD panels

**Array Job Memory Limits:**
- Current capacity: Bash script allocates 4GB memory per job; R processes configured with 6 cores
- Limit: If SNP set size increases beyond 6000 or if added phenotypes increase covariance matrix size, jobs will fail with out-of-memory errors
- Scaling path: Implement adaptive memory allocation based on SNP count; add memory profiling to determine optimal chunk sizes; consider sparse matrix representations for LD; implement progressive GC within jobs

**Model Complexity Constraints:**
- Current capacity: Models include 4 latent factors, multiple indicator variables, SNP effects on factors
- Limit: Adding more phenotypes increases model complexity; convergence issues already present (see WARN tracking); solver options (bobyqa with maxfun=1e5) may be insufficient for larger models
- Scaling path: Test alternative optimization algorithms (nlopt, Nelder-Mead); implement convergence diagnostics; consider hierarchical factor structures for large phenotype sets; profile model estimation time to plan HPC allocation

## Dependencies at Risk

**Deprecated/Unmaintained Packages:**
- Risk: lmerTest and lme4 are stable but aging; optimx, minqa, dfoptim are optimization backends that may have compatibility issues
- Impact: R version updates may break BLAS/LAPACK dependencies; optimization convergence may fail with new solver implementations
- Migration plan: Document minimum R version requirement; test regularly with new R releases; consider migrating to newer modeling frameworks (tidymodels ecosystem) for more active maintenance; implement version pinning in renv.lock or similar

**GenomicSEM Dependency:**
- Risk: Custom package with limited CRAN presence; if maintainer abandons project, bug fixes become difficult
- Impact: Major dependency for GWAS pipeline; vulnerabilities or incompatibilities cannot be easily patched; no alternative implementation readily available
- Migration plan: Audit GenomicSEM source code to understand core functionality; consider forking or implementing critical functions internally; maintain contact with package authors; test regularly with new dependency versions

**OpenAI Integration Remnants:**
- Risk: Code references openai package which is not in main workflow but introduces unnecessary dependency
- Impact: Security surface area for API credentials; package bloat; potential licensing issues if commercial use intended
- Migration plan: Remove all openai library imports and commented credential code; use alternative visualization libraries without external API calls; clean up environment setup code

## Test Coverage Gaps

**No Unit Tests for Data Transformations:**
- What's not tested: Column retyping, winsorization, inverse normal transformation, skewness filtering
- Files: `PheWAS Analyses Resub5.Rmd` (lines 84-151)
- Risk: Data transformation errors would propagate through all downstream analyses undetected; difficult to debug if results are unexpected
- Priority: High - data quality is foundational to all results

**No Validation for Statistical Models:**
- What's not tested: Model convergence, coefficient extraction, result output
- Files: All multi_GWAS_*.R files, PheWAS Analyses Rmd (model fitting sections)
- Risk: Silent convergence failures; incorrect coefficient storage; malformed output files go undetected
- Priority: High - wrong statistical results could invalidate conclusions

**No Pipeline Integration Tests:**
- What's not tested: End-to-end workflow from raw sumstats to final PRS analysis; intermediate file format compatibility
- Files: Entire pipeline from CD_sumstats.R through PheWAS Analyses
- Risk: Individual scripts may work but pipeline breaks at integration points; no verification that outputs match expected format
- Priority: Medium - prevents reproducibility verification

**No Error Recovery Tests:**
- What's not tested: Handling of missing input files, malformed data, convergence failures, memory limits
- Files: All analysis scripts
- Risk: Pipeline stops at unknown points; users must manually investigate; no clear error messages for debugging
- Priority: Medium - improves robustness

## Missing Critical Features

**No Workflow Orchestration:**
- Problem: Pipeline requires manual execution of multiple scripts in specific order; no automation of intermediate steps; no checkpoint system for restart capability
- Blocks: Cannot reliably re-run failed analyses; difficult to audit which analyses have completed; hard to update single step without manual resubmission

**No Results Aggregation Framework:**
- Problem: GWAS results are written to 914+ CSV files per analysis; no automated aggregation, validation, or summary statistics
- Blocks: Cannot efficiently combine results; no automated quality control of output files; downstream analyses must manually locate and process outputs

**No Reproducibility Metadata:**
- Problem: No record of computational environment, package versions, input data versions, or execution parameters
- Blocks: Results cannot be fully reproduced; impossible to debug version-specific issues; no clear audit trail for peer review

**No Visualization or Quality Control Report:**
- Problem: Results exist but no automated diagnostics for model fit quality, convergence issues, or outlier detection
- Blocks: Cannot quickly assess analysis quality; convergence warnings are captured but never reviewed; potential issues go undetected

---

*Concerns audit: 2026-03-04*
