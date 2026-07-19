from dataclasses import dataclass


@dataclass(frozen=True)
class ProxyMapping:
    idea_keyword: str
    asset_class: str
    proxy_ticker: str
    benchmark: str
    expected_direction: str
    rationale: str


DEFAULT_PROXY_MAPPINGS = [
    ProxyMapping("intermediate duration", "fixed_income", "IEF", "AGG", "long", "Intermediate Treasury duration proxy."),
    ProxyMapping("long duration", "fixed_income", "TLT", "AGG", "long", "Long Treasury duration proxy."),
    ProxyMapping("quality", "equity", "QUAL", "SPY", "long", "Quality equity factor ETF."),
    ProxyMapping("cyclical", "equity", "XLI", "SPY", "long", "Industrial cyclicals proxy."),
    ProxyMapping("cyclicals", "equity", "XLI", "SPY", "long", "Industrial cyclicals proxy."),
    ProxyMapping("gold", "commodity", "GLD", "SPY", "long", "Gold ETF proxy."),
    ProxyMapping("oil", "commodity", "USO", "SPY", "long", "Oil ETF proxy."),
    ProxyMapping("usd downside", "fx_rates", "UUP", "SPY", "short", "Short dollar ETF proxy."),
    ProxyMapping("dollar", "fx_rates", "UUP", "SPY", "short", "Dollar ETF proxy."),
    ProxyMapping("reit", "reit", "VNQ", "SPY", "long", "Listed REIT proxy."),
    ProxyMapping("mlp", "mlp", "AMLP", "SPY", "long", "MLP ETF proxy."),
    ProxyMapping("crypto", "crypto", "BTC-USD", "SPY", "long", "Bitcoin proxy for liquid crypto beta."),
    ProxyMapping("bitcoin", "crypto", "BTC-USD", "SPY", "long", "Bitcoin proxy."),
    ProxyMapping("ethereum", "crypto", "ETH-USD", "SPY", "long", "Ethereum proxy."),
]


def map_idea_to_proxy(name: str, asset_class: str, manual_override: str | None = None) -> ProxyMapping:
    if manual_override:
        return ProxyMapping(
            idea_keyword="manual_override",
            asset_class=asset_class,
            proxy_ticker=manual_override,
            benchmark="SPY",
            expected_direction="long",
            rationale="Manual dashboard override.",
        )
    text = f"{name} {asset_class}".lower()
    for mapping in DEFAULT_PROXY_MAPPINGS:
        if mapping.idea_keyword in text or mapping.asset_class == asset_class:
            return mapping
    return ProxyMapping(
        idea_keyword="default",
        asset_class=asset_class,
        proxy_ticker="SPY",
        benchmark="SPY",
        expected_direction="long",
        rationale="Default broad equity proxy; manual review recommended.",
    )


def all_proxy_mappings() -> list[dict]:
    return [mapping.__dict__ for mapping in DEFAULT_PROXY_MAPPINGS]

