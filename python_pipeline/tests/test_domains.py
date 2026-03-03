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
    load_phenotype_metadata,
    _strip_year_suffix,
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


class TestMetadataLookup:
    """Tests for phenotype_metadata.csv integration and year-suffix stripping."""

    def test_metadata_lookup_takes_priority(self, domain_specs):
        """Metadata assignment overrides regex when the variable is in the lookup."""
        # Create a synthetic metadata dict that contradicts regex
        # 'nihtbx_flanker_uncorrected' would normally be Cognition via regex,
        # but if metadata says Substance we should get Substance.
        metadata = {"nihtbx_flanker_uncorrected": {"domain": "Substance", "description": ""}}
        result = assign_domain("nihtbx_flanker_uncorrected", domain_specs, metadata=metadata)
        assert result == "Substance"

    def test_metadata_fallback_to_regex(self, domain_specs):
        """A variable absent from metadata still gets a domain via regex."""
        metadata = {"some_other_var": {"domain": "Cognition", "description": ""}}
        # nihtbx_flanker_agecorrected is not in metadata → should fall through to regex → Cognition
        result = assign_domain("nihtbx_flanker_agecorrected", domain_specs, metadata=metadata)
        assert result == "Cognition"

    def test_load_phenotype_metadata_missing_file(self):
        """load_phenotype_metadata returns empty dict gracefully for a missing file."""
        result = load_phenotype_metadata("/nonexistent/path/metadata.csv")
        assert result == {}

    def test_year_suffix_stripping_3y(self, domain_specs):
        """A _3y-suffixed variable matches the base variable in metadata."""
        metadata = {"stq_y_ss_weekday": {"domain": "Screen Time", "description": ""}}
        result = assign_domain("stq_y_ss_weekday_3y", domain_specs, metadata=metadata)
        assert result == "Screen Time"

    def test_year_suffix_stripping_l(self, domain_specs):
        """A _l-suffixed variable (longitudinal) matches the base variable in metadata."""
        metadata = {"cbcl_scr_syn_total_t": {"domain": "Child Mental Health", "description": ""}}
        result = assign_domain("cbcl_scr_syn_total_t_l", domain_specs, metadata=metadata)
        assert result == "Child Mental Health"

    def test_strip_year_suffix_examples(self):
        """_strip_year_suffix removes known wave suffixes."""
        assert _strip_year_suffix("stq_y_ss_weekday_3y") == "stq_y_ss_weekday"
        assert _strip_year_suffix("cbcl_scr_syn_total_t_l") == "cbcl_scr_syn_total_t"
        assert _strip_year_suffix("nihtbx_flanker_4y") == "nihtbx_flanker"
        # No suffix → unchanged
        assert _strip_year_suffix("nihtbx_flanker_uncorrected") == "nihtbx_flanker_uncorrected"

    def test_assign_domains_to_results_adds_description(self, domain_specs):
        """assign_domains_to_results adds phenotype_description column from metadata."""
        import tempfile, os
        meta_csv = "study_variable,description,domain\nnihtbx_flanker_uncorrected,Flanker test,Cognition\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(meta_csv)
            path = f.name
        try:
            df = pd.DataFrame({"phenotype": ["nihtbx_flanker_uncorrected", "cbcl_scr_syn_total_t"]})
            result = assign_domains_to_results(df, domain_specs, metadata_file=path)
            assert "phenotype_description" in result.columns
            assert result.loc[result["phenotype"] == "nihtbx_flanker_uncorrected",
                               "phenotype_description"].iloc[0] == "Flanker test"
        finally:
            os.unlink(path)
