"""Shared test fixtures for abcd_phewas test suite."""

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def sample_cluster_df() -> pd.DataFrame:
    """20 subjects (sub-01 to sub-20) with cluster labels 1–3."""
    rng = np.random.default_rng(42)
    n = 20
    subjects = [f"sub-{i:02d}" for i in range(1, n + 1)]
    clusters = rng.integers(1, 4, size=n).tolist()
    return pd.DataFrame({"src_subject_id": subjects, "cluster": clusters})


@pytest.fixture
def sample_pheno_df() -> pd.DataFrame:
    """15 subjects (sub-05 to sub-19) with 10 phenotype columns of mixed types.

    Columns:
    - binary_col: values 0 and 1
    - ordinal_col: values 1,2,3,4,5 (sequential integers)
    - categorical_col: values "A","B","C","D" (non-sequential, string)
    - cont_col_1..5: continuous (random normal, >10 unique values each)
    - sentinel_col: continuous with sentinel values mixed in (-999)
    - sparse_col: mostly NaN, too few observations for min_n test
    """
    rng = np.random.default_rng(99)
    n = 15
    subjects = [f"sub-{i:02d}" for i in range(5, 20)]  # sub-05 to sub-19

    data = {
        "src_subject_id": subjects,
        "binary_col": rng.integers(0, 2, size=n).tolist(),
        "ordinal_col": rng.integers(1, 6, size=n).tolist(),
        "categorical_col": rng.choice(["A", "B", "C", "D"], size=n).tolist(),
        "cont_col_1": rng.normal(0, 1, size=n).tolist(),
        "cont_col_2": rng.normal(5, 2, size=n).tolist(),
        "cont_col_3": rng.normal(-3, 0.5, size=n).tolist(),
        "cont_col_4": rng.normal(100, 10, size=n).tolist(),
        "cont_col_5": rng.normal(0.5, 0.1, size=n).tolist(),
        # sentinel_col: some real values mixed with sentinel -999
        "sentinel_col": [
            -999 if i % 4 == 0 else rng.normal(10, 1)
            for i in range(n)
        ],
        # sparse_col: only 3 non-missing values out of 15
        "sparse_col": [rng.normal(0, 1) if i < 3 else np.nan for i in range(n)],
    }
    return pd.DataFrame(data)


@pytest.fixture
def tmp_csv_files(tmp_path, sample_cluster_df, sample_pheno_df):
    """Write cluster and pheno DataFrames to temporary CSV files.

    Returns
    -------
    tuple[str, str]
        (cluster_csv_path, pheno_csv_path)
    """
    cluster_path = str(tmp_path / "clusters.csv")
    pheno_path = str(tmp_path / "pheno.csv")
    sample_cluster_df.to_csv(cluster_path, index=False)
    sample_pheno_df.to_csv(pheno_path, index=False)
    return cluster_path, pheno_path


@pytest.fixture
def tmp_blocklist(tmp_path) -> str:
    """Write a blocklist file with a few variable names.

    Returns
    -------
    str
        Path to the blocklist file.
    """
    blocklist_path = str(tmp_path / "blocklist.txt")
    # List variables that appear in sample_pheno_df to test dropping
    blocked_vars = ["sentinel_col", "sparse_col", "nonexistent_var"]
    with open(blocklist_path, "w") as f:
        f.write("\n".join(blocked_vars) + "\n")
    return blocklist_path
