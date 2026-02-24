"""Configuration dataclass for the ABCD Cluster-Based PheWAS Pipeline."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

import yaml


@dataclass
class PheWASConfig:
    """
    All runtime parameters for one PheWAS analysis pass.

    Fields can be set via a YAML file (from_yaml) and then overridden by
    CLI flags.  Column ranges use 0-based integer indices, matching pandas
    iloc semantics and the positional ranges used in the R code.
    """

    # ------------------------------------------------------------------ #
    # Required — no sensible default
    # ------------------------------------------------------------------ #
    phenotype_file: str = ""
    cluster_file: str = ""
    output_dir: str = ""

    # ------------------------------------------------------------------ #
    # Column identity
    # ------------------------------------------------------------------ #
    subject_id_col: str = "subjectkey"
    sex_col: str = "sex"
    site_id_col: str = "site_id"
    family_id_col: str = "rel_family_id"
    cluster_col: str = "cluster"

    # ------------------------------------------------------------------ #
    # Column-range layout (0-indexed, inclusive on both ends)
    # Mirrors R's lapply(df[, c(1:4, 20, 671:1291)], as.factor) etc.
    # Baseline defaults match FINAL_PHEWAS_baseline_n5556_5.11.23.xlsx
    # ------------------------------------------------------------------ #
    continuous_col_range: list[int] = field(default_factory=lambda: [20, 656])
    binary_col_range: list[int] = field(default_factory=lambda: [670, 1291])

    # ------------------------------------------------------------------ #
    # Preprocessing thresholds
    # ------------------------------------------------------------------ #
    skew_threshold: float = 1.96
    winsorize_sd: float = 3.0

    # ------------------------------------------------------------------ #
    # GLMM settings
    # ------------------------------------------------------------------ #
    optimizer: str = "bobyqa"
    max_iterations: int = 100_000

    # ------------------------------------------------------------------ #
    # Cluster / analysis settings
    # ------------------------------------------------------------------ #
    reference_cluster: Optional[str] = None  # None → first label alphabetically
    sex_stratum: str = "all"                 # "all" | "male" | "female"
    sex_col_male_value: str = "1"
    sex_col_female_value: str = "2"

    # Covariates passed as fixed effects (excluding cluster dummies, which are
    # added automatically).  The default mirrors the R code's 10 PCs + sex + age.
    covariates: list[str] = field(default_factory=lambda: [
        "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9", "C10",
        "sex", "interview_age",
    ])

    # ------------------------------------------------------------------ #
    # Parallelism
    # ------------------------------------------------------------------ #
    n_workers: int = 4

    # ------------------------------------------------------------------ #
    # Domain config (path relative to CWD or absolute)
    # ------------------------------------------------------------------ #
    domain_config_file: str = os.path.join(
        os.path.dirname(__file__), "configs", "domains.yaml"
    )

    # ------------------------------------------------------------------ #
    # Class methods
    # ------------------------------------------------------------------ #

    @classmethod
    def from_yaml(cls, path: str) -> "PheWASConfig":
        """Load a PheWASConfig from a YAML file.

        Unknown keys in the YAML are silently ignored so that a config file
        can contain comments or extra metadata without breaking loading.
        """
        with open(path) as fh:
            data = yaml.safe_load(fh) or {}

        known_fields = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)

    def validate(self) -> None:
        """Raise ValueError for obviously bad configurations."""
        if not self.phenotype_file:
            raise ValueError("phenotype_file must be set.")
        if not self.cluster_file:
            raise ValueError("cluster_file must be set.")
        if not self.output_dir:
            raise ValueError("output_dir must be set.")
        if self.sex_stratum not in ("all", "male", "female"):
            raise ValueError(
                f"sex_stratum must be 'all', 'male', or 'female'. Got: {self.sex_stratum}"
            )
        if len(self.continuous_col_range) != 2:
            raise ValueError("continuous_col_range must be a 2-element [start, end] list.")
        if len(self.binary_col_range) != 2:
            raise ValueError("binary_col_range must be a 2-element [start, end] list.")
