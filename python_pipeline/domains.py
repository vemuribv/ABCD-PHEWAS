"""Domain assignment for ABCD phenotype variables.

Regex-based categorisation into 8 phenotype domains, ported directly from
the R code's grepl() approach in PheWAS Analyses Resub5.Rmd (~lines 2908-3050).

Domain patterns are loaded from configs/domains.yaml.  Each variable is
assigned to the first domain whose include_patterns match (any) and whose
exclude_patterns do not match (any).
"""

from __future__ import annotations

import logging
import os
import re
from typing import Optional

import pandas as pd
import yaml

logger = logging.getLogger(__name__)

# Type alias
DomainSpec = dict  # {name, color, include_patterns, exclude_patterns}

_DEFAULT_DOMAIN_CONFIG = os.path.join(
    os.path.dirname(__file__), "configs", "domains.yaml"
)


# --------------------------------------------------------------------------- #
# Config loading
# --------------------------------------------------------------------------- #

def load_domain_config(filepath: Optional[str] = None) -> list[DomainSpec]:
    """Load domain definitions from a YAML file.

    Parameters
    ----------
    filepath : Optional[str]
        Path to the domains YAML file.  Defaults to
        ``python_pipeline/configs/domains.yaml``.

    Returns
    -------
    list[DomainSpec]
        Ordered list of domain specification dicts.
    """
    path = filepath or _DEFAULT_DOMAIN_CONFIG
    with open(path) as fh:
        cfg = yaml.safe_load(fh)
    specs: list[DomainSpec] = cfg.get("domain_order", [])
    if not specs:
        raise ValueError(f"No domain_order found in {path}")
    logger.info("Loaded %d domain definitions from %s", len(specs), path)
    return specs


# --------------------------------------------------------------------------- #
# Domain assignment
# --------------------------------------------------------------------------- #

def assign_domain(variable_name: str, domain_specs: list[DomainSpec]) -> str:
    """Assign a variable name to the first matching domain.

    Evaluation order mirrors R's sequential grepl approach.

    Parameters
    ----------
    variable_name : str
    domain_specs : list[DomainSpec]
        Ordered list loaded by load_domain_config().

    Returns
    -------
    str
        Domain name, or ``"Unclassified"`` if no domain matches.
    """
    for spec in domain_specs:
        inc_match = any(
            re.search(pat, variable_name)
            for pat in spec.get("include_patterns", [])
        )
        exc_match = any(
            re.search(pat, variable_name)
            for pat in spec.get("exclude_patterns", [])
        )
        if inc_match and not exc_match:
            return spec["name"]
    return "Unclassified"


def assign_domains_to_results(
    results_df: pd.DataFrame,
    domain_specs: list[DomainSpec],
    variable_col: str = "phenotype",
) -> pd.DataFrame:
    """Add ``domain`` and ``domain_color`` columns to a results DataFrame.

    Parameters
    ----------
    results_df : pd.DataFrame
    domain_specs : list[DomainSpec]
    variable_col : str
        Column containing phenotype / variable names.

    Returns
    -------
    pd.DataFrame with added columns ``domain`` and ``domain_color``.
    """
    color_map = {spec["name"]: spec["color"] for spec in domain_specs}
    color_map["Unclassified"] = "#808080"

    results_df = results_df.copy()
    results_df["domain"] = results_df[variable_col].apply(
        lambda v: assign_domain(str(v), domain_specs)
    )
    results_df["domain_color"] = results_df["domain"].map(color_map)

    # Log domain distribution
    counts = results_df["domain"].value_counts()
    logger.info("Domain assignment summary:\n%s", counts.to_string())

    return results_df


def get_domain_order(domain_specs: list[DomainSpec]) -> list[str]:
    """Return domain names in display order (as defined in YAML)."""
    return [spec["name"] for spec in domain_specs]


def get_color_map(domain_specs: list[DomainSpec]) -> dict[str, str]:
    """Return a mapping of domain name → hex color."""
    cmap = {spec["name"]: spec["color"] for spec in domain_specs}
    cmap["Unclassified"] = "#808080"
    return cmap
