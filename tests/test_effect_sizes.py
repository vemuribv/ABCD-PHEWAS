"""Unit tests for effect size functions (Phase 2, Plan 01).

All tests import from abcd_phewas.effect_sizes. In the RED phase,
the module does not exist so every test fails with ImportError.
"""
from __future__ import annotations

import numpy as np
import pytest

from abcd_phewas.effect_sizes import (
    bootstrap_ci,
    cohens_d,
    cramers_v,
    epsilon_squared,
    monte_carlo_chi_square,
    rank_biserial,
)


# ---------------------------------------------------------------------------
# Cohen's d
# ---------------------------------------------------------------------------


class TestCohensD:
    def test_known_values(self):
        """Two groups with known means and equal SD -> d ~ 2.5."""
        rng = np.random.default_rng(42)
        g1 = rng.normal(10, 2, size=100)
        g2 = rng.normal(5, 2, size=100)
        d = cohens_d(g1, g2)
        # Expected Cohen's d = (10 - 5) / 2 = 2.5, allow sampling noise
        assert 2.0 < d < 3.0

    def test_zero_variance(self):
        """Both groups constant (zero pooled SD) -> d = 0.0."""
        g1 = np.array([5.0, 5.0, 5.0, 5.0])
        g2 = np.array([5.0, 5.0, 5.0, 5.0])
        assert cohens_d(g1, g2) == 0.0

    def test_direction(self):
        """group1 > group2 -> positive d; group1 < group2 -> negative d."""
        g_high = np.array([10.0, 11.0, 12.0])
        g_low = np.array([1.0, 2.0, 3.0])
        assert cohens_d(g_high, g_low) > 0
        assert cohens_d(g_low, g_high) < 0


# ---------------------------------------------------------------------------
# Rank-biserial correlation
# ---------------------------------------------------------------------------


class TestRankBiserial:
    def test_boundaries_u_zero(self):
        """U = 0 -> r = 1.0 (maximum positive effect)."""
        assert rank_biserial(0, 10, 10) == pytest.approx(1.0)

    def test_boundaries_u_max(self):
        """U = n1 * n2 -> r = -1.0 (maximum negative effect)."""
        assert rank_biserial(100, 10, 10) == pytest.approx(-1.0)

    def test_midpoint(self):
        """U = n1*n2 / 2 -> r = 0.0 (no effect)."""
        assert rank_biserial(50, 10, 10) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Cramer's V
# ---------------------------------------------------------------------------


class TestCramersV:
    def test_independent_table(self):
        """Independent 2x2 table -> V near 0."""
        # Large sample, approximately independent
        table = np.array([[250, 250], [250, 250]])
        v = cramers_v(table)
        assert v < 0.05

    def test_perfect_association(self):
        """Diagonal table -> V = 1.0."""
        table = np.array([[100, 0], [0, 100]])
        v = cramers_v(table)
        assert v == pytest.approx(1.0, abs=0.01)

    def test_single_dim_zero(self):
        """Table with only one row or one column -> V = 0.0."""
        # 1-row table: min_dim = min(1-1, 2-1) = 0
        table = np.array([[50, 50]])
        v = cramers_v(table)
        assert v == 0.0


# ---------------------------------------------------------------------------
# Epsilon-squared
# ---------------------------------------------------------------------------


class TestEpsilonSquared:
    def test_no_effect(self):
        """H = 0 -> epsilon-squared = 0.0."""
        assert epsilon_squared(0.0, 100) == 0.0

    def test_positive(self):
        """H > 0 -> positive epsilon-squared."""
        eps = epsilon_squared(25.0, 100)
        assert eps > 0
        # H / (n-1) = 25 / 99 ~ 0.2525
        assert eps == pytest.approx(25.0 / 99.0)


# ---------------------------------------------------------------------------
# Monte Carlo chi-square
# ---------------------------------------------------------------------------


class TestMonteCarloChiSquare:
    def test_vs_scipy(self):
        """Non-sparse table: Monte Carlo p close to scipy chi2 p (within 0.05)."""
        from scipy.stats import chi2_contingency

        table = np.array([[50, 30], [20, 100]])
        _, scipy_p, _, _ = chi2_contingency(table, correction=False)
        rng = np.random.default_rng(42)
        mc_p = monte_carlo_chi_square(table, n_replicates=10_000, rng=rng)
        assert abs(mc_p - scipy_p) < 0.05

    def test_reproducibility(self):
        """Same seed -> identical p-value."""
        table = np.array([[10, 5], [3, 82]])
        rng1 = np.random.default_rng(999)
        rng2 = np.random.default_rng(999)
        p1 = monte_carlo_chi_square(table, n_replicates=5000, rng=rng1)
        p2 = monte_carlo_chi_square(table, n_replicates=5000, rng=rng2)
        assert p1 == p2


# ---------------------------------------------------------------------------
# Bootstrap CI
# ---------------------------------------------------------------------------


class TestBootstrapCI:
    def test_normal_data(self):
        """Bootstrap CI for cohens_d returns (low, high) with low < high."""
        rng_data = np.random.default_rng(42)
        g1 = rng_data.normal(10, 2, size=50)
        g2 = rng_data.normal(5, 2, size=50)
        low, high = bootstrap_ci(cohens_d, (g1, g2), n_resamples=500, random_state=42)
        assert low < high
        # Point estimate is ~2.5, CI should contain it
        assert low > 0

    def test_degenerate_data(self):
        """Constant data -> no error raised; returns (nan, nan) or (0, 0)."""
        g1 = np.array([5.0] * 20)
        g2 = np.array([5.0] * 20)
        low, high = bootstrap_ci(cohens_d, (g1, g2), n_resamples=200, random_state=42)
        # Should not raise; result is either (nan, nan) or (0.0, 0.0)
        assert (np.isnan(low) and np.isnan(high)) or (low == 0.0 and high == 0.0)
