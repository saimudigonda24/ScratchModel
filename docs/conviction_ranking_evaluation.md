# Conviction Ranking Evaluation

The ranking evaluator measures whether higher Conviction Agent scores are
associated with better subsequent realized outcomes. It is intentionally
point-in-time:

- every row has an `as_of` recommendation timestamp;
- forward-return windows must begin no earlier than `as_of + execution_lag`;
- duplicate `(as_of, name)` rows are rejected;
- all metrics are computed per date and then averaged.

Metrics include rank IC, Kendall tau-b, long-short spread, hit rate, quantile
bucket returns, permutation significance, and tie fraction.

## Conviction Agent Safety

The Conviction Agent now rejects missing, non-numeric, NaN, infinite, and
out-of-range conviction scores with `ConvictionScoreValidationError`. Ranking
uses Python's stable `sorted()` so equal scores remain deterministic and the
input list is not mutated.

## Future Design

Two teammate tests remain strict expected failures by design:

- `test_confidence_tracks_dispersion`: current confidence means average pick
  conviction, not rank separability. Recommended design is to add a separate
  `rank_confidence`, `score_dispersion`, or `ranking_quality` field instead of
  overloading `AgentFinding.confidence`.
- `test_crowding_is_penalized`: crowding is not part of the current Opportunity
  schema. Recommended design is to add optional `crowding_score`,
  `positioning_risk`, or `consensus_risk` fields and let the Conviction Agent
  consume them explicitly.

These features should be added only after the public research-output schema is
reviewed.
