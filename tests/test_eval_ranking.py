import numpy as np
import pandas as pd
import pytest

from app.services.eval_ranking import (
    PointInTimeViolation,
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
