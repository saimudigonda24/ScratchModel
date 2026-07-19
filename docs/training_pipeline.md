# Approved Training Dataset Pipeline

This project does **not** train directly on raw macro sources. Raw source pulls
and HCP reports are converted into supervised examples only after the workflow
generates a structured research output and a human approves the run.

## Pipeline

```text
Source Pulls
  FRED, BLS, BEA, Census, TradingEconomics, CME FedWatch,
  World Bank, IMF, Yahoo Finance, SEC EDGAR
        |
        v
Timestamped Data Snapshots
  data/snapshots/{run_id}_combined.json
  data/snapshots/{run_id}_{source}.json
        |
        v
Human HCP Macro Report
        |
        v
Structured Research Output
  macro thesis, base/bull/bear cases, opportunities, hedges,
  evidence, risks, confirming data, invalidating data
        |
        v
Human Approval Gate
        |
        v
Supervised JSONL Fine-Tuning Candidate
  datasets/cleaned_examples/hcp_macro_training.jsonl
```

## Build Dataset

```bash
python training/build_training_dataset.py
```

This writes:

```text
datasets/cleaned_examples/hcp_macro_training.jsonl
```

If no run has been fully approved, the file is created with zero examples.
That is intentional: unapproved research must not enter the fine-tuning set.

## Validate Dataset

```bash
python training/validate_training_dataset.py
```

The validator checks:

- every example has `input` and `output`
- output follows the HCP structure
- no unapproved examples are included
- evidence fields are present
- risks are not empty
- example IDs are not duplicated

## Learning Goal

The future model is not learning to magically predict markets from raw data.
It is learning the HCP macro-investing reasoning and output framework:

- how to combine macro data with human reports
- how to structure base, bull, and bear/tail cases
- how to compare opportunities across asset classes
- how to include evidence, risks, confirming data, and invalidating data
- how to preserve human approval as a required control

