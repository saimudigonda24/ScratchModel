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
    assert "Training & Evaluation Controls" in source
    assert "format_dashboard_timestamp" in source
    assert "✓ Connected" in source
    assert "⚠ Fallback" in source
    assert "✗ Error" in source
    assert "○ Untested" in source
