# Architecture Research

**Domain:** PheWAS cluster characterization pipeline (Python, research/bioinformatics)
**Researched:** 2026-03-04
**Confidence:** HIGH (core pipeline pattern), MEDIUM (ABCD-specific domain mapping details)

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Input Layer                           │
│  ┌──────────────────┐       ┌──────────────────────────┐    │
│  │  cluster_file    │       │  phenotype_file          │    │
│  │  (subj_id +      │       │  (subj_id + 3000+ cols)  │    │
│  │   cluster_label) │       │                          │    │
│  └────────┬─────────┘       └────────────┬─────────────┘    │
│           │                              │                   │
└───────────┼──────────────────────────────┼───────────────────┘
            │                              │
┌───────────▼──────────────────────────────▼───────────────────┐
│                     Data Loader / Merger                      │
│  - Join on subject ID                                         │
│  - Filter to subjects present in both files                   │
│  - Validate cluster label range (2-8)                         │
└───────────────────────────────┬──────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────┐
│                   Variable Classifier                         │
│  - Infer type per column: binary / categorical /             │
│    ordinal / continuous                                       │
│  - Flag high-missingness columns                             │
│  - Map variables to ABCD domains via data dictionary         │
└──────────┬─────────────────────────────────┬─────────────────┘
           │                                 │
           ▼                                 ▼
    [Variable metadata]              [Domain mapping table]
    {var: type, domain}              {var: domain_label}
           │
┌──────────▼──────────────────────────────────────────────────┐
│               Statistical Test Engine                        │
│                                                              │
│  ┌──────────────────┐      ┌──────────────────────────┐     │
│  │  Global Test     │      │  One-vs-Rest Tests        │     │
│  │  (K clusters)    │      │  (per cluster, per var)   │     │
│  │  KW / chi2 / F   │      │  Mann-Whitney / Fisher /  │     │
│  │                  │      │  t-test                   │     │
│  └────────┬─────────┘      └────────────┬──────────────┘     │
│           │                             │                    │
│           └──────────┬──────────────────┘                    │
│                      │                                       │
│         ┌────────────▼────────────┐                         │
│         │  Effect Size Calculator  │                         │
│         │  Cohen's d / OR /       │                         │
│         │  Cramer's V / eta^2     │                         │
│         └────────────┬────────────┘                         │
└──────────────────────┼──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              Multiple Comparison Correction                   │
│  - BH FDR (Benjamini-Hochberg)                               │
│  - Bonferroni                                                │
│  - Applied globally across all variables x comparisons       │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                   Results Assembler                           │
│  - Merge p-values, corrected p-values, effect sizes          │
│  - Attach domain labels                                      │
│  - Write results tables (CSV/TSV)                            │
└──────────┬────────────────────────────────────┬─────────────┘
           │                                    │
┌──────────▼─────────────┐          ┌───────────▼─────────────┐
│   Manhattan Plot        │          │   Heatmap               │
│   -log10(p) by variable │          │   Cluster x Sig-Var     │
│   colored by domain     │          │   effect direction +    │
│                         │          │   significance          │
└─────────────────────────┘          └─────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| Data Loader | Merge cluster assignments and phenotype file on subject ID; validate inputs | pandas merge + assertions |
| Variable Classifier | Detect variable type (binary/categorical/ordinal/continuous) per column; flag missingness; attach domain labels | pandas dtype inspection + cardinality heuristics; dict/CSV lookup for domain mapping |
| Domain Mapper | Map variable names to ABCD domain labels using the data dictionary table names | dict from ABCD data-dict TSV or manual curation |
| Statistical Test Engine | Dispatch correct test per variable type; run global (K-group) and one-vs-rest comparisons | scipy.stats (kruskal, chi2_contingency, f_oneway, fisher_exact, mannwhitneyu); pingouin for effect sizes |
| Effect Size Calculator | Compute appropriate effect size per type: Cohen's d, odds ratio, Cramer's V, eta-squared | pingouin or manual numpy/scipy formulas |
| Multiple Comparison Corrector | Apply BH FDR and Bonferroni to the flat list of all p-values | statsmodels.stats.multitest.multipletests |
| Results Assembler | Collect all stats into one tidy DataFrame; write TSV output | pandas DataFrame, to_csv |
| Manhattan Plotter | Plot -log10(p) on y-axis, variables ordered by domain on x-axis, colored by domain; add significance threshold lines | matplotlib / seaborn |
| Heatmap Generator | Rows = significant variables, columns = clusters; cell color = effect direction + magnitude; annotate significance | seaborn.clustermap or matplotlib imshow |
| CLI / Entrypoint | Parse arguments (input files, cluster count, timepoint, output directory); orchestrate full run | argparse or click |

