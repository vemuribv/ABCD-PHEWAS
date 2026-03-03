"""Build phenotype_metadata.csv and domain_crosscheck.csv from published supplements.

Run once from the repo root:
    python python_pipeline/scripts/build_phenotype_metadata.py

Reads:
    python_pipeline/configs/44220_2024_313_MOESM3_ESM.xlsx  (Paul 2024, NHB)
        Table S7. Baseline var descript  -> baseline variable → domain
        Table S9. Follow-up var descrip  -> follow-up variable → domain

Writes:
    python_pipeline/configs/phenotype_metadata.csv
    python_pipeline/configs/domain_crosscheck.csv
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_HERE = Path(__file__).parent
_CONFIG_DIR = _HERE.parent / "configs"

PAUL2024 = _CONFIG_DIR / "44220_2024_313_MOESM3_ESM.xlsx"
CRP_SUPP = _CONFIG_DIR / "1-s2.0-S088915912500145X-mmc1.xlsx"
OUT_METADATA = _CONFIG_DIR / "phenotype_metadata.csv"
OUT_CROSSCHECK = _CONFIG_DIR / "domain_crosscheck.csv"

# ---------------------------------------------------------------------------
# Domain name normalisation
# Supplement headers → our canonical domain names (from domains.yaml)
# ---------------------------------------------------------------------------

_DOMAIN_MAP = {
    "COGNITION": "Cognition",
    "NEUROCOGNITION": "Cognition",
    "SCREEN TIME": "Screen Time",
    "DEMOGRAPHICS": "Demographics",
    "DEMOGRAPHIC": "Demographics",
    # Substance sub-headings all collapse to Substance
    "SUBSTANCE": "Substance",
    "SUBSTANCE USE": "Substance",
    "SUBSTANCE USE AND ATTITUDES": "Substance",
    "ALCOHOL": "Substance",
    "NICOTINE": "Substance",
    "MARIJUANA": "Substance",
    "ILLICIT DRUG": "Substance",
    "ATTITUDES": "Substance",
    "DRUG USE": "Substance",
    "CULTURE/ENVIRONMENT": "Culture/Environment",
    "CULTURE & ENVIRONMENT": "Culture/Environment",
    "CULTURE AND ENVIRONMENT": "Culture/Environment",
    "PHYSICAL HEALTH": "Physical Health",
    "PHSYICAL HEALTH": "Physical Health",   # typo in supplement
    "PHYSICAL HEALTH AND DEVELOPMENT": "Physical Health",
    "FAMILY MENTAL HEALTH": "Family Mental Health",
    "CHILD MENTAL HEALTH": "Child Mental Health",
    # 'OTHER' / Resilience/UPPS-P/BIS-BAS → Child Mental Health
    "OTHER": "Child Mental Health",
    "RESILIENCE": "Child Mental Health",
    "UPPS-P": "Child Mental Health",
    "BIS-BAS": "Child Mental Health",
    "OTHER RESILIENCE/UPPS-P/BIS-BAS": "Child Mental Health",
    "BEHAVIORAL DYSREGULATION": "Child Mental Health",
}

# These raw cell values are not variable names — skip them
_SKIP_VALUES = {
    "nan", "study variable", "original variable name",
    "variable present in two-year follow-up", "description",
    "none", "", "variable present in two-year",
}


def _normalize_domain(raw: str) -> str | None:
    """Map a raw section-header string to our canonical domain name.

    Returns None if the header is not a known domain (should be treated as
    a sub-heading continuation of the previous domain or a structural row).
    """
    clean = raw.strip().upper()
    # Direct lookup
    if clean in _DOMAIN_MAP:
        return _DOMAIN_MAP[clean]
    # Prefix match for composite headings
    for key, val in _DOMAIN_MAP.items():
        if clean.startswith(key):
            return val
    return None


def parse_s7_or_s9(excel_path: Path, sheet_name: str, timepoint: str) -> pd.DataFrame:
    """Parse a Table S7 or S9 sheet and return a tidy DataFrame.

    Sheet layout (col 0 is always an empty spacer):
        col 1: study_variable  OR  domain section header (e.g. "COGNITION")
        col 2: original_variable name (empty for section headers)
        col 3: in_followup (yes/no/new_name; empty for section headers)
        col 4: description text (empty for section headers)

    Parameters
    ----------
    excel_path : Path
    sheet_name : str
    timepoint : str  "baseline" or "followup"

    Returns
    -------
    DataFrame with columns:
        study_variable, original_variable, in_followup, description, domain, timepoint
    """
    df = pd.read_excel(excel_path, sheet_name=sheet_name, header=None, dtype=str)
    # Ensure at least 5 columns (0-indexed)
    while df.shape[1] < 5:
        df[df.shape[1]] = ""

    records: list[dict] = []
    current_domain = "Unclassified"

    for _, row in df.iterrows():
        # Col 0 is always an empty formatting spacer — skip it
        val1 = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""  # study_var / header
        val2 = str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else ""  # original_var
        val3 = str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else ""  # in_followup
        val4 = str(row.iloc[4]).strip() if pd.notna(row.iloc[4]) else ""  # description

        # Skip structural rows: empty col1 or known header text
        if not val1 or val1.lower() in _SKIP_VALUES:
            continue

        # Section header: col1 is all-caps domain name, col2 and col4 are empty
        if not val2 and not val4:
            domain = _normalize_domain(val1)
            if domain is not None:
                current_domain = domain
            # Regardless of recognition, this is not a variable row
            continue

        # Variable row
        records.append({
            "study_variable": val1,
            "original_variable": val2 if val2 not in ("nan", "") else "",
            "in_followup": val3 if val3 not in ("nan", "") else "",
            "description": val4 if val4 not in ("nan", "") else "",
            "domain": current_domain,
            "timepoint": timepoint,
        })

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Build combined metadata
# ---------------------------------------------------------------------------

def build_metadata() -> pd.DataFrame:
    """Parse S7 (baseline) + S9 (follow-up) and combine into one metadata table."""
    print(f"Reading: {PAUL2024.name}")

    # Find actual sheet names (they may include extra whitespace)
    xl = pd.ExcelFile(PAUL2024)
    sheet_names = xl.sheet_names

    s7_name = next((s for s in sheet_names if "S7" in s or "s7" in s.lower()), None)
    s9_name = next((s for s in sheet_names if "S9" in s or "s9" in s.lower()), None)

    if s7_name is None or s9_name is None:
        available = ", ".join(sheet_names)
        raise ValueError(
            f"Could not find S7 / S9 sheets in {PAUL2024.name}. "
            f"Available sheets: {available}"
        )

    print(f"  Parsing '{s7_name}' (baseline) ...")
    baseline = parse_s7_or_s9(PAUL2024, s7_name, "baseline")
    print(f"  -> {len(baseline)} baseline variables")

    print(f"  Parsing '{s9_name}' (follow-up) ...")
    followup = parse_s7_or_s9(PAUL2024, s9_name, "followup")
    print(f"  -> {len(followup)} follow-up variables")

    # Combine: for variables in both timepoints, keep one row and mark timepoints="both"
    combined = pd.concat([baseline, followup], ignore_index=True)

    # Deduplicate: group by study_variable, keep the domain from baseline where possible
    # (baseline is authoritative), merge description and timepoints
    records = []
    for var, grp in combined.groupby("study_variable", sort=False):
        # Take baseline row first if it exists
        bl_rows = grp[grp["timepoint"] == "baseline"]
        fu_rows = grp[grp["timepoint"] == "followup"]

        base_row = bl_rows.iloc[0] if len(bl_rows) else fu_rows.iloc[0]
        domain = base_row["domain"]
        original = base_row["original_variable"]
        desc = base_row["description"]
        if not desc and len(fu_rows):
            desc = fu_rows.iloc[0]["description"]

        if len(bl_rows) and len(fu_rows):
            timepoints = "both"
        elif len(bl_rows):
            timepoints = "baseline"
        else:
            timepoints = "followup"

        in_followup = base_row["in_followup"] if len(bl_rows) else "yes"

        records.append({
            "study_variable": var,
            "original_variable": original,
            "description": desc,
            "domain": domain,
            "timepoints": timepoints,
            "in_followup": in_followup,
        })

    meta = pd.DataFrame(records)
    print(f"\nCombined metadata: {len(meta)} unique variables")
    print("Domain distribution:")
    for dom, cnt in meta["domain"].value_counts().items():
        print(f"  {dom}: {cnt}")

    return meta


# ---------------------------------------------------------------------------
# Cross-check against regex domains
# ---------------------------------------------------------------------------

def build_crosscheck(meta: pd.DataFrame) -> pd.DataFrame:
    """Compare published domain labels to our regex-based assign_domain()."""
    # Import here (avoids circular imports if this script is run standalone)
    sys.path.insert(0, str(_HERE.parent.parent))
    from python_pipeline.domains import assign_domain, load_domain_config

    domain_config = _CONFIG_DIR / "domains.yaml"
    domain_specs = load_domain_config(str(domain_config))

    rows = []
    for _, row in meta.iterrows():
        var = row["study_variable"]
        published = row["domain"]
        regex = assign_domain(var, domain_specs)
        rows.append({
            "study_variable": var,
            "published_domain": published,
            "regex_domain": regex,
            "match": published == regex,
        })

    df = pd.DataFrame(rows)
    n_match = df["match"].sum()
    n_total = len(df)
    pct = 100 * n_match / n_total if n_total else 0
    print(f"\nCross-check: {n_match}/{n_total} variables agree ({pct:.1f}%)")

    mismatch = df[~df["match"]]
    print(f"Mismatches: {len(mismatch)}")
    if len(mismatch):
        top = (
            mismatch.groupby(["published_domain", "regex_domain"])
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
            .head(20)
        )
        print(top.to_string(index=False))

    return df


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not PAUL2024.exists():
        print(f"ERROR: {PAUL2024} not found. Upload the supplement Excel file to configs/.")
        sys.exit(1)

    meta = build_metadata()
    meta.to_csv(OUT_METADATA, index=False)
    print(f"\nWrote: {OUT_METADATA}")

    crosscheck = build_crosscheck(meta)
    crosscheck.to_csv(OUT_CROSSCHECK, index=False)
    print(f"Wrote: {OUT_CROSSCHECK}")


if __name__ == "__main__":
    main()
