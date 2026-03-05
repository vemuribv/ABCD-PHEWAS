# Phase 3: Correction and Outputs - Research

**Researched:** 2026-03-05
**Domain:** Multiple comparison correction, CSV assembly, matplotlib PheWAS Manhattan plotting
**Confidence:** HIGH

## Summary

Phase 3 takes the raw DataFrame from `run_all_tests()` (Phase 2) and produces: (1) a combined results CSV with four correction columns (global/domain x FDR/Bonferroni), domain assignments, and missingness rates; (2) one Manhattan-style PheWAS plot per cluster (one-vs-rest); (3) one global omnibus Manhattan plot. The correction logic is straightforward using `statsmodels.stats.multitest.multipletests`, which supports both `fdr_bh` and `bonferroni` methods. The plotting is the most complex piece, requiring domain-grouped x-axis layout, directional triangle markers, threshold lines, and non-overlapping labels via `adjustText`.

Three new modules are needed: `correction.py` (apply FDR-BH and Bonferroni corrections across four families), `results_writer.py` (assemble the final CSV from Phase 2 output + domain map + missingness + corrections), and `plotter.py` (Manhattan-style PheWAS plots). All inputs are already available from `PipelineResult` (domain_map, missingness) and `run_all_tests()` (12-column DataFrame).

**Primary recommendation:** Use `statsmodels.stats.multitest.multipletests` with method='fdr_bh' and method='bonferroni' for corrections. Use matplotlib with `adjustText` for plots. Keep correction logic purely functional (DataFrame in, DataFrame out) and separate from plotting.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **matplotlib** for all plots (no plotnine/seaborn)
- Up/down triangle markers encode effect direction (positive = up, negative = down)
- Points colored by ABCD domain using the 8-domain palette from `domain_mapper.py`
- Two horizontal threshold lines per plot: FDR q=0.05 (dashed) and Bonferroni 0.05/n_tests (dashed, different color)
- Threshold lines use **global** correction values (not domain-specific)
- Output format: **PNG at 300 DPI**
- `adjustText` library for non-overlapping label placement
- **One combined CSV** for all results (omnibus + all one-vs-rest in a single file)
- Sorted by **raw p-value ascending** (most significant first)
- Includes `domain` column and `missingness_rate` column
- Required columns: variable, domain, comparison_type, cluster_label, test_used, statistic, p_value, effect_size, effect_size_type, ci_lower, ci_upper, n_target, n_rest, missingness_rate, fdr_q_global, bonf_p_global, fdr_q_domain, bonf_p_domain
- **Four correction columns**: fdr_q_global, bonf_p_global, fdr_q_domain, bonf_p_domain
- Omnibus and one-vs-rest corrected **separately** (different test families)
- Within-domain correction follows the same separation
- Label text: raw variable names by default, with optional rename CSV
- R-style `ggrepel` arrow segments replicated via `adjustText`
- Bonferroni threshold computed dynamically from actual test count

### Claude's Discretion
- Exact label selection algorithm (top-N, threshold-based, or hybrid)
- Plot dimensions and aspect ratio
- Font sizes and typography
- Color scheme for threshold lines
- X-axis spacing and domain separator styling
- Filename conventions for output plots and CSV

### Deferred Ideas (OUT OF SCOPE)
None

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| OUTP-01 | Results CSV with variable, domain, test type, statistic, p-value, FDR q, Bonferroni p, effect size, CI, cluster label, n per group, missingness rate | `correction.py` applies multipletests; `results_writer.py` merges domain_map + missingness + corrections into 18-column CSV |
| OUTP-02 | Manhattan-style PheWAS plot per cluster (one-vs-rest) with domain colors, FDR/Bonferroni threshold lines, direction markers, labels on significant hits | `plotter.py` using matplotlib scatter with triangle markers, domain-grouped x-axis, adjustText for labels |
| OUTP-03 | Global Manhattan plot (omnibus test results) | Same plotter module filtering to comparison_type=="omnibus", no direction markers (omnibus has no direction) |

</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| statsmodels | >=0.14 | `multipletests(pvals, method='fdr_bh')` and `method='bonferroni'` | Standard Python library for multiple comparison correction; R's `p.adjust()` equivalent |
| matplotlib | >=3.7 | All plotting (scatter, hlines, text, legends, savefig) | Locked decision from CONTEXT.md |
| adjustText | >=1.0 | Non-overlapping label placement on matplotlib plots | ggrepel equivalent; locked decision |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pandas | >=2.0 (already installed) | DataFrame manipulation for CSV assembly | Always - already in project deps |
| numpy | >=1.24 (already installed) | -log10 transforms, NaN handling | Always - already in project deps |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| statsmodels multipletests | scipy.stats.false_discovery_control | scipy only does BH, not Bonferroni; statsmodels does both in one API |
| adjustText | manual label placement | adjustText handles edge cases (crowded plots, boundary constraints) automatically |

