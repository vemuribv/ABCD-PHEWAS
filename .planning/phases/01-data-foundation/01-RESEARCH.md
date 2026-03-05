# Phase 1: Data Foundation - Research

**Researched:** 2026-03-04
**Domain:** Python data pipeline — pandas, scipy, numpy; ABCD Study phenotype preprocessing
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Variable Type Detection**
- Auto-detect as baseline heuristic: ≤10 unique values = categorical, >10 = continuous
- Binary: exactly 2 unique non-NA values
- Ordinal: ≤10 unique values AND values are sequential integers (e.g., 1,2,3,4,5 Likert scales)
- Nominal categorical: ≤10 unique values but NOT sequential integers
- Type override file: optional CSV where user can manually correct any misclassified variables (columns: variable_name, forced_type). Overrides take precedence over auto-detection.

**Input File Formats**
- Both cluster assignments and phenotype data are CSV files
- Column names for subject ID and cluster label are configurable (not hardcoded)
- Phenotype file is a single wide CSV: one subject ID column + thousands of phenotype columns
- CRLI blocklist: plain text file with one variable name per line

**Domain Mapping**
- Map variables to ABCD domains using variable name regex patterns (not table name prefixes — the R code uses regex on variable names)
- 8 domains with color palette extracted from existing R codebase (see Domain Mapping section below)
- Prefix-to-domain mapping stored in an external YAML or JSON config file (editable without code changes)
- Unclassified variables: show on plots as "Other" domain in neutral color AND generate a report listing unclassified variable names

**Preprocessing Pipeline**
- Two-pass approach matching the R codebase:
  1. Check skewness (|skew| > 1.96)
  2. Winsorize skewed variables (mean ± 3 SD)
  3. Re-check skewness after winsorization
  4. Apply rank-based inverse normal transformation (INT) only to variables still skewed after winsorization
  5. Z-score non-skewed continuous variables
- Ordinal variables: no preprocessing (kept raw)
- Full transformation log: CSV report documenting each variable's preprocessing path
- Configurable sentinel value list: defaults to [-999, 777, 999]

### Claude's Discretion
- Python project structure (module layout, package naming)
- Specific pandas/numpy implementation patterns
- Logging framework and verbosity levels
- Unit test structure and synthetic data generation approach
- Memory optimization for 3,000+ column DataFrames

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DATA-01 | Load cluster assignments (subject ID + cluster label) and single-timepoint phenotype file | pandas read_csv with configurable column names; inner merge on subject ID |
| DATA-02 | Auto-detect variable types: binary, categorical, ordinal, continuous | nunique() + sequential integer check; override CSV applied after |
| DATA-03 | Handle missing data with per-variable NA exclusion and missingness rate reporting | pandas NA semantics; sentinel replacement before type detection |
| DATA-04 | Skip variables with <10 non-missing subjects in any comparison group | Per-group dropna count; filter before test queue |
| DATA-05 | Apply skewness check, winsorization (mean ±3 SD), and rank-based INT to skewed continuous variables (|skew| > 1.96); z-score non-skewed continuous variables | scipy.stats.skew; scipy.stats.mstats.winsorize equivalent via clip; scipy.stats.rankdata for INT |
| DOMN-01 | Assign phenotype variables to ABCD domains using configurable regex mapping | re.search on variable names; YAML config; "Other/Unclassified" fallback |
| DOMN-02 | Preserve existing 8-domain structure and color palette from current R codebase | Extracted verbatim from R code (see Domain Mapping section) |
</phase_requirements>

---

## Summary

Phase 1 builds a clean, typed, domain-labeled pandas DataFrame ready for statistical testing. The primary technical challenges are (1) implementing the exact two-pass preprocessing pipeline that matches the reference R code, (2) robust sentinel-value replacement before type detection, (3) heuristic variable type detection with user override, and (4) regex-based domain assignment from an external YAML config.

The R reference implementation (`PheWAS Analyses Resub5.Rmd`) uses hardcoded column ranges and Excel input. The Python version replaces both with auto-detection and CSV I/O while preserving all statistical logic identically. The domain structure — 8 categories with their exact regex patterns and hex colors — has been fully extracted from the R codebase and is documented below.

Memory is a real concern: 3,000+ column DataFrames at ~5,000 subjects. Using appropriate dtypes (float32 where possible) and processing columns in batches where needed prevents excess memory use.

