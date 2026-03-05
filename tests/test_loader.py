"""Tests for abcd_phewas.loader module.

Covers DATA-01 (loading/merging), DATA-03 (sentinel replacement, missingness),
and DATA-04 (min-n per group filter).
"""

import numpy as np
import pandas as pd
import pytest

from abcd_phewas.config import PipelineConfig
from abcd_phewas.loader import (
    apply_crli_blocklist,
    compute_missingness,
    get_pheno_cols,
    has_enough_data,
    load_and_merge,
    replace_sentinels,
)


# ---------------------------------------------------------------------------
# DATA-01: Load and merge
# ---------------------------------------------------------------------------


def test_inner_merge(tmp_csv_files):
    """Merging cluster df (sub-01..20) with pheno df (sub-05..19) keeps only sub-05..19."""
    cluster_path, pheno_path = tmp_csv_files
    config = PipelineConfig(cluster_path=cluster_path, phenotype_path=pheno_path)
    merged = load_and_merge(config)

    # Pheno df has sub-05 to sub-19 (15 subjects); cluster df has sub-01 to sub-20
    # Inner merge should keep exactly the 15 subjects present in both
    assert len(merged) == 15
    assert set(merged["src_subject_id"]) == {f"sub-{i:02d}" for i in range(5, 20)}


def test_configurable_cols(tmp_path, sample_cluster_df, sample_pheno_df):
    """Loading with non-default subject_col and cluster_col uses those column names."""
    # Rename columns to non-default names
    cluster_df = sample_cluster_df.rename(
        columns={"src_subject_id": "ID", "cluster": "group"}
    )
    pheno_df = sample_pheno_df.rename(columns={"src_subject_id": "ID"})

    cluster_path = str(tmp_path / "clusters_alt.csv")
    pheno_path = str(tmp_path / "pheno_alt.csv")
    cluster_df.to_csv(cluster_path, index=False)
    pheno_df.to_csv(pheno_path, index=False)

    config = PipelineConfig(
        cluster_path=cluster_path,
        phenotype_path=pheno_path,
        subject_col="ID",
        cluster_col="group",
    )
    merged = load_and_merge(config)
    assert "ID" in merged.columns
    assert "group" in merged.columns
    assert len(merged) == 15


# ---------------------------------------------------------------------------
# DATA-03: Sentinel replacement
# ---------------------------------------------------------------------------


def test_sentinel_replacement():
    """DataFrame with sentinels [-999, 777, 999] has them replaced with NaN."""
    df = pd.DataFrame({
        "src_subject_id": ["s1", "s2", "s3", "s4", "s5"],
        "cluster": [1, 1, 2, 2, 3],
        "col_a": [-999, 777, 999, 5.0, 10.0],
    })
    result = replace_sentinels(df, sentinels=[-999, 777, 999],
                               subject_col="src_subject_id",
                               cluster_col="cluster")
    # Only 5.0 and 10.0 should remain; sentinels become NaN
    assert result["col_a"].isna().sum() == 3
    assert set(result["col_a"].dropna().tolist()) == {5.0, 10.0}


def test_sentinel_not_touch_id_cols():
    """Sentinel replacement must NOT touch subject_col or cluster_col."""
    # Use 999 as a cluster label — should NOT be replaced
    df = pd.DataFrame({
        "src_subject_id": ["s1"],
        "cluster": [999],
        "col_a": [999.0],
    })
    result = replace_sentinels(df, sentinels=[-999, 777, 999],
                               subject_col="src_subject_id",
                               cluster_col="cluster")
    assert result["cluster"].iloc[0] == 999  # cluster untouched
    assert pd.isna(result["col_a"].iloc[0])   # phenotype sentinel replaced


def test_sentinel_before_type_detection():
    """A column with values (-999, 0, 1) after sentinel removal has 2 unique values."""
    df = pd.DataFrame({
        "src_subject_id": ["s1", "s2", "s3"],
        "cluster": [1, 1, 2],
        "col_a": [-999.0, 0.0, 1.0],
    })
    result = replace_sentinels(df, sentinels=[-999, 777, 999],
                               subject_col="src_subject_id",
                               cluster_col="cluster")
    unique_non_na = result["col_a"].dropna().nunique()
    assert unique_non_na == 2  # only 0.0 and 1.0 remain


