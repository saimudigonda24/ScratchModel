import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.price_ingestion import PriceIngestionService  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    args = parser.parse_args()
    tickers = [ticker.strip() for ticker in args.tickers.split(",") if ticker.strip()]
    summary = PriceIngestionService().ingest_prices(tickers, args.start, args.end)
    print(summary)


if __name__ == "__main__":
    main()

