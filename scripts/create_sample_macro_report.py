"""Create a realistic sample HCP macro report for workflow testing."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "reports" / "raw" / "sample_macro_report.md"

SAMPLE_REPORT = """# HCP Sample Macro Report

## 7-14 Month Outlook

My base case for the next 7-14 months is a slower but still positive growth
environment. The cycle is late enough that monetary tightening should continue
to bite, but household and corporate balance sheets do not yet point to an
immediate deep recession. The investment implication is to look for assets that
can benefit from disinflation and policy optionality while keeping explicit
hedges against a growth accident.

## U.S. Growth View

U.S. real growth should cool toward below-trend levels. Consumer demand is
likely to soften as excess savings fade, credit availability tightens, and
labor income growth normalizes. I do not yet see enough evidence for a severe
contraction, but the margin of safety is narrowing. The most important growth
signals to watch are payroll breadth, continuing claims, ISM new orders, credit
spreads, and bank lending standards.

## U.S. Inflation View

Inflation should continue to decelerate unevenly. Goods inflation has already
cooled, shelter should gradually contribute less, and wage growth should slow
if the labor market normalizes. The main risk is sticky services inflation that
keeps real policy rates restrictive for longer than markets expect.

## Central Bank Reaction Function

The Federal Reserve is likely to become more two-sided. If inflation keeps
falling and labor cools gradually, the Fed can shift from fighting inflation
toward preserving the expansion. If inflation re-accelerates, the Fed will need
to keep policy tight and risk a sharper growth slowdown. Other developed-market
central banks may follow similar paths, but timing will depend on local wage
dynamics, currency pressure, and fiscal policy.

## Global Country Overlays

- Europe: weak growth and disinflation make policy easing more likely, but
  energy and fiscal risks remain important.
- Japan: policy normalization is possible, but the path should be gradual
  unless wage and inflation data surprise higher.
- China: domestic demand remains uneven, and policy support may stabilize
  activity without creating a powerful global reflation impulse.
- Emerging markets: selected countries with credible disinflation and real
  yields may benefit if the dollar softens.

## Risks To The Thesis

- Core inflation re-accelerates for multiple months.
- Labor-market cooling becomes a layoff cycle.
- Credit spreads widen sharply or bank lending tightens abruptly.
- Fiscal supply pressure pushes long rates higher despite slower growth.
- Geopolitical shocks raise energy prices and hurt consumer real income.

## Assets I Think Could Benefit

- Intermediate-duration high-quality fixed income if inflation cools and policy
  optionality increases.
- Quality equities with pricing power and resilient balance sheets.
- Select non-U.S. currencies if U.S. growth exceptionalism fades.
- Gold as a hedge against lower real rates, policy credibility risk, or
  geopolitical stress.
- Market-neutral and relative-value alternatives if dispersion stays elevated.
- Select REITs and MLPs only where balance sheets, coverage, and refinancing
  risks are manageable.

## What Would Change My Mind

I would reduce confidence in this thesis if core inflation re-accelerates, if
the unemployment rate rises quickly, if credit spreads widen without a policy
offset, if long rates rise because of fiscal risk rather than growth strength,
or if earnings revisions turn broadly negative. I would increase confidence if
inflation decelerates, labor cools gradually, credit remains contained, and
central banks gain room to ease without reigniting inflation.
"""


def create_report(path: Path = REPORT_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(SAMPLE_REPORT)
    return path


def main() -> None:
    path = create_report()
    print(f"Created sample macro report: {path}")


if __name__ == "__main__":
    main()

