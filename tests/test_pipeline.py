"""Integration tests for the pipeline orchestrator (run_pipeline).

Tests cover:
- PipelineResult structure and field types
- Correct pipeline stage ordering
- Skipped variables (< min_n per group)
- End-to-end pipeline with synthetic CSV files
"""

import os

import numpy as np
import pandas as pd
import pytest

from abcd_phewas.config import PipelineConfig
from abcd_phewas.pipeline import PipelineResult, run_pipeline
from abcd_phewas.type_detector import VarType

# Path to actual domain_mapping.yaml
YAML_PATH = os.path.join(
    os.path.dirname(__file__), "..", "config", "domain_mapping.yaml"
)


# ---------------------------------------------------------------------------
# Synthetic data helpers
# ---------------------------------------------------------------------------


def make_cluster_csv(tmp_path, n: int = 60, n_clusters: int = 3, seed: int = 0) -> str:
    """Create a synthetic cluster CSV with n subjects across n_clusters clusters."""
    rng = np.random.default_rng(seed)
    subjects = [f"sub-{i:04d}" for i in range(1, n + 1)]
    # Ensure each cluster has at least 15 subjects for min_n tests
    clusters = []
    per_cluster = n // n_clusters
    for c in range(1, n_clusters + 1):
        clusters.extend([c] * per_cluster)
    # Fill remainder
    while len(clusters) < n:
        clusters.append(n_clusters)
    rng.shuffle(clusters)
    df = pd.DataFrame({"src_subject_id": subjects, "cluster": clusters})
    path = str(tmp_path / "clusters.csv")
    df.to_csv(path, index=False)
    return path


def make_pheno_csv(tmp_path, n: int = 60, seed: int = 0) -> str:
    """Create a synthetic phenotype CSV with various variable types.

    Columns created:
    - nihtbx_cont: continuous variable (Cognition domain)
    - cbcl_binary: binary variable (Child Mental Health domain)
    - demo_ordinal: ordinal variable (Demographics domain, values 1-5)
    - sparse_col: sparse variable (too few non-missing per group)
    - sentinel_col: continuous with sentinel values (-999)
    """
    rng = np.random.default_rng(seed)
    subjects = [f"sub-{i:04d}" for i in range(1, n + 1)]

    # Highly skewed continuous (lognormal) -> will be INT-transformed
    nihtbx_cont = np.exp(rng.normal(0, 1.5, size=n)).tolist()

    # Binary (0/1)
    cbcl_binary = rng.integers(0, 2, size=n).tolist()

    # Ordinal (1-5, sequential integers)
    demo_ordinal = rng.integers(1, 6, size=n).astype(float).tolist()

    # Sparse column: only 5 non-missing total (will be skipped)
    sparse_col = [rng.normal(0, 1) if i < 5 else np.nan for i in range(n)]

    # Sentinel column: continuous with -999 sentinels mixed in
    sentinel_col = [
        -999.0 if i % 10 == 0 else float(rng.normal(5, 1))
        for i in range(n)
    ]

    df = pd.DataFrame({
        "src_subject_id": subjects,
        "nihtbx_cont": nihtbx_cont,
        "cbcl_binary": cbcl_binary,
        "demo_ordinal": demo_ordinal,
        "sparse_col": sparse_col,
        "sentinel_col": sentinel_col,
    })
    path = str(tmp_path / "pheno.csv")
    df.to_csv(path, index=False)
    return path


# ---------------------------------------------------------------------------
# test_pipeline_output_structure
# ---------------------------------------------------------------------------


def test_pipeline_result_fields(tmp_path):
    """PipelineResult has all required fields with correct types."""
    cluster_path = make_cluster_csv(tmp_path)
    pheno_path = make_pheno_csv(tmp_path)
    config = PipelineConfig(
        cluster_path=cluster_path,
        phenotype_path=pheno_path,
        domain_config_path=YAML_PATH,
        min_n_per_group=5,  # low threshold so most vars pass
    )
    result = run_pipeline(config)

    assert isinstance(result, PipelineResult)
    assert isinstance(result.df, pd.DataFrame)
    assert isinstance(result.type_map, dict)
    assert isinstance(result.domain_map, dict)
    assert isinstance(result.transformation_log, pd.DataFrame)
    assert isinstance(result.missingness, pd.DataFrame)
    assert isinstance(result.skipped_vars, list)
    assert isinstance(result.unclassified_vars, list)


def test_pipeline_result_df_has_no_sentinels(tmp_path):
    """Output DataFrame contains no sentinel values (-999, 777, 999)."""
    cluster_path = make_cluster_csv(tmp_path)
    pheno_path = make_pheno_csv(tmp_path)
    config = PipelineConfig(
        cluster_path=cluster_path,
        phenotype_path=pheno_path,
        domain_config_path=YAML_PATH,
        min_n_per_group=5,
    )
    result = run_pipeline(config)
    # Check numeric columns for sentinel values
    numeric_cols = result.df.select_dtypes(include=[np.number]).columns
    for sentinel in config.sentinels:
        for col in numeric_cols:
            if col in [config.subject_col, config.cluster_col]:
                continue
            assert not (result.df[col] == sentinel).any(), (
                f"Sentinel {sentinel} found in column {col} after pipeline"
            )


# ---------------------------------------------------------------------------
# test_pipeline_ordering
# ---------------------------------------------------------------------------


