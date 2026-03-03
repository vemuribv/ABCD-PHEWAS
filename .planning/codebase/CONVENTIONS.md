# Coding Conventions

**Analysis Date:** 2025-03-02

## Naming Patterns

**Files:**
- Lowercase with underscores: `preprocessing.py`, `config.py`, `test_domains.py`
- Test files follow pattern: `test_{module_name}.py`

**Functions:**
- snake_case: `load_phenotype_data()`, `assign_domains_to_results()`, `create_cluster_dummies()`
- Private functions prefixed with underscore: `_strip_year_suffix()`, `_worker()`, `_load_checkpoint()`
- Verbs come first: `load_`, `compute_`, `assign_`, `filter_`, `apply_`, `write_`, `validate_`

**Variables:**
- snake_case: `phenotype_cols`, `continuous_col_range`, `skew_threshold`
- Constant-like module-level variables: `_DEFAULT_YAML`, `_DEFAULT_METADATA`, `_PYMER4_AVAILABLE`, `_YEAR_SUFFIX_RE`

**Types and Classes:**
- PascalCase: `PheWASConfig`, `ModelResult`, `DomainSpec` (type alias)
- Type alias comment: `ModelResult = dict[str, Any]`

## Code Style

**Formatting:**
- PEP 8 adherence (4-space indentation throughout)
- Line continuations for long function calls (see `cli.py` lines 162-167)
- Multiline imports grouped and readable (see `cli.py` lines 39-52)
- Sections marked with comment blocks using dashes: `# -----... -----`

**Future annotations:**
- Every module opens with `from __future__ import annotations` (see `cli.py` line 30, `config.py` line 3, `domains.py` line 19)
- Enables string-based forward references and modern type hint syntax in Python 3.10+

**Linting:**
- No .flake8, .pylintrc, or setup.cfg config files found — uses PEP 8 defaults
- No formatter enforced (no .prettierrc equivalent for Python)

## Import Organization

**Order:**
1. `from __future__ import annotations` (required in all files)
2. Standard library imports: `logging`, `os`, `sys`, `argparse`, `pathlib.Path`, `typing.*`
3. Third-party library imports: `pandas`, `numpy`, `scipy`, `yaml`, `matplotlib`, `pymer4`
4. Local imports: `from .config import`, `from .preprocessing import`

**Path aliases:**
- Relative imports within package: `from .config import`, `from .preprocessing import`
- Module naming: Use package-relative paths, e.g., `python_pipeline.cli:main` in entry points
- No absolute import aliases configured in pyproject.toml

**Example from `cli.py` (lines 30-53):**
```python
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

from .config import PheWASConfig
from .corrections import apply_multiple_corrections
from .domains import assign_domains_to_results, get_domain_order, load_domain_config
```

## Error Handling

**Patterns:**
- ValueError for invalid configuration/data: `raise ValueError(f"...")`  (see `config.py` lines 110-123)
- Exception logging: `except Exception as exc:` with `logger.warning()`  (see `corrections.py` lines 76-80)
- Graceful fallback on missing optional dependencies: Try/except ImportError with `_AVAILABLE` flag (see `models.py` lines 40-47, `visualizations.py` lines 24-28)
- Return empty/neutral values instead of raising: `load_phenotype_metadata()` returns `{}` if file missing (see `domains.py` lines 100-102)

**Example from `domains.py`:**
```python
def load_phenotype_metadata(filepath: Optional[str] = None) -> dict[str, dict]:
    path = filepath or _DEFAULT_METADATA
    if not os.path.exists(path):
        logger.debug("phenotype_metadata not found at %s — using regex-only domains", path)
        return {}
    ...
```

## Logging

**Framework:** Python's built-in `logging` module