# ---------------------------------------------------------------------------
# DATA-03: Missingness rate
# ---------------------------------------------------------------------------


def test_missingness_rate():
    """Missingness rate = count_of_NaN / total_rows per column."""
    df = pd.DataFrame({
        "src_subject_id": ["s1", "s2", "s3", "s4"],
        "cluster": [1, 1, 2, 2],
        "col_a": [1.0, np.nan, 3.0, np.nan],
        "col_b": [1.0, 2.0, 3.0, 4.0],
    })
    pheno_cols = ["col_a", "col_b"]
    result = compute_missingness(df, pheno_cols)

    # col_a: 2 missing out of 4 = 0.5
    assert result.loc[result["variable"] == "col_a", "missingness_rate"].iloc[0] == pytest.approx(0.5)
    # col_b: 0 missing out of 4 = 0.0
    assert result.loc[result["variable"] == "col_b", "missingness_rate"].iloc[0] == pytest.approx(0.0)
    # Check structure
    assert set(result.columns) >= {"variable", "missingness_rate", "n_missing", "n_total"}
    assert result.loc[result["variable"] == "col_a", "n_missing"].iloc[0] == 2
    assert result.loc[result["variable"] == "col_a", "n_total"].iloc[0] == 4


# ---------------------------------------------------------------------------
# DATA-01: CRLI blocklist
# ---------------------------------------------------------------------------


def test_crli_blocklist(tmp_blocklist, sample_pheno_df):
    """Columns listed in blocklist are dropped; unlisted columns remain."""
    # Attach a dummy cluster column for the function signature
    df = sample_pheno_df.copy()
    df["cluster"] = 1

    result = apply_crli_blocklist(df, tmp_blocklist)

    # sentinel_col and sparse_col should be dropped
    assert "sentinel_col" not in result.columns
    assert "sparse_col" not in result.columns
    # nonexistent_var was in blocklist but not in df — no error, just ignored
    # Other columns should remain
    assert "binary_col" in result.columns
    assert "cont_col_1" in result.columns


def test_crli_blocklist_none(sample_pheno_df):
    """Passing blocklist_path=None returns the DataFrame unchanged."""
    df = sample_pheno_df.copy()
    result = apply_crli_blocklist(df, blocklist_path=None)
    pd.testing.assert_frame_equal(result, df)


# ---------------------------------------------------------------------------
# DATA-04: Min-n per group filter
# ---------------------------------------------------------------------------


def test_min_n_filter_fail():
    """Variable with 8 non-missing values in one group returns has_enough_data=False."""
    # Group 1 has 8 non-missing; group 2 has 15
    series = pd.Series([1.0] * 8 + [np.nan] * 2 + [1.0] * 15)
    groups = pd.Series([1] * 10 + [2] * 15)
    assert has_enough_data(series, groups, min_n=10) is False


def test_min_n_filter_pass():
    """Variable with 15 non-missing values in all groups returns has_enough_data=True."""
    series = pd.Series([1.0] * 30)
    groups = pd.Series([1] * 15 + [2] * 15)
    assert has_enough_data(series, groups, min_n=10) is True


def test_min_n_filter_exact_boundary():
    """Exactly min_n non-missing in every group returns True (>= is inclusive)."""
    series = pd.Series([1.0] * 20)
    groups = pd.Series([1] * 10 + [2] * 10)
    assert has_enough_data(series, groups, min_n=10) is True


# ---------------------------------------------------------------------------
# Helper: get_pheno_cols
# ---------------------------------------------------------------------------


def test_get_pheno_cols():
    """get_pheno_cols returns all columns except subject_col and cluster_col."""
    df = pd.DataFrame(columns=["src_subject_id", "cluster", "col_a", "col_b"])
    result = get_pheno_cols(df, subject_col="src_subject_id", cluster_col="cluster")
    assert result == ["col_a", "col_b"]