**Primary recommendation:** pandas + scipy + numpy + PyYAML, structured as a `src/abcd_phewas/` package with one module per pipeline stage. No exotic dependencies needed.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pandas | >=2.0 | DataFrame loading, merging, type detection | Canonical Python data frame; best CSV I/O and NA semantics |
| numpy | >=1.24 | Numerical arrays, z-scoring | Required by pandas and scipy; vectorized ops |
| scipy | >=1.10 | `scipy.stats.skew`, `scipy.stats.rankdata` | Gold-standard scientific Python; exact equivalents to R's psych::describe and RNOmni |
| PyYAML | >=6.0 | Load domain mapping config | Simple, readable config format; no extra deps |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | >=7.4 | Unit tests | All test execution |
| pytest-cov | >=4.0 | Coverage reporting | CI gate |
| loguru | >=0.7 | Structured logging | Preferred over stdlib logging for readability; Claude's discretion |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| scipy.stats.skew | pandas.DataFrame.skew | scipy matches R's psych::describe behavior; pandas skew uses biased estimator by default |
| Manual winsorize via clip | scipy.stats.mstats.winsorize | R uses Winsorize(minval=mean-3sd, maxval=mean+3sd) which is mean-based, not percentile-based; must use manual clip to match |
| PyYAML | JSON | YAML is more human-editable; either works since we read at startup |

**Installation:**
```bash
pip install pandas>=2.0 numpy>=1.24 scipy>=1.10 pyyaml>=6.0 pytest>=7.4 pytest-cov>=4.0 loguru>=0.7
```

---

## Architecture Patterns

### Recommended Project Structure
```
src/
└── abcd_phewas/
    ├── __init__.py
    ├── config.py          # dataclass config loaded from YAML/CLI args
    ├── loader.py          # DATA-01: load, merge, sentinel replacement, CRLI blocking
    ├── type_detector.py   # DATA-02: variable type auto-detection + override CSV
    ├── preprocessor.py    # DATA-05: two-pass skewness, winsorize, INT, z-score + transformation log
    ├── domain_mapper.py   # DOMN-01/02: regex-based domain assignment
    └── pipeline.py        # Orchestrates all stages in order
tests/
├── conftest.py            # Shared fixtures (synthetic DataFrames)
├── test_loader.py
├── test_type_detector.py
├── test_preprocessor.py
└── test_domain_mapper.py
config/
└── domain_mapping.yaml    # Editable regex → domain config
data/
└── (gitignored real data)
```

### Pattern 1: Sentinel Replacement Before Everything

**What:** Replace ABCD sentinel values with `np.nan` immediately after loading, before type detection or any computation.
**When to use:** Always — sentinels must be invisible to all downstream logic.
**Example:**
```python
# Source: extracted from R code (PheWAS_baseline[PheWAS_baseline == "NA"] <- NA)
import numpy as np

DEFAULT_SENTINELS = [-999, 777, 999]

def replace_sentinels(df: pd.DataFrame, sentinels: list[int | float], subject_col: str) -> pd.DataFrame:
    """Replace sentinel values with NaN. Never touch the subject ID column."""
    pheno_cols = [c for c in df.columns if c != subject_col]
    df[pheno_cols] = df[pheno_cols].replace(sentinels, np.nan)
    return df
```

### Pattern 2: Variable Type Detection with Override

**What:** Auto-detect type using unique-value heuristic; then apply override CSV.
**When to use:** All phenotype columns (skip subject ID and cluster label columns).
**Example:**
```python
# Source: CONTEXT.md locked decisions
import pandas as pd
import numpy as np
from enum import Enum

class VarType(str, Enum):
    BINARY = "binary"
    ORDINAL = "ordinal"
    CATEGORICAL = "categorical"
    CONTINUOUS = "continuous"

UNIQUE_THRESHOLD = 10

def detect_type(series: pd.Series) -> VarType:
    """Classify one column. NA values are excluded before counting."""
    vals = series.dropna()
    if vals.empty:
        return VarType.CONTINUOUS  # default for all-NA column
    n_unique = vals.nunique()
    if n_unique == 2:
        return VarType.BINARY
    if n_unique <= UNIQUE_THRESHOLD:
        # Ordinal: sequential integers starting at 1 (Likert-style)
        sorted_vals = sorted(vals.unique())
        is_sequential_int = (
            all(float(v).is_integer() for v in sorted_vals)
            and sorted_vals == list(range(int(min(sorted_vals)), int(max(sorted_vals)) + 1))
        )
        return VarType.ORDINAL if is_sequential_int else VarType.CATEGORICAL
    return VarType.CONTINUOUS

def apply_overrides(type_map: dict[str, VarType], override_csv_path: str | None) -> dict[str, VarType]:
    """Override auto-detected types from user CSV (columns: variable_name, forced_type)."""
    if override_csv_path is None:
        return type_map
    overrides = pd.read_csv(override_csv_path)
    for _, row in overrides.iterrows():
        type_map[row["variable_name"]] = VarType(row["forced_type"])
    return type_map
```

