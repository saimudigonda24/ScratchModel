"""Rank-quality evaluation for conviction-ranked recommendations.

Metrics are computed per as_of date and then averaged. Pooling all rows into one
correlation would mix time-series drift into cross-sectional skill.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

if int(np.__version__.split(".", 1)[0]) >= 2:
    stats = None
else:
    try:
        from scipy import stats
    except (ImportError, ValueError, AttributeError):
        stats = None

from app.services.database import list_outcome_dashboard_data

REQUIRED_COLUMNS = [
    "as_of",
    "name",
    "conviction_score",
    "ret_window_start",
    "ret_window_end",
    "fwd_return",
]

MIN_NAMES_PER_DATE = 5
MIN_DATES = 20


class PointInTimeViolation(Exception):
    """Raised when forward-return windows leak future data into a ranking."""


def validate_schema(df: pd.DataFrame) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")
    if df[["as_of", "name"]].duplicated().any():
        dupes = df[df[["as_of", "name"]].duplicated(keep=False)]
        raise ValueError(f"duplicate (as_of, name) rows:\n{dupes.head()}")


def validate_point_in_time(df: pd.DataFrame, execution_lag: pd.Timedelta | None = None) -> None:
    lag = execution_lag if execution_lag is not None else pd.Timedelta(0)
    normalized = df.copy()
    for column in ["as_of", "ret_window_start", "ret_window_end"]:
        normalized[column] = pd.to_datetime(normalized[column])
    early = normalized[normalized["ret_window_start"] < normalized["as_of"] + lag]
    if not early.empty:
        raise PointInTimeViolation(
            f"lookahead: {len(early)} row(s) open a return window before as_of + {lag}\n"
            f"{early[['as_of', 'name', 'ret_window_start']].head().to_string(index=False)}"
        )
    backwards = normalized[normalized["ret_window_end"] <= normalized["ret_window_start"]]
    if not backwards.empty:
        raise PointInTimeViolation(f"{len(backwards)} row(s) have a non-positive return window")


def _rank_ic(scores: np.ndarray, rets: np.ndarray) -> float:
    if len(scores) < 3:
        return np.nan
    if np.all(scores == scores[0]) or np.all(rets == rets[0]):
        return np.nan
    if stats is not None:
        return float(stats.spearmanr(scores, rets)[0])
    score_ranks = pd.Series(scores).rank(method="average").to_numpy(dtype=float)
    ret_ranks = pd.Series(rets).rank(method="average").to_numpy(dtype=float)
    return float(np.corrcoef(score_ranks, ret_ranks)[0, 1])


def _kendall_tau(scores: np.ndarray, rets: np.ndarray) -> float:
    if len(scores) < 3 or np.all(scores == scores[0]) or np.all(rets == rets[0]):
        return np.nan
    if stats is not None:
        return float(stats.kendalltau(scores, rets, variant="b")[0])
    return _kendall_tau_b_fallback(scores, rets)


def _kendall_tau_b_fallback(scores: np.ndarray, rets: np.ndarray) -> float:
    concordant = discordant = ties_score = ties_ret = 0
    n = len(scores)
    for i in range(n - 1):
        for j in range(i + 1, n):
            score_cmp = np.sign(scores[i] - scores[j])
            ret_cmp = np.sign(rets[i] - rets[j])
            if score_cmp == 0 and ret_cmp == 0:
                continue
            if score_cmp == 0:
                ties_score += 1
            elif ret_cmp == 0:
                ties_ret += 1
            elif score_cmp == ret_cmp:
                concordant += 1
            else:
                discordant += 1
    denom = np.sqrt((concordant + discordant + ties_score) * (concordant + discordant + ties_ret))
    return float((concordant - discordant) / denom) if denom else np.nan


def _tie_fraction(scores: np.ndarray) -> float:
    if len(scores) == 0:
        return np.nan
    _, counts = np.unique(scores, return_counts=True)
    return float(counts[counts > 1].sum() / len(scores))


def _long_short_spread(scores: np.ndarray, rets: np.ndarray, k: int) -> float:
    n = len(scores)
    if n < 2:
        return np.nan
    k_eff = min(k, n // 2)
    if k_eff < 1:
        return np.nan
    order = np.argsort(-scores, kind="stable")
    return float(np.mean(rets[order[:k_eff]]) - np.mean(rets[order[-k_eff:]]))


def _per_date_metrics(g: pd.DataFrame, k: int) -> pd.Series:
    scores = g["conviction_score"].to_numpy(dtype=float)
    returns = g["fwd_return"].to_numpy(dtype=float)
    return pd.Series(
        {
            "n_names": len(g),
            "rank_ic": _rank_ic(scores, returns),
            "kendall_tau": _kendall_tau(scores, returns),
            "ls_spread": _long_short_spread(scores, returns, k),
            "tie_fraction": _tie_fraction(scores),
        }
    )


@dataclass
class EvalReport:
    n_dates: int
    n_usable_dates: int
    mean_names_per_date: float
    mean_tie_fraction: float
    mean_ic: float
    std_ic: float
    ic_t_stat: float
    icir: float
    hit_rate: float
    mean_kendall: float
    mean_ls_spread: float
    ls_spread_t_stat: float
    permutation_p: float
    reverse_mean_ic: float
    bucket_returns: pd.Series
    per_date: pd.DataFrame = field(repr=False)
    warnings: list[str] = field(default_factory=list)

    def to_text(self) -> str:
        buckets = "  ".join(f"Q{index} {value:+.4f}" for index, value in self.bucket_returns.items())
        lines = [
            "conviction ranking eval",
            f"  dates            {self.n_dates} (usable {self.n_usable_dates})",
            f"  names/date       {self.mean_names_per_date:.1f}",
            f"  tie fraction     {self.mean_tie_fraction:.1%}",
            "",
            f"  mean rank IC     {self.mean_ic:+.4f}",
            f"  std IC           {self.std_ic:.4f}",
            f"  ICIR             {self.icir:+.3f}",
            f"  t-stat           {self.ic_t_stat:+.2f}",
            f"  hit rate         {self.hit_rate:.1%}",
            f"  kendall tau-b    {self.mean_kendall:+.4f}",
            "",
            f"  L/S spread       {self.mean_ls_spread:+.4f}  (t {self.ls_spread_t_stat:+.2f})",
            "",
            f"  permutation p    {self.permutation_p:.4f}",
            f"  reversed IC      {self.reverse_mean_ic:+.4f}",
            f"  buckets          {buckets}",
        ]
        if self.warnings:
            lines.append("")
            lines += [f"  ! {warning}" for warning in self.warnings]
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_dates": self.n_dates,
            "n_usable_dates": self.n_usable_dates,
            "mean_names_per_date": self.mean_names_per_date,
            "mean_tie_fraction": self.mean_tie_fraction,
            "mean_ic": self.mean_ic,
            "std_ic": self.std_ic,
            "ic_t_stat": self.ic_t_stat,
            "icir": self.icir,
            "hit_rate": self.hit_rate,
            "mean_kendall": self.mean_kendall,
            "mean_ls_spread": self.mean_ls_spread,
            "ls_spread_t_stat": self.ls_spread_t_stat,
            "permutation_p": self.permutation_p,
            "reverse_mean_ic": self.reverse_mean_ic,
            "bucket_returns": {int(key): float(value) for key, value in self.bucket_returns.items()},
            "warnings": self.warnings,
        }


def evaluate(
    df: pd.DataFrame,
    k: int = 3,
    n_buckets: int = 4,
    n_permutations: int = 1000,
    execution_lag: pd.Timedelta | None = None,
    overlap_factor: float = 1.0,
    seed: int = 0,
) -> EvalReport:
    validate_schema(df)
    validate_point_in_time(df, execution_lag=execution_lag)
    df = df.copy()
    df["as_of"] = pd.to_datetime(df["as_of"])
    per_date = _groupby_apply_no_groups(df, "as_of", _per_date_metrics, k=k)
    ic = per_date["rank_ic"].dropna()
    spread = per_date["ls_spread"].dropna()
    n_usable = len(ic)
    mean_ic = float(ic.mean()) if n_usable else np.nan
    std_ic = float(ic.std(ddof=1)) if n_usable > 1 else np.nan
    icir = mean_ic / std_ic if std_ic and not np.isnan(std_ic) and std_ic > 0 else np.nan
    t_stat = icir * np.sqrt(n_usable / max(overlap_factor, 1.0)) if not np.isnan(icir) else np.nan
    spread_t = (
        float(spread.mean() / (spread.std(ddof=1) / np.sqrt(len(spread))))
        if len(spread) > 1 and spread.std(ddof=1) > 0
        else np.nan
    )
    return EvalReport(
        n_dates=len(per_date),
        n_usable_dates=n_usable,
        mean_names_per_date=float(per_date["n_names"].mean()),
        mean_tie_fraction=float(per_date["tie_fraction"].mean()),
        mean_ic=mean_ic,
        std_ic=std_ic,
        ic_t_stat=t_stat,
        icir=icir,
        hit_rate=float((ic > 0).mean()) if n_usable else np.nan,
        mean_kendall=float(per_date["kendall_tau"].mean()),
        mean_ls_spread=float(spread.mean()) if len(spread) else np.nan,
        ls_spread_t_stat=spread_t,
        permutation_p=permutation_test(df, n_permutations=n_permutations, seed=seed),
        reverse_mean_ic=reverse_baseline(df),
        bucket_returns=quantile_buckets(df, n_buckets=n_buckets),
        per_date=per_date,
        warnings=_collect_warnings(per_date, n_usable),
    )


def _groupby_apply_no_groups(df: pd.DataFrame, by: str, func, **kwargs) -> pd.DataFrame:
    grouped = df.groupby(by, group_keys=True)
    try:
        return grouped.apply(func, include_groups=False, **kwargs)
    except TypeError:
        pieces = []
        keys = []
        for key, group in grouped:
            pieces.append(func(group.drop(columns=[by], errors="ignore"), **kwargs))
            keys.append(key)
        return pd.DataFrame(pieces, index=pd.Index(keys, name=by))


def _collect_warnings(per_date: pd.DataFrame, n_usable: int) -> list[str]:
    warnings = []
    mean_n = per_date["n_names"].mean()
    if mean_n < MIN_NAMES_PER_DATE:
        warnings.append(f"{mean_n:.1f} names/date: sampling error swamps the IC, sign not readable")
    if n_usable < MIN_DATES:
        warnings.append(f"{n_usable} usable dates: t-stat not interpretable, treat as a smoke test")
    tie = per_date["tie_fraction"].mean()
    if tie > 0.5:
        warnings.append(f"{tie:.0%} of names tied: the ranking is mostly not ranking")
    degenerate = per_date["rank_ic"].isna().sum()
    if degenerate:
        warnings.append(f"{degenerate} date(s) had an undefined IC and were dropped")
    return warnings


def _mean_ic_of(df: pd.DataFrame) -> float:
    ics = [
        _rank_ic(
            group["conviction_score"].to_numpy(dtype=float),
            group["fwd_return"].to_numpy(dtype=float),
        )
        for _, group in df.groupby("as_of")
    ]
    usable = [value for value in ics if not np.isnan(value)]
    return float(np.mean(usable)) if usable else np.nan


def reverse_baseline(df: pd.DataFrame) -> float:
    flipped = df.copy()
    flipped["conviction_score"] = -flipped["conviction_score"]
    return _mean_ic_of(flipped)


def permutation_test(df: pd.DataFrame, n_permutations: int = 1000, seed: int = 0) -> float:
    observed = _mean_ic_of(df)
    if np.isnan(observed):
        return np.nan
    rng = np.random.default_rng(seed)
    shuffled = df.copy()
    null = np.empty(n_permutations)
    for index in range(n_permutations):
        shuffled["conviction_score"] = df.groupby("as_of")["conviction_score"].transform(
            lambda series: rng.permutation(series.to_numpy())
        )
        null[index] = _mean_ic_of(shuffled)
    null = null[~np.isnan(null)]
    if len(null) == 0:
        return np.nan
    return float((np.sum(np.abs(null) >= abs(observed)) + 1) / (len(null) + 1))


def quantile_buckets(df: pd.DataFrame, n_buckets: int = 4) -> pd.Series:
    d = df.copy()

    def _bucket(g: pd.DataFrame) -> pd.Series:
        if g["conviction_score"].nunique() < 2:
            return pd.Series(np.nan, index=g.index)
        ranks = g["conviction_score"].rank(ascending=False, method="first")
        try:
            return pd.qcut(ranks, q=min(n_buckets, len(g)), labels=False, duplicates="drop") + 1
        except ValueError:
            return pd.Series(np.nan, index=g.index)

    d["bucket"] = pd.concat([_bucket(group) for _, group in d.groupby("as_of")]).reindex(d.index)
    out = d.dropna(subset=["bucket"]).groupby("bucket")["fwd_return"].mean()
    out.index = out.index.astype(int)
    return out.sort_index()


def make_synthetic_panel(
    n_dates: int = 36,
    n_names: int = 12,
    skill: float = 0.3,
    tie_coarseness: int | None = None,
    seed: int = 42,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2022-01-31", periods=n_dates, freq="ME")
    names = [f"THEME_{index:02d}" for index in range(n_names)]
    rows = []
    for as_of in dates:
        latent = rng.normal(size=n_names)
        noise = rng.normal(size=n_names)
        ret = (skill * latent + np.sqrt(max(1 - skill**2, 0.0)) * noise) * 0.04
        score = np.clip(5 + 2.0 * latent + rng.normal(scale=0.5, size=n_names), 1, 10)
        if tie_coarseness:
            score = np.round(score * tie_coarseness) / tie_coarseness
        for name, conviction_score, fwd_return in zip(names, score, ret):
            rows.append(
                {
                    "as_of": as_of,
                    "name": name,
                    "conviction_score": float(conviction_score),
                    "ret_window_start": as_of + pd.Timedelta(days=1),
                    "ret_window_end": as_of + pd.offsets.MonthEnd(1),
                    "fwd_return": float(fwd_return),
                }
            )
    return pd.DataFrame(rows)


def build_panel_from_outcomes(execution_lag: pd.Timedelta | None = None) -> pd.DataFrame:
    """Build a point-in-time ranking panel from stored evaluated opportunity outcomes."""
    lag = execution_lag if execution_lag is not None else pd.Timedelta(days=1)
    rows = []
    for row in list_outcome_dashboard_data().get("opportunity_outcomes", []):
        if not row.get("outcome_evaluated") or row.get("realized_return") is None:
            continue
        as_of = pd.to_datetime(row.get("start_date") or row.get("created_at"))
        if pd.isna(as_of):
            continue
        ret_start = as_of + lag
        horizon_months = _first_horizon(row.get("target_horizon_months"))
        ret_end = ret_start + pd.DateOffset(months=horizon_months)
        rows.append(
            {
                "as_of": as_of,
                "name": row.get("idea_id"),
                "conviction_score": row.get("conviction_score"),
                "ret_window_start": ret_start,
                "ret_window_end": ret_end,
                "fwd_return": row.get("realized_return"),
            }
        )
    return pd.DataFrame(rows, columns=REQUIRED_COLUMNS)


def evaluate_outcome_rankings(
    min_rows: int = 25,
    execution_lag: pd.Timedelta | None = None,
    n_permutations: int = 300,
) -> dict[str, Any]:
    panel = build_panel_from_outcomes(execution_lag=execution_lag)
    warnings = []
    if len(panel) < min_rows:
        warnings.append(f"{len(panel)} evaluated rows available; need at least {min_rows} before interpreting ranking quality")
        return {"status": "insufficient_history", "rows": len(panel), "warnings": warnings, "report": None}
    try:
        report = evaluate(panel, execution_lag=execution_lag or pd.Timedelta(days=1), n_permutations=n_permutations)
    except PointInTimeViolation as exc:
        return {"status": "point_in_time_violation", "rows": len(panel), "warnings": [str(exc)], "report": None}
    return {"status": "ok", "rows": len(panel), "warnings": report.warnings, "report": report.to_dict()}


def _first_horizon(raw: Any) -> int:
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except ValueError:
            return 1
        raw = parsed
    if isinstance(raw, (list, tuple)) and raw:
        return int(raw[0])
    return 1
