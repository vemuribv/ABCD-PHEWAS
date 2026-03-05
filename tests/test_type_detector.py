"""Tests for abcd_phewas.type_detector module.

Covers DATA-02: variable type auto-detection and override CSV.
"""

import numpy as np
import pandas as pd
import pytest

from abcd_phewas.type_detector import VarType, apply_overrides, detect_all_types, detect_type


# ---------------------------------------------------------------------------
# Basic type detection
# ---------------------------------------------------------------------------


def test_binary():
    """Column with exactly 2 unique non-NA values (0, 1) -> BINARY."""
    s = pd.Series([0, 1, 0, 1, 0, 1, 1, 0])
    assert detect_type(s) == VarType.BINARY


def test_binary_with_na():
    """Column with 2 unique non-NA values but some NaN -> still BINARY."""
    s = pd.Series([0, 1, np.nan, 0, 1, np.nan])
    assert detect_type(s) == VarType.BINARY


def test_ordinal():
    """Column with values (1,2,3,4,5) sequential integers -> ORDINAL."""
    s = pd.Series([1, 2, 3, 4, 5, 1, 2, 3, 4, 5])
    assert detect_type(s) == VarType.ORDINAL


def test_ordinal_as_float():
    """Column with values (1.0, 2.0, 3.0) stored as float -> ORDINAL (not CATEGORICAL)."""
    s = pd.Series([1.0, 2.0, 3.0, 1.0, 2.0, 3.0])
    assert detect_type(s) == VarType.ORDINAL


def test_ordinal_wide_range():
    """Column with values (1,2,3,4,5,6,7,8,9,10) sequential, <=10 unique -> ORDINAL."""
    s = pd.Series(list(range(1, 11)) * 2)
    assert detect_type(s) == VarType.ORDINAL


def test_ordinal_not_starting_at_one():
    """Column with values (0,1,2,3,4,5) sequential integers from 0 -> ORDINAL."""
    s = pd.Series([0, 1, 2, 3, 4, 5])
    assert detect_type(s) == VarType.ORDINAL


def test_categorical():
    """Column with values ("A","B","C","D") non-sequential strings -> CATEGORICAL."""
    s = pd.Series(["A", "B", "C", "D", "A", "B"])
    assert detect_type(s) == VarType.CATEGORICAL


def test_categorical_nonsequential_ints():
    """Column with values (1,3,5,7) non-sequential ints -> CATEGORICAL."""
    s = pd.Series([1, 3, 5, 7, 1, 3, 5, 7])
    assert detect_type(s) == VarType.CATEGORICAL


def test_categorical_few_unique():
    """Column with 3 unique non-sequential values -> CATEGORICAL."""
    s = pd.Series([10, 20, 30, 10, 20, 30])
    assert detect_type(s) == VarType.CATEGORICAL


def test_continuous():
    """Column with >10 unique values -> CONTINUOUS."""
    # Generate 20 distinct float values
    s = pd.Series([float(i) * 0.7 + 0.1 for i in range(20)])
    assert detect_type(s) == VarType.CONTINUOUS


def test_continuous_exactly_11():
    """Column with exactly 11 unique values -> CONTINUOUS (threshold is >10)."""
    s = pd.Series(list(range(11)) * 2)
    assert detect_type(s) == VarType.CONTINUOUS


def test_all_na():
    """Column with all NaN -> CONTINUOUS (default for empty series)."""
    s = pd.Series([np.nan, np.nan, np.nan])
    assert detect_type(s) == VarType.CONTINUOUS


def test_binary_takes_precedence_over_ordinal():
    """Values (0, 1) are both binary AND sequential integers; binary check wins."""
    s = pd.Series([0, 1, 0, 1, 1, 0])
    # n_unique == 2 -> BINARY, not ORDINAL
    assert detect_type(s) == VarType.BINARY


# ---------------------------------------------------------------------------
# Integration: binary after sentinel removal
# ---------------------------------------------------------------------------


