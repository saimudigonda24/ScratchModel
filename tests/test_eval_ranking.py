import numpy as np
import pandas as pd
import pytest

from app.services.eval_ranking import (
    PointInTimeViolation,
    build_panel_from_outcomes,
    evaluate_outcome_rankings,
    _long_short_spread,
    _rank_ic,
    _tie_fraction,
    evaluate,
    make_synthetic_panel,
    permutation_test,
    quantile_buckets,
    validate_point_in_time,
    validate_schema,
)


def panel(rows: list[tuple]) -> pd.DataFrame:
    data = pd.DataFrame(rows, columns=["as_of", "name", "conviction_score", "fwd_return"])
    data["as_of"] = pd.to_datetime(data["as_of"])
    data["ret_window_start"] = data["as_of"] + pd.Timedelta(days=1)
    data["ret_window_end"] = data["as_of"] + pd.Timedelta(days=30)
    return data


def test_perfect_ranking_scores_one():
    assert _rank_ic(np.array([1, 2, 3, 4.0]), np.array([10, 20, 30, 40.0])) == pytest.approx(1.0)


def test_inverted_ranking_scores_minus_one():
    assert _rank_ic(np.array([1, 2, 3, 4.0]), np.array([40, 30, 20, 10.0])) == pytest.approx(-1.0)


def test_ic_is_rank_based_not_level_based():
    assert _rank_ic(np.array([1, 2, 3, 4.0]), np.array([0.001, 0.002, 0.003, 900.0])) == pytest.approx(1.0)


def test_ic_is_nan_when_all_scores_identical():
    assert np.isnan(_rank_ic(np.array([7, 7, 7, 7.0]), np.array([1, 2, 3, 4.0])))


def test_ic_is_nan_on_a_tiny_cross_section():
    assert np.isnan(_rank_ic(np.array([1, 2.0]), np.array([5, 6.0])))


def test_tie_fraction():
    assert _tie_fraction(np.array([8, 8, 8, 1.0])) == pytest.approx(0.75)
    assert _tie_fraction(np.array([1, 2, 3, 4.0])) == pytest.approx(0.0)


def test_long_short_spread():
    scores = np.array([10, 9, 2, 1.0])
    rets = np.array([0.05, 0.03, -0.01, -0.03])
    assert _long_short_spread(scores, rets, k=2) == pytest.approx(0.06)


def test_long_short_legs_cannot_overlap():
    assert _long_short_spread(np.array([3, 2, 1.0]), np.array([0.10, 0.0, -0.10]), k=2) == pytest.approx(0.20)


def test_lookahead_is_rejected():
    data = panel([("2024-01-31", "A", 8.0, 0.02), ("2024-01-31", "B", 3.0, -0.01)])
    data.loc[0, "ret_window_start"] = pd.Timestamp("2024-01-15")
    with pytest.raises(PointInTimeViolation, match="lookahead"):
        validate_point_in_time(data)


def test_zero_lag_rejected_when_lag_demanded():
    data = panel([("2024-01-31", "A", 8.0, 0.02), ("2024-01-31", "B", 3.0, -0.01)])
    data["ret_window_start"] = data["as_of"]
    with pytest.raises(PointInTimeViolation):
        validate_point_in_time(data, execution_lag=pd.Timedelta(days=1))


def test_clean_panel_passes():
    validate_point_in_time(panel([("2024-01-31", "A", 8.0, 0.02)]))


def test_backwards_window_rejected():
    data = panel([("2024-01-31", "A", 8.0, 0.02)])
    data["ret_window_end"] = data["ret_window_start"] - pd.Timedelta(days=1)
    with pytest.raises(PointInTimeViolation):
        validate_point_in_time(data)


def test_duplicate_rows_rejected():
    data = panel([("2024-01-31", "A", 8.0, 0.02), ("2024-01-31", "A", 3.0, -0.01)])
    with pytest.raises(ValueError, match="duplicate"):
        validate_schema(data)


def test_missing_column_rejected():
    data = panel([("2024-01-31", "A", 8.0, 0.02)]).drop(columns=["fwd_return"])
    with pytest.raises(ValueError, match="missing required columns"):
        validate_schema(data)


def test_skilful_panel_is_detected():
    report = evaluate(make_synthetic_panel(skill=0.35, seed=1), n_permutations=300)
    assert report.mean_ic > 0.15
    assert report.permutation_p < 0.05
    assert report.hit_rate > 0.6


def test_skill_free_panel_is_not_detected():
    report = evaluate(make_synthetic_panel(skill=0.0, seed=7), n_permutations=300)
    assert abs(report.mean_ic) < 0.10
    assert report.permutation_p > 0.05


@pytest.mark.slow
def test_type_one_error_across_seeds():
    rejections = sum(
        evaluate(make_synthetic_panel(skill=0.0, seed=seed), n_permutations=200).permutation_p < 0.05
        for seed in range(10)
    )
    assert rejections <= 2, f"{rejections}/10 null panels flagged as skilful"


def test_reversed_ranking_flips_the_ic():
    report = evaluate(make_synthetic_panel(skill=0.35, seed=1), n_permutations=100)
    assert report.reverse_mean_ic == pytest.approx(-report.mean_ic, abs=1e-9)


def test_buckets_decay_monotonically_with_skill():
    buckets = quantile_buckets(make_synthetic_panel(skill=0.5, seed=3), n_buckets=4)
    assert list(buckets.index) == [1, 2, 3, 4]
    assert buckets.is_monotonic_decreasing


def test_thin_cross_section_warns():
    report = evaluate(make_synthetic_panel(n_names=4, n_dates=30, skill=0.3), n_permutations=100)
    assert any("names/date" in warning for warning in report.warnings)


