"""type_detector.py: Variable type auto-detection with override CSV support.

Classification logic (applied in this order):
1. All-NA column                              -> CONTINUOUS (default)
2. Exactly 2 unique non-NA values             -> BINARY
3. <= UNIQUE_THRESHOLD unique non-NA values:
   a. All values are integers AND consecutive  -> ORDINAL
   b. Otherwise                               -> CATEGORICAL
4. > UNIQUE_THRESHOLD unique non-NA values    -> CONTINUOUS

IMPORTANT: Run replace_sentinels() before calling detect_type() or detect_all_types().
Sentinel values (e.g. -999) inflate unique-value counts and cause misclassification.
"""

from __future__ import annotations

from enum import Enum

import pandas as pd
from loguru import logger


UNIQUE_THRESHOLD = 10


class VarType(str, Enum):
    """Variable type classifications for phenotype columns."""

    BINARY = "binary"
    ORDINAL = "ordinal"
    CATEGORICAL = "categorical"
    CONTINUOUS = "continuous"


def detect_type(series: pd.Series) -> VarType:
    """Classify a single column into one of four VarType categories.

    NaN values are excluded before any computation. A column that is entirely
    NaN defaults to CONTINUOUS.

    The sequential integer check handles CSV float-loading: values like
    1.0, 2.0, 3.0 are treated as integers via float(v).is_integer().

    Parameters
    ----------
    series:
        A single phenotype column (may contain NaN).

    Returns
    -------
    VarType
        Detected type: BINARY, ORDINAL, CATEGORICAL, or CONTINUOUS.
    """
    vals = series.dropna()

    if vals.empty:
        return VarType.CONTINUOUS

    n_unique = vals.nunique()

    # Binary check takes precedence (comes before ordinal check)
    if n_unique == 2:
        return VarType.BINARY

    if n_unique <= UNIQUE_THRESHOLD:
        sorted_vals = sorted(vals.unique())
        try:
            is_all_int = all(float(v).is_integer() for v in sorted_vals)
        except (TypeError, ValueError):
            is_all_int = False

        if is_all_int:
            min_val = int(min(sorted_vals))
            max_val = int(max(sorted_vals))
            expected = list(range(min_val, max_val + 1))
            is_consecutive = [int(v) for v in sorted_vals] == expected
        else:
            is_consecutive = False

        if is_all_int and is_consecutive:
            return VarType.ORDINAL
        else:
            return VarType.CATEGORICAL

    return VarType.CONTINUOUS


def detect_all_types(
    df: pd.DataFrame,
    pheno_cols: list[str],
) -> dict[str, VarType]:
    """Classify all phenotype columns in a DataFrame.

    Parameters
    ----------
    df:
        Merged DataFrame with sentinel values already replaced.
    pheno_cols:
        List of phenotype column names to classify. Should exclude subject_col
        and cluster_col (use get_pheno_cols from loader.py).

    Returns
    -------
    dict[str, VarType]
        Mapping of column name -> VarType for each column in pheno_cols.
    """
    type_map: dict[str, VarType] = {}
    for col in pheno_cols:
        vtype = detect_type(df[col])
        type_map[col] = vtype
        logger.debug(f"  {col}: {vtype.value}")

    counts = {vt: sum(1 for v in type_map.values() if v == vt) for vt in VarType}
    logger.info(
        f"Type detection complete: {counts[VarType.BINARY]} binary, "
        f"{counts[VarType.ORDINAL]} ordinal, "
        f"{counts[VarType.CATEGORICAL]} categorical, "
        f"{counts[VarType.CONTINUOUS]} continuous"
    )
    return type_map


def apply_overrides(
    type_map: dict[str, VarType],
    override_path: str | None,
) -> dict[str, VarType]:
    """Override auto-detected types from a user-supplied CSV.

    The override CSV must have columns: variable_name, forced_type.
    The forced_type value must match a VarType enum value (case-insensitive).
    Invalid forced_type values are logged as warnings and skipped.

    Parameters
    ----------
    type_map:
        Dict mapping variable names to their auto-detected VarType.
        Modified in place.
    override_path:
        Path to the override CSV, or None to skip this step.

    Returns
    -------
    dict[str, VarType]
        Updated type map with overrides applied.
    """
    if override_path is None:
        return type_map

    overrides = pd.read_csv(override_path)
    override_count = 0

    for _, row in overrides.iterrows():
        var_name = row["variable_name"]
        forced_type_str = row["forced_type"].strip().lower()
        try:
            forced_type = VarType(forced_type_str)
        except ValueError:
            logger.warning(
                f"apply_overrides: '{forced_type_str}' is not a valid VarType "
                f"for variable '{var_name}'. Valid types: "
                f"{[v.value for v in VarType]}. Skipping."
            )
            continue

        if var_name in type_map:
            old_type = type_map[var_name]
            type_map[var_name] = forced_type
            logger.info(
                f"Override: {var_name} {old_type.value} -> {forced_type.value}"
            )
        else:
            # Variable not in type_map (possibly not in the dataset) — add it anyway
            type_map[var_name] = forced_type
            logger.debug(
                f"Override: {var_name} not in type_map; setting to {forced_type.value}"
            )
        override_count += 1

    logger.info(f"Applied {override_count} type overrides from {override_path}")
    return type_map
