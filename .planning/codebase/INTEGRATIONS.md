# External Integrations

**Analysis Date:** 2026-03-04

## Data Sources & APIs

**Genetic Databases:**
- 1000 Genomes reference data
  - Purpose: Reference allele frequencies and LD block structure
  - Integration: Used in summary statistics processing and LDSC calculations
  - Files referenced: `reference.1000G.maf.0.005.txt`, `eur_w_ld_chr/` directory, `ldblk_1kg_eur/`

- HapMap3 SNP list
  - Purpose: SNP quality filtering during GWAS munge
  - File: `w_hm3.snplist`
  - Used in: `cross_disorder_munge.R`

**GWAS Summary Statistics:**
Multiple publicly available GWAS summary statistics for psychiatric phenotypes:
- ADHD: `adhd_eur_jun2017.txt` (European ancestry, 49,736 samples)
- ASD: `ASD.txt` (43,778 samples)
- GAD: `dbGAP_GAD2eur.txt` (175,163 samples)
- OCD: `ocd_aug2017.txt` (7,281 samples)
- Panic/Agoraphobia: `PAU.txt` (435,563 samples)
- Anorexia Nervosa: `pgc_AN2_2.txt` (46,322 samples)
- Bipolar: `pgc_BIP.txt` (101,963 samples)
- MDD: `PGC_UKB_depression_genome-wide.txt` (449,150 samples)
- PTSD: `PTSD_freeze2.txt` (70,332 samples)
- Schizophrenia: `SCZ3.txt` (157,013 samples)
- Tourette Syndrome: `TS.txt` (12,140 samples)

  Implementation: Direct file loading in `CD_sumstats.R`, `cross_disorder_munge.R`
  No API integration - files are local

## Data Storage

**Databases:**
- None detected - Not a traditional database application

**File Storage:**
- Local filesystem only
  - Input data: GWAS summary statistics (`.txt`), reference files
  - Processing: Intermediate `.RData` files for checkpointing
  - Output: CSV result files organized by analysis factor and SNP set
  - Location paths: `./split_sumstats/`, `./results/`, `./results_indep/`

**Caching:**
- `.RData` files serve as cache/checkpoint system:
  - `CD_sumstats.RData` - Cached processed summary statistics
  - `LDSCoutput_CD.RData` - Cached LDSC covariance matrices
  - Loaded via `load()` function in R scripts
  - Reduces recomputation of expensive munging and LDSC steps

**Phenotype Data:**
- Excel file: `FINAL_PHEWAS_baseline_n5556_5.11.23.xlsx`
  - Contains: ABCD baseline clinical and behavioral phenotypes
  - Loaded in: `PheWAS Analyses Resub5.Rmd` line 85
  - Format: XLSX with mixed numeric and categorical columns
  - Scope: n=5,556 participants

## Authentication & Identity

**Auth Provider:**
- None detected - No user authentication system

**API Keys:**
- OpenAI API key
  - Variable: `OPENAI_API_KEY`
  - Status: Commented out in code (`PheWAS Analyses Resub5.Rmd` line 61)
  - Purpose: Would enable GPT integration for analytical commentary (experimental)
  - Access method: Would be set via `.Renviron` or environment variable

## Monitoring & Observability

**Error Tracking:**
- None detected - No formal error tracking service

**Logs:**
- SLURM log files (HPC job output)
  - Naming pattern: `*.out` and `*.err` files
  - Examples: `CD_munge.out`, `CD_munge.err`, `PRScsComp-chr%a.out`
  - Location: Specified in SLURM headers: `--output=` and `--error=` directives
  - Purpose: Job execution logs and error messages
  - Accessed via: HPC job management commands

- R console output
  - Mechanism: `print()` statements in R scripts (e.g., "loading summary statistics", "finished loading")
  - Logged to: SLURM stdout/stderr when run via HPC

**Metrics:**
- Not detected - No metrics collection infrastructure

## CI/CD & Deployment

**Hosting:**
- HPC Cluster (location: `aalab` partition based on SLURM scripts)
  - Job submission: SLURM scheduler
  - Workspace: `/scratch/aalab/` for working data

**CI Pipeline:**
- Not detected - No automated CI/CD pipeline

**Execution Model:**
- Manual workflow orchestration via shell scripts
- Sequential dependency chain:
  1. `cross_disorder_munge.sh` - Munge GWAS data
  2. `CD_sumstats.sh` (via `CD_sumstats.R`) - Prepare summary statistics
  3. `split_sumstats_CD2.R` - Partition SNP sets
  4. `multi_GWAS_CD2.sh` / `multi_GWAS_CD2_ind_*.sh` - Run multivariate GWAS (parallelized)
  5. `PheWAS Analyses Resub5.Rmd` - Generate PheWAS results and figures

## Environment Configuration

**Required Environment Variables:**
- `OPENAI_API_KEY` - For GPT integration (optional, commented out)

**Configuration Files:**
- SLURM batch script headers define HPC resources:
  - Job name, node allocation, CPU/memory, output paths
  - Array job ranges for chromosome parallelization
  - Module loads: `r/3.4.4-python-2.7.15-java-11`

**Secrets Location:**
- Not applicable - No production secrets detected
- OpenAI key would be stored in `.Renviron` (not committed to repo)

## Webhooks & Callbacks

**Incoming:**
- Not detected - No webhook endpoints

**Outgoing:**
- Not detected - No outgoing webhook calls

## External Command-Line Tools

**PRScs:**
- Tool: `/ref/aalab/software/PRScs/PRScs.py`
- Type: Python external tool for polygenic risk score calculation
- Called in: `PRScs_ABCD_EUR_*.sh` shell scripts
- Parameters:
  - `--ref_dir` - LD reference block directory
  - `--bim_prefix` - Genotype file prefix
  - `--chrom` - Chromosome number (from SLURM array ID)
  - `--sst_file` - GWAS summary statistics input
  - `--n_gwas` - Sample size for calibration
  - `--out_dir` - Output directory for scores
- Integration: Called from SLURM job array for parallel processing across 22 chromosomes

## Data Flow Summary

```
GWAS Summary Statistics (11 phenotypes)
    ↓
cross_disorder_munge.R (Munge for LDSC)
    ↓
CD_sumstats.R (Standardize alleles, compute coefficients)
    ↓
LDSC.R (Calculate genetic covariance matrix)
    ↓
split_sumstats_CD2.R (Partition into 6000 SNP sets)
    ↓
multi_GWAS_CD2.R (Multivariate GWAS with SNP effects)
    ↓
ABCD Phenotype Data (Excel)
    ↓
PheWAS Analyses Resub5.Rmd (PRS-PheWAS associations)
    ↓
Results (CSV files organized by factor and SNP set)
```

## Integration Points Requiring Attention

**Data Dependencies:**
- GWAS summary statistics files must be in working directory before analysis
- 1000 Genomes reference files must be accessible via specified paths
- ABCD phenotype Excel file must be in exact location: `FINAL_PHEWAS_baseline_n5556_5.11.23.xlsx`

**Path Dependencies:**
- PRScs tool path: `/ref/aalab/software/PRScs/PRScs.py` (absolute, HPC-specific)
- LD reference directory: `ldblk_1kg_eur/` (must be accessible before PRScs execution)
- Working directories: Relative paths in R scripts depend on correct working directory

**Resource Constraints:**
- Memory: 20GB jobs (LDSC calculations) - check HPC allocation
- CPU: Jobs request 1-6 cores - adjust `--cpus-per-task` based on system
- Disk: Large intermediate `.RData` files - ensure scratch space available

---

*Integration audit: 2026-03-04*
