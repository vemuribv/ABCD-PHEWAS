# Architecture

**Analysis Date:** 2026-03-04

## Pattern Overview

**Overall:** Multi-stage genomic statistical analysis pipeline

**Key Characteristics:**
- Sequential processing workflow with discrete, reusable stages
- Heavy reliance on GenomicSEM package for structural equation modeling
- Parallel computation for scalable GWAS analysis
- Data transformation and preparation at each stage
- Integration of multiple GWAS summary statistics across 11 psychiatric phenotypes

## Layers

**Data Preparation Layer:**
- Purpose: Munge raw GWAS summary statistics, filter SNPs, standardize across datasets
- Location: `cross_disorder_munge.R`, `CD_sumstats.R`
- Contains: Data filtering (MAF, info scores), reference allele alignment, format standardization
- Depends on: GenomicSEM package, raw GWAS summary statistics files, reference datasets
- Used by: Statistical modeling layers

**Covariance Estimation Layer:**
- Purpose: Compute genetic covariance matrix among 11 psychiatric phenotypes using LD Score Regression
- Location: `LDSC.R`
- Contains: LD score regression computation, trait prevalence calculations, covariance matrix generation
- Depends on: Munged GWAS summary statistics, LD reference data (eur_w_ld_chr/)
- Used by: Multivariate GWAS model specification

**Data Splitting Layer:**
- Purpose: Partition large SNP datasets into manageable chunks for parallel processing
- Location: `split_sumstats_CD2.R`
- Contains: SNP dataset chunking (6000 SNPs per chunk), file serialization
- Depends on: CD_sumstats.RData from preparation layer
- Used by: Multivariate GWAS analysis

**Multivariate GWAS Layer:**
- Purpose: Conduct structural equation modeling of SNP effects on latent factors
- Location: `multi_GWAS_CD2.R`, `multi_GWAS_ind_*.R` (Compulsive, Psychotic, Neurodev, Internal)
- Contains: Factor model specification, SNP effect estimation, parallel GWAS execution
- Depends on: Split summary statistics, LDSC covariance matrix, GenomicSEM userGWAS function
- Used by: Results aggregation and PheWAS analysis

**Analysis & Visualization Layer:**
- Purpose: Aggregate GWAS results, conduct PRS-PheWAS analyses, generate figures
- Location: `PheWAS Analyses Resub5.Rmd`
- Contains: PRS calculation, phenotype association testing, effect estimation, visualization generation
- Depends on: Multivariate GWAS results, ABCD phenotype data, PRS weights
- Used by: Publication/reporting

## Data Flow

**Primary Pipeline Flow:**

1. **Munge Stage** (`cross_disorder_munge.sh` → `cross_disorder_munge.R`)
   - Input: Raw GWAS summary statistics (11 files: adhd_eur_jun2017.txt, ASD.txt, dbGAP_GAD2eur.txt, etc.)
   - Process: Filter by HM3 SNPs, MAF ≥ 0.01, info ≥ 0.9
   - Output: `cross_disorder_munge.Rdata` (standardized summary statistics)

2. **Summary Statistics Preparation** (`CD_sumstats.R`)
   - Input: Raw GWAS files, reference dataset (reference.1000G.maf.0.005.txt), sample sizes
   - Process: standardize alleles, handle logit SE transformations, apply MAF/info filters
   - Output: `CD_sumstats.RData` (prepared multivariate summary statistics object)

3. **LD Score Regression** (`LDSC.R`)
   - Input: Prepared summary statistics, LD reference data (eur_w_ld_chr/)
   - Process: Estimate genetic covariance matrix among 11 traits, account for prevalence
   - Output: `LDSCoutput_CD.RData` (11x11 genetic covariance matrix)

4. **SNP Dataset Splitting** (`split_sumstats_CD2.R`)
   - Input: `CD_sumstats.RData`
   - Process: Split into chunks of 6000 SNPs for parallel processing
   - Output: Multiple text files in `./split_sumstats/split_sumstats2/` (sumstats0.txt, sumstats1.txt, ..., sumstats914.txt)
   - Metadata: `num_SNP_sets2.txt` (total number of sets = 915)

5. **Multivariate GWAS - Correlated Factors Model** (`multi_GWAS_CD2.sh` → `multi_GWAS_CD2.R`)
   - Input: Each SNP chunk from split_sumstats2/, LDSC covariance matrix
   - Process: For each SNP chunk, fit SEM with 4 latent factors (Compulsive, Psychotic, Neurodev, Internal) with cross-factor covariances and SNP effects on all factors
   - Output: 4 result files per SNP set in `./results/F1_sumstats/`, `./results/F2_sumstats/`, `./results/F3_sumstats/`, `./results/F4_sumstats/`
   - Execution: SLURM job array (0-914 chunks, 8 CPUs/task, 4GB mem per task, parallel=TRUE cores=6)

