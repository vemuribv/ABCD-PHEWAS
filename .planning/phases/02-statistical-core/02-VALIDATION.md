---
phase: 2
slug: statistical-core
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-05
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.4+ |
| **Config file** | `pyproject.toml` [tool.pytest.ini_options] |
| **Quick run command** | `/opt/homebrew/bin/python3.9 -m pytest tests/test_stat_engine.py -x -v` |
| **Full suite command** | `/opt/homebrew/bin/python3.9 -m pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `/opt/homebrew/bin/python3.9 -m pytest tests/test_stat_engine.py -x -v`
- **After every plan wave:** Run `/opt/homebrew/bin/python3.9 -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 0 | ALL | unit | `pytest tests/test_stat_engine.py -x` | No - Wave 0 creates | pending |
| 02-01-02 | 01 | 1 | STAT-01, STAT-02 | unit | `pytest tests/test_stat_engine.py::test_omnibus -x` | No - Wave 0 | pending |
| 02-01-03 | 01 | 1 | STAT-03 | unit | `pytest tests/test_stat_engine.py::test_effect_sizes -x` | No - Wave 0 | pending |
| 02-01-04 | 01 | 1 | STAT-01 | unit | `pytest tests/test_stat_engine.py::test_fisher_fallback -x` | No - Wave 0 | pending |
| 02-01-05 | 01 | 1 | STAT-01 | unit | `pytest tests/test_stat_engine.py::test_monte_carlo_fallback -x` | No - Wave 0 | pending |
| 02-01-06 | 01 | 2 | STAT-06 | unit | `pytest tests/test_stat_engine.py::test_multi_cluster_support -x` | No - Wave 0 | pending |
| 02-01-07 | 01 | 2 | ALL | unit | `pytest tests/test_stat_engine.py::test_result_shape_assertion -x` | No - Wave 0 | pending |
| 02-01-08 | 01 | 2 | STAT-03 | unit | `pytest tests/test_stat_engine.py::test_confidence_intervals -x` | No - Wave 0 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_stat_engine.py` — stubs for STAT-01 through STAT-06 on synthetic data
- [ ] `tests/conftest.py` — extend with synthetic data fixtures (known effect sizes, sparse tables, multi-cluster data)

*Existing infrastructure covers framework (pytest already configured).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Effect sizes match R reference | STAT-03 | Requires ABCD data comparison | Run both R and Python pipelines on same subset, compare effect size columns |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