### Pattern 3: Two-Pass Preprocessing (Matches R Reference)

**What:** Exactly mirror the R pipeline — skewness check → winsorize → re-check → INT if still skewed → z-score the non-skewed.
**When to use:** All continuous variables only. Ordinal/binary/categorical are untouched.
**Example:**
```python
# Source: R lines 96-128 (PheWAS Analyses Resub5.Rmd)
# R: psych::describe → skew; Python: scipy.stats.skew
# R: DescTools::Winsorize(minval=mean-3sd, maxval=mean+3sd); Python: manual clip
# R: qnorm((rank(x, na.last="keep")-0.5)/sum(!is.na(x))); Python: scipy.stats.rankdata with "average"

from scipy import stats
import numpy as np

SKEW_THRESHOLD = 1.96

def _scipy_skew(arr: np.ndarray) -> float:
    """scipy.stats.skew with bias=True matches psych::describe (Fisher's definition)."""
    clean = arr[~np.isnan(arr)]
    return float(stats.skew(clean, bias=True)) if len(clean) > 2 else 0.0

def winsorize_mean_sd(arr: np.ndarray, n_sd: float = 3.0) -> np.ndarray:
    """Mean ± n_sd winsorization — matches R's DescTools::Winsorize with mean-based bounds."""
    clean = arr[~np.isnan(arr)]
    if len(clean) == 0:
        return arr
    mu, sigma = np.nanmean(arr), np.nanstd(arr, ddof=1)
    return np.clip(arr, mu - n_sd * sigma, mu + n_sd * sigma)

def rank_based_int(arr: np.ndarray) -> np.ndarray:
    """Rank-based inverse normal transformation.
    Matches R: qnorm((rank(x, na.last='keep') - 0.5) / sum(!is.na(x)))
    """
    result = np.full_like(arr, np.nan, dtype=float)
    mask = ~np.isnan(arr)
    n = mask.sum()
    if n == 0:
        return result
    ranks = stats.rankdata(arr[mask], method="average")
    result[mask] = stats.norm.ppf((ranks - 0.5) / n)
    return result

def z_score(arr: np.ndarray) -> np.ndarray:
    """Z-score using ddof=1 (sample std) to match R's default scale()."""
    mu, sigma = np.nanmean(arr), np.nanstd(arr, ddof=1)
    if sigma == 0:
        return np.zeros_like(arr, dtype=float)
    return (arr - mu) / sigma

def preprocess_continuous_column(arr: np.ndarray, col_name: str) -> tuple[np.ndarray, dict]:
    """Two-pass preprocessing. Returns (transformed_array, log_entry_dict)."""
    log = {"variable": col_name, "skew_initial": None, "winsorized": False,
           "skew_post_winsor": None, "int_applied": False, "z_scored": False}

    skew1 = _scipy_skew(arr)
    log["skew_initial"] = skew1

    if abs(skew1) > SKEW_THRESHOLD:
        arr = winsorize_mean_sd(arr)
        log["winsorized"] = True
        skew2 = _scipy_skew(arr)
        log["skew_post_winsor"] = skew2

        if abs(skew2) > SKEW_THRESHOLD:
            arr = rank_based_int(arr)
            log["int_applied"] = True
        else:
            arr = z_score(arr)
            log["z_scored"] = True
    else:
        arr = z_score(arr)
        log["z_scored"] = True

    return arr, log
```

### Pattern 4: Domain Assignment from YAML Config