## Recommended Project Structure

```
abcd_phewas/
├── data/
│   ├── domain_map.tsv          # ABCD variable → domain label (curated once)
│   └── variable_metadata.tsv   # Optional: pre-classified variable types
├── abcd_phewas/
│   ├── __init__.py
│   ├── cli.py                  # Entrypoint: argparse/click, orchestrates run
│   ├── loader.py               # Data loading, subject ID merging, validation
│   ├── classifier.py           # Variable type inference, domain mapping
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── global_tests.py     # K-group tests (KW, chi2, ANOVA)
│   │   └── one_vs_rest.py      # Binary comparisons per cluster
│   ├── effects.py              # Effect size calculation per type
│   ├── correction.py           # BH FDR + Bonferroni via statsmodels
│   ├── results.py              # Assembles DataFrame, writes TSV
│   └── plots/
│       ├── __init__.py
│       ├── manhattan.py        # PheWAS Manhattan plot
│       └── heatmap.py          # Cluster x variable heatmap
├── notebooks/                  # Exploratory / validation notebooks
├── tests/                      # pytest unit tests
│   ├── test_loader.py
│   ├── test_classifier.py
│   ├── test_tests.py
│   └── test_plots.py
├── pyproject.toml
└── README.md
```

### Structure Rationale

- **abcd_phewas/tests/:** Statistical tests are the most complex and testable module; separate global vs. one-vs-rest to keep functions small and independently testable.
- **abcd_phewas/plots/:** Visualization is always independently replaceable; keeping it separate prevents coupling plot logic to stats logic.
- **data/domain_map.tsv:** Domain mapping is static data, not code. Keeping it as a data file means it can be updated without touching Python.
- **cli.py as orchestrator:** Keeps the pipeline linear and auditable — each stage produces an artifact that the next stage consumes.

## Architectural Patterns

### Pattern 1: Dispatcher Pattern for Variable Types

**What:** A single dispatch function routes each variable to the correct statistical test based on its inferred type. All tests share the same call signature and return the same result schema.

**When to use:** Mandatory here — there are 3000+ variables of mixed types. The dispatcher eliminates branching in the main loop.

**Trade-offs:** Clear routing logic; adds one layer of indirection; type inference errors cascade silently if not validated early.

**Example:**

```python
# classifier.py — infer type once, store in metadata
def infer_variable_type(series: pd.Series) -> str:
    n_unique = series.dropna().nunique()
    if n_unique == 2:
        return "binary"
    elif n_unique <= 10:
        return "categorical"  # or "ordinal" with domain knowledge
    else:
        return "continuous"

# tests/global_tests.py — dispatcher
TEST_DISPATCH = {
    "binary":      run_chi2_global,
    "categorical": run_chi2_global,
    "ordinal":     run_kruskal_global,
    "continuous":  run_kruskal_global,
}

def run_global_test(var: str, series: pd.Series, labels: pd.Series, var_type: str) -> dict:
    fn = TEST_DISPATCH[var_type]
    return fn(var, series, labels)
```

### Pattern 2: Tidy Results Schema

**What:** Every test function — global and one-vs-rest — returns a dict with a fixed set of keys. The results assembler appends all dicts into one DataFrame at the end.

**When to use:** Always in mass-testing pipelines. Prevents schema drift as new test types are added.

**Trade-offs:** Slightly verbose to fill unused keys (e.g., OR is None for continuous variables); pays back in clean output tables.

**Example:**