**Setup:**
- `setup_logging(level: str)` in `utils.py` configures root logger with timestamp, level, and module name
- Format: `"%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"` (see `utils.py` line 23)
- All modules use `logger = logging.getLogger(__name__)` (see every module's top lines)

**Patterns:**
- `logger.info()` for major pipeline stages (see `cli.py` line 157: "=== Stage 1: Load + preprocess phenotype data ===")
- `logger.warning()` for recoverable issues (see `cli.py` line 261: "No results produced")
- `logger.debug()` for optional/fallback paths (see `domains.py` line 101)
- Count summaries in logs: `logger.info("Loaded %d rows × %d cols from %s", len(df), len(df.columns), filepath)`
- Domain distribution logged after assignment: `logger.info("Domain assignment summary:\n%s", counts.to_string())`

## Comments

**When to Comment:**
- Section headers: `# --------- ... ---------` (78 dashes) to separate major logic sections
- Not on every line — code is self-documenting via function names
- Docstrings explain the "why" of complex operations

**JSDoc/TSDoc equivalents (NumPy-style docstrings):**
- Used on all public functions and classes
- Three-part structure: summary line, Parameters section, Returns section
- See `domains.py` lines 58-79 (load_domain_config):
```python
def load_domain_config(filepath: Optional[str] = None) -> list[DomainSpec]:
    """Load domain definitions from a YAML file.

    Parameters
    ----------
    filepath : Optional[str]
        Path to the domains YAML file.  Defaults to
        ``python_pipeline/configs/domains.yaml``.

    Returns
    -------
    list[DomainSpec]
        Ordered list of domain specification dicts.
    """
```

## Function Design

**Size:** Functions generally 15–80 lines
- Large orchestration functions: 100+ lines (e.g., `run_pipeline()` in `cli.py` is 168 lines of stages)
- Utility/transformation functions: 5–30 lines

**Parameters:**
- Use required parameters for critical inputs (no defaults)
- Use Optional[type] with `None` default for optional features
- Collection parameters use `list[str]`, `set[str]`, `dict[str, Any]`
- Use **kwargs sparingly; prefer explicit named parameters

**Return Values:**
- Functions return a single value or tuple
- Dataframe transformations return new DataFrame (non-mutating): `.copy()` before modifying (see `preprocessing.py` line 198, `corrections.py` line 50)
- Helper functions return typed values: `ModelResult = dict[str, Any]` for model outputs
- Optional returns use `Optional[type]`: `Optional[str]`, `Optional[dict]`

**Example from `preprocessing.py` (lines 31–88):**
```python
def load_phenotype_data(
    filepath: str,
    continuous_col_range: tuple[int, int],
    binary_col_range: tuple[int, int],
    subject_id_col: str = "subjectkey",
) -> pd.DataFrame:
    """Load an ABCD phenotype file and assign column dtypes by positional range."""
    # ... function body ...
    return df
```

## Module Design

**Exports:**
- All public functions and classes exported directly (no `__all__` used)
- Private functions/vars prefixed with underscore: `_strip_year_suffix`, `_YEAR_SUFFIX_RE`, `_DEFAULT_DOMAIN_CONFIG`

**Barrel Files:**
- `python_pipeline/__init__.py` is empty — no re-exports
- Imports done explicitly from submodules: `from .config import PheWASConfig`

**Module responsibilities:**
- `config.py` — Configuration dataclass and YAML loading
- `preprocessing.py` — Data I/O, transformations (winsorize, INT, zscore)
- `domains.py` — Domain assignment (metadata + regex fallback)
- `corrections.py` — Statistical corrections (FDR, Bonferroni)
- `models.py` — GLMM formula building and fitting (pymer4 wrapper)
- `parallel.py` — ProcessPoolExecutor dispatch, checkpointing
- `visualizations.py` — Matplotlib-based plots (Manhattan, forest, stacked bar)
- `cli.py` — Argument parsing and pipeline orchestration
- `utils.py` — Logging setup, file I/O, validation helpers

---

*Convention analysis: 2025-03-02*