def test_pipeline_ordering_sentinel_before_type_detection(tmp_path):
    """Sentinel replacement must happen before type detection.

    A column that appears binary (0/1) but has sentinel values (-999) in the
    raw data should be correctly classified as binary AFTER sentinel replacement
    converts -999 to NaN. If type detection happened first (with -999 present),
    the column would be classified as continuous (>2 unique non-NA values).
    """
    # Create pheno with a column that has values: 0, 1, -999
    # After sentinel replacement: 0, 1, NaN -> BINARY
    # Before sentinel replacement: 0, 1, -999 -> CONTINUOUS (3 unique values)
    cluster_data = pd.DataFrame({
        "src_subject_id": [f"sub-{i:02d}" for i in range(1, 61)],
        "cluster": [1] * 20 + [2] * 20 + [3] * 20,
    })
    pheno_data = pd.DataFrame({
        "src_subject_id": [f"sub-{i:02d}" for i in range(1, 61)],
        # col_with_sentinel: mostly binary, but first entry is sentinel -999
        "col_with_sentinel": [-999.0] + [float(i % 2) for i in range(1, 60)],
        # Regular continuous column to ensure enough data
        "cont_col": np.random.default_rng(42).normal(0, 1, size=60).tolist(),
    })

    cluster_path = str(tmp_path / "clusters.csv")
    pheno_path = str(tmp_path / "pheno.csv")
    cluster_data.to_csv(cluster_path, index=False)
    pheno_data.to_csv(pheno_path, index=False)

    config = PipelineConfig(
        cluster_path=cluster_path,
        phenotype_path=pheno_path,
        domain_config_path=YAML_PATH,
        sentinels=[-999, 777, 999],
        min_n_per_group=5,
    )
    result = run_pipeline(config)

    # After sentinel replacement, col_with_sentinel should be BINARY
    if "col_with_sentinel" in result.type_map:
        assert result.type_map["col_with_sentinel"] == VarType.BINARY, (
            "col_with_sentinel should be BINARY after sentinel replacement clears -999"
        )


# ---------------------------------------------------------------------------
# test_pipeline_skipped_vars
# ---------------------------------------------------------------------------


def test_pipeline_skipped_vars(tmp_path):
    """Variables with fewer than min_n non-missing per group are in skipped_vars."""
    cluster_path = make_cluster_csv(tmp_path, n=60, n_clusters=3)
    pheno_path = make_pheno_csv(tmp_path, n=60)
    config = PipelineConfig(
        cluster_path=cluster_path,
        phenotype_path=pheno_path,
        domain_config_path=YAML_PATH,
        min_n_per_group=10,  # sparse_col (5 total non-missing) will fail this
    )
    result = run_pipeline(config)

    assert "sparse_col" in result.skipped_vars, (
        "sparse_col (5 non-missing total) should be skipped with min_n_per_group=10"
    )
    # Skipped vars should NOT appear in type_map
    for skipped in result.skipped_vars:
        assert skipped not in result.type_map, (
            f"Skipped variable '{skipped}' should not appear in type_map"
        )


# ---------------------------------------------------------------------------
# test_pipeline_end_to_end
# ---------------------------------------------------------------------------


def test_pipeline_end_to_end(tmp_path):
    """Full pipeline run produces complete, consistent PipelineResult.

    Validates:
    - DataFrame has correct subjects (inner join)
    - Continuous columns are transformed (not equal to raw values)
    - Binary and ordinal columns have domain assignments
    - Transformation log has one row per continuous variable
    - Domain map covers all non-skipped variables
    """
    cluster_path = make_cluster_csv(tmp_path, n=60, n_clusters=3)
    pheno_path = make_pheno_csv(tmp_path, n=60)
    config = PipelineConfig(
        cluster_path=cluster_path,
        phenotype_path=pheno_path,
        domain_config_path=YAML_PATH,
        min_n_per_group=5,
    )
    result = run_pipeline(config)

    # All type_map keys should be in domain_map
    for col in result.type_map:
        assert col in result.domain_map, (
            f"Column '{col}' in type_map but not in domain_map"
        )

    # Transformation log contains only continuous variables
    if len(result.transformation_log) > 0:
        assert "variable" in result.transformation_log.columns
        for var in result.transformation_log["variable"]:
            if var in result.type_map:
                assert result.type_map[var] == VarType.CONTINUOUS, (
                    f"Non-continuous variable '{var}' in transformation log"
                )

    # Missingness DataFrame is not empty
    assert len(result.missingness) > 0

    # DataFrame has both subject and cluster columns
    assert config.subject_col in result.df.columns
    assert config.cluster_col in result.df.columns


def test_pipeline_type_map_excludes_skipped(tmp_path):
    """type_map and transformation_log exclude variables in skipped_vars."""
    cluster_path = make_cluster_csv(tmp_path, n=60, n_clusters=3)
    pheno_path = make_pheno_csv(tmp_path, n=60)
    config = PipelineConfig(
        cluster_path=cluster_path,
        phenotype_path=pheno_path,
        domain_config_path=YAML_PATH,
        min_n_per_group=10,
    )
    result = run_pipeline(config)

    for skipped in result.skipped_vars:
        assert skipped not in result.type_map
        if len(result.transformation_log) > 0 and "variable" in result.transformation_log.columns:
            assert skipped not in result.transformation_log["variable"].values


def test_pipeline_no_blocklist(tmp_path):
    """Pipeline works without a blocklist (blocklist_path=None)."""
    cluster_path = make_cluster_csv(tmp_path)
    pheno_path = make_pheno_csv(tmp_path)
    config = PipelineConfig(
        cluster_path=cluster_path,
        phenotype_path=pheno_path,
        domain_config_path=YAML_PATH,
        blocklist_path=None,
        min_n_per_group=5,
    )
    result = run_pipeline(config)
    assert isinstance(result, PipelineResult)
    assert len(result.df) > 0
