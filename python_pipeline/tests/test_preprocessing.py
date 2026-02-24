"""Unit tests for preprocessing.py.

Validates that the Python transformations match the expected R outputs:
  - winsorize_column  → DescTools::Winsorize
  - inverse_normal_transform → qnorm((rank(x, na.last="keep") - 0.5) / sum(!is.na(x)))
  - zscore_column     → scale()
  - compute_skewness  → psych::describe skew
  - create_cluster_dummies
  - filter_by_sex
"""

import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm

from python_pipeline.preprocessing import (
    compute_skewness,
    create_cluster_dummies,
    filter_by_sex,
    identify_skewed_columns,
    inverse_normal_transform,
    load_cluster_labels,
    merge_clusters,
    preprocess_continuous_phenotypes,
    winsorize_column,
    zscore_column,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

@pytest.fixture()
def small_series():
    """A small non-skewed series."""
    return pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])


@pytest.fixture()
def skewed_series():
    """A series with extreme outlier to induce skewness."""
    return pd.Series([1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 100.0])


@pytest.fixture()
def series_with_nan():
    return pd.Series([1.0, 2.0, np.nan, 4.0, 5.0])


# --------------------------------------------------------------------------- #
# winsorize_column
# --------------------------------------------------------------------------- #

class TestWinsorizeColumn:
    def test_no_outliers_unchanged(self, small_series):
        result = winsorize_column(small_series, n_sd=3.0)
        pd.testing.assert_series_equal(result, small_series)

    def test_outlier_clipped(self, skewed_series):
        result = winsorize_column(skewed_series, n_sd=3.0)
        mu = skewed_series.mean()
        sigma = skewed_series.std(ddof=1)
        upper = mu + 3.0 * sigma
        assert result.max() <= upper + 1e-10

    def test_nan_preserved(self):
        s = pd.Series([1.0, np.nan, 3.0, 1000.0])
        result = winsorize_column(s, n_sd=1.0)
        assert np.isnan(result.iloc[1])

    def test_zero_variance_returns_original(self):
        s = pd.Series([5.0, 5.0, 5.0])
        result = winsorize_column(s, n_sd=3.0)
        pd.testing.assert_series_equal(result, s)


# --------------------------------------------------------------------------- #
# inverse_normal_transform
# --------------------------------------------------------------------------- #

class TestInverseNormalTransform:
    def test_output_length_matches_input(self, small_series):
        result = inverse_normal_transform(small_series)
        assert len(result) == len(small_series)

    def test_nan_positions_preserved(self, series_with_nan):
        result = inverse_normal_transform(series_with_nan)
        assert np.isnan(result.iloc[2])

    def test_known_values(self):
        """Verify against manual calculation of R's formula.

        x = [1, 2, 3, 4]  (n=4, no NaN)
        ranks = [1, 2, 3, 4]
        transformed = qnorm((rank - 0.5) / 4)
                     = qnorm([0.125, 0.375, 0.625, 0.875])
        """
        x = pd.Series([1.0, 2.0, 3.0, 4.0])
        result = inverse_normal_transform(x)
        expected = norm.ppf(np.array([0.125, 0.375, 0.625, 0.875]))
        np.testing.assert_allclose(result.values, expected, atol=1e-10)

    def test_monotonic_ordering(self, small_series):
        """INT must preserve the rank order of non-NaN values."""
        result = inverse_normal_transform(small_series)
        assert list(result) == sorted(result)

    def test_all_nan_returns_nan(self):
        s = pd.Series([np.nan, np.nan, np.nan])
        result = inverse_normal_transform(s)
        assert result.isna().all()


# --------------------------------------------------------------------------- #
# zscore_column
# --------------------------------------------------------------------------- #

class TestZscoreColumn:
    def test_mean_zero(self, small_series):
        result = zscore_column(small_series)
        assert abs(result.mean()) < 1e-10

    def test_std_one(self, small_series):
        result = zscore_column(small_series)
        assert abs(result.std(ddof=1) - 1.0) < 1e-10

    def test_nan_preserved(self, series_with_nan):
        result = zscore_column(series_with_nan)
        assert np.isnan(result.iloc[2])

    def test_zero_variance(self):
        s = pd.Series([3.0, 3.0, 3.0])
        result = zscore_column(s)
        assert (result == 0.0).all()


# --------------------------------------------------------------------------- #
# compute_skewness / identify_skewed_columns
# --------------------------------------------------------------------------- #

class TestSkewness:
    def test_symmetric_series_low_skew(self, small_series):
        skews = compute_skewness(pd.DataFrame({"x": small_series}), ["x"])
        assert abs(skews["x"]) < 1.96

    def test_skewed_series_high_skew(self, skewed_series):
        skews = compute_skewness(pd.DataFrame({"x": skewed_series}), ["x"])
        assert abs(skews["x"]) > 1.96

    def test_identify_skewed_returns_correct_cols(self, skewed_series, small_series):
        df = pd.DataFrame({"skewed": skewed_series, "normal": small_series})
        df_padded = pd.concat(
            [df, pd.DataFrame({"skewed": [np.nan] * 2, "normal": [np.nan] * 2})],
            ignore_index=True,
        )
        skews = compute_skewness(df_padded, ["skewed", "normal"])
        flagged = identify_skewed_columns(skews, threshold=1.96)
        assert "skewed" in flagged
        assert "normal" not in flagged


