# Phase 2: Statistical Core - Research

**Researched:** 2026-03-05
**Domain:** Non-parametric statistical testing, effect sizes, confidence intervals
**Confidence:** HIGH

## Summary

Phase 2 builds a statistical test engine that takes Phase 1's `PipelineResult` (preprocessed DataFrame, type_map, domain_map) and produces a results DataFrame with one row per (variable, comparison) pair containing raw p-values, effect sizes, confidence intervals, and test metadata. The engine must handle four variable types (BINARY, ORDINAL, CATEGORICAL, CONTINUOUS) across two comparison modes (omnibus across all K clusters, one-vs-rest per cluster), with automatic fallback to Fisher's exact for sparse 2x2 tables and Monte Carlo simulated chi-square for sparse larger tables.

All required statistical functions are available in `scipy.stats` (scipy 1.13.1 is installed): `kruskal`, `mannwhitneyu`, `chi2_contingency`, `fisher_exact`, and `bootstrap`. The rank-biserial correlation for Mann-Whitney U and epsilon-squared for Kruskal-Wallis are simple formulas computable from the test statistics. Cramer's V and Cohen's d are standard formulas. Monte Carlo simulated chi-square p-values for sparse >2x2 tables require a custom implementation (scipy does not have R's `simulate.p.value` equivalent), but this is straightforward using random permutation of contingency table margins.

**Primary recommendation:** Build a single `stat_engine.py` module with a dispatch function keyed on (VarType, comparison_type) that selects the correct test, computes effect size, and returns a standardized result row. Parallelize across variables using `concurrent.futures.ProcessPoolExecutor` for the 3,000+ variable workload.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- KW across all K clusters IS the omnibus for continuous/ordinal variables (no separate omnibus KW)
- Chi-square across all K clusters IS the omnibus for binary/categorical variables
- One-vs-rest uses Mann-Whitney U for continuous/ordinal (target cluster vs pooled rest)
- One-vs-rest uses chi-square or Fisher's exact for binary/categorical (target vs rest contingency table)
- P-value count assertion: n_variables x (n_clusters + 1) where +1 is the omnibus
- Continuous one-vs-rest: Cohen's d (target cluster vs pooled rest)
- Ordinal one-vs-rest: Rank-biserial correlation from Mann-Whitney U (directional, -1 to +1)
- Binary/categorical one-vs-rest: Cramer's V from 2xL contingency table
- Continuous/ordinal omnibus: Epsilon-squared from Kruskal-Wallis (0 to 1)
- Binary/categorical omnibus: Cramer's V from KxL contingency table
- Confidence intervals computed in Phase 2 alongside effect sizes (bootstrap or analytic)
- Fisher's exact for 2x2 tables when any expected cell count < 5 (Cochran's rule)
- For larger tables (>2x2) with sparse cells: chi-square with simulated p-value (Monte Carlo)
- Fisher's exact NOT used for tables larger than 2x2
- Results include 'test_used' column for methods reporting
- Results DataFrame: one row per (variable, comparison) pair
- Columns: variable, comparison_type, cluster_label, test_used, statistic, p_value, effect_size, effect_size_type, ci_lower, ci_upper, n_target, n_rest
- STAT-04 and STAT-05 (correction) deferred to Phase 3; Phase 2 produces raw p-values ONLY

### Claude's Discretion
- Test engine module structure (single module vs split by test type)
- Synthetic data generation for unit tests
- Parallelization strategy for running tests across 3,000+ variables
- Bootstrap parameters (n_resamples for CIs)
- Exact Monte Carlo simulation parameters (n_replicates for simulated chi-square)

