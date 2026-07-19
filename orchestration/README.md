# Orchestration

The runnable orchestrator lives in `backend/app/orchestration/research_orchestrator.py`.

It decides:

- which agent handles each task
- the order of macro thesis, asset-class review, risk review, debate, human approval, evaluation, and training-data conversion
- what shared context is passed between agents
- where outputs are saved for future training and evaluation
- when human review is required

