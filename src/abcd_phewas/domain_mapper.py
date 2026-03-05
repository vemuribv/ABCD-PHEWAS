"""Regex-based domain assignment for ABCD phenotype variables (DOMN-01, DOMN-02).

Loads domain regex patterns and colors from a YAML config file and assigns
each phenotype variable to exactly one domain. Ordering in the YAML is
significant: first match wins (see config/domain_mapping.yaml header comment).

R reference: PheWAS Analyses Resub5.Rmd — domain grouping is based on the
ABCD data dictionary categories with hand-tuned regex patterns.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG = Path(__file__).parent / "data" / "domain_mapping.yaml"


def load_domain_config(yaml_path: str | None = None) -> list[dict]:
    """Load domain mapping config from a YAML file.

    Parameters
    ----------
    yaml_path:
        Path to the YAML config file. If *None*, uses the bundled
        default at ``abcd_phewas/data/domain_mapping.yaml``.

    Returns
    -------
    list[dict]
        List of domain dicts, each with keys: 'domain', 'color', 'patterns'.
        Preserves YAML order (important: first match wins during assignment).
    """
    path = Path(yaml_path) if yaml_path is not None else _DEFAULT_CONFIG
    with open(path, "r") as f:
        config = yaml.safe_load(f)
    return config["domains"]


def assign_domain(col_name: str, domain_config: list[dict]) -> tuple[str, str]:
    """Assign a single variable to a domain using regex matching.

    Iterates domain_config in order. For each domain, tries all patterns
    using case-insensitive regex search. The first pattern that matches
    determines the domain. If no pattern matches, returns Other/Unclassified.

    Parameters
    ----------
    col_name:
        Variable name to classify.
    domain_config:
        List of domain dicts from load_domain_config().

    Returns
    -------
    tuple[str, str]
        (domain_name, hex_color)

    Notes
    -----
    Pattern matching is case-insensitive (re.IGNORECASE).
    First match wins — domain order in YAML config is meaningful.
    """
    for domain_entry in domain_config:
        domain_name = domain_entry["domain"]
        color = domain_entry["color"]
        patterns = domain_entry["patterns"]

        # Skip the catch-all (empty patterns list)
        if not patterns:
            continue

        for pattern in patterns:
            if re.search(pattern, col_name, re.IGNORECASE):
                logger.debug(
                    "Column '%s' -> domain '%s' (matched pattern '%s')",
                    col_name,
                    domain_name,
                    pattern,
                )
                return (domain_name, color)

    # No pattern matched: fallback to Other/Unclassified
    logger.debug("Column '%s' -> Other/Unclassified (no pattern matched)", col_name)
    return ("Other/Unclassified", "#AAAAAA")


def assign_all_domains(
    pheno_cols: list[str],
    domain_config: list[dict],
) -> tuple[dict[str, tuple[str, str]], list[str]]:
    """Assign all phenotype columns to domains.

    Parameters
    ----------
    pheno_cols:
        List of phenotype column names to classify.
    domain_config:
        List of domain dicts from load_domain_config().

    Returns
    -------
    tuple[dict[str, tuple[str, str]], list[str]]
        - domain_map: {col_name: (domain_name, hex_color)} for every input column
        - unclassified_vars: list of column names assigned to Other/Unclassified

    Notes
    -----
    Both classified and unclassified variables appear in domain_map.
    unclassified_vars is a convenience list for manual review.
    """
    domain_map: dict[str, tuple[str, str]] = {}
    unclassified_vars: list[str] = []

    for col in pheno_cols:
        domain_name, color = assign_domain(col, domain_config)
        domain_map[col] = (domain_name, color)
        if domain_name == "Other/Unclassified":
            unclassified_vars.append(col)

    classified = len(pheno_cols) - len(unclassified_vars)
    logger.info(
        "Domain assignment complete: %d classified, %d unclassified (%.1f%% coverage)",
        classified,
        len(unclassified_vars),
        100.0 * classified / len(pheno_cols) if pheno_cols else 0.0,
    )

    return domain_map, unclassified_vars
