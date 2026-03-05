---
phase: 3
slug: correction-and-outputs
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-05
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=7.4 |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `/opt/homebrew/bin/python3.9 -m pytest python_pipeline/tests/ -x -q` |
| **Full suite command** | `/opt/homebrew/bin/python3.9 -m pytest python_pipeline/tests/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `/opt/homebrew/bin/python3.9 -m pytest python_pipeline/tests/ -x -q`
- **After every plan wave:** Run `/opt/homebrew/bin/python3.9 -m pytest python_pipeline/tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 0 | OUTP-01 | unit | `python3.9 -m pytest python_pipeline/tests/test_correction.py -x` | No - W0 | pending |
| 03-01-02 | 01 | 0 | OUTP-01 | unit | `python3.9 -m pytest python_pipeline/tests/test_results_writer.py -x` | No - W0 | pending |
| 03-01-03 | 01 | 0 | OUTP-02, OUTP-03 | smoke | `python3.9 -m pytest python_pipeline/tests/test_plotter.py -x` | No - W0 | pending |
| 03-02-01 | 02 | 1 | OUTP-01 | unit | `python3.9 -m pytest python_pipeline/tests/test_correction.py -v` | No - W0 | pending |
| 03-03-01 | 03 | 1 | OUTP-01 | unit | `python3.9 -m pytest python_pipeline/tests/test_results_writer.py -v` | No - W0 | pending |
| 03-04-01 | 04 | 2 | OUTP-02 | smoke | `python3.9 -m pytest python_pipeline/tests/test_plotter.py::test_ovr -v` | No - W0 | pending |
| 03-05-01 | 05 | 2 | OUTP-03 | smoke | `python3.9 -m pytest python_pipeline/tests/test_plotter.py::test_omnibus -v` | No - W0 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `python_pipeline/tests/test_correction.py` — stubs for OUTP-01 (correction logic: NaN handling, family separation, global vs domain)
- [ ] `python_pipeline/tests/test_results_writer.py` — stubs for OUTP-01 (CSV assembly: column completeness, sort order, domain/missingness merge)
- [ ] `python_pipeline/tests/test_plotter.py` — stubs for OUTP-02, OUTP-03 (plot rendering: smoke test PNG produced, correct DPI)

*Note: Plot tests should be smoke tests (file created, correct dimensions, non-zero file size) rather than pixel-level assertions.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Manhattan plot visual correctness (label readability, domain color accuracy, marker direction) | OUTP-02, OUTP-03 | Visual quality requires human judgment | Open output PNG, verify: domain colors match palette, up/down triangles match effect direction, labels don't overlap, threshold lines visible |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
