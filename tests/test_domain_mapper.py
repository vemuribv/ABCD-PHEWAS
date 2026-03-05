"""Tests for domain mapper module (DOMN-01, DOMN-02).

Tests cover:
- Correct domain assignment from regex patterns
- Other/Unclassified fallback
- Exactly 8 named domains in YAML
- First-match-wins ordering
- assign_all_domains returning domain map and unclassified list
- Case-insensitive regex matching
"""

import os

import pytest

from abcd_phewas.domain_mapper import assign_all_domains, assign_domain, load_domain_config

# Path to actual domain_mapping.yaml created in Plan 01
YAML_PATH = os.path.join(
    os.path.dirname(__file__), "..", "config", "domain_mapping.yaml"
)


@pytest.fixture
def domain_config():
    """Load the actual YAML config used in the project."""
    return load_domain_config(YAML_PATH)


# ---------------------------------------------------------------------------
# load_domain_config
# ---------------------------------------------------------------------------


def test_load_domain_config_returns_list(domain_config):
    """load_domain_config returns a list of dicts."""
    assert isinstance(domain_config, list)
    assert len(domain_config) > 0


def test_load_domain_config_dict_shape(domain_config):
    """Each domain dict has 'domain', 'color', 'patterns' keys."""
    for entry in domain_config:
        assert "domain" in entry
        assert "color" in entry
        assert "patterns" in entry
        assert isinstance(entry["patterns"], list)


# ---------------------------------------------------------------------------
# test_eight_domains
# ---------------------------------------------------------------------------


def test_eight_domains(domain_config):
    """Config has exactly 8 named domains (Other/Unclassified is the 9th catch-all)."""
    named_domains = [d for d in domain_config if d["domain"] != "Other/Unclassified"]
    assert len(named_domains) == 8, (
        f"Expected 8 named domains, got {len(named_domains)}: "
        f"{[d['domain'] for d in named_domains]}"
    )


def test_domain_names_match_r_codebase(domain_config):
    """Domain names must exactly match the R codebase names."""
    expected_names = {
        "Cognition",
        "Screen Time",
        "Demographics",
        "Substance",
        "Culture/Environment",
        "Physical Health",
        "Family Mental Health",
        "Child Mental Health",
    }
    actual_names = {d["domain"] for d in domain_config if d["domain"] != "Other/Unclassified"}
    assert actual_names == expected_names, (
        f"Domain name mismatch. Missing: {expected_names - actual_names}, "
        f"Extra: {actual_names - expected_names}"
    )


# ---------------------------------------------------------------------------
# assign_domain — specific variable -> domain assignments
# ---------------------------------------------------------------------------


def test_domain_assignment_cognition(domain_config):
    """nihtbx_flanker -> Cognition with darkorange1 color."""
    domain, color = assign_domain("nihtbx_flanker_uncorrected", domain_config)
    assert domain == "Cognition"
    assert color == "#FF7F00"


def test_domain_assignment_child_mental_health(domain_config):
    """cbcl_scr_syn_totprob -> Child Mental Health."""
    domain, color = assign_domain("cbcl_scr_syn_totprob_t", domain_config)
    assert domain == "Child Mental Health"
    assert color == "#00008B"


def test_domain_assignment_screen_time(domain_config):
    """stq_y_ss_weekday -> Screen Time."""
    domain, color = assign_domain("stq_y_ss_weekday", domain_config)
    assert domain == "Screen Time"


def test_domain_assignment_demographics(domain_config):
    """demo_sex_v2 -> Demographics."""
    domain, color = assign_domain("demo_sex_v2", domain_config)
    assert domain == "Demographics"


def test_domain_assignment_substance(domain_config):
    """tlfb_alc -> Substance."""
    domain, color = assign_domain("tlfb_alc", domain_config)
    assert domain == "Substance"


def test_domain_assignment_physical_health(domain_config):
    """anthro_bmi_calc -> Physical Health."""
    domain, color = assign_domain("anthro_bmi_calc", domain_config)
    assert domain == "Physical Health"


def test_domain_assignment_family_mental_health(domain_config):
    """asr_scr_totprob_r -> Family Mental Health."""
    domain, color = assign_domain("asr_scr_totprob_r", domain_config)
    assert domain == "Family Mental Health"


# ---------------------------------------------------------------------------
# test_unclassified_fallback
# ---------------------------------------------------------------------------


def test_unclassified_fallback(domain_config):
    """Completely unknown variable -> Other/Unclassified with gray color."""
    domain, color = assign_domain("unknown_variable_xyz_qrs", domain_config)
    assert domain == "Other/Unclassified"
    assert color == "#AAAAAA"


# ---------------------------------------------------------------------------
# test_case_insensitive
# ---------------------------------------------------------------------------


def test_case_insensitive_upper(domain_config):
    """NIHTBX_FLANKER (all caps) matches Cognition pattern 'nihtbx'."""
    domain, _ = assign_domain("NIHTBX_FLANKER", domain_config)
    assert domain == "Cognition"


def test_case_insensitive_mixed(domain_config):
    """NiHtBx_flanker (mixed case) matches Cognition."""
    domain, _ = assign_domain("NiHtBx_flanker", domain_config)
    assert domain == "Cognition"


# ---------------------------------------------------------------------------
# test_first_match_wins
# ---------------------------------------------------------------------------


def test_first_match_wins(domain_config):
    """Variable matching multiple patterns gets assigned to first-matching domain.

    Craft a variable name that could match both 'nihtbx' (Cognition, position 0)
    and a later domain pattern — should be assigned to Cognition.
    """
    # nihtbx_stq would match both nihtbx (Cognition) and stq (Screen Time)
    # First match wins -> Cognition
    domain, _ = assign_domain("nihtbx_stq_score", domain_config)
    assert domain == "Cognition"


# ---------------------------------------------------------------------------
# assign_all_domains
# ---------------------------------------------------------------------------


def test_assign_all_domains_returns_tuple(domain_config):
    """assign_all_domains returns a tuple of (dict, list)."""
    cols = ["nihtbx_flanker", "cbcl_total", "unknown_var"]
    result = assign_all_domains(cols, domain_config)
    assert isinstance(result, tuple)
    assert len(result) == 2
    domain_map, unclassified = result
    assert isinstance(domain_map, dict)
    assert isinstance(unclassified, list)


def test_assign_all_domains_maps_all_columns(domain_config):
    """Every input column appears in the domain_map."""
    cols = ["nihtbx_flanker", "cbcl_total", "unknown_xyz", "demo_age"]
    domain_map, _ = assign_all_domains(cols, domain_config)
    assert set(domain_map.keys()) == set(cols)


def test_assign_all_domains_unclassified_list(domain_config):
    """Unclassified variables are reported separately."""
    cols = ["nihtbx_flanker", "unknown_var_abc", "another_mystery_col", "cbcl_total"]
    domain_map, unclassified = assign_all_domains(cols, domain_config)
    assert "unknown_var_abc" in unclassified
    assert "another_mystery_col" in unclassified
    # Classified variables NOT in unclassified list
    assert "nihtbx_flanker" not in unclassified
    assert "cbcl_total" not in unclassified


def test_assign_all_domains_values_are_tuples(domain_config):
    """Each value in domain_map is a (domain_name, hex_color) tuple."""
    cols = ["nihtbx_flanker", "cbcl_total"]
    domain_map, _ = assign_all_domains(cols, domain_config)
    for col, value in domain_map.items():
        assert isinstance(value, tuple)
        assert len(value) == 2
        domain_name, color = value
        assert isinstance(domain_name, str)
        assert color.startswith("#")