```python
RESULT_SCHEMA = {
    "variable": None,
    "domain": None,
    "var_type": None,
    "comparison": None,        # "global" or "cluster_N_vs_rest"
    "n_cluster": None,
    "n_rest": None,
    "statistic": None,
    "p_value": None,
    "effect_size": None,       # Cohen's d, Cramer's V, OR depending on type
    "effect_size_type": None,
    "p_fdr": None,
    "p_bonferroni": None,
}
```

### Pattern 3: Correction Applied to Flat List

**What:** Collect all raw p-values from all tests (global + all one-vs-rest) into one flat list, apply BH FDR and Bonferroni once across all of them, then distribute corrected values back to each result row.

**When to use:** Standard for PheWAS. Controls FWER/FDR at the level of the full analysis, not per-cluster or per-type.

**Trade-offs:** Stricter than per-cluster correction; this is the scientifically defensible choice given the one-vs-rest design.

**Example:**

```python
from statsmodels.stats.multitest import multipletests

all_pvals = results_df["p_value"].values
_, p_fdr, _, _ = multipletests(all_pvals, method="fdr_bh")
_, p_bonf, _, _ = multipletests(all_pvals, method="bonferroni")
results_df["p_fdr"] = p_fdr
results_df["p_bonferroni"] = p_bonf
```

## Data Flow

### Full Pipeline Flow

```
cluster_file.csv + phenotype_file.csv
        │
        ▼
    loader.py
        │  merged DataFrame (subjects × (cluster_label + 3000+ phenotype cols))
        ▼
    classifier.py
        │  variable_metadata: {var_name: {type, domain}}
        ▼
    tests/global_tests.py      →  list of result dicts (one per variable)
    tests/one_vs_rest.py       →  list of result dicts (one per variable × cluster)
        │
        ▼  (flat list of all result dicts)
    correction.py
        │  adds p_fdr, p_bonferroni columns
        ▼
    results.py
        │  writes results.tsv
        ▼
    plots/manhattan.py   →  manhattan.png
    plots/heatmap.py     →  heatmap.png
```

### Key Data Flows

