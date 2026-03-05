---
phase: 1
slug: data-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-04
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.4+ |
| **Config file** | `pyproject.toml [tool.pytest.ini_options]` — Wave 0 installs |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ --cov=src/abcd_phewas --cov-report=term-missing` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ --cov=src/abcd_phewas --cov-report=term-missing`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 1 | DATA-01 | unit | `pytest tests/test_loader.py::test_inner_merge -x` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01 | 1 | DATA-01 | unit | `pytest tests/test_loader.py::test_configurable_cols -x` | ❌ W0 | ⬜ pending |
| 1-01-03 | 01 | 1 | DATA-03 | unit | `pytest tests/test_loader.py::test_sentinel_replacement -x` | ❌ W0 | ⬜ pending |
| 1-01-04 | 01 | 1 | DATA-03 | unit | `pytest tests/test_loader.py::test_missingness_rate -x` | ❌ W0 | ⬜ pending |
| 1-01-05 | 01 | 1 | DATA-04 | unit | `pytest tests/test_loader.py::test_min_n_filter -x` | ❌ W0 | ⬜ pending |
| 1-02-01 | 02 | 1 | DATA-02 | unit | `pytest tests/test_type_detector.py::test_binary -x` | ❌ W0 | ⬜ pending |
| 1-02-02 | 02 | 1 | DATA-02 | unit | `pytest tests/test_type_detector.py::test_ordinal -x` | ❌ W0 | ⬜ pending |
| 1-02-03 | 02 | 1 | DATA-02 | unit | `pytest tests/test_type_detector.py::test_categorical -x` | ❌ W0 | ⬜ pending |
| 1-02-04 | 02 | 1 | DATA-02 | unit | `pytest tests/test_type_detector.py::test_continuous -x` | ❌ W0 | ⬜ pending |
| 1-02-05 | 02 | 1 | DATA-02 | unit | `pytest tests/test_type_detector.py::test_override -x` | ❌ W0 | ⬜ pending |
| 1-03-01 | 03 | 1 | DATA-05 | unit | `pytest tests/test_preprocessor.py::test_two_pass_int -x` | ❌ W0 | ⬜ pending |
| 1-03-02 | 03 | 1 | DATA-05 | unit | `pytest tests/test_preprocessor.py::test_two_pass_zscore -x` | ❌ W0 | ⬜ pending |
| 1-03-03 | 03 | 1 | DATA-05 | unit | `pytest tests/test_preprocessor.py::test_non_skewed_zscore -x` | ❌ W0 | ⬜ pending |
| 1-03-04 | 03 | 1 | DATA-05 | unit | `pytest tests/test_preprocessor.py::test_transformation_log -x` | ❌ W0 | ⬜ pending |
| 1-03-05 | 03 | 1 | DATA-05 | unit | `pytest tests/test_preprocessor.py::test_ordinal_passthrough -x` | ❌ W0 | ⬜ pending |
| 1-04-01 | 04 | 1 | DOMN-01 | unit | `pytest tests/test_domain_mapper.py::test_domain_assignment -x` | ❌ W0 | ⬜ pending |
| 1-04-02 | 04 | 1 | DOMN-01 | unit | `pytest tests/test_domain_mapper.py::test_unclassified_fallback -x` | ❌ W0 | ⬜ pending |
| 1-04-03 | 04 | 1 | DOMN-02 | unit | `pytest tests/test_domain_mapper.py::test_eight_domains -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `pyproject.toml` — pytest configuration and project metadata
- [ ] `tests/conftest.py` — shared fixtures: synthetic 10-col DataFrame with known type mix, sentinels, cluster labels
- [ ] `tests/test_loader.py` — stubs for DATA-01, DATA-03, DATA-04
- [ ] `tests/test_type_detector.py` — stubs for DATA-02
- [ ] `tests/test_preprocessor.py` — stubs for DATA-05
- [ ] `tests/test_domain_mapper.py` — stubs for DOMN-01, DOMN-02
- [ ] `config/domain_mapping.yaml` — initial domain config extracted from R code
- [ ] Framework install: `pip install pytest pytest-cov`

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
