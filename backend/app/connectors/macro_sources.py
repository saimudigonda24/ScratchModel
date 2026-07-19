from app.models import MacroDataSnapshot
from app.services.market_data import MarketDataService


def ingest_all_sources() -> MacroDataSnapshot:
    return MarketDataService().get_all_data()

