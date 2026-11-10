from httpx import Client
from dotenv import load_dotenv
from src.database.market_repository import save_candles
import os

load_dotenv()

api_key = os.getenv("TWELVE_DATA_API_KEY")


def fetch_eurusd(api_key, outputsize=5000):
    with Client(timeout=30) as client:
        url = "https://api.twelvedata.com/time_series"

        params = {
            "apikey": api_key,
            "symbol": "EUR/USD",
            "interval": "1min",
            "outputsize": outputsize,
            "timezone": "UTC"
        }

        response = client.get(url, params=params)
        response.raise_for_status()

        data = response.json()

        if data.get("status") == "error":
            raise RuntimeError(data.get("message", "Erro na Twelve Data"))

        return data.get("values", [])


if __name__ == "__main__":
    candles = fetch_eurusd(api_key)
    inserted = save_candles(candles)

    print(f"Candles recebidos: {len(candles)}")
    print(f"Novos candles persistidos: {inserted}")
    print(f"Candles ignorados ou já existentes: {len(candles) - inserted}")