**Installation:**
```bash
pip install statsmodels matplotlib adjustText
```

**pyproject.toml update needed:**
```
dependencies = [
    ...existing...
    "statsmodels>=0.14",
    "matplotlib>=3.7",
    "adjustText>=1.0",
]
```

## Architecture Patterns

### Recommended Project Structure
```
src/abcd_phewas/
    correction.py        # apply_corrections(df) -> df with 4 new columns
    results_writer.py    # assemble_results(raw_df, domain_map, missingness) -> final_df + CSV write
    plotter.py           # manhattan_plot(df, ...) -> saves PNG; omnibus_plot(df, ...) -> saves PNG
```

### Pattern 1: Correction as Pure Function
**What:** `apply_corrections()` takes the raw results DataFrame, splits into omnibus/OVR families, applies FDR-BH and Bonferroni separately within each family, then does the same within each domain. Returns DataFrame with 4 new correction columns.
**When to use:** Always -- corrections must be applied before CSV or plotting.
**Example:**
```python
# Source: statsmodels official docs
from statsmodels.stats.multitest import multipletests

def apply_corrections(df: pd.DataFrame) -> pd.DataFrame:
    """Add fdr_q_global, bonf_p_global, fdr_q_domain, bonf_p_domain columns."""
    df = df.copy()

    # Initialize correction columns with NaN
    for col in ['fdr_q_global', 'bonf_p_global', 'fdr_q_domain', 'bonf_p_domain']:
        df[col] = np.nan

    # Global corrections: omnibus and OVR as separate families
    for comp_type in ['omnibus', 'one_vs_rest']:
        mask = df['comparison_type'] == comp_type
        pvals = df.loc[mask, 'p_value'].values

        # Handle NaN p-values: exclude from correction, leave as NaN
        valid = ~np.isnan(pvals)
        if valid.sum() == 0:
            continue

        _, fdr_q, _, _ = multipletests(pvals[valid], method='fdr_bh')
        _, bonf_p, _, _ = multipletests(pvals[valid], method='bonferroni')

        idx = df.index[mask][valid]
        df.loc[idx, 'fdr_q_global'] = fdr_q
        df.loc[idx, 'bonf_p_global'] = bonf_p

    # Within-domain corrections: same split by comp_type, then by domain
    for comp_type in ['omnibus', 'one_vs_rest']:
        for domain in df['domain'].unique():
            mask = (df['comparison_type'] == comp_type) & (df['domain'] == domain)
            pvals = df.loc[mask, 'p_value'].values
            valid = ~np.isnan(pvals)
            if valid.sum() < 2:  # need at least 2 tests for correction
                continue

            _, fdr_q, _, _ = multipletests(pvals[valid], method='fdr_bh')
            _, bonf_p, _, _ = multipletests(pvals[valid], method='bonferroni')

            idx = df.index[mask][valid]
            df.loc[idx, 'fdr_q_domain'] = fdr_q
            df.loc[idx, 'bonf_p_domain'] = bonf_p

    return df
```

### Pattern 2: Domain-Grouped X-Axis Layout
**What:** Variables are sorted by domain, then alphabetically within domain. Each variable gets a sequential x-position. Domain boundaries are marked with gaps or alternating background shading.
**When to use:** For all Manhattan-style plots.
**Example:**
```python
# Build x-positions grouped by domain
domain_order = [d['domain'] for d in domain_config]  # preserve YAML order
df_plot = df_plot.copy()
df_plot['domain_rank'] = df_plot['domain'].map(
    {d: i for i, d in enumerate(domain_order)}
)
df_plot = df_plot.sort_values(['domain_rank', 'variable']).reset_index(drop=True)

# Add gaps between domains
gap = 5
x_pos = []
current_x = 0
prev_domain = None
for _, row in df_plot.iterrows():
    if row['domain'] != prev_domain and prev_domain is not None:
        current_x += gap
    x_pos.append(current_x)
    current_x += 1
    prev_domain = row['domain']
df_plot['x_pos'] = x_pos
```