6. **Multivariate GWAS - Independent Factor Models** (4 parallel workflows)
   - `multi_GWAS_CD2_ind_Compulsive.sh` → `multi_GWAS_ind_Compulsive.R`
   - `multi_GWAS_CD2_ind_Psychotic.sh` → `multi_GWAS_ind_Psychotic.R`
   - `multi_GWAS_CD2_ind_Neurodev.sh` → `multi_GWAS_ind_Neurodev.R`
   - `multi_GWAS_CD2_ind_Internal.sh` → `multi_GWAS_ind_Internal.R`
   - Process: Same SEM structure but SNP effects constrained to operate only through specific factor indicators (e.g., only through Compulsive indicators for Compulsive model)
   - Output: Independent results sets in `./results_indep/[Factor]/F1_sumstats/`, etc.

7. **PheWAS Analysis & Visualization** (`PheWAS Analyses Resub5.Rmd`)
   - Input: Multivariate GWAS results, ABCD baseline phenotype data (FINAL_PHEWAS_baseline_n5556_5.11.23.xlsx), PRS weights
   - Process: Calculate PRS per participant, test association with 650+ phenotypes, adjust for covariates/site/family structure, generate publication figures
   - Output: Statistical results, plots, summary tables (PDF/HTML/Word via RMarkdown)

**State Management:**
- RData files serve as pipeline checkpoints (cross_disorder_munge.Rdata, CD_sumstats.RData, LDSCoutput_CD.RData)
- Shell scripts use sed templating to dynamically insert SNP set numbers
- Results accumulated across 915 parallel job submissions before aggregation
- No persistent state manager; reliance on filesystem for intermediate results

## Key Abstractions

**Factor Model:**
- Purpose: Represent latent psychopathology dimensions (Compulsive, Psychotic, Neurodevelopmental, Internalizing) with observable disorder indicators
- Examples: `multi_GWAS_CD2.R` lines 18-61 (corr_fact_mod), `multi_GWAS_ind_Compulsive.R` lines 18-63
- Pattern: Lavaan syntax for SEM specification; factors defined as linear combinations of disorders with fixed/free loadings; factor covariances explicitly specified

**Genetic Covariance Structure:**
- Purpose: Encode genetic correlations between psychiatric phenotypes derived from LDSC
- Examples: LDSC matrix stored in `LDSCoutput_CD.RData`, used in `multi_GWAS_CD2.R` line 64
- Pattern: Symmetric covariance matrix input to userGWAS; constrains SNP effect estimation across traits

**SNP Batch Processing:**
- Purpose: Enable parallelization of computationally intensive GWAS across manageable chunks
- Examples: `split_sumstats_CD2.R` lines 4-14, `multi_GWAS_CD2.sh` lines 17-25 (sed template)
- Pattern: Master script (multi_GWAS_CD2.R) with NUMBER placeholder replaced per job; SLURM array job distributes chunks; results collected per chunk

## Entry Points

**Data Preparation Entry:**
- Location: `cross_disorder_munge.sh`
- Triggers: Manual job submission to SLURM cluster
- Responsibilities: Load GenomicSEM, munge 11 raw GWAS files, output standardized statistics object

**Summary Statistics Entry:**
- Location: `CD_sumstats.R` (executed standalone)
- Triggers: Post-munge, manually invoked
- Responsibilities: Transform raw files into multivariate summary statistics object with aligned alleles and scaled coefficients

**LD Score Regression Entry:**
- Location: `LDSC.R` (executed standalone)
- Triggers: Post-munge, manually invoked in parallel with CD_sumstats.R
- Responsibilities: Compute genetic covariance matrix using summary statistics and LD reference data

**Multivariate GWAS Entries:**
- Location: `multi_GWAS_CD2.sh`, `multi_GWAS_CD2_ind_Compulsive.sh`, etc.
- Triggers: SLURM job submission; depends on split_sumstats_CD2.R completion
- Responsibilities: Parallelize GWAS across SNP chunks; fit SEM per chunk; collect results

**PheWAS Analysis Entry:**
- Location: `PheWAS Analyses Resub5.Rmd`
- Triggers: Manual RMarkdown render/knit
- Responsibilities: Load phenotype data and multivariate GWAS results; calculate PRS; test associations; generate publication-quality figures

## Error Handling

**Strategy:** Minimal formal error handling; relies on batch job logging and manual inspection

**Patterns:**
- SLURM job logging: stdout/stderr captured in `./results/set.%a.out` and `./results/set.%a.err` per job array
- R print statements for progress tracking (e.g., `print("GWAS completed")` in `multi_GWAS_CD2.R` line 65)
- File-based validation: num_SNP_sets.txt records expected chunk count for downstream verification
- No explicit try-catch blocks; early termination on data loading or computation failures

## Cross-Cutting Concerns

**Logging:** GenomicSEM and R base functions emit to stdout/stderr; user-inserted print() statements mark major pipeline stages

**Validation:** MAF filtering (0.01), info score thresholds (0.6 in CD_sumstats.R, 0.9 in cross_disorder_munge.R), SNP presence in reference datasets

**Resource Constraints:** Parallel batch sizes set manually (cores=6 in userGWAS calls); SLURM configuration hardcoded (8 CPUs, 4GB mem per multi_GWAS_CD2.sh job)

---

*Architecture analysis: 2026-03-04*
