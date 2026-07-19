# HCP Macro Theme AI Investment System Architecture

## Target Flow

```text
External Data Sources
  FRED | BLS | BEA | Census | CME FedWatch | Yahoo Finance
  SEC EDGAR | World Bank | IMF | TradingEconomics
        |
        v
Shared Connector Layer
  retries | cache | raw JSON snapshots | normalization | unavailable status
        |
        v
Market Data Service
  get_growth_data()
  get_inflation_data()
  get_rates_data()
  get_labor_data()
  get_credit_data()
  get_equity_data()
  get_fx_data()
  get_commodity_data()
  get_crypto_data()
  get_global_macro_data()
        |
        v
Knowledge Retrieval Layer
  HCP reports | approved IC outputs | debate transcripts | Fed speeches
  IMF/World Bank reports | research papers | earnings summaries
        |
        v
Macro Thesis Agent
        |
        v
Asset-Class Agents
  Equity | Fixed Income | FX/Rates | Commodities | Crypto | MLP | REIT | Alts
        |
        v
Multi-Round Debate Engine
  Round 1: independent answers
  Round 2: cross-provider critiques
  Round 3: revised opinions
  Round 4: judge consensus
        |
        v
Risk & Hedge Engine
        |
        v
Human Review
        |
        v
Training Dataset Builder
        |
        v
Future Fine-Tuning
```

## Data Sources

Each source-specific connector subclasses the shared HTTP connector base. The
base provides retries, exponential backoff, caching, raw JSON persistence,
timestamps, and graceful unavailable signals when credentials or approved
endpoints are missing.

Current connector modules:

- `backend/app/connectors/fred.py`
- `backend/app/connectors/bls.py`
- `backend/app/connectors/bea.py`
- `backend/app/connectors/census.py`
- `backend/app/connectors/cme_fedwatch.py`
- `backend/app/connectors/yahoo_finance.py`
- `backend/app/connectors/sec_edgar.py`
- `backend/app/connectors/world_bank.py`
- `backend/app/connectors/imf.py`
- `backend/app/connectors/trading_economics.py`

## Market Data Layer

`backend/app/services/market_data.py` is now the single interface between
research logic and external data sources. Agents should consume normalized
signals from this service rather than directly importing connector modules.

## RAG Layer

`backend/app/services/knowledge_base.py` provides a lightweight retrieval layer.
It can index HCP macro reports and retrieve relevant documents before agent
reasoning. The current implementation is lexical and file-backed; production
should replace this with embeddings and a durable vector store.

## Debate Layer

`backend/app/services/model_debate.py` now stores multiple rounds:

1. Independent provider answers
2. Cross-provider critiques
3. Revised provider opinions
4. Debate Judge consensus

The debate output preserves all raw provider responses for future evaluation
and training.

## Historical Backtesting

`backend/app/services/backtesting.py` defines the point-in-time replay boundary
and standard test dates:

- January 2020
- June 2021
- March 2022
- March 2023
- January 2024
- October 2024

Current scores are placeholders until Phase 5 adds vintage datasets and
realized outcome comparisons.

## Human Learning

SQLite stores reports, thesis versions, agent outputs, model debates, approval
decisions, training candidates, evaluations, and data snapshots. The knowledge
base indexes new HCP reports as institutional memory.

## Quality Gate

Approved training examples require human approval and quality scores of at
least 6.0 across the evaluation dimensions:

- reasoning quality
- macro consistency
- cross-asset consistency
- evidence quality
- risk analysis
- hedging quality
- clarity
- actionability

