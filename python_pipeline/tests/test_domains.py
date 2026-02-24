"""Unit tests for domains.py.

Verifies that domain assignment matches the R grepl logic.
"""

import os
import pytest

from python_pipeline.domains import (
    assign_domain,
    assign_domains_to_results,
    get_color_map,
    get_domain_order,
    load_domain_config,
)
import pandas as pd


_DEFAULT_YAML = os.path.join(
    os.path.dirname(__file__), "..", "configs", "domains.yaml"
)


@pytest.fixture(scope="module")
def domain_specs():
    return load_domain_config(_DEFAULT_YAML)


class TestLoadDomainConfig:
    def test_returns_list(self, domain_specs):
        assert isinstance(domain_specs, list)

    def test_eight_domains_loaded(self, domain_specs):
        assert len(domain_specs) == 8

    def test_each_spec_has_required_keys(self, domain_specs):
        for spec in domain_specs:
            assert "name" in spec
            assert "color" in spec
            assert "include_patterns" in spec
            assert "exclude_patterns" in spec


class TestAssignDomain:
    def test_cognition(self, domain_specs):
        assert assign_domain("nihtbx_flanker_agecorrected", domain_specs) == "Cognition"

    def test_screen_time(self, domain_specs):
        assert assign_domain("screen_time_wkdy", domain_specs) == "Screen Time"

    def test_substance(self, domain_specs):
        assert assign_domain("tlfb_alc_use", domain_specs) == "Substance"

    def test_child_mental_health(self, domain_specs):
        assert assign_domain("cbcl_scr_syn_internal_t", domain_specs) == "Child Mental Health"

    def test_physical_health_puberty(self, domain_specs):
        assert assign_domain("pds_score", domain_specs) == "Physical Health"

    def test_family_mental_health(self, domain_specs):
        assert assign_domain("asr_scr_anxdep_t", domain_specs) == "Family Mental Health"

    def test_unclassified_variable(self, domain_specs):
        domain = assign_domain("xyz_totally_unknown_var_12345", domain_specs)
        assert domain == "Unclassified"

    def test_first_match_wins(self, domain_specs):
        # "nihtbx" should hit Cognition before anything else
        result = assign_domain("nihtbx_reading_uncorrected", domain_specs)
        assert result == "Cognition"


class TestAssignDomainsToResults:
    def test_adds_domain_column(self, domain_specs):
        df = pd.DataFrame({"phenotype": ["nihtbx_flanker", "cbcl_scr_syn_total_t"]})
        result = assign_domains_to_results(df, domain_specs)
        assert "domain" in result.columns

    def test_adds_domain_color_column(self, domain_specs):
        df = pd.DataFrame({"phenotype": ["nihtbx_flanker"]})
        result = assign_domains_to_results(df, domain_specs)
        assert "domain_color" in result.columns
        assert result["domain_color"].iloc[0].startswith("#")

    def test_original_df_not_mutated(self, domain_specs):
        df = pd.DataFrame({"phenotype": ["nihtbx_flanker"]})
        original_cols = list(df.columns)
        assign_domains_to_results(df, domain_specs)
        assert list(df.columns) == original_cols


class TestHelpers:
    def test_get_domain_order_length(self, domain_specs):
        order = get_domain_order(domain_specs)
        assert len(order) == len(domain_specs)

    def test_get_color_map_has_unclassified(self, domain_specs):
        cmap = get_color_map(domain_specs)
        assert "Unclassified" in cmap
        assert cmap["Unclassified"] == "#808080"
