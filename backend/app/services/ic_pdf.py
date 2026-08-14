from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


OUTPUT_DIR = Path(__file__).resolve().parents[3] / "output" / "pdf"


def generate_ic_pdf(outlook: dict[str, Any], output_path: Path | None = None) -> bytes:
    """Create a manager-ready static PDF without application controls."""
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer, pagesize=letter, leftMargin=0.55 * inch, rightMargin=0.55 * inch,
        topMargin=0.6 * inch, bottomMargin=0.55 * inch,
        title=f"HCP Investment Committee Report - {outlook.get('run_id', '')}",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="HCPTitle", parent=styles["Title"], alignment=TA_CENTER,
        textColor=colors.HexColor("#17324D"), fontSize=19, leading=23, spaceAfter=12,
    ))
    styles.add(ParagraphStyle(
        name="HCPSection", parent=styles["Heading2"], textColor=colors.HexColor("#17324D"),
        fontSize=12, leading=15, spaceBefore=10, spaceAfter=6,
    ))
    body = styles["BodyText"]
    body.fontSize = 8.5
    body.leading = 11
    story = [
        Paragraph("HCP Macro Theme AI", styles["HCPTitle"]),
        Paragraph("Investment Committee Research Report", styles["Heading1"]),
        Paragraph(f"Run: {_safe(outlook.get('run_id'))} | Date: {_safe(outlook.get('run_date'))}", body),
        Paragraph(_safe(outlook.get("disclaimer")), body),
        Spacer(1, 10),
        Paragraph("Executive Summary", styles["HCPSection"]),
        Paragraph(_safe(outlook.get("executive_outlook")), body),
    ]
    scenario = outlook.get("scenario_definition", {})
    story.extend([
        Paragraph("Scenario / Initial Conditions", styles["HCPSection"]),
        _key_value_table([
            ("Theme", scenario.get("name")), ("Growth", scenario.get("growth_outlook")),
            ("Growth Surprise", scenario.get("growth_surprise")),
            ("Inflation", scenario.get("inflation_outlook")),
            ("Inflation Surprise", scenario.get("inflation_surprise")),
            ("Expected Fed Response", scenario.get("expected_fed_response")),
            ("Fed Position", scenario.get("fed_position")), ("Horizon", scenario.get("time_horizon")),
        ]),
        Paragraph("Historical Analogs", styles["HCPSection"]),
        _rows_table(
            outlook.get("historical_analogs", [])[:5],
            [("Period", "period"), ("Similarity", "similarity_score"), ("Weight", "analog_weight"), ("Why It Matters", "why_it_matters")],
        ),
        Paragraph("Expected Asset-Class Performance", styles["HCPSection"]),
        _rows_table(
            outlook.get("expected_asset_class_performance", [])[:18],
            [("Asset", "subsegment"), ("Outlook", "outlook"), ("Conviction", "conviction"), ("Driver", "primary_macro_driver")],
        ),
        PageBreak(),
        Paragraph("Suggested Portfolio", styles["HCPSection"]),
        Paragraph("Long / Overweight", styles["Heading3"]),
        _rows_table(
            outlook.get("suggested_portfolio", {}).get("long_overweight", []),
            [("Subsegment", "subsegment"), ("Direction", "direction"), ("Conviction", "conviction"), ("Why Now", "why_now"), ("Proxy*", "tracking_benchmark_proxy")],
        ),
        Paragraph("Short / Underweight", styles["Heading3"]),
        _rows_table(
            outlook.get("suggested_portfolio", {}).get("short_underweight", []),
            [("Subsegment", "subsegment"), ("Direction", "direction"), ("Conviction", "conviction"), ("Risk", "main_risk"), ("Proxy*", "tracking_benchmark_proxy")],
        ),
        Paragraph("* Proxies are for paper tracking only; recommendations are asset-class/subsegment views.", body),
        Paragraph("Unexpected / Non-Consensus Opportunities", styles["HCPSection"]),
        _rows_table(
            outlook.get("unexpected_opportunities", []),
            [("Subsegment", "subsegment"), ("Why Surfaced", "why_model_surfaced_it"), ("What Makes It Wrong", "what_would_make_it_wrong")],
        ),
        Paragraph("Risks and Invalidation", styles["HCPSection"]),
        _rows_table(
            outlook.get("risk_register", []),
            [("Risk", "risk"), ("Impact", "impact"), ("Warning", "early_warning_indicator")],
        ),
        Paragraph("Investment Committee Decisions", styles["HCPSection"]),
        Paragraph(_safe(outlook.get("decisions_for_investment_committee")), body),
    ])
    evolution = outlook.get("portfolio_evolution")
    if evolution:
        story.extend([
            PageBreak(), Paragraph("12-Month Portfolio Evolution", styles["HCPSection"]),
            _rows_table(
                evolution.get("portfolio_changes", []),
                [("From", "from_phase"), ("To", "to_phase"), ("Added", "positions_added"), ("Removed", "positions_removed"), ("Direction Changes", "direction_changes")],
            ),
        ])
    document.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    data = buffer.getvalue()
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(data)
    return data


def save_ic_pdf(outlook: dict[str, Any]) -> Path:
    path = OUTPUT_DIR / f"{outlook.get('run_id', 'hcp_ic_report')}.pdf"
    generate_ic_pdf(outlook, path)
    return path


def _safe(value: Any) -> str:
    if value is None or value == "":
        return "Not available."
    if isinstance(value, (list, tuple)):
        return "; ".join(_safe(item) for item in value)
    if isinstance(value, dict):
        return "; ".join(f"{key}: {_safe(item)}" for key, item in value.items())
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _key_value_table(rows: list[tuple[str, Any]]) -> Table:
    data = [[Paragraph(str(key), getSampleStyleSheet()["BodyText"]), Paragraph(_safe(value), getSampleStyleSheet()["BodyText"])] for key, value in rows]
    table = Table(data, colWidths=[1.45 * inch, 5.4 * inch])
    table.setStyle(_table_style())
    return table


def _rows_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> Table:
    styles = getSampleStyleSheet()
    if not rows:
        return Table([[Paragraph("No evidence-qualified items available.", styles["BodyText"])]], colWidths=[6.85 * inch])
    data = [[Paragraph(label, styles["BodyText"]) for label, _ in columns]]
    for row in rows:
        data.append([Paragraph(_safe(row.get(key)), styles["BodyText"]) for _, key in columns])
    widths = [6.85 * inch / len(columns)] * len(columns)
    table = Table(data, colWidths=widths, repeatRows=1)
    table.setStyle(_table_style())
    return table


def _table_style() -> TableStyle:
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DDE8F0")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#17324D")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#AAB7C4")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])


def _page_footer(canvas, document) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#596B7C"))
    canvas.drawString(0.55 * inch, 0.3 * inch, "HCP Research - Human review required - No trade execution")
    canvas.drawRightString(7.95 * inch, 0.3 * inch, f"Page {document.page}")
    canvas.restoreState()
