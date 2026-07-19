from dataclasses import asdict, dataclass
from math import sqrt


@dataclass
class PricePoint:
    date: str
    close: float


@dataclass
class ReturnMetrics:
    total_return: float
    benchmark_return: float
    benchmark_relative_return: float
    max_drawdown: float
    volatility: float
    sharpe_like: float
    hit_miss_label: str


def periodic_returns(prices: list[PricePoint]) -> list[float]:
    return [
        prices[index].close / prices[index - 1].close - 1
        for index in range(1, len(prices))
        if prices[index - 1].close != 0
    ]


def total_return(prices: list[PricePoint]) -> float:
    if len(prices) < 2 or prices[0].close == 0:
        return 0.0
    return prices[-1].close / prices[0].close - 1


def max_drawdown(prices: list[PricePoint]) -> float:
    peak = prices[0].close if prices else 0.0
    worst = 0.0
    for point in prices:
        peak = max(peak, point.close)
        if peak:
            worst = min(worst, point.close / peak - 1)
    return worst


def realized_volatility(prices: list[PricePoint]) -> float:
    returns = periodic_returns(prices)
    if len(returns) < 2:
        return 0.0
    mean_return = sum(returns) / len(returns)
    variance = sum((item - mean_return) ** 2 for item in returns) / (len(returns) - 1)
    return sqrt(variance) * sqrt(252)


def hit_miss(total: float, expected_direction: str) -> str:
    if expected_direction == "short":
        return "hit" if total < 0 else "miss"
    return "hit" if total > 0 else "miss"


def calculate_return_metrics(
    prices: list[PricePoint],
    benchmark_prices: list[PricePoint],
    expected_direction: str = "long",
) -> ReturnMetrics:
    ret = total_return(prices)
    benchmark_ret = total_return(benchmark_prices)
    vol = realized_volatility(prices)
    sharpe = ret / vol if vol else 0.0
    return ReturnMetrics(
        total_return=ret,
        benchmark_return=benchmark_ret,
        benchmark_relative_return=ret - benchmark_ret,
        max_drawdown=max_drawdown(prices),
        volatility=vol,
        sharpe_like=sharpe,
        hit_miss_label=hit_miss(ret, expected_direction),
    )


def metrics_dict(metrics: ReturnMetrics) -> dict:
    return asdict(metrics)


def hedge_effectiveness(hedge_returns: list[float], portfolio_returns: list[float]) -> float:
    stress = [index for index, value in enumerate(portfolio_returns) if value < 0]
    if not stress:
        return 0.0
    positive_hedge = sum(1 for index in stress if index < len(hedge_returns) and hedge_returns[index] > 0)
    return positive_hedge / len(stress)
