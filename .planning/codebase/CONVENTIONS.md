# Coding Conventions

**Analysis Date:** 2026-03-04

## Naming Patterns

**Files:**
- Mixed naming convention used: `snake_case` for data processing files (`split_sumstats_CD2.R`, `cross_disorder_munge.R`) and `CamelCase` for analysis files (`PheWAS Analyses Resub5.Rmd`)
- File names are descriptive of their purpose (e.g., `LDSC.R` for LDSC analysis, `multi_GWAS_CD2.R` for cross-disorder GWAS)
- Pattern: `script_purpose.R` or `Analysis_Description.Rmd`

**Functions:**
- Function names use `snake_case`: `withWarnings()`, `split()`, `write.table()`, `read.table()`
- Custom functions defined with lowercase: `withWarnings <- function(expr)`
- Functions use descriptive names that indicate purpose
- Example from `PheWAS Analyses Resub5.Rmd`: `withWarnings()` clearly indicates warning capture behavior

**Variables:**
- Mixed convention: `snake_case` for local variables, `CamelCase` for data frames
- Data frames use `PascalCase`: `PheWAS_baseline`, `CD_sumstats`, `LDSCoutput_CD`, `Ind_Compulsive_Mod`
- Vectors use `snake_case` or simple letters: `N`, `se.logit`, `files`, `traits`, `sample.prev`
- Temporary/loop variables use single letters: `i`, `a`, `x`
- Aggregated results use descriptive `PascalCase`: `Results`, `Results_cont`, `Results_cat`, `Beta`, `STE`, `Pval`, `Area`, `Warn`
- Example from `LDSC.R`: `traits`, `sample.prev`, `population.prev`, `ld`, `wld`, `trait.names`, `LDSCoutput_CD`

**Types:**
- Data types indicated by usage context: logical vectors (`se.logit <- c(F,F,T...)`)
- No explicit type annotations used; R's implicit typing followed
- Character vectors: `files <- list("adhd_eur_jun2017.txt", ...)`
- Numeric vectors: `N = c(49735.8584, 43777.8191, ...)`

## Code Style

**Formatting:**
- No automated formatter detected (.prettierrc, .Rprofile, etc.)
- Indentation: 2 spaces for nested code blocks (observed in Rmd file code chunks)
- Line breaks: Long function calls broken across multiple lines
- Example from `CD_sumstats.R`:
  ```r
  CD_sumstats <- sumstats(files=files,ref=ref,trait.names=c("adhd", "asd", "gad", "ocd", "pau", "an",
                                                            "bip", "mdd", "ptsd", "scz", "ts"),
                          se.logit=se.logit,OLS = OLS,linprob=NULL,prop=prop, info.filter=.6, maf.filter=0.01,
                          keep.indel=FALSE,parallel=FALSE,cores=NULL)
  ```
- Arguments aligned vertically when wrapping
- Space around operators: `=`, `<-`, `~`
- No spaces inside function parentheses: `function()` not `function ()`

**Linting:**
- No linter configuration detected (no .lintr, .Rprofile)
- Code follows base R style conventions informally
- No automated style checking tools in place

## Import Organization

**Order:**
1. Core tidyverse packages: `library(data.table)`, `library(dplyr)`, `library(tidyr)`, `library(purrr)`
2. Statistical/modeling packages: `library(lmerTest)`, `library(lme4)`, `library(lavaan.survey)`, `library(glmmTMB)`
3. Visualization packages: `library(ggplot2)`, `library(ggrepel)`, `library(ggsci)`, `library(RColorBrewer)`
4. Data handling: `library(readxl)`, `library(reshape2)`
5. Specialized packages: `library(GenomicSEM)`, `library(survey)`, `library(DHARMa)`, `library(glmnet)`

**Path Aliases:**
- No path aliases used
- Relative file paths used throughout: `"./split_sumstats/split_sumstats3/sumstatsNUMBER.txt"`
- Data directory structure referenced as: `./split_sumstats/`, `./results/`, `./results_indep/`

