from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "app.py"


def test_streamlit_layout_has_no_nested_expanders():
    lines = FRONTEND.read_text().splitlines()
    expander_stack: list[int] = []
    for line_number, line in enumerate(lines, start=1):
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        while expander_stack and indent <= expander_stack[-1]:
            expander_stack.pop()
        if stripped.startswith("with st.expander("):
            assert not expander_stack, f"nested st.expander at frontend/app.py:{line_number}"
            expander_stack.append(indent)


def test_system_monitor_smoke_layout_sections_present():
    source = FRONTEND.read_text()

    assert 'st.header("System Monitor")' in source
    assert 'with st.expander("Scheduled Jobs")' in source
    assert 'with st.expander("Technical Details")' in source
    assert "FRED Connection" in source
    assert "Data Sources & Model Providers" in source
    assert "Scenario Comparison Readiness" in source
    assert "Local Scenario Parser" in source
    assert "Use Rule-Based Fallback" in source
    assert "Reparse Scenario" in source
    assert "Use Parsed Values" in source
    assert "Parser Provider" in source
    assert "Parser Model" in source
    assert "Scenario ID" in source
    assert "Scenario Hash" in source
    assert "Section A - Macro Conditions" in source
    assert "Section B - Risk and Probability" in source
    assert "Section C - Regions and Narrative" in source
    assert "Reset Scenario" in source
    assert "Parsed scenario loaded into controls." in source
    assert "Widget Values Refreshed" in source
    assert "Parse Duration" in source
    assert "Credit stress" in source and "/ 10" in source
    assert "recession_pct / 100" in source
    assert "probability_pct / 100" in source
    assert "Training & Evaluation Controls" in source
    assert "format_dashboard_timestamp" in source
    assert "✓ Connected" in source
    assert "⚠ Fallback" in source
    assert "✗ Error" in source
    assert "○ Untested" in source