def test_binary_after_sentinel():
    """Column with (-999, 0, 1) after sentinel removal has 2 unique -> BINARY.

    This test validates the correct pipeline order: replace sentinels before
    running detect_type. The test itself simulates the sentinel-replaced series.
    """
    # Simulate sentinel replacement already done:
    s = pd.Series([-999.0, 0.0, 1.0]).replace(-999, np.nan)
    assert detect_type(s) == VarType.BINARY


# ---------------------------------------------------------------------------
# detect_all_types
# ---------------------------------------------------------------------------


def test_detect_all_types():
    """DataFrame with mixed columns returns correct dict mapping."""
    df = pd.DataFrame({
        "src_subject_id": ["s1", "s2", "s3", "s4", "s5", "s6",
                           "s7", "s8", "s9", "s10", "s11", "s12"],
        "cluster": [1] * 12,
        "binary_col": [0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
        "ordinal_col": [1, 2, 3, 4, 5, 1, 2, 3, 4, 5, 1, 2],
        "cat_col": ["A", "B", "C", "D", "A", "B", "C", "D", "A", "B", "C", "D"],
        "cont_col": [float(i) * 0.3 + 1.1 for i in range(12)],
    })
    pheno_cols = ["binary_col", "ordinal_col", "cat_col", "cont_col"]
    result = detect_all_types(df, pheno_cols)

    assert isinstance(result, dict)
    assert result["binary_col"] == VarType.BINARY
    assert result["ordinal_col"] == VarType.ORDINAL
    assert result["cat_col"] == VarType.CATEGORICAL
    assert result["cont_col"] == VarType.CONTINUOUS
    # Should only contain pheno_cols, not subject/cluster cols
    assert "src_subject_id" not in result
    assert "cluster" not in result


# ---------------------------------------------------------------------------
# apply_overrides
# ---------------------------------------------------------------------------


def test_override(tmp_path):
    """Auto-detected categorical overridden by CSV -> result is continuous."""
    # Set up type map with categorical auto-detection
    type_map = {
        "col_cat": VarType.CATEGORICAL,
        "col_bin": VarType.BINARY,
    }

    # Write override CSV
    override_path = str(tmp_path / "overrides.csv")
    override_df = pd.DataFrame({
        "variable_name": ["col_cat"],
        "forced_type": ["continuous"],
    })
    override_df.to_csv(override_path, index=False)

    result = apply_overrides(type_map, override_path)
    assert result["col_cat"] == VarType.CONTINUOUS
    # Non-overridden column unchanged
    assert result["col_bin"] == VarType.BINARY


def test_override_none():
    """apply_overrides with None returns type_map unchanged."""
    type_map = {"col_a": VarType.BINARY, "col_b": VarType.ORDINAL}
    result = apply_overrides(type_map, override_path=None)
    assert result == type_map


def test_override_invalid_type_skipped(tmp_path, caplog):
    """Invalid forced_type in override CSV is skipped with a warning."""
    import logging

    type_map = {"col_a": VarType.CATEGORICAL}

    override_path = str(tmp_path / "bad_override.csv")
    override_df = pd.DataFrame({
        "variable_name": ["col_a"],
        "forced_type": ["invalid_type"],
    })
    override_df.to_csv(override_path, index=False)

    # Should not raise; original type preserved
    result = apply_overrides(type_map, override_path)
    assert result["col_a"] == VarType.CATEGORICAL


def test_override_all_types(tmp_path):
    """Override CSV can set all four VarType values."""
    type_map = {
        "col_b": VarType.CATEGORICAL,
        "col_o": VarType.CATEGORICAL,
        "col_c": VarType.CATEGORICAL,
        "col_k": VarType.CATEGORICAL,
    }
    override_path = str(tmp_path / "all_types.csv")
    override_df = pd.DataFrame({
        "variable_name": ["col_b", "col_o", "col_c", "col_k"],
        "forced_type": ["binary", "ordinal", "continuous", "categorical"],
    })
    override_df.to_csv(override_path, index=False)

    result = apply_overrides(type_map, override_path)
    assert result["col_b"] == VarType.BINARY
    assert result["col_o"] == VarType.ORDINAL
    assert result["col_c"] == VarType.CONTINUOUS
    assert result["col_k"] == VarType.CATEGORICAL
