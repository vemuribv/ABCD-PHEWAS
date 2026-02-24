"""GLMM model fitting via pymer4 (R/lme4 wrapper).

Mirrors the R code's lmer / glmer calls from PheWAS Analyses Resub5.Rmd:

  Continuous outcome:
      lmer(phenotype ~ cluster_1 + cluster_2 + C1 + ... + C10 + sex +
           interview_age + (1|site_id) + (1|rel_family_id),
           control = lmerControl(optimizer="bobyqa",
                                  optCtrl=list(maxfun=1e5)))

  Binary outcome:
      glmer(phenotype ~ cluster_1 + cluster_2 + C1 + ... + C10 + sex +
            interview_age + (1|site_id) + (1|rel_family_id),
            family = "binomial", nAGQ = 0,
            control = glmerControl(optimizer="bobyqa",
                                    optCtrl=list(maxfun=1e5)))

Each call to run_single_phenotype() returns k-1 ModelResult dicts, one per
cluster dummy column.
"""

from __future__ import annotations

import logging
import warnings
from typing import Any, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Type alias for a single result row
ModelResult = dict[str, Any]

# ------------------------------------------------------------------ #
# Lazy import of pymer4 so the module can be imported even if pymer4
# is not yet installed (e.g., during unit testing with mocks).
# ------------------------------------------------------------------ #
try:
    from pymer4.models import Lmer
    _PYMER4_AVAILABLE = True
except ImportError:
    _PYMER4_AVAILABLE = False
    logger.warning(
        "pymer4 not found.  Model fitting will fail.  Install pymer4 and R/lme4."
    )


# --------------------------------------------------------------------------- #
# Formula building
# --------------------------------------------------------------------------- #

def build_formula(
    phenotype: str,
    cluster_dummy_cols: list[str],
    covariates: list[str],
    site_id_col: str = "site_id",
    family_id_col: Optional[str] = "rel_family_id",
    include_family_re: bool = True,
) -> str:
    """Build an lme4-style formula string for pymer4.

    Example output (3 clusters, reference=0):
        "cbcl_total ~ cluster_1 + cluster_2 + C1 + C2 + sex + interview_age +
         (1|site_id) + (1|rel_family_id)"

    Parameters
    ----------
    phenotype : str
        Name of the outcome column.
    cluster_dummy_cols : list[str]
        Names of k-1 dummy columns for cluster contrasts (e.g., ["cluster_1", "cluster_2"]).
    covariates : list[str]
        Covariate column names (e.g., ["C1", ..., "C10", "sex", "interview_age"]).
    site_id_col : str
        Column for site-level random intercept.
    family_id_col : Optional[str]
        Column for family-level random intercept.  None omits this term.
    include_family_re : bool
        If False the family random-effect term is omitted (used for reshist
        variables in R that lack family nesting).

    Returns
    -------
    str
        Complete formula string.
    """
    predictors = " + ".join(cluster_dummy_cols + covariates)
    re_terms = f"(1|{site_id_col})"
    if include_family_re and family_id_col:
        re_terms += f" + (1|{family_id_col})"
    return f"{phenotype} ~ {predictors} + {re_terms}"


# --------------------------------------------------------------------------- #
# Model fitting
# --------------------------------------------------------------------------- #

def _lmer_control_str(optimizer: str, max_iterations: int) -> str:
    """Build an R lmerControl() string for pymer4's control parameter."""
    return (
        f'lmerControl(optimizer="{optimizer}", '
        f'optCtrl=list(maxfun={max_iterations}))'
    )


def _glmer_control_str(optimizer: str, max_iterations: int) -> str:
    """Build an R glmerControl() string for pymer4's control parameter."""
    return (
        f'glmerControl(optimizer="{optimizer}", '
        f'optCtrl=list(maxfun={max_iterations}))'
    )


