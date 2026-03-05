---
status: diagnosed
phase: 01-data-foundation
source: [01-01-SUMMARY.md, 01-02-SUMMARY.md]
started: 2026-03-05T00:39:33Z
updated: 2026-03-05T01:10:00Z
---

## Current Test
<!-- OVERWRITE each test - shows where we are -->

[testing complete]

## Tests

### 1. Package installs and imports cleanly
expected: Run `import abcd_phewas; print(abcd_phewas.__version__)` in the project venv. It prints a version string with no errors.
result: pass

### 2. Full test suite passes
expected: Run `python -m pytest tests/ -v` in the project venv. All 75 tests pass with no failures or errors.
result: skipped
reason: Test suite requires repo source; not practical on secure server. Tests pass locally (75/75).

### 3. Loader merges cluster and phenotype CSVs
expected: Run `from abcd_phewas.loader import load_and_merge; help(load_and_merge)`. The function signature shows it takes cluster_path, pheno_path, and config parameters. No import errors.
result: pass

### 4. Type detector classifies variables
expected: Run `from abcd_phewas.type_detector import VarType; print(list(VarType))`. Shows the four types: BINARY, ORDINAL, CATEGORICAL, CONTINUOUS.
result: pass

### 5. Domain mapping config loads
expected: Run `from abcd_phewas.domain_mapper import load_domain_config; cfg = load_domain_config('config/domain_mapping.yaml'); print([d['name'] for d in cfg])`. Shows all 9 domain names (8 ABCD domains + Other/Unclassified).
result: issue
reported: "[Errno 2] No such file or directory: 'config/domain_mapping.yaml'"
severity: major

### 6. Pipeline orchestrator runs end-to-end
expected: Run `from abcd_phewas.pipeline import run_pipeline, PipelineResult; print(PipelineResult.__dataclass_fields__.keys())`. Shows all result fields: df, type_map, domain_map, transformation_log, missingness, skipped_vars, unclassified_vars.
result: pass

### 7. Preprocessor transforms continuous variables
expected: Run `from abcd_phewas.preprocessor import preprocess_continuous_column; print(preprocess_continuous_column.__doc__[:100] if preprocess_continuous_column.__doc__ else 'function exists')`. Function loads without error, showing it exists and is importable.
result: pass

## Summary

total: 7
passed: 5
issues: 1
pending: 0
skipped: 1

## Gaps

- truth: "Domain mapping config loads from 'config/domain_mapping.yaml' and returns 9 domain names"
  status: failed
  reason: "User reported: [Errno 2] No such file or directory: 'config/domain_mapping.yaml'"
  severity: major
  test: 5
  root_cause: "load_domain_config() takes a raw path string with no package-relative resolution. config/domain_mapping.yaml is relative to CWD, which fails when running from a Jupyter notebook on a different server where CWD != project root."
  artifacts:
    - path: "src/abcd_phewas/domain_mapper.py"
      issue: "load_domain_config() line 35 uses raw open(yaml_path) with no fallback to package-relative path"
    - path: "config/domain_mapping.yaml"
      issue: "Config file exists in repo but isn't bundled with package or discoverable via importlib"
  missing:
    - "Add a default path resolver using importlib.resources or pathlib relative to package root"
    - "Bundle config/domain_mapping.yaml as package data or provide a get_default_config_path() helper"