### Deferred Ideas (OUT OF SCOPE)
None
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| STAT-01 | One-vs-rest comparison per cluster: KW for continuous/ordinal, chi-square/Fisher for binary/categorical | scipy.stats.mannwhitneyu (one-vs-rest continuous/ordinal), chi2_contingency + fisher_exact (binary/categorical); test dispatch by VarType enum |
| STAT-02 | Global omnibus test per variable across all clusters | scipy.stats.kruskal (continuous/ordinal omnibus), chi2_contingency (categorical/binary omnibus) |
| STAT-03 | Effect sizes: Cohen's d (continuous), Cramer's V (binary/categorical) | Hand-computed formulas from test statistics; rank-biserial from U statistic; epsilon-squared from H statistic; bootstrap CIs via scipy.stats.bootstrap |
| STAT-04 | Global FDR and Bonferroni correction | DEFERRED to Phase 3 per CONTEXT.md; Phase 2 outputs raw p-values only |
| STAT-05 | Within-domain FDR and Bonferroni correction | DEFERRED to Phase 3 per CONTEXT.md; Phase 2 outputs raw p-values only |
| STAT-06 | Support 2-8 clusters | Engine parameterized by cluster labels from data; no hardcoded cluster count; tested with both 2-cluster and 8-cluster synthetic data |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| scipy | 1.13.1 (installed) | KW, Mann-Whitney U, chi2_contingency, fisher_exact, bootstrap | Standard scientific Python; already a project dependency |
| numpy | 2.0.2 (installed) | Array operations, random number generation for Monte Carlo | Already a project dependency |
| pandas | 2.3.3 (installed) | DataFrame manipulation, crosstab for contingency tables | Already a project dependency |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| concurrent.futures | stdlib | ProcessPoolExecutor for parallelization | When running 3,000+ variable tests |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Manual Cohen's d | pingouin library | Extra dependency for a 3-line formula; not worth it |
| Manual Monte Carlo chi-square | rpy2 + R's chisq.test | Adds R dependency for one function; manual simulation is simple |
| scipy.stats.bootstrap | Manual bootstrap loop | scipy.stats.bootstrap handles BCa intervals correctly; use it |

**Installation:**
```bash
# No new packages needed - scipy, numpy, pandas already installed
```

## Architecture Patterns

### Recommended Project Structure
```
src/abcd_phewas/
    stat_engine.py        # Main test dispatch + result assembly
    effect_sizes.py       # Cohen's d, Cramer's V, rank-biserial, epsilon-squared, CIs
    tests/                # (existing tests/ dir at project root)
tests/
    test_stat_engine.py   # Synthetic data tests for all test paths
    conftest.py           # Extended with statistical test fixtures
```

### Pattern 1: Test Dispatch by (VarType, ComparisonType)
**What:** A dispatch function that selects the correct statistical test based on variable type and comparison mode (omnibus vs one-vs-rest).
**When to use:** Every variable-comparison pair.
**Example:**
```python
# Source: Project architecture decision
from enum import Enum

class ComparisonType(str, Enum):
    OMNIBUS = "omnibus"
    ONE_VS_REST = "one_vs_rest"

# Dispatch table
TEST_DISPATCH = {
    (VarType.CONTINUOUS, ComparisonType.OMNIBUS): run_kruskal_wallis,
    (VarType.ORDINAL, ComparisonType.OMNIBUS): run_kruskal_wallis,
    (VarType.BINARY, ComparisonType.OMNIBUS): run_chi_square_omnibus,
    (VarType.CATEGORICAL, ComparisonType.OMNIBUS): run_chi_square_omnibus,
    (VarType.CONTINUOUS, ComparisonType.ONE_VS_REST): run_mann_whitney,
    (VarType.ORDINAL, ComparisonType.ONE_VS_REST): run_mann_whitney,
    (VarType.BINARY, ComparisonType.ONE_VS_REST): run_chi_square_pairwise,
    (VarType.CATEGORICAL, ComparisonType.ONE_VS_REST): run_chi_square_pairwise,
}
```