def fit_continuous_model(
    df: pd.DataFrame,
    formula: str,
    optimizer: str = "bobyqa",
    max_iterations: int = 100_000,
) -> Optional[Any]:
    """Fit a linear mixed-effects model via pymer4.Lmer.

    Mirrors R's lmer(..., control=lmerControl(optimizer="bobyqa", optCtrl=list(maxfun=1e5))).

    Parameters
    ----------
    df : pd.DataFrame
    formula : str
        lme4-style formula string.
    optimizer : str
    max_iterations : int

    Returns
    -------
    Fitted pymer4 Lmer object or None if fitting failed.
    """
    if not _PYMER4_AVAILABLE:
        raise RuntimeError("pymer4 is not installed.  Cannot fit models.")

    try:
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            model = Lmer(formula, data=df)
            model.fit(
                REML=True,
                control=_lmer_control_str(optimizer, max_iterations),
                verbose=False,
            )
        return model
    except Exception as exc:
        logger.debug("Continuous model failed (%s): %s", formula.split("~")[0].strip(), exc)
        return None


def fit_binary_model(
    df: pd.DataFrame,
    formula: str,
    optimizer: str = "bobyqa",
    max_iterations: int = 100_000,
) -> Optional[Any]:
    """Fit a binomial GLMM via pymer4.Lmer with family='binomial'.

    Mirrors R's glmer(..., family="binomial", nAGQ=0,
                       control=glmerControl(optimizer="bobyqa", ...)).

    Note: pymer4 uses Lmer for both linear and generalised models; the
    family is specified via the family argument to fit().

    Parameters
    ----------
    df : pd.DataFrame
    formula : str
    optimizer : str
    max_iterations : int

    Returns
    -------
    Fitted pymer4 Lmer object or None if fitting failed.
    """
    if not _PYMER4_AVAILABLE:
        raise RuntimeError("pymer4 is not installed.  Cannot fit models.")

    try:
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            model = Lmer(formula, data=df, family="binomial")
            model.fit(
                control=_glmer_control_str(optimizer, max_iterations),
                verbose=False,
            )
        return model
    except Exception as exc:
        logger.debug("Binary model failed (%s): %s", formula.split("~")[0].strip(), exc)
        return None


# --------------------------------------------------------------------------- #
# Result extraction
# --------------------------------------------------------------------------- #

def _get_pval_column(coefs: pd.DataFrame, is_binary: bool) -> str:
    """Determine the p-value column name in pymer4's coefs DataFrame.

    pymer4 column names differ slightly across versions and model types.
    We search for known variants.
    """
    candidates = ["P-val", "Pr(>|t|)", "Pr(>|z|)", "p-value", "Pval"]
    for c in candidates:
        if c in coefs.columns:
            return c
    # Fallback: take the last numeric column (usually p-value)
    numeric_cols = coefs.select_dtypes(include=[np.number]).columns.tolist()
    if numeric_cols:
        return numeric_cols[-1]
    raise ValueError(
        f"Cannot identify p-value column in pymer4 coefs. Columns: {list(coefs.columns)}"
    )


