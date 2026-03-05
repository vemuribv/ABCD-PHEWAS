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


# ---------------------------------------------------------------------------
# Phase 2 fixtures: statistical test data with known effect sizes
# ---------------------------------------------------------------------------


@pytest.fixture
def two_cluster_data() -> pd.DataFrame:
    """200 subjects in 2 clusters (100 each) with 4 phenotype columns.

    Known effect sizes baked in:
    - cont_pheno: cluster 1 mean=10 sd=2, cluster 2 mean=5 sd=2 -> Cohen's d ~ 2.5
    - binary_pheno: cluster 1 ~80% 1s, cluster 2 ~20% 1s
    - ordinal_pheno: cluster 1 values 3-5, cluster 2 values 1-3
    - categ_pheno: cluster 1 mostly "A", cluster 2 mostly "B"
    """
    rng = np.random.default_rng(42)
    n_per = 100
    subjects = [f"sub-{i:04d}" for i in range(2 * n_per)]
    clusters = [1] * n_per + [2] * n_per

    cont_c1 = rng.normal(10, 2, size=n_per)
    cont_c2 = rng.normal(5, 2, size=n_per)
    cont = np.concatenate([cont_c1, cont_c2])

    binary_c1 = rng.choice([0, 1], size=n_per, p=[0.2, 0.8])
    binary_c2 = rng.choice([0, 1], size=n_per, p=[0.8, 0.2])
    binary = np.concatenate([binary_c1, binary_c2])

    ordinal_c1 = rng.integers(3, 6, size=n_per)  # 3, 4, 5
    ordinal_c2 = rng.integers(1, 4, size=n_per)  # 1, 2, 3
    ordinal = np.concatenate([ordinal_c1, ordinal_c2])

    categ_c1 = rng.choice(["A", "B", "C"], size=n_per, p=[0.7, 0.2, 0.1])
    categ_c2 = rng.choice(["A", "B", "C"], size=n_per, p=[0.1, 0.7, 0.2])
    categ = np.concatenate([categ_c1, categ_c2])

    return pd.DataFrame({
        "src_subject_id": subjects,
        "cluster": clusters,
        "cont_pheno": cont,
        "binary_pheno": binary,
        "ordinal_pheno": ordinal,
        "categ_pheno": categ,
    })


@pytest.fixture
def eight_cluster_data() -> pd.DataFrame:
    """400 subjects in 8 clusters (50 each) with 4 phenotype columns.

    Cluster 1 has distinct effect vs rest for all phenotype types.
    """
    rng = np.random.default_rng(123)
    n_per = 50
    n_total = 8 * n_per
    subjects = [f"sub-{i:04d}" for i in range(n_total)]
    clusters = []
    for c in range(1, 9):
        clusters.extend([c] * n_per)

    # Continuous: cluster 1 mean=15, rest mean=10, all sd=2
    cont = []
    for c in range(1, 9):
        mean = 15.0 if c == 1 else 10.0
        cont.extend(rng.normal(mean, 2, size=n_per).tolist())

    # Binary: cluster 1 ~90% 1s, rest ~40% 1s
    binary = []
    for c in range(1, 9):
        p1 = 0.9 if c == 1 else 0.4
        binary.extend(rng.choice([0, 1], size=n_per, p=[1 - p1, p1]).tolist())

    # Ordinal: cluster 1 values 4-5, rest values 1-3
    ordinal = []
    for c in range(1, 9):
        if c == 1:
            ordinal.extend(rng.integers(4, 6, size=n_per).tolist())
        else:
            ordinal.extend(rng.integers(1, 4, size=n_per).tolist())

    # Categorical: cluster 1 mostly "X", rest mostly "Y"/"Z"
    categ = []
    for c in range(1, 9):
        if c == 1:
            categ.extend(rng.choice(["X", "Y", "Z"], size=n_per, p=[0.8, 0.1, 0.1]).tolist())
        else:
            categ.extend(rng.choice(["X", "Y", "Z"], size=n_per, p=[0.1, 0.5, 0.4]).tolist())

    return pd.DataFrame({
        "src_subject_id": subjects,
        "cluster": clusters,
        "cont_pheno": cont,
        "binary_pheno": binary,
        "ordinal_pheno": ordinal,
        "categ_pheno": categ,
    })


@pytest.fixture
def sparse_contingency_2x2() -> np.ndarray:
    """2x2 contingency table with expected cell count < 5."""
    return np.array([[1, 8], [2, 89]])


@pytest.fixture
def sparse_contingency_3x3() -> np.ndarray:
    """3x3 contingency table with expected cell count < 5."""
    return np.array([[1, 2, 0], [3, 1, 1], [0, 2, 90]])
