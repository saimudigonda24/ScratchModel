import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.database import list_scenario_recommendations
from app.services.scenario_lab import (
    MacroScenario,
    create_demo_three_phase_sequence,
    create_or_update_scenario_sequence,
    cross_asset_historical_performance,
    generate_phase_postmortem,
    generate_scenario_recommendations,
    identify_historical_analogs,
    save_phase,
    scenario_comparison_matrix,
)


def _scenario() -> dict:
    return MacroScenario(
        scenario_name="Inflation surprise with strong growth",
        scenario_date="2026-07-19",
        growth_direction="strong",
        inflation_direction="rising",
        inflation_surprise="higher",
        central_bank_policy_stance="delayed_tightening",
        expected_policy_path="gradual_then_faster",
        central_bank_curve_position="behind",
        labor_market_conditions="tight",
        financial_conditions="easy",
        fiscal_conditions="expansionary",
        recession_probability=0.25,
        scenario_duration="6-12 months",
        probability=0.55,
        conviction=7.0,
        invalidation_triggers=["Inflation rolls over", "Labor weakens"],
    ).__dict__


def test_scenario_phase_linking_and_analogs():
    sequence = create_or_update_scenario_sequence("Scenario Lab Test", "Test sequence")
    phase = save_phase(sequence["sequence_id"], 1, _scenario(), data_snapshot={"as_of": "2026-07-19"})

    analogs = identify_historical_analogs(phase)

    assert phase["sequence_id"] == sequence["sequence_id"]
    assert analogs["ranked_historical_analogs"]
    assert analogs["ranked_historical_analogs"][0]["similarity_score"] > 0
    assert analogs["ranked_historical_analogs"][0]["important_differences"]


def test_cross_asset_performance_and_recommendations_are_frozen():
    sequence = create_or_update_scenario_sequence("Scenario Recommendation Test", "Test sequence")
    phase = save_phase(sequence["sequence_id"], 1, _scenario(), data_snapshot={"point_in_time_only": "2026-07-19"})
    analogs = identify_historical_analogs(phase)
    performance = cross_asset_historical_performance(analogs["ranked_historical_analogs"])
    recommendations = generate_scenario_recommendations(phase, analogs)
    stored = list_scenario_recommendations(phase["phase_id"])

    assert performance["rows"]
    assert performance["summary"]
    assert recommendations["ranked_recommendations"]
    assert stored
    assert stored[0]["frozen_snapshot"]["scenario"]["scenario_name"] == phase["scenario"]["scenario_name"]


def test_scenario_comparison_postmortem_and_demo_sequence():
    demo = create_demo_three_phase_sequence()
    first_phase = demo["phases"][0]["phase"]
    postmortem = generate_phase_postmortem(first_phase["phase_id"])
    matrix = scenario_comparison_matrix()

    assert len(demo["phases"]) == 3
    assert demo["phases"][0]["analogs"]["ranked_historical_analogs"]
    assert demo["phases"][1]["recommendations"]["ranked_recommendations"]
    assert demo["phases"][2]["cross_asset_performance"]["summary"]
    assert "what_model_got_right" in postmortem
    assert matrix["matrix"]