def extract_cluster_results(
    model: Any,
    cluster_dummy_cols: list[str],
    phenotype: str,
    is_binary: bool,
) -> list[ModelResult]:
    """Extract beta, SE, and p-value for each cluster dummy from a fitted pymer4 model.

    In pymer4, model.coefs is a DataFrame indexed by predictor names.
    Continuous (Lmer):  columns include "Estimate", "SE", "T-stat", "P-val"
    Binary (Lmer):      columns include "Estimate", "SE", "Z-stat", "P-val"

    Mirrors R (where row 2 is the first non-intercept predictor):
        summary(a)$coefficients[2, 1]  → Beta
        summary(a)$coefficients[2, 2]  → SE
        summary(a)$coefficients[2, 5]  → p-value (lmer: 5 columns; glmer: 4 columns)

    Parameters
    ----------
    model : fitted pymer4 Lmer object
    cluster_dummy_cols : list[str]
    phenotype : str
    is_binary : bool

    Returns
    -------
    list of ModelResult dicts — one per cluster contrast.
    """
    results: list[ModelResult] = []
    coefs: pd.DataFrame = model.coefs

    pval_col = _get_pval_column(coefs, is_binary)

    for dummy_col in cluster_dummy_cols:
        if dummy_col not in coefs.index:
            results.append(_failed_result(phenotype, dummy_col, "coefficient_not_found"))
            continue

        row = coefs.loc[dummy_col]
        try:
            beta = float(row["Estimate"])
            se = float(row.get("SE", row.get("Std. Error", np.nan)))
            pval = float(row[pval_col])
        except (KeyError, TypeError, ValueError) as exc:
            logger.debug(
                "Extraction error for %s / %s: %s", phenotype, dummy_col, exc
            )
            results.append(_failed_result(phenotype, dummy_col, str(exc)))
            continue

        results.append({
            "phenotype": phenotype,
            "cluster_contrast": dummy_col,
            "beta": beta,
            "se": se,
            "pval": pval,
            "converged": True,
            "warning": None,
        })

    return results


def _failed_result(
    phenotype: str,
    cluster_contrast: str,
    reason: str,
) -> ModelResult:
    return {
        "phenotype": phenotype,
        "cluster_contrast": cluster_contrast,
        "beta": np.nan,
        "se": np.nan,
        "pval": np.nan,
        "converged": False,
        "warning": reason,
    }


# --------------------------------------------------------------------------- #
# Top-level per-phenotype function (unit of parallel dispatch)
# --------------------------------------------------------------------------- #

def run_single_phenotype(
    df: pd.DataFrame,
    phenotype: str,
    is_binary: bool,
    cluster_dummy_cols: list[str],
    covariates: list[str],
    site_id_col: str = "site_id",
    family_id_col: Optional[str] = "rel_family_id",
    include_family_re: bool = True,
    optimizer: str = "bobyqa",
    max_iterations: int = 100_000,
) -> list[ModelResult]:
    """Fit one GLMM and return k-1 result rows (one per cluster contrast).

    This is the unit of work dispatched to parallel workers.

    Parameters
    ----------
    df : pd.DataFrame
        Fully preprocessed data including cluster dummy columns and covariates.
    phenotype : str
        Name of the outcome column.
    is_binary : bool
        True → binomial GLMM; False → linear LMM.
    cluster_dummy_cols : list[str]
    covariates : list[str]
    site_id_col : str
    family_id_col : Optional[str]
    include_family_re : bool
    optimizer : str
    max_iterations : int

    Returns
    -------
    list of ModelResult dicts.  On failure returns NaN rows with converged=False.
    """
    # Drop rows where the outcome is missing
    analysis_df = df.dropna(subset=[phenotype]).copy()

    # Skip phenotypes with no variance or too few non-missing values
    if len(analysis_df) < 20:
        return [
            _failed_result(phenotype, dc, "insufficient_observations")
            for dc in cluster_dummy_cols
        ]

    if is_binary:
        n_pos = (analysis_df[phenotype].astype(str) == "1").sum()
        if n_pos < 5 or (len(analysis_df) - n_pos) < 5:
            return [
                _failed_result(phenotype, dc, "insufficient_binary_variation")
                for dc in cluster_dummy_cols
            ]

    formula = build_formula(
        phenotype,
        cluster_dummy_cols,
        covariates,
        site_id_col=site_id_col,
        family_id_col=family_id_col,
        include_family_re=include_family_re,
    )

    if is_binary:
        model = fit_binary_model(analysis_df, formula, optimizer, max_iterations)
    else:
        model = fit_continuous_model(analysis_df, formula, optimizer, max_iterations)

    if model is None:
        return [_failed_result(phenotype, dc, "fit_failed") for dc in cluster_dummy_cols]

    return extract_cluster_results(model, cluster_dummy_cols, phenotype, is_binary)