### Pattern 2: Standardized Result Row
**What:** Every test function returns the same dict structure regardless of test type.
**When to use:** All test functions must return this shape.
**Example:**
```python
def make_result_row(
    variable: str,
    comparison_type: str,  # "omnibus" or "one_vs_rest"
    cluster_label: str | None,  # None for omnibus
    test_used: str,
    statistic: float,
    p_value: float,
    effect_size: float,
    effect_size_type: str,
    ci_lower: float,
    ci_upper: float,
    n_target: int,
    n_rest: int | None,  # None for omnibus
) -> dict:
    ...
```

### Pattern 3: Sparse Table Fallback Chain
**What:** For binary/categorical one-vs-rest comparisons, check expected cell frequencies and fall back to Fisher's exact (2x2) or Monte Carlo simulation (>2x2) when sparse.
**When to use:** Every chi-square test on contingency tables.
**Example:**
```python
from scipy.stats import chi2_contingency, fisher_exact
import numpy as np

def run_chi_square_with_fallback(observed: np.ndarray) -> tuple[float, float, str]:
    """Returns (statistic, p_value, test_used)."""
    chi2, p, dof, expected = chi2_contingency(observed, correction=False)

    if (expected < 5).any():
        if observed.shape == (2, 2):
            odds_ratio, p = fisher_exact(observed)
            return odds_ratio, p, "fisher_exact"
        else:
            # Monte Carlo simulated p-value
            p = monte_carlo_chi_square(observed, n_replicates=10000)
            return chi2, p, "chi_square_simulated"

    return chi2, p, "chi_square"
```

### Pattern 4: Variable-Level Parallelization
**What:** Parallelize at the variable level, not the test level; each variable produces K+1 result rows.
**When to use:** When processing 3,000+ variables.
**Example:**
```python
from concurrent.futures import ProcessPoolExecutor

def test_single_variable(args):
    """Process one variable: omnibus + K one-vs-rest comparisons."""
    variable, data, cluster_labels, var_type = args
    rows = []
    rows.append(run_omnibus(variable, data, cluster_labels, var_type))
    for label in sorted(set(cluster_labels)):
        rows.append(run_one_vs_rest(variable, data, cluster_labels, label, var_type))
    return rows

def run_all_tests(df, type_map, cluster_col, n_workers=None):
    args_list = [(var, df[[var, cluster_col]], df[cluster_col], vtype)
                 for var, vtype in type_map.items()]

    with ProcessPoolExecutor(max_workers=n_workers) as executor:
        results = list(executor.map(test_single_variable, args_list))

    return pd.DataFrame([row for var_rows in results for row in var_rows])
```

### Anti-Patterns to Avoid
- **Testing significance before computing effect size:** Effect sizes must be computed for ALL (variable, cluster) pairs, not just those passing a significance threshold. The CONTEXT explicitly locks this.
- **Hardcoding cluster counts:** The engine must derive K from the data. Use `df[cluster_col].unique()` to get cluster labels dynamically.
- **Using Fisher's exact for >2x2 tables:** Computationally intractable for large tables. Use Monte Carlo simulation instead.
- **Thread-based parallelism:** While scipy is thread-safe (unlike rpy2), using ProcessPoolExecutor is consistent with project convention and avoids GIL concerns with numpy.
- **NaN propagation in tests:** Always dropna before passing to scipy test functions. scipy's `nan_policy='propagate'` returns NaN, which is wrong for per-variable exclusion.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Kruskal-Wallis test | Custom rank-based test | `scipy.stats.kruskal` | Handles ties, returns exact H statistic |
| Mann-Whitney U test | Custom rank-sum | `scipy.stats.mannwhitneyu` | Handles ties, continuity correction, returns U statistic |
| Chi-square test | Manual expected frequency calc | `scipy.stats.chi2_contingency` | Returns expected frequencies for Cochran's rule check |
| Fisher's exact test | Manual hypergeometric | `scipy.stats.fisher_exact` | Only works on 2x2 (by design) |
| Contingency tables | Manual cross-tabulation | `pd.crosstab` | Handles NaN exclusion, returns proper array for scipy |
| Bootstrap CIs | Manual resampling loop | `scipy.stats.bootstrap` | BCa intervals, vectorized, handles edge cases |

