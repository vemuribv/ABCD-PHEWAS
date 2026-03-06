"""Publication-quality Manhattan-style PheWAS plots.

Generates one-vs-rest (OVR) Manhattan plots per cluster with directional
triangle markers and global omnibus Manhattan plots with circular markers.
Both use domain-based x-axis grouping, FDR + Bonferroni threshold lines,
and adjustText for non-overlapping labels.

R reference: PheWAS Analyses Resub5.Rmd Manhattan plot output.
"""
from __future__ import annotations

import logging
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for PNG generation

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from adjustText import adjust_text

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_x_positions(
    df_plot: pd.DataFrame,
    domain_config: list[dict],
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Assign sequential x positions grouped by domain with gaps between domains.

    Parameters
    ----------
    df_plot:
        Filtered DataFrame (one comparison type, possibly one cluster).
        Must have a 'domain' column.
    domain_config:
        Domain config list (preserves YAML ordering).

    Returns
    -------
    tuple[pd.DataFrame, dict[str, float]]
        (df with 'x_pos' column added, {domain_name: center_x}).
    """
    domain_order = [d["domain"] for d in domain_config]
    # Add "Other/Unclassified" if present but not in config
    present_domains = set(df_plot["domain"].unique())
    for d in domain_order.copy():
        if d not in present_domains:
            domain_order.remove(d)
    for d in present_domains:
        if d not in domain_order:
            domain_order.append(d)

    gap = 5
    x = 0
    x_positions = {}
    domain_centers: dict[str, float] = {}

    df_plot = df_plot.copy()
    df_plot["x_pos"] = 0.0

    for domain in domain_order:
        mask = df_plot["domain"] == domain
        if mask.sum() == 0:
            continue

        domain_vars = sorted(df_plot.loc[mask, "variable"].unique())
        start_x = x

        for var in domain_vars:
            var_mask = (df_plot["domain"] == domain) & (df_plot["variable"] == var)
            df_plot.loc[var_mask, "x_pos"] = x
            x_positions[var] = x
            x += 1

        end_x = x - 1
        domain_centers[domain] = (start_x + end_x) / 2.0
        x += gap  # gap between domains

    return df_plot, domain_centers


def _add_threshold_lines(
    ax: matplotlib.axes.Axes,
    df_plot: pd.DataFrame,
    n_tests: int,
) -> None:
    """Add Bonferroni and FDR threshold lines to the axes.

    Parameters
    ----------
    ax:
        Matplotlib axes.
    df_plot:
        Filtered plot DataFrame with fdr_q_global and p_value columns.
    n_tests:
        Total number of tests in the correction family.
    """
    if n_tests <= 0:
        return

    # Bonferroni line
    bonf_threshold = 0.05 / n_tests
    bonf_neg_log = -np.log10(bonf_threshold)
    ax.axhline(bonf_neg_log, color="red", linestyle="--", linewidth=0.8,
               label=f"Bonferroni (p={bonf_threshold:.2e})", zorder=1)

    # FDR line: largest p_value where fdr_q_global <= 0.05
    valid = df_plot.dropna(subset=["fdr_q_global", "p_value"])
    fdr_sig = valid[valid["fdr_q_global"] <= 0.05]
    if len(fdr_sig) > 0:
        fdr_p_threshold = fdr_sig["p_value"].max()
        fdr_neg_log = -np.log10(fdr_p_threshold)
        ax.axhline(fdr_neg_log, color="blue", linestyle="--", linewidth=0.8,
                   label=f"FDR 5% (p={fdr_p_threshold:.2e})", zorder=1)


def _add_labels(
    ax: matplotlib.axes.Axes,
    df_plot: pd.DataFrame,
    x_col: str = "x_pos",
    y_col: str = "neg_log_p",
    rename_map: dict[str, str] | None = None,
) -> None:
    """Add non-overlapping text labels to significant hits.

    Label selection: Bonferroni-significant hits first (up to 20). If fewer
    than 5 Bonferroni-significant, supplement with FDR-significant up to 15
    total.

    Parameters
    ----------
    ax:
        Matplotlib axes (must have all elements already drawn).
    df_plot:
        DataFrame with x_pos, neg_log_p, variable, bonf_p_global, fdr_q_global.
    x_col, y_col:
        Column names for coordinates.
    rename_map:
        Optional {variable_name: display_label} for prettier names.
    """
    rename_map = rename_map or {}

    # Drop NaN y-values
    valid = df_plot.dropna(subset=[y_col])
    if len(valid) == 0:
        return

    # Select labels: Bonferroni-significant
    bonf_hits = valid[valid["bonf_p_global"] <= 0.05].nsmallest(20, "p_value")
    label_df = bonf_hits.copy()

    # Supplement with FDR if fewer than 5 Bonferroni
    if len(label_df) < 5:
        fdr_hits = valid[valid["fdr_q_global"] <= 0.05].nsmallest(15, "p_value")
        label_df = pd.concat([label_df, fdr_hits]).drop_duplicates(subset="variable").head(15)

    if len(label_df) == 0:
        return

    texts = []
    for _, row in label_df.iterrows():
        display = rename_map.get(row["variable"], row["variable"])
        txt = ax.text(
            row[x_col], row[y_col], display,
            fontsize=6, ha="center", va="bottom",
        )
        texts.append(txt)

    if texts:
        adjust_text(
            texts, ax=ax,
            arrowprops=dict(arrowstyle="->", color="gray", lw=0.5),
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def manhattan_plot(
    df: pd.DataFrame,
    cluster_label: str,
    domain_config: list[dict],
    output_path: str,
    rename_map: dict[str, str] | None = None,
) -> None:
    """Generate a one-vs-rest Manhattan plot for a specific cluster.

    Parameters
    ----------
    df:
        Full corrected results DataFrame (all comparison types, all clusters).
    cluster_label:
        Cluster to plot (e.g. "Cluster_1").
    domain_config:
        Domain config list from load_domain_config().
    output_path:
        File path for the output PNG.
    rename_map:
        Optional variable-name-to-display-label mapping.
    """
    # Filter to OVR for this cluster
    df_plot = df[
        (df["comparison_type"] == "one_vs_rest") & (df["cluster_label"] == cluster_label)
    ].copy()

    if len(df_plot) == 0:
        logger.warning("No OVR results for cluster '%s'; skipping plot.", cluster_label)
        return

    # Compute -log10(p)
    df_plot["neg_log_p"] = -np.log10(df_plot["p_value"].clip(lower=1e-300))

    # Build x positions
    df_plot, domain_centers = _build_x_positions(df_plot, domain_config)

    # Build domain color map
    domain_colors = {d["domain"]: d["color"] for d in domain_config}
    domain_colors.setdefault("Other/Unclassified", "#AAAAAA")
    df_plot["color"] = df_plot["domain"].map(domain_colors)

    # Create figure
    fig, ax = plt.subplots(figsize=(16, 6))

    # Alternating background bands per domain
    domain_order = [d for d in domain_colors if d in domain_centers]
    for i, domain in enumerate(domain_order):
        d_data = df_plot[df_plot["domain"] == domain]
        if len(d_data) == 0:
            continue
        x_min = d_data["x_pos"].min() - 0.5
        x_max = d_data["x_pos"].max() + 0.5
        if i % 2 == 0:
            ax.axvspan(x_min, x_max, color="#f0f0f0", alpha=0.5, zorder=0)

    # Scatter: positive effect size (upward triangle)
    pos = df_plot[df_plot["effect_size"] >= 0]
    if len(pos) > 0:
        ax.scatter(
            pos["x_pos"], pos["neg_log_p"],
            c=pos["color"], marker="^", s=30, alpha=0.8,
            edgecolors="none", zorder=2,
        )

    # Scatter: negative effect size (downward triangle)
    neg = df_plot[df_plot["effect_size"] < 0]
    if len(neg) > 0:
        ax.scatter(
            neg["x_pos"], neg["neg_log_p"],
            c=neg["color"], marker="v", s=30, alpha=0.8,
            edgecolors="none", zorder=2,
        )

    # n_tests = total OVR tests in the full DataFrame (not just this cluster)
    n_tests = len(df[df["comparison_type"] == "one_vs_rest"])
    _add_threshold_lines(ax, df_plot, n_tests)

    # X-axis: domain center ticks
    if domain_centers:
        ax.set_xticks(list(domain_centers.values()))
        ax.set_xticklabels(list(domain_centers.keys()), rotation=30, ha="right", fontsize=9)

    ax.set_ylabel(r"$-\log_{10}(p)$", fontsize=11)
    ax.set_title(f"PheWAS: Cluster {cluster_label} vs. Rest", fontsize=13, weight="bold")
    ax.legend(fontsize=8, loc="upper right")

    # Labels (must be last)
    _add_labels(ax, df_plot, rename_map=rename_map)

    # Save
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved OVR Manhattan plot to %s", output_path)


def omnibus_plot(
    df: pd.DataFrame,
    domain_config: list[dict],
    output_path: str,
    rename_map: dict[str, str] | None = None,
) -> None:
    """Generate an omnibus Manhattan plot.

    Parameters
    ----------
    df:
        Full corrected results DataFrame.
    domain_config:
        Domain config list from load_domain_config().
    output_path:
        File path for the output PNG.
    rename_map:
        Optional variable-name-to-display-label mapping.
    """
    df_plot = df[df["comparison_type"] == "omnibus"].copy()

    if len(df_plot) == 0:
        logger.warning("No omnibus results; skipping plot.")
        return

    # Compute -log10(p)
    df_plot["neg_log_p"] = -np.log10(df_plot["p_value"].clip(lower=1e-300))

    # Build x positions
    df_plot, domain_centers = _build_x_positions(df_plot, domain_config)

    # Build domain color map
    domain_colors = {d["domain"]: d["color"] for d in domain_config}
    domain_colors.setdefault("Other/Unclassified", "#AAAAAA")
    df_plot["color"] = df_plot["domain"].map(domain_colors)

    # Create figure
    fig, ax = plt.subplots(figsize=(16, 6))

    # Alternating background bands
    domain_order = [d for d in domain_colors if d in domain_centers]
    for i, domain in enumerate(domain_order):
        d_data = df_plot[df_plot["domain"] == domain]
        if len(d_data) == 0:
            continue
        x_min = d_data["x_pos"].min() - 0.5
        x_max = d_data["x_pos"].max() + 0.5
        if i % 2 == 0:
            ax.axvspan(x_min, x_max, color="#f0f0f0", alpha=0.5, zorder=0)

    # Single scatter with circular markers (omnibus has no direction)
    ax.scatter(
        df_plot["x_pos"], df_plot["neg_log_p"],
        c=df_plot["color"], marker="o", s=30, alpha=0.8,
        edgecolors="none", zorder=2,
    )

    # n_tests = number of omnibus tests
    n_tests = len(df_plot)
    _add_threshold_lines(ax, df_plot, n_tests)

    # X-axis: domain center ticks
    if domain_centers:
        ax.set_xticks(list(domain_centers.values()))
        ax.set_xticklabels(list(domain_centers.keys()), rotation=30, ha="right", fontsize=9)

    ax.set_ylabel(r"$-\log_{10}(p)$", fontsize=11)
    ax.set_title("PheWAS: Omnibus Test (All Clusters)", fontsize=13, weight="bold")
    ax.legend(fontsize=8, loc="upper right")

    # Labels (must be last)
    _add_labels(ax, df_plot, rename_map=rename_map)

    # Save
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved omnibus Manhattan plot to %s", output_path)