**Load patterns:**
- `library()` preferred over `require()` for main packages (e.g., `library(devtools)`)
- `require()` used for GenomicSEM: `require(GenomicSEM)` (pattern inconsistency)
- Order: External packages first, then custom library loads

## Error Handling

**Patterns:**
- Custom warning capture implemented via `withWarnings()` function defined in Rmd
- Used with `withCallingHandlers()` to muffled warnings in loops
- Example from `PheWAS Analyses Resub5.Rmd` (lines 69-77):
  ```r
  withWarnings <- function(expr) {
    myWarnings <- NULL
    wHandler <- function(w) {
      myWarnings <<- c(myWarnings, list(w))
      invokeRestart("muffleWarning")
    }
    val <- withCallingHandlers(expr, warning = wHandler)
    list(value = val, warnings = myWarnings)
  }
  ```
- Applied to model fitting: `LMEOut <- withWarnings( a <- lmer(...) )`
- Warnings captured in vector: `Warn[i] <- LMEOut$warnings`
- No explicit error catching with `tryCatch()` detected
- No validation checks (stopifnot) observed
- Silent failures: Missing data handled implicitly with `na.rm=TRUE` in functions

## Logging

**Framework:** Base R `print()` function

**Patterns:**
- Status messages printed to console: `print("loading summary statistics from set NUMBER...")`
- Progress tracking: `print(i)` for loop counter output
- Completion messages: `print("finished loading summary statistics from set NUMBER")`
- No structured logging framework (no logging package)
- File output via `write.table()`, `write.csv()`, `fwrite()` for results
- Example from `multi_GWAS_CD2.R`:
  ```r
  print("loading summary statistics from set NUMBER...")
  split_sumstats <- read.table("./split_sumstats/split_sumstats3/sumstatsNUMBER.txt", header = TRUE)
  print("finished loading summary statistics from set NUMBER")
  ```

## Comments

**When to Comment:**
- Section headers use `###` for major sections: `### load necessary packages`
- Descriptive comments for non-obvious operations
- Inline comments explaining data transformations
- Comments on parameter changes requested: `#******CHANGE*******add your covariates...`
- Commented-out code for alternatives: `#remotes::install_version()`, `#install.packages()`, `#edit_r_environ()`

**JSDoc/TSDoc:**
- Not used; R documentation not generated
- Function definitions lack formal documentation strings
- Comments above functions describe purpose informally

## Function Design

**Size:**
- Most scripts are short data processing pipelines (16-92 lines)
- Single-purpose files (e.g., `LDSC.R` is 13 lines, `CD_sumstats.R` is 24 lines)
- Larger analysis Rmd file is segmented into code chunks by research question
- Multi-step functions broken into sequential statements rather than helper functions

**Parameters:**
- Functions accept multiple arguments without validation
- Example from `withWarnings()`: Single expression parameter
- GenomicSEM functions use named arguments extensively
- Optional parameters with defaults: `write.table(..., quote=FALSE, row.names=FALSE)`
- No parameter validation checks observed

**Return Values:**
- Functions return data structures (data frames, lists)
- `withWarnings()` returns named list: `list(value = val, warnings = myWarnings)`
- Implicit returns from last expression (R default)
- Results assigned to named objects for downstream use

## Module Design

**Exports:**
- No formal module/package structure
- Script files save results via `save()`, `write.csv()`, `fwrite()` to disk
- RData files: `save(CD_sumstats, file="CD_sumstats.RData")`
- CSV files used for sharing results: `write.csv(CF1, file="./results/F1_sumstats/NUMBER.csv")`

**Barrel Files:**
- Not applicable; no package structure
- Each R file is standalone executable script
- Dependencies managed through explicit `load()` and `read.table()` calls

---

*Convention analysis: 2026-03-04*