**Key insight:** All statistical tests are in scipy; the only custom code needed is effect size formulas (4 simple functions), the Monte Carlo chi-square simulation, and the dispatch/assembly logic.

## Common Pitfalls

### Pitfall 1: NaN Handling in Contingency Tables
**What goes wrong:** `pd.crosstab` excludes NaN by default, but if a cluster has zero observations for a category, the contingency table may have zero rows/columns, causing chi-square to fail.
**Why it happens:** Per-variable NA exclusion means different variables have different subject sets.
**How to avoid:** After creating the contingency table, check for all-zero rows/columns and remove them. Verify the table has at least 2 rows and 2 columns before running chi-square.
**Warning signs:** `chi2_contingency` raises `ValueError` or returns p=1.0 with 0 statistic.

### Pitfall 2: Mann-Whitney U Statistic Interpretation for Rank-Biserial
**What goes wrong:** `scipy.stats.mannwhitneyu` returns U1 (the U for the first sample). The rank-biserial correlation formula `r = 1 - (2*U)/(n1*n2)` requires knowing which U was returned.
**Why it happens:** scipy returns U1 for x, but the formula needs the correct U for directionality.
**How to avoid:** Use the formula `r = 1 - (2 * U) / (n1 * n2)` where U is the statistic returned by scipy (which is U for x=target group). This gives positive r when target group has higher ranks.
**Warning signs:** Effect sizes systematically inverted (all negative when they should be positive or vice versa).

### Pitfall 3: Cohen's d with Unequal Group Sizes
**What goes wrong:** Using simple pooled SD formula when groups are very unequal (e.g., 1 cluster of 50 vs rest of 5000).
**Why it happens:** One-vs-rest creates inherently unbalanced groups.
**How to avoid:** Use the pooled SD with Welch-style weighting: `s_pooled = sqrt(((n1-1)*s1^2 + (n2-1)*s2^2) / (n1+n2-2))`. This is the standard Cohen's d pooled SD formula and handles unequal n correctly.
**Warning signs:** Extreme effect sizes (|d| > 3) for variables with small cluster sizes.

### Pitfall 4: Empty or Single-Value Groups After NA Exclusion
**What goes wrong:** After dropping NaN for a specific variable, a cluster may have 0 or 1 observation, making tests impossible.
**Why it happens:** Phase 1's min-n filter checks across all variables jointly, but individual variables may have more missingness.
**How to avoid:** Check group sizes per variable before running each test. If any group has < 2 observations, return NaN for that test with a warning. The min-n filter at Phase 1 uses `min_n_per_group=10` which should prevent this in practice, but defensive coding is essential.
**Warning signs:** `scipy.stats.kruskal` raises ValueError about all-identical groups.

### Pitfall 5: Monte Carlo Chi-Square Reproducibility
**What goes wrong:** Monte Carlo p-values change between runs, making tests non-deterministic.
**Why it happens:** Random table generation without seeding.
**How to avoid:** Accept a `random_state` parameter and use `numpy.random.Generator` with a fixed seed for testing. In production, use a session-level seed for reproducibility.
**Warning signs:** Test assertions fail intermittently.