def test_short_history_warns():
    report = evaluate(make_synthetic_panel(n_dates=8, skill=0.3), n_permutations=100)
    assert any("usable dates" in warning for warning in report.warnings)


def test_heavy_ties_warn():
    report = evaluate(make_synthetic_panel(skill=0.3, tie_coarseness=1), n_permutations=100)
    assert any("tied" in warning for warning in report.warnings)


def test_overlap_factor_deflates_the_t_stat():
    synthetic = make_synthetic_panel(skill=0.3, seed=2)
    naive = evaluate(synthetic, n_permutations=50, overlap_factor=1.0).ic_t_stat
    corrected = evaluate(synthetic, n_permutations=50, overlap_factor=3.0).ic_t_stat
    assert corrected == pytest.approx(naive / np.sqrt(3.0), rel=1e-6)
    assert corrected < naive


def test_permutation_p_is_never_zero():
    assert permutation_test(make_synthetic_panel(skill=0.9, seed=5), n_permutations=100) > 0


def outcome_row(
    *,
    row_id: int = 1,
    run_id: str = "run_1",
    idea_id: str = "Quality equities",
    start_date: str = "2024-01-01",
    horizons: list[int] | str = "[1]",
    conviction_score: float = 7.0,
    fwd_return: float = 0.2,
    quality: float | None = 8.0,
    updated_at: str = "2024-03-01T00:00:00",
) -> dict:
    return {
        "id": row_id,
        "run_id": run_id,
        "idea_id": idea_id,
        "asset_class": "equity",
        "start_date": start_date,
        "target_horizon_months": horizons,
        "conviction_score": conviction_score,
        "realized_return": fwd_return,
        "outcome_evaluated": 1,
        "outcome_quality_score": quality,
        "created_at": "2024-01-02T00:00:00",
        "updated_at": updated_at,
    }


def test_outcome_panel_deduplicates_exact_repeated_rows():
    rows = [
        outcome_row(row_id=1, fwd_return=0.19, quality=7.0, updated_at="2024-02-01T00:00:00"),
        outcome_row(row_id=2, fwd_return=0.20, quality=8.0, updated_at="2024-03-01T00:00:00"),
    ]
    panel_data, metadata = build_panel_from_outcomes(outcome_rows=rows, include_metadata=True)

    assert len(panel_data) == 1
    assert metadata["duplicate_rows_removed"] == 1
    assert panel_data.iloc[0]["fwd_return"] == pytest.approx(0.20)
    validate_schema(panel_data[["as_of", "name", "conviction_score", "ret_window_start", "ret_window_end", "fwd_return"]])


def test_outcome_panel_keeps_same_idea_at_different_horizons():
    rows = [outcome_row(horizons="[1, 3]")]
    panel_data, metadata = build_panel_from_outcomes(outcome_rows=rows, include_metadata=True)

    assert len(panel_data) == 2
    assert metadata["horizons"] == [1, 3]
    assert panel_data["name"].nunique() == 2
    assert panel_data[["as_of", "name"]].duplicated().sum() == 0


def test_duplicate_database_join_rows_use_highest_quality_then_latest():
    rows = [
        outcome_row(row_id=5, fwd_return=0.05, quality=6.0, updated_at="2024-05-01T00:00:00"),
        outcome_row(row_id=6, fwd_return=0.11, quality=9.0, updated_at="2024-04-01T00:00:00"),
        outcome_row(row_id=7, fwd_return=0.09, quality=9.0, updated_at="2024-03-01T00:00:00"),
    ]
    panel_data, metadata = build_panel_from_outcomes(outcome_rows=rows, include_metadata=True)

    assert len(panel_data) == 1
    assert metadata["duplicate_rows_removed"] == 2
    assert panel_data.iloc[0]["source_outcome_id"] == 6
    assert panel_data.iloc[0]["fwd_return"] == pytest.approx(0.11)


def test_outcome_ranking_returns_not_ready_for_insufficient_data():
    response = evaluate_outcome_rankings(outcome_rows=[outcome_row()], min_rows=25)

    assert response["status"] == "not_ready"
    assert response["reason"] == "insufficient_history"
    assert response["rows"] == 1
    assert response["row_counts"]["canonical_rows"] == 1


def test_outcome_ranking_valid_response_from_canonical_outcomes():
    rows = []
    for date_index, as_of in enumerate(pd.date_range("2021-01-31", periods=22, freq="ME")):
        for name_index in range(6):
            conviction = float(10 - name_index)
            rows.append(
                outcome_row(
                    row_id=date_index * 10 + name_index,
                    run_id=f"run_{date_index}",
                    idea_id=f"idea_{name_index}",
                    start_date=str(as_of.date()),
                    conviction_score=conviction,
                    fwd_return=(6 - name_index) * 0.01,
                    quality=8.0,
                    updated_at=f"{as_of.date()}T12:00:00",
                )
            )

    response = evaluate_outcome_rankings(outcome_rows=rows, min_rows=25, n_permutations=20)

    assert response["status"] == "ok"
    assert response["rows"] == len(rows)
    assert response["report"]["mean_ic"] > 0


def test_outcome_ranking_handles_invalid_panels_without_uncaught_500():
    rows = [
        outcome_row(row_id=1, conviction_score=7.0),
        outcome_row(row_id=2, conviction_score=None, quality=9.0, updated_at="2024-04-01T00:00:00"),
    ]

    response = evaluate_outcome_rankings(outcome_rows=rows, min_rows=1)

    assert response["status"] == "not_ready"
    assert response["reason"] == "invalid_ranking_panel"
    assert response["report"] is None