### Pattern 3: Directional Triangle Markers
**What:** Positive effect = upward triangle, negative = downward triangle. Uses matplotlib marker codes `'^'` and `'v'`.
**When to use:** One-vs-rest plots only (omnibus has no direction).
**Example:**
```python
# Source: matplotlib marker documentation
direction = np.where(df_plot['effect_size'] > 0, '^', 'v')

# Must scatter each marker type separately (matplotlib limitation)
for marker, label in [('^', 'Positive'), ('v', 'Negative')]:
    mask = direction == marker
    ax.scatter(
        df_plot.loc[mask, 'x_pos'],
        df_plot.loc[mask, 'neg_log_p'],
        c=df_plot.loc[mask, 'color'],
        marker=marker,
        s=20,
        edgecolors='none',
    )
```

### Anti-Patterns to Avoid
- **Correcting omnibus and OVR together:** These are different test families. The R code corrects each cluster's results separately; our CONTEXT.md specifies global OVR correction (all clusters pooled for OVR family), but omnibus and OVR must remain separate.
- **Applying correction to NaN p-values:** `multipletests` will crash on NaN input. Filter them out first, then map corrected values back.
- **Calling adjust_text before finalizing axes:** The library needs final axis dimensions. Set xlim, ylim, title, and all other plot elements BEFORE calling `adjust_text()`.
- **Using seaborn or plotnine:** Locked out by CONTEXT.md decision.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| FDR correction | Custom BH step-up procedure | `multipletests(pvals, method='fdr_bh')` | Edge cases with ties, NaN handling, numerical stability |
| Bonferroni correction | `p * n_tests` manually | `multipletests(pvals, method='bonferroni')` | Capping at 1.0, NaN handling, consistency with FDR API |
| Non-overlapping labels | Manual text placement | `adjustText.adjust_text()` | Iterative repositioning algorithm handles crowded plots, boundary avoidance |
| Domain color mapping | Hardcoded color dict | `domain_mapper.load_domain_config()` + `assign_domain()` | Already built in Phase 1, colors defined in YAML |

**Key insight:** `multipletests` returns corrected p-values directly (capped at 1.0), handling the same edge cases as R's `p.adjust()`. Do not manually multiply p-values by test count.

## Common Pitfalls

### Pitfall 1: NaN P-Values in Correction Input
**What goes wrong:** `multipletests` raises ValueError if pvals array contains NaN.
**Why it happens:** Phase 2 returns NaN p-values for degenerate/insufficient-data variables.
**How to avoid:** Filter to non-NaN p-values before calling `multipletests`, then map corrected values back to original positions. Leave correction columns as NaN for variables that had NaN p-values.
**Warning signs:** ValueError from statsmodels on first run.

### Pitfall 2: Correction Family Confusion
**What goes wrong:** Mixing omnibus and OVR p-values in the same correction pool inflates or deflates significance.
**Why it happens:** Natural instinct is to correct all p-values together.
**How to avoid:** Always filter by `comparison_type` before calling `multipletests`. Four global families: (omnibus, FDR), (omnibus, Bonf), (OVR, FDR), (OVR, Bonf). Same four within each domain.
**Warning signs:** Corrected p-values don't match expectations; q-values are suspiciously small or large.

### Pitfall 3: matplotlib Marker Type Limitation
**What goes wrong:** Trying to pass a column of marker types to `ax.scatter()` does not work. matplotlib's `marker` parameter accepts a single marker per scatter call.
**Why it happens:** Unlike ggplot's `aes(shape=direction)`, matplotlib requires separate scatter calls for different markers.
**How to avoid:** Loop over marker types ('^' and 'v') and scatter each subset separately.
**Warning signs:** TypeError or all points rendered with same marker.

### Pitfall 4: adjust_text Called Too Early
**What goes wrong:** Labels repositioned incorrectly, placed outside plot boundaries, or overlapping.
**Why it happens:** `adjust_text` uses current axis dimensions. If axes are resized after calling it, positions become wrong.
**How to avoid:** Set all axis limits, labels, title, and figure size BEFORE calling `adjust_text()`. Call it last, right before `savefig()`.
**Warning signs:** Labels appear at wrong positions or outside the visible plot area.

### Pitfall 5: Domain Column Missing from Results DataFrame
**What goes wrong:** Within-domain correction cannot be applied without knowing each variable's domain.
**Why it happens:** Phase 2's `run_all_tests()` output has 12 columns but no `domain` column. Domain info lives in `PipelineResult.domain_map`.
**How to avoid:** Merge domain information from `domain_map` into the results DataFrame before applying corrections. The `results_writer.py` module should do this merge early.
**Warning signs:** KeyError on 'domain' column during within-domain correction loop.

