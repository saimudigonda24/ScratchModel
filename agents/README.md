# Agent Inventory

The runnable agent implementations live in `backend/app/agents`.

- Data Ingestion Agent
- Macro Thesis Agent
- Equity Agent
- Fixed Income Agent
- FX/Rates Agent
- Commodities Agent
- Crypto Agent
- MLP Agent
- REIT Agent
- Alts Agent
- Risk & Hedge Agent
- Debate Judge Agent
- Human Review Agent
- Training Data Builder Agent
- Evaluation Agent
- Conviction Agent

Each module exposes a `SYSTEM_PROMPT` and a class with a `run()` method that accepts Pydantic schemas and returns an `AgentOutput`.
