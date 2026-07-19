# Outcome Tracking And Evaluation

Phase 5 adds the measurement layer that determines whether HCP research ideas
worked after approval.

## Outcome Tables

SQLite now includes:

- `thesis_outcomes`
- `opportunity_outcomes`
- `hedge_outcomes`
- `forecast_outcomes`
- `realized_market_returns`

## Proxy Mapping

Broad research ideas are mapped to measurable instruments:

- intermediate duration -> `IEF`
- long duration -> `TLT`
- quality equities -> `QUAL`
- cyclicals -> `XLI`
- gold -> `GLD`
- oil -> `USO`
- USD downside -> short `UUP`
- REITs -> `VNQ`
- MLPs -> `AMLP`
- crypto -> `BTC-USD` or `ETH-USD`

Manual override support is available in the proxy mapping service and should be
exposed more fully in a future dashboard form.

## Metrics

The return calculator computes:

- total return
- benchmark-relative return
- max drawdown
- volatility
- Sharpe-like score
- hit/miss label
- hedge effectiveness during stress windows

The calibration module computes:

- Brier score
- calibration buckets
- overconfidence score
- underconfidence score

## Price Ingestion

Yahoo Finance daily price ingestion is available through:

```bash
python scripts/ingest_prices.py --tickers IEF,SPY,GLD,VNQ,AMLP,BTC-USD --start 2020-01-01 --end 2026-12-31
```

The service stores raw responses in `data/raw_prices` and normalized daily rows
in SQLite. Duplicate `(ticker, date, source)` rows are ignored.

## Automated Evaluation

Run:

```bash
python scripts/evaluate_outcomes.py
```

The evaluator finds approved opportunities, applies proxy mappings or manual
overrides, checks whether the target horizon has elapsed, loads stored prices,
calculates outcome metrics, and updates `opportunity_outcomes`.

## Scheduler

Scheduler config:

```text
config/scheduler.yaml
```

Run once:

```bash
python scripts/run_scheduler.py
```

Dry run:

```bash
python scripts/run_scheduler.py --dry-run
```

Configured jobs cover price ingestion, macro ingestion, research generation,
outcome evaluation, and monthly calibration reports.

## Thesis And Hedge Outcomes

`thesis_outcome_evaluator.py` scores the overall thesis after the fact across
growth, inflation, central bank reaction, country overlays, probability bands,
invalidation triggers, and narrative quality.

`hedge_evaluator.py` detects stress windows and evaluates hedge performance,
drag, convexity, timing usefulness, and whether the hedge protected the
opportunity set.

## Calibration Reports

Generate:

```bash
python scripts/generate_calibration_report.py
```

Reports are saved to:

```text
reports/calibration/
```

## Fine-Tuning Readiness

Run:

```bash
python scripts/fine_tuning_readiness_report.py
```

The report summarizes approved examples, outcome-evaluated examples, eligible
examples, asset-class coverage, regime coverage, average quality score,
calibration quality, examples still needed, and readiness recommendation.

## Manual Overrides

The dashboard `Outcomes & Evaluation` tab can save overrides for:

- proxy ticker
- benchmark ticker
- expected direction
- start date
- target horizon
- notes

## Training Gate

Examples are eligible for future fine-tuning only if:

- human approved
- evidence complete
- risks complete
- proxy mapping complete
- enough time has passed to evaluate outcome
- outcome metrics are calculated
- quality score passes the configured threshold
