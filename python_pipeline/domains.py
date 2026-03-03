"""Domain assignment for ABCD phenotype variables.

Two-layer lookup:
1. **Metadata-first**: check ``phenotype_metadata.csv`` (generated from the Paul
   2024 published supplements) for an authoritative domain label.  Year-specific
   suffixes (``_3y``, ``_4y``, ``_l``, etc.) are stripped before lookup so that
   variables from 3-year and 4-year follow-ups map to the same domain as their
   baseline counterparts.
2. **Regex fallback**: if the variable is not in the metadata (e.g. imaging
   variables, novel instruments), apply the grepl-style patterns from
   ``configs/domains.yaml`` — ported from PheWAS Analyses Resub5.Rmd
   (~lines 2908-3050).

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
_DEFAULT_METADATA = os.path.join(
    os.path.dirname(__file__), "configs", "phenotype_metadata.csv"
)

# Regex that matches common ABCD year-wave suffixes to strip before metadata lookup.
# Examples: stq_y_ss_weekday_3y, nihtbx_flanker_4y, cbcl_scr_syn_total_l
_YEAR_SUFFIX_RE = re.compile(
    r"(_[23456]y|_y[23456]|_3yr|_4yr|_5yr|_yr[23456]|_l)$",
    re.IGNORECASE,
)


def _strip_year_suffix(varname: str) -> str:
    """Remove a trailing ABCD year/wave suffix, if present."""
    return _YEAR_SUFFIX_RE.sub("", varname)


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


def load_phenotype_metadata(filepath: Optional[str] = None) -> dict[str, dict]:
    """Load variable → ``{domain, description}`` lookup from phenotype_metadata.csv.

    Returns an empty dict if *filepath* is ``None`` and the default bundled
    file does not exist — allowing graceful fallback to regex-only assignment.

    Parameters
    ----------
    filepath : Optional[str]
        Path to ``phenotype_metadata.csv``.  Defaults to the bundled file at
        ``python_pipeline/configs/phenotype_metadata.csv``.

    Returns
    -------
    dict[str, dict]
        Mapping ``{study_variable: {"domain": str, "description": str}}``.
    """
    path = filepath or _DEFAULT_METADATA
    if not os.path.exists(path):
        logger.debug("phenotype_metadata not found at %s — using regex-only domains", path)
        return {}
    df = pd.read_csv(path, dtype=str)
    lookup: dict[str, dict] = {}
    for _, row in df.iterrows():
        var = str(row.get("study_variable", "")).strip()
        if not var:
            continue
        lookup[var] = {
            "domain": str(row.get("domain", "Unclassified")).strip(),
            "description": str(row.get("description", "")).strip(),
        }
    logger.info("Loaded phenotype metadata for %d variables from %s", len(lookup), path)
    return lookup


# --------------------------------------------------------------------------- #
# Domain assignment
# --------------------------------------------------------------------------- #

def assign_domain(
    variable_name: str,
    domain_specs: list[DomainSpec],
    metadata: Optional[dict] = None,
) -> str:
    """Assign a variable name to the first matching domain.

    Lookup order:
    1. Exact match in *metadata* (authoritative, from published supplement).
    2. Year-suffix-stripped match in *metadata* (handles 3yr/4yr variants).
    3. Regex patterns from *domain_specs* (fallback for imaging/novel vars).

    Parameters
    ----------
    variable_name : str
    domain_specs : list[DomainSpec]
        Ordered list loaded by :func:`load_domain_config`.
    metadata : Optional[dict]
        Lookup returned by :func:`load_phenotype_metadata`.  If ``None``,
        only regex patterns are used.

    Returns
    -------
    str
        Domain name, or ``"Unclassified"`` if no domain matches.
    """
    # 1. Exact metadata lookup
    if metadata:
        if variable_name in metadata:
            return metadata[variable_name]["domain"]
        # 2. Year-suffix-stripped lookup
        stripped = _strip_year_suffix(variable_name)
        if stripped != variable_name and stripped in metadata:
            return metadata[stripped]["domain"]

    # 3. Regex fallback
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
    metadata_file: Optional[str] = None,
) -> pd.DataFrame:
    """Add ``domain``, ``domain_color``, and ``phenotype_description`` columns.

    Parameters
    ----------
    results_df : pd.DataFrame
    domain_specs : list[DomainSpec]
    variable_col : str
        Column containing phenotype / variable names.
    metadata_file : Optional[str]
        Path to ``phenotype_metadata.csv``.  ``None`` uses the bundled default.

    Returns
    -------
    pd.DataFrame with added columns ``domain``, ``domain_color``, and
    ``phenotype_description``.
    """
    color_map = {spec["name"]: spec["color"] for spec in domain_specs}
    color_map["Unclassified"] = "#808080"

    metadata = load_phenotype_metadata(metadata_file)

    results_df = results_df.copy()
    results_df["domain"] = results_df[variable_col].apply(
        lambda v: assign_domain(str(v), domain_specs, metadata=metadata)
    )
    results_df["domain_color"] = results_df["domain"].map(color_map)
    results_df["phenotype_description"] = results_df[variable_col].apply(
        lambda v: metadata.get(str(v), {}).get("description", "")
        or metadata.get(_strip_year_suffix(str(v)), {}).get("description", "")
    )

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
