import os

from app.connectors.base import HTTPMarketDataConnector
from app.models import DataSignal


CENSUS_SERIES = [
    {
        "name": "Retail Sales",
        "url": "https://api.census.gov/data/timeseries/eits/marts",
        "params": {"get": "data_type_code,seasonally_adj,category_code,cell_value,error_data,time_slot_id", "for": "us:*", "time": "from 2024"},
        "preferred_terms": ("MRTS", "44X72", "SM"),
        "interpretation": "Census normalized live Monthly Advance Retail Sales data.",
    },
    {
        "name": "Housing Starts",
        "url": "https://api.census.gov/data/timeseries/eits/resconst",
        "params": {"get": "data_type_code,seasonally_adj,category_code,cell_value,error_data,time_slot_id", "for": "us:*", "time": "from 2024"},
        "preferred_terms": ("START", "STARTS", "HOUST"),
        "interpretation": "Census normalized live New Residential Construction housing-starts data.",
    },
    {
        "name": "Building Permits",
        "url": "https://api.census.gov/data/timeseries/eits/resconst",
        "params": {"get": "data_type_code,seasonally_adj,category_code,cell_value,error_data,time_slot_id", "for": "us:*", "time": "from 2024"},
        "preferred_terms": ("PERMIT", "PERMITS", "APERMITS"),
        "interpretation": "Census normalized live New Residential Construction building-permits data.",
    },
]


class CensusConnector(HTTPMarketDataConnector):
    source_name = "Census Bureau"

    def fetch_signals(self) -> list[DataSignal]:
        if not os.getenv("CENSUS_API_KEY"):
            return [self.unavailable_signal("Census economic indicators", "missing CENSUS_API_KEY")]
        return [self.fetch_census_signal(spec) for spec in CENSUS_SERIES]

    def fetch_census_signal(self, spec: dict) -> DataSignal:
        params = dict(spec["params"])
        params["key"] = os.getenv("CENSUS_API_KEY")
        data = self.fetch_json(spec["url"], params)
        if data.get("unavailable"):
            return self.unavailable_signal(spec["name"], data.get("reason", "request unavailable"))
        try:
            rows = data["payload"]
            header, values = rows[0], rows[1:]
            selected = _select_latest_row(header, values, spec["preferred_terms"])
            index = {name: position for position, name in enumerate(header)}
            value = selected[index["cell_value"]]
            time_value = selected[index.get("time_slot_id", index.get("time", 0))]
            category = selected[index.get("category_code", 0)]
            data_type = selected[index.get("data_type_code", 0)]
            return DataSignal(
                source=self.source_name,
                name=spec["name"],
                value=str(value),
                as_of=str(time_value),
                direction="neutral",
                interpretation=f"{spec['interpretation']} Selected category={category}, data_type={data_type}.",
            )
        except Exception as exc:
            return self.unavailable_signal(spec["name"], f"normalization failed: {exc}")


def _select_latest_row(header: list[str], rows: list[list[str]], preferred_terms: tuple[str, ...]) -> list[str]:
    if not rows:
        raise ValueError("no Census rows returned")
    lowered_terms = tuple(term.lower() for term in preferred_terms)
    scored_rows = []
    for row in rows:
        text = " ".join(str(value).lower() for value in row)
        score = sum(term in text for term in lowered_terms)
        scored_rows.append((score, row))
    scored_rows.sort(key=lambda item: (item[0], _row_sort_key(header, item[1])), reverse=True)
    return scored_rows[0][1]


def _row_sort_key(header: list[str], row: list[str]) -> str:
    index = {name: position for position, name in enumerate(header)}
    for key in ("time_slot_id", "time"):
        if key in index:
            return str(row[index[key]])
    return ""
