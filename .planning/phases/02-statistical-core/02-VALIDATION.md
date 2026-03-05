---
phase: 2
slug: statistical-core
status: draft
nyquist_compliant: true
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
| **Quick run command** | `/opt/homebrew/bin/python3.9 -m pytest tests/test_effect_sizes.py tests/test_stat_engine.py -x -v` |
| **Full suite command** | `/opt/homebrew/bin/python3.9 -m pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run relevant test file (`test_effect_sizes.py` or `test_stat_engine.py`) with `-x -v`
- **After every plan wave:** Run `/opt/homebrew/bin/python3.9 -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-T1 | 01 | 1 | STAT-03 | unit (RED) | `pytest tests/test_effect_sizes.py -x -v` (expects FAIL) | Wave 0 creates | pending |
| 02-01-T2 | 01 | 1 | STAT-03 | unit (GREEN) | `pytest tests/test_effect_sizes.py -x -v` (expects PASS) | Created by T1 | pending |
| 02-02-T1 | 02 | 2 | STAT-01, STAT-02, STAT-06 | unit | `pytest tests/test_stat_engine.py -x -v` | Wave 0 creates | pending |
| 02-03-T1 | 03 | 3 | STAT-04, STAT-05, STAT-06 | integration | `pytest tests/test_stat_engine.py -x -v` | Exists from 02-02-T1 | pending |
| 02-03-T2 | 03 | 3 | ALL | full suite | `pytest tests/ -v` | All exist | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_effect_sizes.py` — stubs/tests for all effect size functions (Plan 01 Task 1 creates this)
- [ ] `tests/test_stat_engine.py` — stubs for dispatch, test runners, fallback chain (Plan 02 Task 1 creates this)
- [ ] `tests/conftest.py` — extend with synthetic data fixtures (known effect sizes, sparse tables, multi-cluster data)

*Existing infrastructure covers framework (pytest already configured).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Effect sizes match R reference | STAT-03 | Requires ABCD data comparison | Run both R and Python pipelines on same subset, compare effect size columns |

---

## Scope Notes

- **Plan 02-02 Task 1 size:** This task contains dispatch table, 4 test runners, orchestrator, and 12+ tests in a single task. Accepted as-is because Plan 02 contains only this one task (well within the 2-3 task/plan budget and ~50% context target). The components are tightly coupled -- splitting the dispatch table from its test runners would create artificial boundaries.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (test_effect_sizes.py and test_stat_engine.py)
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved
