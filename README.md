# HCP Macro Theme AI Investment System

V1 functional research system for AI-assisted macro investing research with a
7-14 month horizon. The app ingests macro/market data, reads human HCP macro
reports, runs multi-agent cross-asset analysis, compares provider/model answers,
stores results in SQLite, queues human approvals, evaluates output quality, and
exports approved JSONL training examples.

This is research and decision support only. It does not place trades, route
orders, or treat investment hypotheses as financial advice.

## What V1 Includes

- FastAPI backend with modular agents and orchestration.
- Streamlit dashboard for running analyses, reviewing history, approving or
  rejecting outputs, inspecting debates, and exporting training data.
- LLM provider wrappers for OpenAI, Anthropic, and Gemini.
- Fallback behavior when API keys are missing or providers fail.
- Data connectors for FRED, Yahoo Finance, SEC EDGAR, and World Bank, with mock
  fallback data.
- SQLite persistence for reports, thesis versions, opportunities, hedges, model
  debates, approvals, training examples, evals, data snapshots, and agent outputs.
- Model debate workflow with three provider slots.
- Evaluation scorecard from 0-10 for macro consistency, evidence quality,
  cross-asset reasoning, risk awareness, hedge quality, clarity, and actionability.
- JSONL training-data export gated by human approval.
- Production-facing Phase 4 layers: shared connector base, Market Data Service,
  multi-round debate, RAG scaffold, historical backtest scaffold, and quality
  gate for training examples.
- Phase 5 measurement layer: proxy mapping, realized return calculations,
  forecast calibration, outcome tables, and dashboard outcome summaries.
- Phase 6 outcome automation: Yahoo historical price ingestion, manual proxy
  overrides, automated outcome evaluation, and stored-price backtest comparison.
- Phase 7 living-system operations: lightweight scheduler, thesis-level outcome
  scoring, hedge-specific evaluation, calibration reports, system monitor, and
  fine-tuning readiness report.
- Institutional operating mode: historical HCP document import, structured
  parsing, institutional-memory retrieval with retrieval reasons, historical
  post-mortem linking, professional investment committee reports, and
  institutional readiness scoring. Training data is now treated as a byproduct
  of high-quality research, not the primary workflow.

## Phase 4 Architecture

```text
External Data Sources
  -> Shared Connector Layer
  -> Market Data Service
  -> Knowledge Retrieval (RAG)
  -> Macro Thesis Agent
  -> Asset-Class Agents
  -> Multi-Round Debate Engine
  -> Risk & Hedge Engine
  -> Human Review
  -> Training Dataset Builder
  -> Future Fine-Tuning
```

See `docs/architecture.md` for the full diagram and layer descriptions.

## Institutional Research Workflow

```text
Live Market Data
  -> Current HCP Research
  -> Similar Historical HCP Reports
  -> Similar Historical Outcomes
  -> Lessons Learned
  -> Updated Macro Thesis
  -> Specialist Asset-Class Agents
  -> Multi-Round Debate
  -> Risk & Hedge Review
  -> Human Review
  -> Investment Committee Report
  -> Outcome Tracking
  -> Institutional Memory Update
  -> Training Dataset Byproduct
```

Historical HCP reports can be imported from Markdown, plain text, email exports,
PDF, or DOCX. PDF/DOCX parsing uses optional local parser support when available
and otherwise preserves the original file with a parser-status note. Every
document stores both the original text/file reference and a structured
representation with thesis, growth, inflation, central bank, country,
opportunity, hedge, risk, probability, invalidation, monitoring, and conclusion
fields.

Each workflow run now saves a professional investment committee report under
`reports/investment_committee/` and in SQLite.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
pip install -r frontend/requirements.txt
cp .env.example .env
```

## API Keys

Edit `.env`:

```bash
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=
FRED_API_KEY=
TRADING_ECONOMICS_API_KEY=
SEC_USER_AGENT="Heritage Capital Partners research contact@example.com"
HCP_API_URL=http://localhost:8000
HCP_USE_REAL_DATA=false
```

No key should be hardcoded. If keys are missing, the app still runs with mock
LLM answers and mock data.

## Run With Mock Data

Keep this in `.env`:

```bash
HCP_USE_REAL_DATA=false
```

Then run:

```bash
uvicorn app.main:app --app-dir backend --port 8000
```

## Run With Real Data

Set:

```bash
HCP_USE_REAL_DATA=true
FRED_API_KEY=your_fred_key
SEC_USER_AGENT="Your Firm your.email@example.com"
```

Yahoo Finance and World Bank do not require keys in this starter. SEC EDGAR
requires a compliant user agent. Any failed source falls back to mock data.

## Run The Frontend

```bash
streamlit run frontend/app.py
```

If your local environment blocks Streamlit file watching:

```bash
HOME=/private/tmp python -m streamlit run frontend/app.py --server.port 8501 --server.headless true --server.fileWatcherType none --browser.gatherUsageStats false
```

## Run A Full Analysis

Use the dashboard:

1. Paste or upload a macro report.
2. Click `Run New Analysis`.
3. Review the current thesis, data signals, opportunities, hedges, debate, and
   evaluation scorecard.
4. Use the `Approvals` tab to approve, reject, or request revision.
5. Export approved JSONL after all approval items for a run are approved.

Or call the API:

```bash
curl -X POST http://localhost:8000/workflow/run \
  -H "Content-Type: application/json" \
  -d '{"report_title":"HCP Report","report_text":"Growth is slowing, inflation is cooling, and central banks are becoming more two-sided."}'
```

## Review And Approve Outputs

Dashboard: use the `Approvals` tab.

Each approval card shows the opportunity or hedge name, asset class, thesis
fit, evidence, risks, confirming data, invalidating data, model debate notes,
and current approval status. Use `Approve`, `Reject`, or `Needs Revision`.

API:

```bash
curl http://localhost:8000/approvals
curl -X POST http://localhost:8000/approvals/1/approved
curl -X POST http://localhost:8000/approvals/1/rejected
curl -X POST http://localhost:8000/approvals/1/needs_revision
```

Training candidates become exportable only when all approval items for that run
are approved.

To seed one fully approved demo run:

```bash
python scripts/seed_approved_training_example.py
```

Normal report-driven workflow:

```bash
python scripts/create_sample_macro_report.py
python scripts/run_hcp_analysis_from_report.py --report reports/raw/sample_macro_report.md
```

The run-from-report command leaves all approval items pending. Review and
approve the run in Streamlit before building the training dataset.

## Export JSONL Training Data

Dashboard: click `Export Approved JSONL`.

API:

```bash
curl -X POST http://localhost:8000/training/export-approved
```

Manual converter for saved research outputs:

```bash
python training/convert_outputs_to_jsonl.py --input-dir reports/outputs --output datasets/jsonl/hcp_training_examples.jsonl
```

Approved exports are written to:

```text
datasets/jsonl/approved_hcp_training_examples.jsonl
```

## Build The First Supervised Training Dataset

Do not fine-tune on raw sources. First convert approved workflow runs into
supervised examples:

```bash
python training/build_training_dataset.py
```

This creates:

```text
datasets/cleaned_examples/hcp_macro_training.jsonl
```

Validate it with:

```bash
python training/validate_training_dataset.py
```

The Streamlit sidebar also has `Build Training Dataset` and `Validate Dataset`
buttons, and the `Training/Evals` tab previews the latest JSONL examples,
source run IDs, and creation dates.

The model is learning the HCP reasoning and output framework: macro thesis
structure, cross-asset comparison, evidence use, risks, confirming data,
invalidating data, and human-review discipline. It is not learning magical
market prediction from raw source data. See `docs/training_pipeline.md`.

## Useful API Endpoints

- `GET /health`
- `GET /signals`
- `POST /workflow/run`
- `POST /workflow/upload-text`
- `GET /history/reports`
- `GET /history/thesis`
- `GET /history/debates`
- `GET /approvals`
- `POST /approvals/{approval_id}/{status}`
- `GET /artifacts/training-examples`
- `GET /artifacts/evaluations`
- `POST /training/export-approved`
- `GET /outcomes`
- `GET /outcomes/proxy-mappings`
- `POST /outcomes/export-evaluation-dataset`
- `POST /outcomes/proxy-override`
- `POST /outcomes/ingest-prices`
- `POST /outcomes/evaluate`
- `GET /system/scheduler`
- `POST /system/scheduler/run`
- `POST /outcomes/generate-calibration-report`
- `GET /outcomes/latest-calibration-report`
- `GET /training/fine-tuning-readiness`
- `GET /docs`

## Database

SQLite database:

```text
data/hcp_research.sqlite3
```

Tables:

- `macro_reports`
- `macro_thesis_versions`
- `opportunities`
- `hedges`
- `model_debate_outputs`
- `human_approvals`
- `training_examples`
- `evaluation_results`
- `data_snapshots`
- `agent_outputs`
- `thesis_outcomes`
- `opportunity_outcomes`
- `hedge_outcomes`
- `forecast_outcomes`
- `realized_market_returns`
- `daily_prices`
- `proxy_overrides`
- `scheduled_job_runs`

## Outcome Tracking

Phase 5 measures whether approved research ideas worked. See
`docs/outcome_tracking.md`.

The Streamlit dashboard includes an `Outcomes & Evaluation` tab showing:

- approved opportunities awaiting outcome tracking
- proxy ticker mappings
- realized return table
- hedge effectiveness table
- forecast calibration rows
- hit rate by asset class
- average return by conviction bucket
- best and worst recommendations
- evaluation dataset export

Price ingestion:

```bash
python scripts/ingest_prices.py --tickers IEF,SPY,GLD,VNQ,AMLP,BTC-USD --start 2020-01-01 --end 2026-12-31
```

Automated outcome evaluation:

```bash
python scripts/evaluate_outcomes.py
```

Scheduler dry run:

```bash
python scripts/run_scheduler.py --dry-run
```

Generate calibration report:

```bash
python scripts/generate_calibration_report.py
```

Fine-tuning readiness report:

```bash
python scripts/fine_tuning_readiness_report.py
```

The Streamlit dashboard also includes a `System Monitor` tab showing scheduled
job status, last successful ingestion, last outcome evaluation, latest
calibration report, failed jobs, freshness warnings, and fine-tuning readiness.

## Tests

```bash
python -m pytest tests
```

The test suite covers connectors, orchestration, database save/load, debate
judge/model-debate flow, training conversion, and evaluation scoring.

## Next Steps

- Replace deterministic agent internals with schema-validated LLM outputs.
- Add point-in-time/vintage datasets for the historical backtesting framework.
- Replace lexical RAG with embeddings and a durable vector database.
- Expand source normalization into analytical features and release calendars.
- Add human-labeled evaluation sets and realized-outcome tracking.
- Add additional market data vendors for total-return adjusted histories.
- Add scheduled jobs for automatic price ingestion and horizon-based evaluation.
- Add thesis-level and hedge-specific outcome automation beyond opportunity outcomes.
- Replace the simple scheduler with a production queue when deployment needs it.
- Add regime labels and enough diverse outcome examples before any fine-tuning.
- Fine-tune only after enough approved, high-quality examples exist.