**What:** Apply regex patterns in priority order; first match wins. Unmatched → "Other/Unclassified".
**When to use:** Every phenotype column after CRLI blocking.
**Example:**
```python
# Source: R lines 2918-2961, CONTEXT.md
import re
import yaml

def load_domain_config(yaml_path: str) -> list[dict]:
    """Returns list of {domain, color, patterns} in priority order."""
    with open(yaml_path) as f:
        return yaml.safe_load(f)["domains"]

def assign_domain(col_name: str, domain_config: list[dict]) -> tuple[str, str]:
    """Returns (domain_name, hex_color). Falls back to Other/Unclassified."""
    for entry in domain_config:
        for pattern in entry["patterns"]:
            if re.search(pattern, col_name, re.IGNORECASE):
                return entry["domain"], entry["color"]
    return "Other/Unclassified", "#AAAAAA"
```

**domain_mapping.yaml (initial content from R codebase):**
```yaml
# Source: PheWAS Analyses Resub5.Rmd lines 2914-2961
# Order matters: first match wins. More specific patterns should come first.
domains:
  - domain: "Cognition"
    color: "#FF7F00"   # darkorange1
    patterns:
      - "nihtbx"
      - "RAVLT"
      - "cash"
      - "lmt"
      - "wisc"

  - domain: "Screen Time"
    color: "#20B2AA"   # lightseagreen
    patterns:
      - "screen"
      - "stq"

  - domain: "Demographics"
    color: "#DA70D6"   # orchid3
    patterns:
      - "demo"
      - "prtnr_wor"
      - "prnt_wor"

  - domain: "Substance"
    color: "#87CEFA"   # lightskyblue
    patterns:
      - "tlfb"
      - "path"
      - "isip"
      - "su_"
      - "caff"
      - "rules_"
      - "peer_dev"

  - domain: "Culture/Environment"
    color: "#FFD700"   # goldenrod1
    patterns:
      - "crpbi"
      - "fes"
      - "prosocial"
      - "school"
      - "reshist"
      - "monitor"
      - "neighborhood"
      - "enviro"
      - "pmq"
      - "psb_"
      - "nsc_"
      - "srpf"

  - domain: "Physical Health"
    color: "#2E8B57"   # seagreen
    patterns:
      - "medhx"
      - "devhx"
      - "tbi"
      - "pds"
      - "puber"
      - "sports"
      - "sai_"
      - "filtered_"
      - "anthro"
      - "child_"
      - "antidep_"
      - "sds_"
      - "sleep"
      - "weight"
      - "SSRI"
      - "antidep"
      - "hormon_sal"
      - "medicat"
      - "physical"
      - "caff_24"
      - "caff_ago"

  - domain: "Family Mental Health"
    color: "#FFB6C1"   # pink2
    patterns:
      - "asr_"
      - "famhx"
      - "fam_hist"

  - domain: "Child Mental Health"
    color: "#00008B"   # deepskyblue4
    patterns:
      - "ksad"
      - "cbcl"
      - "prodrom"
      - "pps_"
      - "upps"
      - "bisbas"
      - "bis_"
      - "resiliency"
      - "kbi"
      - "gen_child"
      - "pgbi"
      - "bpm"
      - "ADHD"

  - domain: "Other/Unclassified"
    color: "#AAAAAA"
    patterns: []  # catch-all, never matched by loop — assigned as fallback
```

**IMPORTANT NOTE on colors:** The R code uses R color names (`darkorange1`, `lightseagreen`, etc.), not hex values. The hex values above are the closest Python/matplotlib equivalents. Exact hex values should be confirmed against R's color definitions when the plotting phase (Phase 3) runs. The domain names and order are exact.

### Anti-Patterns to Avoid

- **Type detection before sentinel removal:** Sentinels like 999 would inflate unique-value counts and masquerade as valid numerics. Always replace sentinels first.
- **Using pandas.DataFrame.skew() instead of scipy.stats.skew():** pandas uses an adjusted Fisher-Pearson estimator with a different formula. scipy.stats.skew(bias=True) matches R's `psych::describe`.
- **Percentile-based winsorization:** `scipy.stats.mstats.winsorize` clips by percentile rank. The R code uses `Winsorize(minval=mean-3sd, maxval=mean+3sd)` — mean-based bounds. Must implement manually with `np.clip`.
- **Including ordinal variables in preprocessing:** Ordinal variables are kept raw (Kruskal-Wallis is rank-based; transformation would destroy the rank structure).
- **Hardcoding subject ID or cluster column names:** Both must be configurable. The file format from CRLI pipeline may differ from the ABCD phenotype file.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Skewness calculation | Custom skewness formula | `scipy.stats.skew(arr, bias=True)` | Exact match to R's Fisher g1 statistic |
| Normal quantile function | qnorm approximation | `scipy.stats.norm.ppf()` | Exact match to R's `qnorm()` |
| Rank calculation | Custom ranking loop | `scipy.stats.rankdata(method="average")` | Matches R's `rank(x, na.last="keep")` tie-handling |
| CSV I/O for wide files | Custom parser | `pd.read_csv(dtype_backend="numpy_nullable")` | Handles 3,000+ columns without memory explosion |
| YAML parsing | Custom config parser | `yaml.safe_load()` | Standard; safe against code injection |

