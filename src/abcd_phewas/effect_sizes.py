"""Effect size functions, Monte Carlo chi-square, and bootstrap CI wrapper.

Phase 2, Plan 01: Pure math building blocks for the statistical test engine.
Each function takes simple numeric inputs and returns a single value or tuple.
"""
from __future__ import annotations

import warnings
from typing import Callable, Optional, Tuple

import numpy as np
from scipy.stats import bootstrap, chi2_contingency


# ---------------------------------------------------------------------------
# Cohen's d (pooled SD)
# ---------------------------------------------------------------------------


def cohens_d(group1: np.ndarray, group2: np.ndarray) -> float:
    """Compute Cohen's d with pooled standard deviation.

    Parameters
    ----------
    group1 : np.ndarray
        Observations from the target cluster.
    group2 : np.ndarray
        Observations from the comparison group (e.g., pooled rest).

    Returns
    -------
    float
        Cohen's d.  Positive when ``mean(group1) > mean(group2)``.
        Returns 0.0 if pooled SD is zero (both groups constant).
    """
    g1 = np.asarray(group1, dtype=float)
    g2 = np.asarray(group2, dtype=float)
    n1, n2 = len(g1), len(g2)
    var1, var2 = g1.var(ddof=1), g2.var(ddof=1)
    pooled_sd = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
    if pooled_sd == 0.0:
        return 0.0
    return float((g1.mean() - g2.mean()) / pooled_sd)


# ---------------------------------------------------------------------------
# Rank-biserial correlation
# ---------------------------------------------------------------------------


def rank_biserial(u_statistic: float, n1: int, n2: int) -> float:
    """Compute rank-biserial correlation from Mann-Whitney U statistic.

    Parameters
    ----------
    u_statistic : float
        Mann-Whitney U statistic.
    n1 : int
        Sample size of group 1.
    n2 : int
        Sample size of group 2.

    Returns
    -------
    float
        Rank-biserial r in [-1, 1].
    """
    return 1.0 - (2.0 * u_statistic) / (n1 * n2)


# ---------------------------------------------------------------------------
# Cramer's V
# ---------------------------------------------------------------------------


def cramers_v(contingency_table: np.ndarray) -> float:
    """Compute Cramer's V from a contingency table.

    Parameters
    ----------
    contingency_table : np.ndarray
        Observed frequency table (2-D).

    Returns
    -------
    float
        Cramer's V in [0, 1].  Returns 0.0 for degenerate tables
        (single row/column or zero total).
    """
    table = np.asarray(contingency_table)
    n = table.sum()
    if n == 0:
        return 0.0
    nrows, ncols = table.shape
    min_dim = min(nrows - 1, ncols - 1)
    if min_dim == 0:
        return 0.0
    chi2, _, _, _ = chi2_contingency(table, correction=False)
    return float(np.sqrt(chi2 / (n * min_dim)))


# ---------------------------------------------------------------------------
# Epsilon-squared
# ---------------------------------------------------------------------------


def epsilon_squared(h_statistic: float, n_total: int) -> float:
    """Compute epsilon-squared from Kruskal-Wallis H.

    Parameters
    ----------
    h_statistic : float
        Kruskal-Wallis H statistic.
    n_total : int
        Total number of observations across all groups.

    Returns
    -------
    float
        Epsilon-squared in [0, ~1].  Returns 0.0 if ``n_total <= 1``.
    """
    if n_total <= 1:
        return 0.0
    return float(h_statistic / (n_total - 1))


# ---------------------------------------------------------------------------
# Monte Carlo chi-square (simulated p-value)
# ---------------------------------------------------------------------------


def monte_carlo_chi_square(
    observed: np.ndarray,
    n_replicates: int = 10_000,
    rng: Optional[np.random.Generator] = None,
) -> float:
    """Monte Carlo simulation of chi-square p-value.

    Analogous to R's ``chisq.test(..., simulate.p.value = TRUE)``.

    Parameters
    ----------
    observed : np.ndarray
        Observed contingency table (2-D).
    n_replicates : int
        Number of random tables to simulate.
    rng : numpy.random.Generator or None
        Random number generator for reproducibility.

    Returns
    -------
    float
        Conservative simulated p-value: ``(count_ge + 1) / (n_replicates + 1)``.
    """
    if rng is None:
        rng = np.random.default_rng()

    table = np.asarray(observed)
    n = table.sum()

    # Observed chi-square
    chi2_obs, _, _, expected = chi2_contingency(table, correction=False)

    # Expected cell probabilities under independence
    probs = (expected / n).ravel()

    # Simulate random tables and count chi-square >= observed
    count_ge = 0
    for _ in range(n_replicates):
        sim_counts = rng.multinomial(n, probs).reshape(table.shape)
        # Compute chi-square for simulated table (avoid zero expected)
        try:
            chi2_sim, _, _, _ = chi2_contingency(sim_counts, correction=False)
        except ValueError:
            # Degenerate simulated table (e.g., zero row/column)
            continue
        if chi2_sim >= chi2_obs:
            count_ge += 1

    return (count_ge + 1) / (n_replicates + 1)


# ---------------------------------------------------------------------------
# Bootstrap confidence interval wrapper
# ---------------------------------------------------------------------------


def bootstrap_ci(
    statistic_fn: Callable,
    data_args: Tuple[np.ndarray, ...],
    n_resamples: int = 2000,
    confidence_level: float = 0.95,
    random_state: Optional[int] = None,
) -> Tuple[float, float]:
    """Bootstrap confidence interval for a statistic function.

    Uses scipy.stats.bootstrap with the percentile method (not BCa,
    which fails on degenerate data).

    Parameters
    ----------
    statistic_fn : callable
        Function accepting ``(*samples)`` -- e.g. ``cohens_d(group1, group2)``.
        Called with ``vectorized=False`` so scipy passes 1-D arrays directly.
    data_args : tuple of np.ndarray
        Data arrays to pass to ``statistic_fn``.
    n_resamples : int
        Number of bootstrap resamples.
    confidence_level : float
        Confidence level (e.g. 0.95 for 95% CI).
    random_state : int or None
        Seed for reproducibility.

    Returns
    -------
    tuple[float, float]
        (lower, upper) confidence bounds.  Returns ``(nan, nan)`` on failure.
    """
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=RuntimeWarning)
            result = bootstrap(
                data_args,
                statistic=statistic_fn,
                n_resamples=n_resamples,
                confidence_level=confidence_level,
                method="percentile",
                random_state=random_state,
                vectorized=False,
                paired=False,
            )
        low = float(result.confidence_interval.low)
        high = float(result.confidence_interval.high)
        return (low, high)
    except Exception:
        return (float("nan"), float("nan"))
