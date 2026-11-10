
from fastapi import FastAPI, HTTPException

from src.database.market_repository import get_candles

app = FastAPI(title="Market Data Intelligence")


@app.get("/candles")
def read_candles(
    symbol: str = "EUR/USD",
    interval: str = "1min",
    limit: int = 100,
):
    try:
        candles = get_candles(symbol, interval, limit)
        return {
            "symbol": symbol,
            "interval": interval,
            "count": len(candles),
            "candles": candles,
        }
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail="Erro ao consultar candles.",
        ) from error


@app.get("/health")
def health_check():
    return {"status": "ok"}
