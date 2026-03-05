# Phase 3: Correction and Outputs - Context

**Gathered:** 2026-03-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Apply global and within-domain multiple comparison correction (FDR-BH and Bonferroni) to Phase 2's raw p-value array, produce a single combined results CSV, and generate publication-quality Manhattan-style PheWAS plots (one per cluster one-vs-rest comparison + one global omnibus plot).

</domain>

<decisions>
## Implementation Decisions

### Plotting library & style
- **matplotlib** for all plots (no plotnine/seaborn)
- Up/down triangle markers encode effect direction (positive = up, negative = down), matching R code's `shape = direction`
- Points colored by ABCD domain using the 8-domain palette from `domain_mapper.py`
- Two horizontal threshold lines per plot: FDR q=0.05 (dashed) and Bonferroni 0.05/n_tests (dashed, different color)
- Threshold lines use **global** correction values (not domain-specific)
- Output format: **PNG at 300 DPI**
- `adjustText` library for non-overlapping label placement (matplotlib equivalent of ggrepel)

### Label strategy
- **Claude's discretion** on which variables get text labels (e.g., top-N most significant, or Bonferroni-significant, or hybrid approach)
- Label text: **raw variable names by default**, with an optional rename CSV file (two columns: `variable_name`, `display_label`) for cleaned names
- If rename CSV is provided, mapped names are used; otherwise raw column names appear on plots

### Results CSV layout
- **One combined CSV** for all results (omnibus + all one-vs-rest comparisons in a single file)
- Sorted by **raw p-value ascending** (most significant first)
- Includes a `domain` column for each variable (from domain_mapper)
- Includes a `missingness_rate` column per variable (from Phase 1's PipelineResult)
- Required columns: variable, domain, comparison_type, cluster_label, test_used, statistic, p_value, effect_size, effect_size_type, ci_lower, ci_upper, n_target, n_rest, missingness_rate, fdr_q_global, bonf_p_global, fdr_q_domain, bonf_p_domain

### Correction scope
- **Four correction columns** in the CSV: fdr_q_global, bonf_p_global, fdr_q_domain, bonf_p_domain
- Omnibus and one-vs-rest p-values corrected **separately** (different test families)
  - Global omnibus: FDR/Bonferroni across all n_variables omnibus p-values
  - Global one-vs-rest: FDR/Bonferroni across all n_variables x n_clusters one-vs-rest p-values
- Within-domain correction follows the same separation: omnibus and one-vs-rest corrected separately within each domain
- This yields 4 correction families at global level (omnibus FDR, omnibus Bonf, OVR FDR, OVR Bonf) and the same 4 within each domain

### Claude's Discretion
- Exact label selection algorithm (top-N, threshold-based, or hybrid)
- Plot dimensions and aspect ratio
- Font sizes and typography
- Color scheme for threshold lines
- X-axis spacing and domain separator styling
- Filename conventions for output plots and CSV

</decisions>

<specifics>
## Specific Ideas

- R code uses `ggrepel` with arrow segments from labels to points — adjustText should replicate this style
- R code's Bonferroni threshold is at `-log10(0.05/1271)` — Python version should compute dynamically from the actual test count
- The R code has extensive manual "Relabel Results" sections — the optional rename CSV replaces this with a data-driven approach
- Manhattan plot x-axis should group variables by domain (alternating background shading or gap separators between domains)

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `domain_mapper.py`: `load_domain_config()` returns domain list with colors; `assign_domain()` maps variables — directly usable for plot coloring and x-axis grouping
- `stat_engine.py`: `make_result_row()` produces standardized 12-column dicts; `run_all_tests()` returns a DataFrame ready for correction
- `PipelineResult` dataclass: provides `missingness` dict for the missingness_rate column
- `config.py`: `PipelineConfig` dataclass — may need extension for output paths and plot settings

### Established Patterns
- Dataclass-based configuration (PipelineConfig)
- Phase 2 output is a pandas DataFrame with columns: variable, comparison_type, cluster_label, test_used, statistic, p_value, effect_size, effect_size_type, ci_lower, ci_upper, n_target, n_rest
- Domain mapping config in YAML at `abcd_phewas/data/domain_mapping.yaml`
- `scipy.stats` already in use — `statsmodels.stats.multitest.multipletests` is the natural choice for FDR/Bonferroni

### Integration Points
- Input: DataFrame from `run_all_tests()` (Phase 2) + `PipelineResult.missingness` + `domain_map` from Phase 1
- Output: results CSV + Manhattan plot PNGs consumed by Phase 4's CLI orchestrator
- New modules needed: `correction.py` (multiple comparison), `plotter.py` (Manhattan plots), `results_writer.py` (CSV assembly)

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-correction-and-outputs*
*Context gathered: 2026-03-05*