# --------------------------------------------------------------------------- #
# preprocess_continuous_phenotypes
# --------------------------------------------------------------------------- #

class TestPreprocessContinuousPhenotypes:
    def test_returns_dataframe_same_shape(self):
        np.random.seed(42)
        df = pd.DataFrame({"a": np.random.randn(50), "b": np.random.randn(50)})
        result = preprocess_continuous_phenotypes(df, ["a", "b"])
        assert result.shape == df.shape

    def test_continuous_cols_are_zscored(self):
        df = pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0, 5.0]})
        result = preprocess_continuous_phenotypes(df, ["a"])
        assert abs(result["a"].mean()) < 1e-10

    def test_original_df_not_mutated(self):
        df = pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0, 5.0]})
        original_values = df["a"].copy()
        preprocess_continuous_phenotypes(df, ["a"])
        pd.testing.assert_series_equal(df["a"], original_values)


# --------------------------------------------------------------------------- #
# create_cluster_dummies
# --------------------------------------------------------------------------- #

class TestCreateClusterDummies:
    @pytest.fixture()
    def df_with_clusters(self):
        return pd.DataFrame({
            "subjectkey": ["s1", "s2", "s3", "s4", "s5", "s6"],
            "cluster": ["0", "0", "1", "1", "2", "2"],
        })

    def test_creates_correct_number_of_dummies(self, df_with_clusters):
        df, dummy_cols, ref = create_cluster_dummies(df_with_clusters, "cluster")
        assert len(dummy_cols) == 2  # k=3 clusters → 2 dummies

    def test_reference_is_first_alphabetically_by_default(self, df_with_clusters):
        _, _, ref = create_cluster_dummies(df_with_clusters, "cluster")
        assert ref == "0"

    def test_custom_reference(self, df_with_clusters):
        _, dummy_cols, ref = create_cluster_dummies(
            df_with_clusters, "cluster", reference_cluster="1"
        )
        assert ref == "1"
        assert "cluster_0" in dummy_cols
        assert "cluster_2" in dummy_cols
        assert "cluster_1" not in dummy_cols

    def test_dummy_values_correct(self, df_with_clusters):
        df, dummy_cols, _ = create_cluster_dummies(df_with_clusters, "cluster")
        # cluster_1 should be 1 only for rows with cluster=="1"
        assert df["cluster_1"].tolist() == [0, 0, 1, 1, 0, 0]
        assert df["cluster_2"].tolist() == [0, 0, 0, 0, 1, 1]

    def test_invalid_reference_raises(self, df_with_clusters):
        with pytest.raises(ValueError, match="not found"):
            create_cluster_dummies(df_with_clusters, "cluster", reference_cluster="9")


# --------------------------------------------------------------------------- #
# filter_by_sex
# --------------------------------------------------------------------------- #

class TestFilterBySex:
    @pytest.fixture()
    def df_with_sex(self):
        return pd.DataFrame({
            "subjectkey": [f"s{i}" for i in range(6)],
            "sex": ["1", "1", "1", "2", "2", "2"],
            "value": [1, 2, 3, 4, 5, 6],
        })

    def test_all_stratum_returns_all(self, df_with_sex):
        result = filter_by_sex(df_with_sex, "sex", "all")
        assert len(result) == 6

    def test_male_stratum(self, df_with_sex):
        result = filter_by_sex(df_with_sex, "sex", "male")
        assert len(result) == 3
        assert (result["sex"] == "1").all()

    def test_female_stratum(self, df_with_sex):
        result = filter_by_sex(df_with_sex, "sex", "female")
        assert len(result) == 3
        assert (result["sex"] == "2").all()

    def test_invalid_stratum_raises(self, df_with_sex):
        with pytest.raises(ValueError, match="sex_stratum must be"):
            filter_by_sex(df_with_sex, "sex", "other")


# --------------------------------------------------------------------------- #
# load_cluster_labels / merge_clusters
# --------------------------------------------------------------------------- #

class TestClusterIO:
    def test_load_cluster_labels(self, tmp_path):
        csv = tmp_path / "clusters.csv"
        csv.write_text("subjectkey,cluster\ns1,0\ns2,1\ns3,2\n")
        df = load_cluster_labels(str(csv))
        assert list(df.columns) == ["subjectkey", "cluster"]
        assert len(df) == 3

    def test_load_missing_column_raises(self, tmp_path):
        csv = tmp_path / "clusters.csv"
        csv.write_text("subject,cluster\ns1,0\n")
        with pytest.raises(ValueError, match="missing required columns"):
            load_cluster_labels(str(csv), subject_id_col="subjectkey")

    def test_merge_inner_join(self):
        pheno = pd.DataFrame({
            "subjectkey": ["s1", "s2", "s3", "s4"],
            "score": [1.0, 2.0, 3.0, 4.0],
        })
        clusters = pd.DataFrame({
            "subjectkey": ["s1", "s2", "s3"],
            "cluster": ["0", "1", "0"],
        })
        merged = merge_clusters(pheno, clusters)
        assert len(merged) == 3
        assert "s4" not in merged["subjectkey"].values