### Pitfall 6: Omnibus Plots Should Not Have Direction Markers
**What goes wrong:** Plotting omnibus results with up/down triangles is misleading (omnibus tests don't have a direction).
**Why it happens:** Reusing the OVR plotting code for omnibus without adjusting.
**How to avoid:** Use circular markers ('o') for the omnibus plot. Only OVR plots use directional triangles.
**Warning signs:** Visual inspection shows directional markers on omnibus plot.

## Code Examples

### Applying Multiple Comparison Correction
```python
# Source: statsmodels official docs
from statsmodels.stats.multitest import multipletests

pvals = np.array([0.001, 0.04, 0.03, 0.5, 0.0001])

# FDR Benjamini-Hochberg
reject_fdr, pvals_fdr, _, _ = multipletests(pvals, alpha=0.05, method='fdr_bh')
# pvals_fdr contains adjusted q-values

# Bonferroni
reject_bonf, pvals_bonf, _, _ = multipletests(pvals, alpha=0.05, method='bonferroni')
# pvals_bonf contains adjusted p-values (capped at 1.0)
```

### Manhattan Plot Core Structure
```python
import matplotlib.pyplot as plt
from adjustText import adjust_text

fig, ax = plt.subplots(figsize=(16, 6))

# Domain colors from domain_map
colors = [domain_map[var][1] for var in df_plot['variable']]

# Scatter points (split by marker type for OVR)
for marker, mask in [('^', pos_mask), ('v', neg_mask)]:
    ax.scatter(
        df_plot.loc[mask, 'x_pos'],
        df_plot.loc[mask, 'neg_log_p'],
        c=[colors[i] for i in mask.index[mask]],
        marker=marker, s=20, edgecolors='none', zorder=3,
    )

# Threshold lines
n_tests = len(df_plot)
ax.axhline(-np.log10(0.05 / n_tests), color='red', ls='--', lw=0.8,
           label=f'Bonferroni (p={0.05/n_tests:.2e})')
# FDR threshold: find the largest p_value where fdr_q <= 0.05
fdr_thresh = df_plot.loc[df_plot['fdr_q_global'] <= 0.05, 'p_value'].max()
if not np.isnan(fdr_thresh):
    ax.axhline(-np.log10(fdr_thresh), color='blue', ls='--', lw=0.8,
               label='FDR q=0.05')

# Labels on significant hits
sig_mask = df_plot['fdr_q_global'] <= 0.05
texts = []
for _, row in df_plot[sig_mask].iterrows():
    texts.append(ax.text(row['x_pos'], row['neg_log_p'], row['variable'],
                         fontsize=6, ha='center', va='bottom'))

# Adjust labels (MUST be called last)
adjust_text(texts,
            x=df_plot['x_pos'].values,
            y=df_plot['neg_log_p'].values,
            arrowprops=dict(arrowstyle='->', color='gray', lw=0.5),
            ax=ax)

# Domain labels on x-axis
domain_centers = df_plot.groupby('domain')['x_pos'].mean()
ax.set_xticks(domain_centers.values)
ax.set_xticklabels(domain_centers.index, rotation=30, ha='right', fontsize=7)

ax.set_ylabel('-log10(p-value)')
ax.set_xlabel('')
fig.savefig('manhattan_ovr_cluster1.png', dpi=300, bbox_inches='tight')
plt.close(fig)
```

### Merging Domain and Missingness into Results
```python
def assemble_results(
    raw_df: pd.DataFrame,
    domain_map: dict[str, tuple[str, str]],
    missingness: pd.DataFrame,
) -> pd.DataFrame:
    """Merge domain and missingness columns into raw results."""
    df = raw_df.copy()

    # Add domain column
    df['domain'] = df['variable'].map(lambda v: domain_map.get(v, ('Other/Unclassified', '#AAAAAA'))[0])

    # Add missingness_rate column
    # missingness DataFrame has variable as index or column
    miss_dict = missingness.set_index('variable')['missingness_rate'].to_dict()
    df['missingness_rate'] = df['variable'].map(miss_dict)

    return df
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual `p * n_tests` | `multipletests(method='bonferroni')` | statsmodels 0.8+ | Handles edge cases, NaN, capping at 1.0 |
| ggrepel in R | `adjustText` in Python | adjustText 1.0+ (2023) | Equivalent iterative repositioning for matplotlib |
| Separate CSV per cluster | Combined CSV with comparison_type column | This project design | Single file easier to filter and analyze downstream |

**Deprecated/outdated:**
- `statsmodels.sandbox.stats.multicomp`: old location, use `statsmodels.stats.multitest` instead

## Open Questions

1. **FDR threshold line position on plot**
   - What we know: Bonferroni line is straightforward: `-log10(0.05 / n_tests)`. FDR is adaptive, not a fixed threshold.
   - What's unclear: How to draw a single FDR threshold line when the BH procedure gives variable-specific decisions, not a single cutoff.
   - Recommendation: Use the largest raw p-value that still passes FDR as the threshold line position. This is the BH step-up procedure's effective cutoff. If no tests pass, omit the FDR line.

2. **Missingness DataFrame structure**
   - What we know: `PipelineResult.missingness` is a DataFrame computed in `pipeline.py` via `compute_missingness()`.
   - What's unclear: Exact column names and whether variable names are index or column.
   - Recommendation: Check `loader.py::compute_missingness()` during implementation; adapt merge accordingly.

3. **Optional rename CSV format**
   - What we know: Two columns: `variable_name`, `display_label`. Used for cleaned names on plot labels.
   - What's unclear: Whether this file path should be in PipelineConfig or passed as a parameter to the plotter.
   - Recommendation: Pass as optional parameter to plot functions; do not add to PipelineConfig (it's a presentation concern, not a pipeline concern).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=7.4 |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `/opt/homebrew/bin/python3.9 -m pytest tests/ -x -q` |
| Full suite command | `/opt/homebrew/bin/python3.9 -m pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| OUTP-01 | Correction produces 4 correction columns; CSV has all 18 required columns; sorted by p_value ascending | unit | `python3.9 -m pytest tests/test_correction.py tests/test_results_writer.py -x` | No - Wave 0 |
| OUTP-02 | OVR Manhattan plot renders with domain colors, triangle markers, threshold lines, labels, 300 DPI | unit+smoke | `python3.9 -m pytest tests/test_plotter.py -x` | No - Wave 0 |
| OUTP-03 | Omnibus Manhattan plot renders with domain colors, circular markers, threshold lines | unit+smoke | `python3.9 -m pytest tests/test_plotter.py -x` | No - Wave 0 |

### Sampling Rate
- **Per task commit:** `/opt/homebrew/bin/python3.9 -m pytest tests/ -x -q`
- **Per wave merge:** `/opt/homebrew/bin/python3.9 -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_correction.py` -- covers OUTP-01 (correction logic: NaN handling, family separation, global vs domain)
- [ ] `tests/test_results_writer.py` -- covers OUTP-01 (CSV assembly: column completeness, sort order, domain/missingness merge)
- [ ] `tests/test_plotter.py` -- covers OUTP-02, OUTP-03 (plot rendering: smoke test that PNG is produced, correct dimensions, correct DPI)

Note: Plot tests should be smoke tests (file created, correct dimensions, non-zero file size) rather than pixel-level assertions. Use `matplotlib.testing` only if needed for regression.

## Sources

### Primary (HIGH confidence)
- [statsmodels multipletests docs](https://www.statsmodels.org/dev/generated/statsmodels.stats.multitest.multipletests.html) - function signature, method options, return values
- [adjustText PyPI](https://pypi.org/project/adjustText/) - version 1.3.0, basic usage
- [adjustText examples](https://adjusttext.readthedocs.io/en/latest/Examples.html) - adjust_text() signature, arrowprops, usage pattern
- Existing codebase: `stat_engine.py`, `domain_mapper.py`, `pipeline.py`, `config.py` - Phase 2 output schema, domain_map structure, PipelineResult dataclass

### Secondary (MEDIUM confidence)
- R reference code: `PheWAS Analyses Resub5.Rmd` lines 2963-3051 - plot structure (ggplot + geom_point + geom_text_repel + geom_hline), xpos layout, direction encoding, FDR labeling threshold

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - statsmodels multipletests is the standard Python equivalent of R's p.adjust(); verified via official docs
- Architecture: HIGH - pattern follows existing codebase conventions (pure functions, dataclass config, DataFrame in/out)
- Pitfalls: HIGH - NaN handling and family separation are well-documented concerns; marker limitation is a known matplotlib behavior

**Research date:** 2026-03-05
**Valid until:** 2026-04-05 (stable domain, all libraries mature)
