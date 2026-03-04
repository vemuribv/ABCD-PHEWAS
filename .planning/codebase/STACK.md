# Technology Stack

**Analysis Date:** 2026-03-04

## Languages

**Primary:**
- R (Version 3.4.4+) - Core analysis language for all GWAS, PheWAS, and statistical modeling

**Supporting:**
- Bash - Job submission and workflow orchestration on HPC systems
- YAML - SLURM job configuration (via shell script headers)

## Runtime

**Environment:**
- R 3.4.4-python-2.7.15-java-11 (loaded via HPC module system)
  - Specified in: `cross_disorder_munge.sh` and related SLURM scripts
  - Module loading: `ml load r/3.4.4-python-2.7.15-java-11`

**Package Manager:**
- CRAN (R package repository)
- No lockfile present (version pinning handled via explicit `install_version()` calls where needed)

## Frameworks

**Core Statistical Frameworks:**
- **GenomicSEM** - Primary package for multivariate GWAS and genomic structural equation modeling
  - Used in: `CD_sumstats.R`, `LDSC.R`, `multi_GWAS_CD2.R`, `multi_GWAS_ind_*.R`, `cross_disorder_munge.R`
  - Core functions: `sumstats()`, `munge()`, `ldsc()`, `userGWAS()`

**Statistical Modeling:**
- **lavaan** (with lavaan.survey extension v1.1.3.1) - Structural equation modeling
  - Explicit version pin in: `PheWAS Analyses Resub5.Rmd` line 30
- **lme4** / **lmerTest** - Linear mixed effects models with hypothesis testing
- **glmmTMB** - Generalized linear mixed models via Template Model Builder

**Data Wrangling:**
- **dplyr** - Data manipulation and tidyverse ecosystem
- **data.table** - Fast data frame operations
- **tidyr** - Data reshaping and pivoting
- **plyr** - Data splitting, applying, combining

**Visualization:**
- **ggplot2** - Grammar of graphics for statistical visualization
- **ggrepel** - Text and label repulsion
- **ggsci** - Scientific journal color scales
- **ggforce** - Extensions to ggplot2
- **ggh4x** - Hierarchical faceting and color scales
- **ggnewscale** - Multiple scales per aesthetic
- **ggpubr** - Publication-ready plots
- **gplots** - Heatmaps and other plots
- **RColorBrewer** - Color palettes
- **Polychrome** - Qualitative color palettes

**Statistical Analysis:**
- **survey** - Complex survey sampling analysis
- **psych** - Factor analysis, descriptive statistics
- **caret** - Classification and regression training
- **glmnet** - Elastic net regularization
- **optimx** / **minqa** / **dfoptim** - Numerical optimization
- **mice** - Multiple imputation by chained equations
- **RNOmni** - Rank-based inverse normal transformation
- **DHARMa** - Residual diagnostics for GLMMs
- **naniar** / **VIM** - Missing data visualization and handling
- **DescTools** - Descriptive statistics and confidence intervals
- **stringr** - String manipulation
- **forcats** - Factor manipulation

**Development & Reporting:**
- **rmarkdown** - Reproducible documents (R Markdown)
  - Output formats: PDF, HTML, Word
- **devtools** - Development tools (package building, installation from GitHub)
- **readxl** - Excel file reading
- **openai** - OpenAI API integration (GPT for analytical commentary)
- **remotes** - Package installation from remote sources
- **tibble** / **purrr** - Modern data structures and functional programming

**Parallel Computing:**
- **doParallel** - Parallel backend for foreach
- **foreach** - Loop parallelization
- **future.apply** - Functional programming with futures
- **parallel** - Base R parallel computing
- **progress** - Progress bar for long operations

## Build/Dev Tools

**HPC Job Submission:**
- SLURM (Simple Linux Utility for Resource Management)
  - Arrays for chromosome-parallel processing (PRScs scripts)
  - Job configuration in shell script headers

**Python Integration:**
- PRScs - Python-based polygenic risk score calculation
  - External dependency: `/ref/aalab/software/PRScs/PRScs.py`
  - Referenced in: `PRScs_ABCD_EUR_*.sh` scripts

## Key Dependencies

**Critical:**
- **GenomicSEM** - Central to entire analysis pipeline. Handles summary statistics munging, covariance matrix calculation via LDSC, and multivariate GWAS.
  - Impact: Without this, cannot perform core analyses

**Infrastructure:**
- **lavaan.survey** (v1.1.3.1) - Specific version required for survey-weighted structural equation modeling
- **lme4/lmerTest** - Required for mixed-effects analysis in PheWAS
- **ggplot2 ecosystem** - Required for all figure generation

## Configuration

**Environment:**
- R environment variables: `OPENAI_API_KEY` (commented out in code, would be set via `.Renviron`)
- HPC resource allocation via SLURM headers in shell scripts
- Working directories specified as local paths (e.g., `./split_sumstats/`, `./results/`)

**Build/Execution:**
- SLURM configuration headers in shell scripts define:
  - CPU allocation: 1 to 6 cores per task
  - Memory: 10GB to 20GB per job
  - Array job ranges for chromosome-parallel processing (e.g., `--array=1-22` for 22 chromosomes)
  - Output directories for logs and results

## Data Requirements

**Input Data:**
- GWAS summary statistics for 11 psychiatric phenotypes (stored as `.txt` files)
  - Loaded in: `CD_sumstats.R`
  - Source files: ADHD, ASD, GAD, OCD, Panic/Agoraphobia, Anorexia, Bipolar, MDD, PTSD, Schizophrenia, Tourette's

- 1000 Genomes reference files:
  - `reference.1000G.maf.0.005.txt` - Reference allele frequencies
  - `w_hm3.snplist` - HapMap3 SNP list for LDSC
  - LD block files: `eur_w_ld_chr/` directory

- ABCD phenotype data:
  - `FINAL_PHEWAS_baseline_n5556_5.11.23.xlsx` - Baseline clinical data

**Intermediate Data:**
- `.RData` files for checkpointing:
  - `CD_sumstats.RData` - Processed summary statistics
  - `LDSCoutput_CD.RData` - LDSC covariance matrices
  - `cross_disorder_munge.Rdata` - Munged GWAS data

**Output Data:**
- CSV files with GWAS results organized by SNP sets and factors:
  - `./results/F1_sumstats/`, `./results/F2_sumstats/`, etc.
  - `./results_indep/Compulsive/`, `./results_indep/Neurodev/`, etc.

## Platform Requirements

**Development:**
- macOS, Linux, or HPC cluster environment (demonstrated by SLURM usage)
- R 3.4.4+ with CRAN package repository access
- Python 2.7.15+ (for PRScs)
- Java 11 (bundled with R module)

**Production/Analysis:**
- HPC cluster with SLURM scheduler
- Minimum 20GB RAM for largest jobs
- Multi-core processors (up to 6 cores utilized)
- Network access to GWAS summary statistics repositories and reference data servers

## External Tool Dependencies

**PRScs:**
- Location: `/ref/aalab/software/PRScs/PRScs.py`
- Purpose: Polygenic risk score calculation with continuous shrinkage
- Input: GWAS summary statistics, LD reference blocks
- Called via: `PRScs_ABCD_EUR_*.sh` scripts

**LD Reference Blocks:**
- Location: `ldblk_1kg_eur/` (external reference, not in repo)
- Source: 1000 Genomes European ancestry samples

---

*Stack analysis: 2026-03-04*
