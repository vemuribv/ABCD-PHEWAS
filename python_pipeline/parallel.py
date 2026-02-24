"""Parallel dispatch for PheWAS model fitting.

Uses ProcessPoolExecutor rather than threads because pymer4 calls R via
rpy2, and R's C internals are not thread-safe.  Each worker process has
its own R session.

Checkpoint file support:
  - On start, already-completed phenotypes are read from the checkpoint
    file and skipped.
  - After each phenotype completes, its name is appended to the file.
  - This allows interrupted runs to resume from where they left off.
"""

from __future__ import annotations

import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Optional

import pandas as pd

from .models import ModelResult

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Checkpoint helpers
# --------------------------------------------------------------------------- #

def _load_checkpoint(filepath: Optional[str]) -> set[str]:
    """Return the set of phenotype names already completed."""
    if filepath is None:
        return set()
    p = Path(filepath)
    if not p.exists():
        return set()
    try:
        done = set(
            line.strip()
            for line in p.read_text().splitlines()
            if line.strip()
        )
        if done:
            logger.info("Checkpoint: %d phenotypes already completed.", len(done))
        return done
    except Exception as exc:
        logger.warning("Could not read checkpoint file %s: %s", filepath, exc)
        return set()


def _append_checkpoint(filepath: Optional[str], phenotype: str) -> None:
    """Append a completed phenotype name to the checkpoint file."""
    if filepath is None:
        return
    try:
        with open(filepath, "a") as fh:
            fh.write(phenotype + "\n")
    except Exception as exc:
        logger.warning("Could not write checkpoint for %s: %s", phenotype, exc)


# --------------------------------------------------------------------------- #
# Worker wrapper
# --------------------------------------------------------------------------- #

def _worker(
    run_single_fn: Callable,
    df: pd.DataFrame,
    phenotype: str,
    is_binary: bool,
    kwargs: dict,
) -> list[ModelResult]:
    """Top-level function executed in a subprocess.

    Must be a top-level (importable) function for pickling.
    """
    return run_single_fn(
        df=df,
        phenotype=phenotype,
        is_binary=is_binary,
        **kwargs,
    )


# --------------------------------------------------------------------------- #
# Main parallel dispatcher
# --------------------------------------------------------------------------- #

def run_phewas_parallel(
    df: pd.DataFrame,
    phenotype_cols: list[str],
    binary_cols: set[str],
    run_single_fn: Callable,
    run_single_kwargs: dict[str, Any],
    n_workers: int = 4,
    checkpoint_file: Optional[str] = None,
) -> list[ModelResult]:
    """Distribute GLMM fitting across worker processes.

    Parameters
    ----------
    df : pd.DataFrame
        Fully preprocessed data with cluster dummies, covariates, and outcomes.
    phenotype_cols : list[str]
        All phenotype column names to test (~1200 for ABCD).
    binary_cols : set[str]
        Subset of phenotype_cols that require logistic GLMM (glmer / Lmer2).
    run_single_fn : Callable
        models.run_single_phenotype — serializable top-level function.
    run_single_kwargs : dict
        Keyword args for run_single_fn except ``phenotype`` and ``is_binary``.
    n_workers : int
        Number of parallel worker processes.
    checkpoint_file : Optional[str]
        Path to a plain-text checkpoint file for resumable runs.

    Returns
    -------
    list[ModelResult]
        Flat list of result dicts (k-1 rows per phenotype).
    """
    completed = _load_checkpoint(checkpoint_file)
    remaining = [p for p in phenotype_cols if p not in completed]

    total = len(phenotype_cols)
    skipped = total - len(remaining)
    logger.info(
        "PheWAS dispatch: %d total phenotypes, %d completed (checkpoint), "
        "%d to run on %d workers.",
        total, len(completed), len(remaining), n_workers,
    )

    if not remaining:
        logger.info("All phenotypes already completed — nothing to run.")
        return []

    all_results: list[ModelResult] = []
    done_count = 0

    if n_workers <= 1:
        # Sequential fallback — useful for debugging or when R is not fork-safe
        for pheno in remaining:
            try:
                results = run_single_fn(
                    df=df,
                    phenotype=pheno,
                    is_binary=(pheno in binary_cols),
                    **run_single_kwargs,
                )
                all_results.extend(results)
                _append_checkpoint(checkpoint_file, pheno)
            except Exception as exc:
                logger.error("Phenotype %s failed: %s", pheno, exc)
            done_count += 1
            if done_count % 100 == 0:
                logger.info("Progress: %d / %d phenotypes done.", done_count, len(remaining))
    else:
        with ProcessPoolExecutor(max_workers=n_workers) as executor:
            futures = {
                executor.submit(
                    _worker,
                    run_single_fn,
                    df,
                    pheno,
                    pheno in binary_cols,
                    run_single_kwargs,
                ): pheno
                for pheno in remaining
            }

            for future in as_completed(futures):
                pheno = futures[future]
                try:
                    results = future.result()
                    all_results.extend(results)
                    _append_checkpoint(checkpoint_file, pheno)
                except Exception as exc:
                    logger.error("Phenotype %s raised an exception: %s", pheno, exc)

                done_count += 1
                if done_count % 100 == 0:
                    logger.info(
                        "Progress: %d / %d phenotypes done.", done_count, len(remaining)
                    )

    logger.info(
        "Parallel fitting complete: %d result rows from %d phenotypes.",
        len(all_results), len(remaining),
    )
    return all_results
