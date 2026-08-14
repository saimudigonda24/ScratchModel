from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "frontend" / "scenario_state.py"
SPEC = importlib.util.spec_from_file_location("scenario_ui_state_under_test", MODULE_PATH)
assert SPEC and SPEC.loader
scenario_state = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scenario_state)
apply_successful_parse = scenario_state.apply_successful_parse
normalize_scenario_options = scenario_state.normalize_scenario_options


def test_empty_options_response_still_provides_populated_widget_choices():
    options, debug = normalize_scenario_options(None)

    assert len(options["growth_outlook"]) > 0
    assert len(options["inflation_direction"]) > 0
    assert len(options["central_bank_stance"]) > 0
    assert debug["missing_fields"] == []
    assert "growth_outlook" in debug["api_missing_fields"]


def test_parse_response_updates_canonical_scenario_and_widget_version():
    state = {
        "current_scenario": {"parser_provider": "manual", "growth_outlook": "moderate growth"},
        "scenario_widget_version": 4,
        "scenario_parse_status": "Reset scenario loaded.",
    }
    response = {
        "status": "ok",
        "scenario": {
            "scenario_name": "Parsed Scenario",
            "growth_outlook": "slowing growth",
            "parser_provider": "ollama",
            "parser_model": "llama3.1:8b",
            "scenario_id": "scenario_123",
        },
    }

    applied, error = apply_successful_parse(state, response)

    assert applied is True
    assert error is None
    assert state["current_scenario"]["parser_provider"] == "ollama"
    assert state["current_scenario"]["parser_model"] == "llama3.1:8b"
    assert state["scenario_builder"]["growth_outlook"] == "slowing growth"
    assert state["scenario_widget_version"] == 5
    assert state["latest_widget_version_after_assignment"] == 5
    assert state["scenario_parse_status"] == "Parsed scenario loaded into controls."


def test_successful_parse_does_not_trigger_reset_scenario():
    state = {"scenario_widget_version": 0, "scenario_parse_status": "Reset scenario loaded."}
    response = {
        "status": "ok",
        "scenario": {
            "scenario_name": "Live Parsed Scenario",
            "parser_provider": "ollama",
            "parser_model": "llama3.1:8b",
        },
    }

    applied, _ = apply_successful_parse(state, response)

    assert applied is True
    assert state["current_scenario"]["scenario_name"] == "Live Parsed Scenario"
    assert "Reset" not in state["scenario_parse_status"]


def test_parser_failure_preserves_existing_scenario():
    original = {"scenario_name": "Keep Me", "parser_provider": "ollama"}
    state = {"current_scenario": original.copy(), "scenario_widget_version": 2}

    applied, error = apply_successful_parse(
        state,
        {"status": "not_ready", "reason": "ollama_parser_unavailable"},
    )

    assert applied is False
    assert error == "ollama_parser_unavailable"
    assert state["current_scenario"] == original
    assert state["scenario_widget_version"] == 2