1. **Subject join:** cluster_file → loader → inner join with phenotype_file on subject ID → unified DataFrame passed to all downstream components.
2. **Metadata propagation:** classifier produces variable_metadata dict; this dict is threaded through test engine and results assembler so every output row has domain and type labels without re-computing.
3. **P-value correction:** raw p-values accumulate in a results list throughout test engine; correction is applied in one batch before writing output — never row-by-row.
4. **Effect direction encoding:** heatmap encodes both significance (alpha of color) and effect direction (sign of Cohen's d or log-OR) — requires the sign, not just the magnitude, from the test functions.

## Scaling Considerations

This is a research pipeline, not a web service. Scale is defined by variable count and cluster count, not user count.

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 3,000 vars, 4 clusters (baseline) | Pure pandas + scipy, single process, runs in minutes |
| 10,000+ vars or 8 clusters | Add joblib.Parallel over variables; each variable is independent |
| Full ABCD (30,000+ vars across all domains) | Chunked processing; intermediate result files; avoid holding full matrix in RAM |

### Scaling Priorities

1. **First bottleneck:** Variable loop — 3,000 variables × (K+1) tests each. Parallelize with `joblib.Parallel(n_jobs=-1)` over variables. Each test is embarrassingly parallel.
2. **Second bottleneck:** Memory — loading all 3,000+ columns at once. Use column chunking if RAM is constrained; process in batches of 500 variables and concatenate result rows.

## Anti-Patterns

### Anti-Pattern 1: Re-Classifying Variable Type Inside the Test Loop

**What people do:** Call `infer_variable_type()` inside the per-variable test loop for each of the K+1 comparisons (global + one-vs-rest).

**Why it's wrong:** Type classification is expensive (requires scanning values); it produces different results for different subset sizes (e.g., a variable that looks binary globally might look continuous in a small cluster). Inconsistent type classification breaks the correction step.

**Do this instead:** Classify types once on the full dataset before any tests run. Store in `variable_metadata` and pass to all test functions.

### Anti-Pattern 2: Applying Correction Per-Cluster

**What people do:** Collect p-values from one-vs-rest tests for cluster 1, apply FDR, then repeat for cluster 2, etc.

**Why it's wrong:** FDR correction should be applied across all tests in the analysis simultaneously. Per-cluster correction inflates false discovery rate at the experiment level.

**Do this instead:** Accumulate all p-values (global + all one-vs-rest for all clusters) into one list, apply BH FDR once.

### Anti-Pattern 3: Hardcoding the Domain Mapping as a Dict in Code

**What people do:** Write `domain_map = {"cbcl_q01": "mental_health", ...}` directly in a Python file.

**Why it's wrong:** ABCD variables number in the thousands; the mapping becomes unmaintainable in code. Re-releases of ABCD add/rename variables.

**Do this instead:** Load domain mapping from a TSV file (`data/domain_map.tsv`) derived from the ABCD data dictionary. The pipeline reads it at startup.

### Anti-Pattern 4: Generating Plots Inside the Test Loop

**What people do:** Create a Manhattan plot after each cluster's one-vs-rest test completes.

**Why it's wrong:** Plots need the final corrected p-values, which are only available after all tests finish and correction is applied globally.

**Do this instead:** Complete all tests and correction first; write results table; generate plots from the results table as a final step.

### Anti-Pattern 5: Using ANOVA for Non-Normal Phenotype Data Without Checking

**What people do:** Apply ANOVA (parametric) to all "continuous" variables by default.

**Why it's wrong:** ABCD phenotype data includes cognitive scores, symptom counts, and questionnaire scales — most of which are non-normal. ANOVA is sensitive to violations in small groups (sparse clusters).

**Do this instead:** Default to Kruskal-Wallis for continuous and ordinal variables (non-parametric). Add ANOVA as an optional flag only when normality can be assumed (e.g., raw brain volume measures).

## Integration Points

### External Services

None — this is an offline batch pipeline. All inputs are local files.

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| loader → classifier | pandas DataFrame passed in memory | loader validates subjects are present in both inputs before passing |
| classifier → test engine | variable_metadata dict + merged DataFrame | metadata dict is the contract: test engine trusts the type labels |
| test engine → correction | flat list of result dicts with raw p_value | correction module does not need to know variable type; operates on p_value column only |
| correction → plots | results DataFrame (with p_fdr, p_bonferroni) | plots are read-only consumers of results; no feedback to test engine |

## Build Order Implications

The dependency graph implies this build sequence:

1. **loader.py** — nothing depends on it except everything. Build first. Validates input contract.
2. **classifier.py** — depends on loader output; provides metadata to all other components.
3. **correction.py** — pure function (list of p-values in, corrected p-values out); can be built and tested independently before tests are implemented.
4. **tests/global_tests.py** — depends on classifier metadata; simpler than one-vs-rest (fewer comparisons).
5. **tests/one_vs_rest.py** — depends on global_tests patterns; adds cluster-loop logic.
6. **effects.py** — add alongside tests (per-test effect sizes). Can start simple (Cohen's d only) and extend.
7. **results.py** — depends on all test output + correction; build after tests are stable.
8. **plots/manhattan.py** — depends on results.py output only; build after results table is stable.
9. **plots/heatmap.py** — requires both significance and effect direction from results; build last.

## Sources

- [PYPE: Python PheWAS pipeline (Patterns, 2024)](https://www.cell.com/patterns/fulltext/S2666-3899(24)00096-5)
- [R PheWAS package: data analysis and plotting tools (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC4133579/)
- [PheTK: PheWAS analysis on large-scale biobank data (Bioinformatics, 2025)](https://academic.oup.com/bioinformatics/article/41/1/btae719/7919600)
- [pyPheWAS: MASI Lab Python implementation](https://github.com/MASILab/pyPheWAS)
- [statsmodels multipletests documentation](https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html)
- [scipy.stats.kruskal documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.kruskal.html)
- [pingouin: compute_effsize for Cohen's d](https://pingouin-stats.org/generated/pingouin.compute_effsize.html)

---
*Architecture research for: Python PheWAS cluster characterization pipeline (ABCD Study)*
*Researched: 2026-03-04*