**Key insight:** Every statistical primitive in this phase has an exact scipy/numpy equivalent to the R function. Hand-rolling any of these risks introducing numerical divergence that would invalidate reproducibility claims in the manuscript.

---

## Common Pitfalls

### Pitfall 1: Type Detection on Pre-Sentinel Data
**What goes wrong:** A variable like `(-999, 0, 1)` has 3 unique values. After sentinel removal it has 2, making it binary. If type detection runs first, it misclassifies as categorical/ordinal.
**Why it happens:** Sentinel replacement is easy to skip for "efficiency" — it should be the very first step.
**How to avoid:** Enforce ordering in `pipeline.py`. Write an assertion: sentinel replacement must precede type detection.
**Warning signs:** Binary variables showing up as ordinal or categorical in results.

### Pitfall 2: Wide DataFrame Memory Overhead
**What goes wrong:** 3,000 columns × 5,000 rows of float64 ≈ 120 MB baseline. With intermediate copies during preprocessing, peak memory can hit 500+ MB.
**Why it happens:** pandas operations like `replace()` or `apply()` on full DataFrames create copies by default.
**How to avoid:** Use `df[col] = ...` in-place column updates. Load phenotype file with `dtype=float32` where feasible. Drop CRLI-blocked columns immediately after loading before any other operations.
**Warning signs:** Memory usage grows linearly with processing steps.

### Pitfall 3: Sequential Integer Check Fragility
**What goes wrong:** A variable with values `(1.0, 2.0, 3.0)` stored as float fails an integer check because `isinstance(1.0, int)` is False.
**Why it happens:** CSV loading converts everything to float64.
**How to avoid:** Check `float(v).is_integer()` rather than `isinstance(v, int)`. Also check that the range is consecutive: `sorted_vals == list(range(int(min), int(max)+1))`.
**Warning signs:** Likert-scale variables showing up as "categorical" instead of "ordinal".

### Pitfall 4: CRLI Block Applied Too Late
**What goes wrong:** CRLI variables undergo type detection, sentinel replacement, preprocessing — then get dropped. Wastes compute and pollutes the transformation log.
**Why it happens:** Blocking step is added as an afterthought.
**How to avoid:** Drop CRLI variables immediately after the merge in `loader.py`, before any downstream processing.

### Pitfall 5: Missing Data Rate Misreported
**What goes wrong:** Missingness rate is computed before sentinel replacement, so sentinels are counted as non-missing data.
**Why it happens:** Same ordering issue as Pitfall 1.
**How to avoid:** Compute missingness rates only after sentinel replacement.

### Pitfall 6: Domain Regex Order Sensitivity
**What goes wrong:** A variable `asr_cbcl_...` matches both "Family Mental Health" (asr_) and "Child Mental Health" (cbcl) patterns. Which domain it falls into depends on YAML order.
**Why it happens:** First-match-wins is implicit; users editing the YAML may not realize order matters.
**How to avoid:** Document in YAML that order is priority order. Log which pattern matched for any variable assigned a domain — helps diagnose surprising assignments.

---

## Code Examples

### Loading and Merging (DATA-01)
```python
# Source: CONTEXT.md locked decisions
import pandas as pd

def load_and_merge(
    cluster_path: str,
    phenotype_path: str,
    subject_col: str,
    cluster_col: str,
) -> pd.DataFrame:
    clusters = pd.read_csv(cluster_path, usecols=[subject_col, cluster_col])
    pheno = pd.read_csv(phenotype_path)
    merged = pd.merge(clusters, pheno, on=subject_col, how="inner")
    return merged
```