### Pitfall 6: Bootstrap CI Failures for Degenerate Data
**What goes wrong:** `scipy.stats.bootstrap` raises errors when the statistic is constant across all resamples (e.g., Cramer's V = 0 for all bootstrap samples).
**Why it happens:** When groups have identical distributions, effect size is exactly 0 in every resample, BCa method fails.
**How to avoid:** Catch `DegenerateDataWarning` from scipy. For degenerate cases, return CI = (0.0, 0.0) or use percentile method as fallback instead of BCa.
**Warning signs:** Warnings about degenerate bootstrap distributions.

## Code Examples

### Effect Size: Cohen's d
```python
# Source: Standard formula (Lakens, 2013)
import numpy as np

def cohens_d(group1: np.ndarray, group2: np.ndarray) -> float:
    """Cohen's d with pooled standard deviation."""
    n1, n2 = len(group1), len(group2)
    var1, var2 = np.var(group1, ddof=1), np.var(group2, ddof=1)
    pooled_sd = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
    if pooled_sd == 0:
        return 0.0
    return (np.mean(group1) - np.mean(group2)) / pooled_sd
```

### Effect Size: Rank-Biserial Correlation from Mann-Whitney U
```python
# Source: Kerby (2014), rank-biserial from U statistic
def rank_biserial(u_statistic: float, n1: int, n2: int) -> float:
    """Rank-biserial correlation from Mann-Whitney U.

    Returns value in [-1, 1]. Positive means group1 has higher ranks.
    """
    return 1 - (2 * u_statistic) / (n1 * n2)
```

### Effect Size: Cramer's V
```python
# Source: Standard formula
import numpy as np

def cramers_v(contingency_table: np.ndarray) -> float:
    """Cramer's V from observed contingency table."""
    from scipy.stats import chi2_contingency
    chi2, _, _, _ = chi2_contingency(contingency_table, correction=False)
    n = contingency_table.sum()
    min_dim = min(contingency_table.shape) - 1
    if min_dim == 0 or n == 0:
        return 0.0
    return np.sqrt(chi2 / (n * min_dim))
```

### Effect Size: Epsilon-Squared from Kruskal-Wallis
```python
# Source: Tomczak & Tomczak (2014)
def epsilon_squared(h_statistic: float, n_total: int) -> float:
    """Epsilon-squared from Kruskal-Wallis H statistic.

    Range: 0 to 1.
    """
    if n_total <= 1:
        return 0.0
    return h_statistic / ((n_total ** 2 - 1) / (n_total + 1))
    # Simplified: H / (n - 1)
```

Note: The standard formula is `e^2 = (H - k + 1) / (n - k)` or simply `H / (n^2 - 1)/(n + 1)`. The most common formulation: `e^2 = H / ((n^2 - 1) / (n + 1))`. Let me verify:

```python
# Tomczak & Tomczak (2014): epsilon_squared = H / (n^2 - 1)/(n + 1)
# Which simplifies to: H * (n + 1) / (n^2 - 1) = H / (n - 1)
def epsilon_squared(h_statistic: float, n_total: int) -> float:
    """Epsilon-squared effect size for Kruskal-Wallis."""
    if n_total <= 1:
        return 0.0
    return h_statistic / (n_total - 1)
```

### Monte Carlo Simulated Chi-Square P-Value
```python
# Source: Equivalent to R's chisq.test(simulate.p.value=TRUE)
import numpy as np
from scipy.stats import chi2_contingency

def monte_carlo_chi_square(
    observed: np.ndarray,
    n_replicates: int = 10_000,
    rng: np.random.Generator | None = None,
) -> float:
    """Simulated p-value for chi-square test via random table generation.

    Generates random contingency tables with the same marginals as observed,
    computes chi-square for each, returns proportion >= observed chi-square.
    """
    if rng is None:
        rng = np.random.default_rng()

    chi2_obs, _, _, _ = chi2_contingency(observed, correction=False)

    row_sums = observed.sum(axis=1)
    col_sums = observed.sum(axis=0)
    n = observed.sum()

    count_ge = 0
    for _ in range(n_replicates):
        # Generate random table with fixed marginals using rcont2 algorithm
        simulated = _random_contingency_table(row_sums, col_sums, n, rng)
        chi2_sim, _, _, _ = chi2_contingency(simulated, correction=False)
        if chi2_sim >= chi2_obs:
            count_ge += 1

    return (count_ge + 1) / (n_replicates + 1)  # +1 for conservative estimate
```

### Bootstrap CI for Effect Size
```python
# Source: scipy.stats.bootstrap official API
from scipy.stats import bootstrap
import numpy as np

def bootstrap_ci_cohens_d(
    group1: np.ndarray,
    group2: np.ndarray,
    n_resamples: int = 2000,
    confidence_level: float = 0.95,
    random_state: int | None = None,
) -> tuple[float, float]:
    """Bootstrap CI for Cohen's d using scipy.stats.bootstrap."""
    def statistic(g1, g2, axis):
        n1 = g1.shape[axis]
        n2 = g2.shape[axis]
        m1 = np.mean(g1, axis=axis)
        m2 = np.mean(g2, axis=axis)
        v1 = np.var(g1, ddof=1, axis=axis)
        v2 = np.var(g2, ddof=1, axis=axis)
        pooled = np.sqrt(((n1 - 1) * v1 + (n2 - 1) * v2) / (n1 + n2 - 2))
        pooled = np.where(pooled == 0, 1.0, pooled)  # avoid div by zero
        return (m1 - m2) / pooled

    try:
        result = bootstrap(
            (group1, group2),
            statistic,
            n_resamples=n_resamples,
            confidence_level=confidence_level,
            method="percentile",  # BCa can fail on degenerate data
            random_state=random_state,
            paired=False,
        )
        return result.confidence_interval.low, result.confidence_interval.high
    except Exception:
        # Fallback: return NaN CI
        return float("nan"), float("nan")
```

### P-Value Count Assertion
```python
# Source: CONTEXT.md locked decision
def assert_result_shape(results_df, n_variables, n_clusters):
    """Assert the results DataFrame has exactly the expected number of rows."""
    expected_rows = n_variables * (n_clusters + 1)  # +1 for omnibus
    actual_rows = len(results_df)
    assert actual_rows == expected_rows, (
        f"Expected {expected_rows} result rows "
        f"({n_variables} vars x ({n_clusters} clusters + 1 omnibus)), "
        f"got {actual_rows}"
    )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual bootstrap loops | `scipy.stats.bootstrap` | scipy 1.7+ (2021) | Correct BCa intervals, vectorized |
| fisher_exact only for 2x2 | Still only 2x2 in scipy | Unchanged | Must use Monte Carlo for larger sparse tables |
| Yates correction always | Correction=False + fallback chain | Best practice | Yates overcorrects; better to use Fisher/Monte Carlo |

**Deprecated/outdated:**
- `scipy.stats.mstats.kruskalwallis`: Use `scipy.stats.kruskal` instead (same functionality, better API)

## Open Questions

1. **Bootstrap n_resamples tradeoff**
   - What we know: 2000 resamples is adequate for 95% CIs (Efron & Tibshirani). 9999 is scipy default.
   - What's unclear: With 3,000+ variables and K clusters, total bootstrap operations = 3000 * K * 2000. At K=8 this is 48M resamples.
   - Recommendation: Use 2000 for CIs (sufficient accuracy, reasonable runtime). Consider making configurable.

2. **Monte Carlo n_replicates**
   - What we know: R's default is 2000 for `simulate.p.value`. 10,000 gives finer resolution.
   - What's unclear: How many sparse tables will actually trigger Monte Carlo in ABCD data.
   - Recommendation: Use 10,000 (conservative, since it only triggers for sparse tables which are a minority).

3. **Random contingency table generation**
   - What we know: R uses the rcont2 algorithm (Patefield 1981) for efficient random table generation with fixed marginals.
   - What's unclear: Whether a Python implementation exists or if we need to implement rcont2.
   - Recommendation: Use a simple multinomial sampling approach for the Monte Carlo simulation. For the expected table sizes (2xL or KxL with small K and L), performance is not critical since it only triggers for sparse tables.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.4+ |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `/opt/homebrew/bin/python3.9 -m pytest tests/test_stat_engine.py -x -v` |
| Full suite command | `/opt/homebrew/bin/python3.9 -m pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STAT-01 | One-vs-rest per cluster: MWU for continuous/ordinal, chi-sq/Fisher for binary/cat | unit | `pytest tests/test_stat_engine.py::test_one_vs_rest_continuous -x` | No - Wave 0 |
| STAT-01 | Fisher exact fallback on sparse 2x2 | unit | `pytest tests/test_stat_engine.py::test_fisher_fallback -x` | No - Wave 0 |
| STAT-01 | Monte Carlo chi-square on sparse >2x2 | unit | `pytest tests/test_stat_engine.py::test_monte_carlo_fallback -x` | No - Wave 0 |
| STAT-02 | Omnibus KW for continuous, chi-square for categorical | unit | `pytest tests/test_stat_engine.py::test_omnibus -x` | No - Wave 0 |
| STAT-03 | Cohen's d, rank-biserial, Cramer's V, epsilon-squared all computed | unit | `pytest tests/test_stat_engine.py::test_effect_sizes -x` | No - Wave 0 |
| STAT-03 | CIs present for all effect sizes | unit | `pytest tests/test_stat_engine.py::test_confidence_intervals -x` | No - Wave 0 |
| STAT-03 | Effect sizes for ALL pairs, not just significant | unit | `pytest tests/test_stat_engine.py::test_effect_sizes_all_pairs -x` | No - Wave 0 |
| STAT-06 | Works with 2 clusters and 8 clusters | unit | `pytest tests/test_stat_engine.py::test_multi_cluster_support -x` | No - Wave 0 |
| ALL | Result shape assertion: n_vars * (n_clusters + 1) | unit | `pytest tests/test_stat_engine.py::test_result_shape_assertion -x` | No - Wave 0 |
| ALL | Synthetic data covering all 4 variable types | unit | `pytest tests/test_stat_engine.py -x` | No - Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_stat_engine.py -x -v`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_stat_engine.py` -- covers STAT-01 through STAT-06 on synthetic data
- [ ] `tests/conftest.py` -- extend with synthetic data fixtures for statistical tests (known effect sizes, sparse tables, multi-cluster data)

## Sources

### Primary (HIGH confidence)
- scipy.stats API (verified against installed scipy 1.13.1): `kruskal`, `mannwhitneyu`, `chi2_contingency`, `fisher_exact`, `bootstrap` -- all confirmed available and API signatures verified
- Project source code: `src/abcd_phewas/pipeline.py`, `config.py`, `type_detector.py` -- confirmed VarType enum, PipelineResult dataclass, PipelineConfig dataclass
- `pyproject.toml` -- confirmed scipy>=1.10, numpy>=1.24, pandas>=2.0 as dependencies

### Secondary (MEDIUM confidence)
- Effect size formulas: Cohen's d (Cohen, 1988), Cramer's V (Cramer, 1946), rank-biserial (Kerby, 2014), epsilon-squared (Tomczak & Tomczak, 2014) -- standard textbook formulas
- Monte Carlo chi-square: equivalent to R's `chisq.test(simulate.p.value=TRUE, B=10000)` -- standard practice for sparse contingency tables

### Tertiary (LOW confidence)
- Random contingency table generation (rcont2 Patefield 1981): may need simplified multinomial approach rather than exact algorithm; validate against R output if needed

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already installed and API-verified
- Architecture: HIGH - straightforward dispatch pattern, well-understood test selection
- Effect sizes: HIGH - standard formulas with clear references
- Monte Carlo simulation: MEDIUM - custom implementation needed, but algorithm is straightforward
- Bootstrap CIs: MEDIUM - scipy.stats.bootstrap handles most cases, but degenerate data edge cases need defensive coding
- Pitfalls: HIGH - documented from known scipy behaviors and statistical edge cases

**Research date:** 2026-03-05
**Valid until:** 2026-04-05 (stable domain, no fast-moving dependencies)
