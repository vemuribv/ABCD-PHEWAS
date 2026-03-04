# Stack Research

**Domain:** PheWAS (Phenome-Wide Association Study) pipeline — cluster characterization with mixed variable types
**Researched:** 2026-03-04
**Confidence:** HIGH (versions verified via PyPI; statistical approach verified via SciPy/statsmodels official docs)

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.11+ | Runtime | 3.11 has meaningful speed improvements over 3.10; 3.12+ still has ecosystem gaps for scientific stack |
| pandas | 3.0.1 | Data loading, merging cluster assignments with phenotype file, results tables | 3.x has stable pyarrow backend for memory efficiency with wide dataframes (3000+ columns); breaking change from 2.x is copy-on-write semantics — no silent mutation |
| scipy | 1.17.1 | All statistical tests: kruskal, chi2_contingency, fisher_exact, f_oneway, false_discovery_control | The authoritative source for these tests in Python; 1.15+ added `scipy.stats.false_discovery_control` as a clean FDR interface |
| statsmodels | 0.14.6 | `multipletests` for Benjamini-Hochberg and Bonferroni correction over arrays of p-values | Standard for multiple comparison correction in Python science; `multipletests(pvals, method='fdr_bh')` and `method='bonferroni'` in one call |
| matplotlib | 3.10.8 | Base rendering for all plots; controls figure size, DPI, layout | Required by seaborn; also used directly for Manhattan plot (scatter + domain-colored x-axis) and savefig at 300–600 DPI for publication |
| seaborn | 0.13.2 | Heatmap (`seaborn.heatmap`) for cluster x significant-variable visualization; color palettes | Best-in-class heatmap API with diverging palettes (RdBu_r for effect direction), annotation support, and tight matplotlib integration |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pingouin | 0.6.0 | Effect sizes: `kruskal()` returns eta-squared directly; `compute_effsize()` for Cohen's d (binary one-vs-rest) | Use for effect size columns in results table — scipy does not return effect sizes, only p-values and test statistics |
| scikit-posthocs | 0.12.0 | Post-hoc pairwise tests (Dunn's test) after significant Kruskal-Wallis | Use only when global test is significant and you want per-cluster pairwise breakdowns; not needed for one-vs-rest design |
| adjustText | 1.3.0 | Automatic non-overlapping label placement on Manhattan plot | Use when annotating top-N significant variables on Manhattan plot; prevents label collisions without manual tuning |
| numpy | 2.x (via scipy/pandas) | Array math, vectorized operations | Indirect dependency; do not import directly unless doing custom effect-size math |
| tqdm | latest | Progress bars for the variable-by-variable test loop (3000+ iterations) | Use in the main test loop so the pipeline does not appear frozen during long runs |
| PyYAML or tomllib | stdlib (tomllib 3.11+) | Configuration file for paths, FDR threshold, domain dictionary path | Use `tomllib` (stdlib, no install) for pipeline config; avoids external dependency |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| uv | Fast package management and virtual environment | Replaces pip + venv; `uv pip install` is 10–100x faster; use `uv venv` for project isolation |
| Jupyter Lab | Exploratory analysis and plot iteration | Use for development only; pipeline itself should be a `.py` script for reproducibility |
| pytest | Unit tests for the statistical dispatch logic | Test the test-selector (which test fires for binary vs continuous vs ordinal) with synthetic data |
| ruff | Linting and formatting | Replaces flake8 + black in one tool; zero-config defaults are good for scientific Python |

---

## Installation

```bash
# Create environment
uv venv .venv && source .venv/bin/activate

# Core pipeline
uv pip install pandas==3.0.1 scipy==1.17.1 statsmodels==0.14.6 matplotlib==3.10.8 seaborn==0.13.2

# Effect sizes and post-hoc
uv pip install pingouin==0.6.0 scikit-posthocs==0.12.0

# Plot utilities
uv pip install adjustText==1.3.0 tqdm

# Dev
uv pip install pytest ruff jupyterlab
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| scipy.stats.kruskal + pingouin | pingouin.kruskal exclusively | If you want a single-library call that returns test stat + p-value + effect size in one DataFrame row — acceptable, but pingouin is slower on tight loops; use scipy for the p-value pass, pingouin only for effect sizes on significant hits |
| statsmodels.stats.multitest.multipletests | scipy.stats.false_discovery_control (1.15+) | Use scipy's new function if you only need FDR-BH and want fewer dependencies — but `multipletests` handles Bonferroni + FDR in one call, which this project needs |
| seaborn.heatmap | plotly heatmap | Use plotly if you need interactive HTML export for a web app or dashboard; for publication PDFs, seaborn + matplotlib is simpler and more controllable |
| matplotlib Manhattan (custom) | qmplot | Use qmplot if you are doing a true GWAS Manhattan plot (chromosome-based x-axis); for PheWAS domain-grouped x-axis, build it in raw matplotlib — qmplot's chromosome assumptions break for phenotype data |
| pandas | polars | Use polars if the phenotype file exceeds memory (>10GB); for ABCD at ~3000 columns x ~10k subjects, pandas 3.x with pyarrow backend is sufficient |
| uv | conda | Use conda if collaborators require it or if you need R/Python interop environment management; for a pure Python pipeline, uv is faster and simpler |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| pyPheWAS | Designed exclusively for ICD billing codes (EMR PheWAS), not for continuous/mixed phenotype arrays; cannot ingest ABCD-style data dictionaries | Build custom dispatcher: scipy tests per variable type |
| PYPE | Assumes genotype as the independent variable; regression-centric (OLS); does not handle categorical/ordinal variable types cleanly | Build custom dispatcher; statsmodels multipletests for correction |
| R's PheWAS package (via rpy2) | Adds R runtime dependency, rpy2 interop overhead, and debugging complexity; the PROJECT.md mandates Python | scipy + statsmodels cover all required tests natively |
| seaborn.clustermap | Performs hierarchical clustering on the heatmap's rows/columns — this would reorder clusters and break the intended cluster 1/2/3/... labeling | Use `seaborn.heatmap` directly; sort columns by domain group, then by p-value within domain |
| pingouin for the main test loop | pingouin's DataFrame-returning API has overhead per call; running it 3000+ times for the global test pass is slow | Use `scipy.stats.kruskal` in the fast pass; then call `pingouin.kruskal` only on significant variables for effect size |
| pandas < 2.0 | Copy-on-write semantics not enforced — silent mutation bugs in wide DataFrame operations; also missing pyarrow backend stability | pandas 3.0.1 |
| scipy < 1.14 | `scipy.stats.false_discovery_control` added in 1.14; older versions lack modern API surface | scipy 1.17.1 |

---

## Stack Patterns by Variant

**For the global test (does any cluster differ on this variable?):**
- Use `scipy.stats.kruskal` for continuous/ordinal, `scipy.stats.chi2_contingency` for categorical/binary (expected cell count > 5), `scipy.stats.fisher_exact` for binary with small cells
- Collect all p-values into a numpy array, then call `statsmodels.stats.multitest.multipletests` once for FDR-BH and once for Bonferroni
- This two-pass design (all tests, then one correction call) is faster and statistically correct — corrections must be computed over the full set of tests simultaneously

**For one-vs-rest per cluster:**
- For each cluster k: create binary label (in cluster k vs. not), run the same type-appropriate test
- Same correction logic applies — collect all p-values across all variables AND all clusters before correcting
- Effect size: for binary outcome use odds ratio (from 2x2 table); for continuous use Cohen's d (pingouin.compute_effsize) or eta-squared from Kruskal-Wallis

**For the Manhattan plot:**
- x-axis: variables sorted by ABCD domain group (alphabetical or by domain size), then by position within domain
- y-axis: -log10(p-value) from global test
- Color: one color per domain group (seaborn color_palette with enough distinct colors; `husl` works up to ~20 domains)
- Significance lines: dashed horizontal at FDR q < 0.05 and solid at Bonferroni-corrected p < 0.05
- Use `adjustText` for top-N labels to avoid overlap

**For the heatmap:**
- Rows: clusters (2–8 rows)
- Columns: significant variables only (filtered by FDR threshold), sorted by domain then by absolute effect size within domain
- Cell value: standardized effect direction (e.g., standardized mean difference for continuous, log-odds for binary)
- Color: diverging palette (RdBu_r), centered at zero
- Add row color bars for cluster and column color bars for domain using seaborn's `col_colors` / `row_colors` parameter on a `ClusterMap` wrapper, but with `col_cluster=False, row_cluster=False` to preserve ordering

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| pandas 3.0.1 | scipy 1.17.1, statsmodels 0.14.6 | No known conflicts; all require numpy 1.23+ |
| seaborn 0.13.2 | matplotlib 3.10.x | seaborn 0.13 requires matplotlib >= 3.4; 3.10 is confirmed compatible |
| pingouin 0.6.0 | pandas 3.x | pingouin 0.6.0 released Feb 2026 — explicitly supports pandas 3.x |
| scikit-posthocs 0.12.0 | scipy 1.17.x | 0.12.0 released Feb 2026; requires scipy >= 1.9 |
| adjustText 1.3.0 | matplotlib 3.10.x | Pure matplotlib wrapper; no version sensitivity |
| Python 3.11 | All above | 3.12 is acceptable but has minor ecosystem rough edges in statsmodels; 3.11 is the safest choice as of 2026-03 |

---

## Sources

- PyPI JSON API (verified 2026-03-04): pandas 3.0.1, scipy 1.17.1, statsmodels 0.14.6, matplotlib 3.10.8, seaborn 0.13.2, pingouin 0.6.0, scikit-posthocs 0.12.0, adjustText 1.3.0
- SciPy 1.17 docs — [chi2_contingency](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.chi2_contingency.html), [fisher_exact](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.fisher_exact.html), [kruskal](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.kruskal.html) — HIGH confidence
- statsmodels 0.15 dev docs — [multipletests](https://www.statsmodels.org/dev/generated/statsmodels.stats.multitest.multipletests.html) — HIGH confidence
- [PYPE paper (Cell Patterns, 2024)](https://www.cell.com/patterns/fulltext/S2666-3899(24)00096-5) — confirms statsmodels as standard for mass regression PheWAS in Python — MEDIUM confidence
- [pyPheWAS docs](https://pyphewas.readthedocs.io/en/latest/phewas_tools.html) — confirms this library is ICD-code specific, not general phenotype array — HIGH confidence (negative finding)
- [seaborn clustermap docs](https://seaborn.pydata.org/generated/seaborn.clustermap.html) — confirmed `col_cluster=False` / `row_cluster=False` parameters — HIGH confidence
- [Python Graph Gallery: Manhattan Plot with Matplotlib](https://python-graph-gallery.com/manhattan-plot-with-matplotlib/) — pattern for domain-colored PheWAS Manhattan — MEDIUM confidence
- [ABCD Data Dictionary](https://data-dict.abcdstudy.org/) — confirmed table-name-based domain grouping is the standard approach for ABCD variable categorization — MEDIUM confidence

---

*Stack research for: ABCD PheWAS Cluster Characterization Pipeline*
*Researched: 2026-03-04*