### CRLI Blocking
```python
def apply_crli_blocklist(df: pd.DataFrame, blocklist_path: str | None) -> pd.DataFrame:
    if blocklist_path is None:
        return df
    with open(blocklist_path) as f:
        blocked = {line.strip() for line in f if line.strip()}
    cols_to_drop = [c for c in df.columns if c in blocked]
    return df.drop(columns=cols_to_drop)
```

### Missingness Rate Report (DATA-03)
```python
def compute_missingness(df: pd.DataFrame, pheno_cols: list[str]) -> pd.Series:
    """Returns Series of missingness rates (0-1) per phenotype column."""
    return df[pheno_cols].isna().mean()
```

### Skip Variables with <10 Non-Missing Per Group (DATA-04)
```python
def has_enough_data(series: pd.Series, groups: pd.Series, min_n: int = 10) -> bool:
    """True if every group has >= min_n non-missing observations."""
    return all(
        series[groups == g].notna().sum() >= min_n
        for g in groups.unique()
    )
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| R hardcoded column ranges for type assignment | Python auto-detection with heuristic | This phase | Generalizes to any ABCD release/variable set |
| Excel input (readxl) | CSV input (pandas) | This phase | Faster I/O, no Excel dependency |
| R RNOmni for INT | scipy.stats.norm.ppf + rankdata | This phase | Exact numerical match |
| R DescTools::Winsorize | Manual np.clip with mean±3SD bounds | This phase | Matches R's mean-based (not percentile) bounds |

**Deprecated/outdated:**
- Excel-based input: R code uses `FINAL_PHEWAS_baseline_n5556_5.11.23.xlsx`. Python version uses CSV only.
- Hardcoded column range indexing: `PheWAS_baseline[,21:312]` — replaced by auto-detection.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.4+ |
| Config file | `pytest.ini` or `pyproject.toml [tool.pytest.ini_options]` — Wave 0 gap |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ --cov=src/abcd_phewas --cov-report=term-missing` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DATA-01 | Inner merge keeps only subjects in both files | unit | `pytest tests/test_loader.py::test_inner_merge -x` | Wave 0 |
| DATA-01 | Configurable column names load correctly | unit | `pytest tests/test_loader.py::test_configurable_cols -x` | Wave 0 |
| DATA-02 | Binary detection (exactly 2 unique non-NA values) | unit | `pytest tests/test_type_detector.py::test_binary -x` | Wave 0 |
| DATA-02 | Ordinal detection (sequential ints ≤10 unique) | unit | `pytest tests/test_type_detector.py::test_ordinal -x` | Wave 0 |
| DATA-02 | Categorical detection (≤10 unique, non-sequential) | unit | `pytest tests/test_type_detector.py::test_categorical -x` | Wave 0 |
| DATA-02 | Continuous detection (>10 unique) | unit | `pytest tests/test_type_detector.py::test_continuous -x` | Wave 0 |
| DATA-02 | Override CSV takes precedence over auto-detection | unit | `pytest tests/test_type_detector.py::test_override -x` | Wave 0 |
| DATA-03 | Sentinel values (-999, 777, 999) become NaN | unit | `pytest tests/test_loader.py::test_sentinel_replacement -x` | Wave 0 |
| DATA-03 | Missingness rates computed after sentinel removal | unit | `pytest tests/test_loader.py::test_missingness_rate -x` | Wave 0 |
| DATA-04 | Variables with <10 non-missing per group are flagged | unit | `pytest tests/test_loader.py::test_min_n_filter -x` | Wave 0 |
| DATA-05 | Skewed variable → winsorized → re-checked → INT applied | unit | `pytest tests/test_preprocessor.py::test_two_pass_int -x` | Wave 0 |
| DATA-05 | Skewed variable → winsorized → non-skewed → z-scored | unit | `pytest tests/test_preprocessor.py::test_two_pass_zscore -x` | Wave 0 |
| DATA-05 | Non-skewed variable → z-scored directly | unit | `pytest tests/test_preprocessor.py::test_non_skewed_zscore -x` | Wave 0 |
| DATA-05 | Transformation log CSV contains correct entries | unit | `pytest tests/test_preprocessor.py::test_transformation_log -x` | Wave 0 |
| DATA-05 | Ordinal variables pass through unmodified | unit | `pytest tests/test_preprocessor.py::test_ordinal_passthrough -x` | Wave 0 |
| DOMN-01 | Variable matched to correct domain by regex | unit | `pytest tests/test_domain_mapper.py::test_domain_assignment -x` | Wave 0 |
| DOMN-01 | Unmatched variable gets "Other/Unclassified" + neutral color | unit | `pytest tests/test_domain_mapper.py::test_unclassified_fallback -x` | Wave 0 |
| DOMN-02 | All 8 domain names and colors match R codebase exactly | unit | `pytest tests/test_domain_mapper.py::test_eight_domains -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/ -x -q`
- **Per wave merge:** `pytest tests/ --cov=src/abcd_phewas --cov-report=term-missing`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/conftest.py` — shared fixtures: synthetic 10-col DataFrame with known type mix, sentinels, cluster labels
- [ ] `tests/test_loader.py` — covers DATA-01, DATA-03, DATA-04
- [ ] `tests/test_type_detector.py` — covers DATA-02
- [ ] `tests/test_preprocessor.py` — covers DATA-05
- [ ] `tests/test_domain_mapper.py` — covers DOMN-01, DOMN-02
- [ ] `config/domain_mapping.yaml` — initial domain config extracted from R code
- [ ] `pyproject.toml` or `pytest.ini` — pytest configuration
- [ ] Framework install: `pip install pytest pytest-cov`

---

## Open Questions

1. **R color name → hex mapping exactness (DOMN-02)**
   - What we know: R color names from the codebase are `darkorange1`, `lightseagreen`, `orchid3`, `lightskyblue`, `goldenrod1`, `seagreen`, `pink2`, `deepskyblue4`
   - What's unclear: R's internal color table may not exactly match web hex values. The exact matplotlib/hex equivalents need verification when Phase 3 (plotting) runs.
   - Recommendation: Store domain colors as R color name strings in YAML now; add hex mapping in Phase 3 when matplotlib is introduced. Don't block Phase 1 on this.

2. **CRLI blocklist variable names (DATA-01)**
   - What we know: Blocklist is a plain-text file, one variable per line (locked decision)
   - What's unclear: The actual variable names in the blocklist are not yet confirmed by the research team (flagged in STATE.md)
   - Recommendation: Build the loader to accept any valid path; test with a synthetic blocklist. The actual blocklist file is a data dependency, not a code dependency.

3. **Cluster assignment file column names**
   - What we know: Subject ID column and cluster column names are configurable (locked decision)
   - What's unclear: Exact defaults from the CRLI pipeline output (flagged in STATE.md)
   - Recommendation: Make defaults configurable at CLI/config level; document expected format in README-style docstring.

4. **ABCD sentinel code completeness**
   - What we know: Default list is [-999, 777, 999]; extensible via config
   - What's unclear: Whether instrument-specific codes (-1 for "don't know", 888 for "refused") are needed for the specific ABCD release used
   - Recommendation: Implement extensible sentinel list now; the research team can add instrument-specific codes to the config without code changes.

---

## Sources

### Primary (HIGH confidence)
- `PheWAS Analyses Resub5.Rmd` (project R reference) — extracted domain patterns (lines 2918-2961), color palette (line 2914), preprocessing logic (lines 96-128, 640-661)
- CONTEXT.md — all locked decisions and implementation specifications

### Secondary (MEDIUM confidence)
- scipy documentation pattern for `rankdata` and `norm.ppf` — matches documented R `qnorm((rank(x, na.last="keep")-0.5)/n)` formula
- pandas 2.0 documentation — `read_csv`, NA semantics, `replace()`

### Tertiary (LOW confidence)
- R-to-Python color name mapping — R color table equivalents to hex; needs verification in Phase 3

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — pandas/scipy/numpy are the unambiguous standard for this problem; no research needed
- Architecture: HIGH — module-per-stage is well-established for linear data pipelines
- Preprocessing logic: HIGH — extracted directly from R reference implementation with line citations
- Domain mapping: HIGH — regex patterns and colors extracted verbatim from R codebase
- Color hex values: LOW — R-to-hex conversion not verified against R's color table; flagged as Phase 3 concern
- Pitfalls: HIGH — all identified from code analysis of R reference and known pandas/numpy behaviors

**Research date:** 2026-03-04
**Valid until:** 2026-09-04 (scipy/pandas APIs are stable; domain config is project-specific, not version-sensitive)
