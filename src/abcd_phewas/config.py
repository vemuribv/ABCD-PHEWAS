"""PipelineConfig: Central configuration dataclass for the abcd_phewas pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PipelineConfig:
    """Configuration for the ABCD PheWAS pipeline.

    Attributes
    ----------
    cluster_path:
        Path to the CSV file containing cluster assignments.
        Must contain subject_col and cluster_col columns.
    phenotype_path:
        Path to the wide-format phenotype CSV file.
        One row per subject; subject_col + thousands of phenotype columns.
    subject_col:
        Column name for the subject identifier. Configurable because cluster
        assignment files may use different column names than the phenotype file.
    cluster_col:
        Column name for the cluster label in the cluster assignment file.
    blocklist_path:
        Optional path to a plain-text CRLI blocklist file (one variable per line).
        Matching columns are dropped immediately after merging.
    override_path:
        Optional path to a CSV file with columns (variable_name, forced_type).
        Overrides auto-detected variable types.
    domain_config_path:
        Path to the YAML config file containing domain regex patterns and colors.
    sentinels:
        List of numeric values treated as missing data. Replaced with NaN before
        any downstream processing.
    min_n_per_group:
        Minimum number of non-missing observations required per cluster group.
        Variables not meeting this threshold in any group are excluded from tests.
    skew_threshold:
        Absolute skewness threshold for triggering winsorization (two-pass pipeline).
    winsor_n_sd:
        Number of standard deviations for mean-based winsorization bounds.
    """

    cluster_path: str
    phenotype_path: str
    subject_col: str = "src_subject_id"
    cluster_col: str = "cluster"
    blocklist_path: str | None = None
    override_path: str | None = None
    domain_config_path: str = "config/domain_mapping.yaml"
    sentinels: list[int | float] = field(default_factory=lambda: [-999, 777, 999])
    min_n_per_group: int = 10
    skew_threshold: float = 1.96
    winsor_n_sd: float = 3.0
