"""Visualizations for the ABCD Cluster-Based PheWAS Pipeline.

Three plot types, faithful to the R ggplot2 outputs in PheWAS Analyses Resub5.Rmd:

1. plot_manhattan  — PheWAS Manhattan plot (-log10 p by phenotype, domain-colored)
2. plot_forest     — Effect-size forest plot for significant phenotypes
3. plot_stacked_bar — Domain breakdown of significant hits per cluster contrast
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")  # non-interactive backend — safe in parallel workers
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

try:
    from adjustText import adjust_text as _adjust_text
    _ADJUST_TEXT_AVAILABLE = True
except ImportError:
    _ADJUST_TEXT_AVAILABLE = False

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #

def _ensure_dir(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def _sort_by_domain(
    results_df: pd.DataFrame,
    domain_order: list[str],
) -> pd.DataFrame:
    """Sort DataFrame by domain order then by phenotype name within each domain."""
    domain_cat = pd.Categorical(
        results_df["domain"],
        categories=domain_order + ["Unclassified"],
        ordered=True,
    )
    results_df = results_df.copy()
    results_df["_domain_order"] = domain_cat.codes
    results_df = (
        results_df
        .sort_values(["_domain_order", "phenotype"])
        .drop(columns=["_domain_order"])
        .reset_index(drop=True)
    )
    return results_df


# --------------------------------------------------------------------------- #
# 1. Manhattan plot
# --------------------------------------------------------------------------- #

def plot_manhattan(
    results_df: pd.DataFrame,
    cluster_contrast: str,
    domain_specs: list[dict],
    output_path: str,
    pval_col: str = "pval",
    fdr_col: str = "pval_fdr",
    bonferroni_n: Optional[int] = None,
    title: str = "Cluster PheWAS",
    subtitle: str = "",
    figsize: tuple[float, float] = (12, 5),
    point_size: float = 18.0,
    label_fdr_threshold: float = 0.05,
    dpi: int = 300,
) -> None:
    """PheWAS Manhattan-style scatter plot.

    X-axis: phenotypes sorted by domain order (with domain labels at midpoints).
    Y-axis: -log10(raw p-value).
    Color:  by domain (8-color scheme from domain_specs).
    Shape:  ▲ (triangle-up) for beta > 0, ▽ (triangle-down) for beta ≤ 0.
    Labels: variable names for FDR-significant phenotypes (adjustText).
    Line:   dashed coral horizontal at Bonferroni threshold.

    Mirrors R's Compulsive_Plot_Finala/b outputs.

    Parameters
    ----------
    results_df : pd.DataFrame
        Pre-filtered to a single cluster_contrast.
        Required columns: phenotype, domain, domain_color, beta, pval, pval_fdr.
    cluster_contrast : str
        Label for title / filename (e.g., "cluster_2_vs_cluster_0").
    domain_specs : list[dict]
        Ordered domain definitions from load_domain_config().
    output_path : str
        PNG save path.
    pval_col : str
        Raw p-value column name.
    fdr_col : str
        FDR-adjusted p-value column name (used for labelling).
    bonferroni_n : Optional[int]
        Denominator for Bonferroni threshold line.  Defaults to len(results_df).
    title, subtitle : str
        Plot title strings.
    figsize : tuple
    point_size : float
    label_fdr_threshold : float
        Label phenotypes with FDR < this value.
    dpi : int
    """
    _ensure_dir(output_path)

    domain_order = [spec["name"] for spec in domain_specs]
    color_map: dict[str, str] = {spec["name"]: spec["color"] for spec in domain_specs}
    color_map["Unclassified"] = "#808080"

    df = _sort_by_domain(results_df.copy(), domain_order)
    df["x_pos"] = range(len(df))
    df["neg_log_p"] = -np.log10(df[pval_col].clip(lower=1e-300))
    df["direction"] = df["beta"].apply(lambda b: "^" if (not np.isnan(b) and b > 0) else "v")

    fig, ax = plt.subplots(figsize=figsize)

    # Plot points by domain (separate scatter call per domain for legend)
    legend_handles: list[mpatches.Patch] = []
    for spec in domain_specs + [{"name": "Unclassified", "color": "#808080"}]:
        domain_name = spec["name"]
        color = spec["color"] if isinstance(spec, dict) and "color" in spec else "#808080"
        sub = df[df["domain"] == domain_name]
        if sub.empty:
            continue

        for direction, marker in [("^", "^"), ("v", "v")]:
            d = sub[sub["direction"] == direction]
            if d.empty:
                continue
            ax.scatter(
                d["x_pos"], d["neg_log_p"],
                c=color, marker=marker, s=point_size,
                linewidths=0, alpha=0.85, zorder=3,
            )

        legend_handles.append(
            mpatches.Patch(color=color, label=domain_name)
        )

    # FDR labels
    sig_mask = df[fdr_col].notna() & (df[fdr_col] < label_fdr_threshold)
    sig = df[sig_mask]
    texts = []
    for _, row in sig.iterrows():
        texts.append(
            ax.text(
                row["x_pos"], row["neg_log_p"],
                row["phenotype"],
                fontsize=4.5, ha="center", va="bottom",
                color=row.get("domain_color", "#333333"),
            )
        )
    if texts:
        if _ADJUST_TEXT_AVAILABLE:
            try:
                _adjust_text(
                    texts, ax=ax,
                    arrowprops=dict(arrowstyle="-", color="gray", lw=0.4),
                    expand_points=(1.2, 1.4),
                )
            except Exception:
                pass  # adjustText occasionally fails; labels still plotted

    # Bonferroni threshold line
    n = bonferroni_n or len(df)
    bonf_y = -math.log10(0.05 / max(n, 1))
    ax.axhline(
        bonf_y, color="#CD5C5C", linestyle="--", linewidth=0.9,
        label=f"Bonferroni (n={n})", zorder=2,
    )

    # Domain x-axis labels at midpoints
    for spec in domain_specs:
        domain_name = spec["name"]
        domain_rows = df[df["domain"] == domain_name]
        if domain_rows.empty:
            continue
        mid = domain_rows["x_pos"].median()
        ax.text(
            mid, -bonf_y * 0.08,
            domain_name,
            ha="center", va="top",
            fontsize=5.5, color=spec["color"],
            rotation=30,
            transform=ax.transData,
        )

    ax.axhline(0, color="black", linewidth=0.5, zorder=1)
    ax.set_xlim(-1, len(df) + 1)
    y_max = max(df["neg_log_p"].max() * 1.15, bonf_y * 1.3)
    ax.set_ylim(-bonf_y * 0.20, y_max)
    ax.set_ylabel("-log\u2081\u2080(p)", fontsize=9, fontweight="bold")
    ax.set_xlabel("")
    full_title = f"{title}  |  {cluster_contrast}"
    if subtitle:
        full_title += f"\n{subtitle}"
    ax.set_title(full_title, fontsize=9, fontweight="bold")
    ax.set_xticks([])

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_visible(False)

    # Legend (right side, small)
    ax.legend(
        handles=legend_handles,
        loc="upper right",
        fontsize=5,
        framealpha=0.7,
        ncol=2,
        handlelength=0.8,
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    logger.info("Manhattan plot saved: %s", output_path)


# --------------------------------------------------------------------------- #
# 2. Forest plot
# --------------------------------------------------------------------------- #

def plot_forest(
    results_df: pd.DataFrame,
    cluster_contrast: str,
    output_path: str,
    significance_col: str = "pval_fdr",
    significance_threshold: float = 0.05,
    max_phenotypes: int = 50,
    figsize: tuple[float, float] = (8, 10),
    dpi: int = 300,
) -> None:
    """Forest plot of effect sizes with 95% CI for significant phenotypes.

    Points are colored by domain and sorted by beta (descending).
    A vertical line at 0 marks the null effect.

    Parameters
    ----------
    results_df : pd.DataFrame
        Pre-filtered to a single cluster_contrast.
        Required columns: phenotype, beta, se, domain, domain_color, significance_col.
    cluster_contrast : str
    output_path : str
    significance_col : str
    significance_threshold : float
    max_phenotypes : int
        Limit rows to keep the plot readable.
    figsize : tuple
    dpi : int
    """
    _ensure_dir(output_path)

    sig = results_df[
        results_df[significance_col].notna()
        & (results_df[significance_col] < significance_threshold)
        & results_df["beta"].notna()
    ].copy()

    if sig.empty:
        logger.info(
            "No significant phenotypes for %s — skipping forest plot.", cluster_contrast
        )
        return

    sig = sig.sort_values("beta", ascending=False).head(max_phenotypes).reset_index(drop=True)
    sig["ci_low"] = sig["beta"] - 1.96 * sig["se"]
    sig["ci_high"] = sig["beta"] + 1.96 * sig["se"]

    # Dynamic figure height
    n = len(sig)
    height = max(figsize[1], n * 0.28 + 1.5)
    fig, ax = plt.subplots(figsize=(figsize[0], height))

    for i, row in sig.iterrows():
        color = row.get("domain_color", "#333333") or "#333333"
        ax.errorbar(
            row["beta"], i,
            xerr=[[row["beta"] - row["ci_low"]], [row["ci_high"] - row["beta"]]],
            fmt="o",
            color=color,
            capsize=3,
            markersize=5,
            linewidth=1.0,
            elinewidth=0.8,
        )

    ax.axvline(0, color="black", linewidth=0.8, linestyle="-", zorder=1)
    ax.set_yticks(range(n))
    ax.set_yticklabels(sig["phenotype"].tolist(), fontsize=7)
    ax.invert_yaxis()  # largest effect at top

    ax.set_xlabel("Beta (Effect Size, 95% CI)", fontsize=9, fontweight="bold")
    ax.set_title(
        f"Forest Plot: {cluster_contrast}\n(FDR < {significance_threshold})",
        fontsize=10, fontweight="bold",
    )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.tight_layout()
    plt.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    logger.info("Forest plot saved: %s", output_path)


# --------------------------------------------------------------------------- #
# 3. Stacked bar plot
# --------------------------------------------------------------------------- #

def plot_stacked_bar(
    results_df: pd.DataFrame,
    domain_specs: list[dict],
    output_path: str,
    significance_col: str = "pval_fdr",
    significance_threshold: float = 0.05,
    figsize: tuple[float, float] = (11, 5),
    dpi: int = 300,
) -> None:
    """Grouped bar chart of significant phenotype counts per domain per contrast.

    X-axis: domain categories (in canonical order).
    Y-axis: count of FDR-significant phenotypes.
    Bar color: one color per cluster contrast.

    Parameters
    ----------
    results_df : pd.DataFrame
        Combined results across all cluster contrasts.
        Required columns: phenotype, domain, cluster_contrast, significance_col.
    domain_specs : list[dict]
    output_path : str
    significance_col : str
    significance_threshold : float
    figsize : tuple
    dpi : int
    """
    _ensure_dir(output_path)

    domain_order = [spec["name"] for spec in domain_specs]

    sig = results_df[
        results_df[significance_col].notna()
        & (results_df[significance_col] < significance_threshold)
    ].copy()

    if sig.empty:
        logger.info("No significant phenotypes — skipping stacked bar plot.")
        return

    pivot = (
        sig
        .groupby(["cluster_contrast", "domain"])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=domain_order, fill_value=0)
    )

    n_contrasts = len(pivot)
    colors = plt.cm.tab10(np.linspace(0, 0.9, n_contrasts))  # type: ignore[attr-defined]

    fig, ax = plt.subplots(figsize=figsize)
    x = np.arange(len(domain_order))
    bar_width = 0.8 / max(n_contrasts, 1)

    for i, (contrast, row) in enumerate(pivot.iterrows()):
        offset = (i - n_contrasts / 2 + 0.5) * bar_width
        ax.bar(
            x + offset, row.values,
            width=bar_width * 0.9,
            label=contrast,
            color=colors[i],
        )

    ax.set_xticks(x)
    ax.set_xticklabels(domain_order, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel(f"# Significant Phenotypes (FDR < {significance_threshold})", fontsize=9)
    ax.set_title(
        "Significant Phenotypes by Domain and Cluster Contrast",
        fontsize=10, fontweight="bold",
    )
    ax.legend(title="Cluster Contrast", fontsize=8, title_fontsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.tight_layout()
    plt.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    logger.info("Stacked bar plot saved: %s", output_path)
