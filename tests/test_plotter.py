"""Smoke tests for Manhattan-style PheWAS plotting functions."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from abcd_phewas.plotter import manhattan_plot, omnibus_plot


def _make_synthetic_corrected_df() -> pd.DataFrame:
    """Create a synthetic corrected DataFrame with ~30 rows across 3 domains."""
    rng = np.random.RandomState(42)

    domains = ["Neurocognition", "Mental Health", "Physical Health"]
    domain_colors = {"Neurocognition": "#E41A1C", "Mental Health": "#377EB8", "Physical Health": "#4DAF4A"}

    rows = []
    idx = 0
    for domain in domains:
        for i in range(5):
            var_name = f"{domain.lower().replace(' ', '_')}_var_{i}"
            # OVR rows for cluster 1 and cluster 2
            for cluster in ["Cluster_1", "Cluster_2"]:
                p = rng.uniform(0.0001, 0.5)
                es = rng.uniform(-1.0, 1.0)
                rows.append({
                    "variable": var_name,
                    "domain": domain,
                    "comparison_type": "one_vs_rest",
                    "cluster_label": cluster,
                    "test_used": "welch_t",
                    "statistic": rng.uniform(-3, 3),
                    "p_value": p,
                    "effect_size": es,
                    "effect_size_type": "cohens_d",
                    "ci_lower": es - 0.3,
                    "ci_upper": es + 0.3,
                    "n_target": 200,
                    "n_rest": 800,
                    "missingness_rate": rng.uniform(0, 0.1),
                    "fdr_q_global": min(p * 5, 1.0),
                    "bonf_p_global": min(p * 30, 1.0),
                    "fdr_q_domain": min(p * 3, 1.0),
                    "bonf_p_domain": min(p * 10, 1.0),
                })
                idx += 1

            # Omnibus row
            p_omni = rng.uniform(0.001, 0.8)
            rows.append({
                "variable": var_name,
                "domain": domain,
                "comparison_type": "omnibus",
                "cluster_label": np.nan,
                "test_used": "kruskal_wallis",
                "statistic": rng.uniform(0, 15),
                "p_value": p_omni,
                "effect_size": rng.uniform(0, 0.3),
                "effect_size_type": "epsilon_squared",
                "ci_lower": np.nan,
                "ci_upper": np.nan,
                "n_target": 1000,
                "n_rest": 0,
                "missingness_rate": rng.uniform(0, 0.1),
                "fdr_q_global": min(p_omni * 5, 1.0),
                "bonf_p_global": min(p_omni * 15, 1.0),
                "fdr_q_domain": min(p_omni * 3, 1.0),
                "bonf_p_domain": min(p_omni * 10, 1.0),
            })

    df = pd.DataFrame(rows)

    # Make a few hits very significant (Bonferroni-passing)
    sig_mask = df.index[:3]
    df.loc[sig_mask, "p_value"] = 1e-8
    df.loc[sig_mask, "fdr_q_global"] = 1e-6
    df.loc[sig_mask, "bonf_p_global"] = 1e-5

    # Add one NaN p-value row
    df.loc[df.index[-1], "p_value"] = np.nan

    return df


def _make_domain_config() -> list[dict]:
    """Create a minimal domain config matching the synthetic data."""
    return [
        {"domain": "Neurocognition", "color": "#E41A1C", "patterns": ["neurocog"]},
        {"domain": "Mental Health", "color": "#377EB8", "patterns": ["mental"]},
        {"domain": "Physical Health", "color": "#4DAF4A", "patterns": ["physical"]},
    ]


class TestManhattanPlot:
    """Tests for OVR manhattan_plot()."""

    def test_ovr_manhattan_creates_png(self, tmp_path):
        df = _make_synthetic_corrected_df()
        domain_config = _make_domain_config()
        out = tmp_path / "manhattan_cluster1.png"

        manhattan_plot(df, "Cluster_1", domain_config, str(out))

        assert out.exists()
        assert out.stat().st_size > 0

        # Verify DPI
        from PIL import Image
        img = Image.open(out)
        dpi = img.info.get("dpi", (72, 72))
        assert abs(dpi[0] - 300) < 1, f"Expected ~300 DPI, got {dpi[0]}"

    def test_ovr_uses_triangle_markers(self, tmp_path):
        """Verify plot completes with both positive and negative effect sizes."""
        df = _make_synthetic_corrected_df()
        domain_config = _make_domain_config()
        out = tmp_path / "manhattan_triangles.png"

        # Ensure mix of positive and negative effect sizes
        assert (df[df["comparison_type"] == "one_vs_rest"]["effect_size"] > 0).any()
        assert (df[df["comparison_type"] == "one_vs_rest"]["effect_size"] < 0).any()

        manhattan_plot(df, "Cluster_1", domain_config, str(out))
        assert out.exists()

    def test_no_significant_hits_no_crash(self, tmp_path):
        """Plot should still render when no results pass any threshold."""
        df = _make_synthetic_corrected_df()
        domain_config = _make_domain_config()

        # Make all p-values non-significant
        df["p_value"] = 0.9
        df["fdr_q_global"] = 1.0
        df["bonf_p_global"] = 1.0

        out = tmp_path / "manhattan_nosig.png"
        manhattan_plot(df, "Cluster_1", domain_config, str(out))

        assert out.exists()
        assert out.stat().st_size > 0


class TestOmnibusPlot:
    """Tests for omnibus_plot()."""

    def test_omnibus_manhattan_creates_png(self, tmp_path):
        df = _make_synthetic_corrected_df()
        domain_config = _make_domain_config()
        out = tmp_path / "omnibus.png"

        omnibus_plot(df, domain_config, str(out))

        assert out.exists()
        assert out.stat().st_size > 0

        # Verify DPI
        from PIL import Image
        img = Image.open(out)
        dpi = img.info.get("dpi", (72, 72))
        assert abs(dpi[0] - 300) < 1, f"Expected ~300 DPI, got {dpi[0]}"

    def test_omnibus_no_significant_hits(self, tmp_path):
        """Omnibus plot renders even with no significant hits."""
        df = _make_synthetic_corrected_df()
        domain_config = _make_domain_config()

        omni_mask = df["comparison_type"] == "omnibus"
        df.loc[omni_mask, "p_value"] = 0.9
        df.loc[omni_mask, "fdr_q_global"] = 1.0
        df.loc[omni_mask, "bonf_p_global"] = 1.0

        out = tmp_path / "omnibus_nosig.png"
        omnibus_plot(df, domain_config, str(out))

        assert out.exists()
        assert out.stat().st_size > 0
