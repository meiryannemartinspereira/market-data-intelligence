
import json

import pandas as pd
from langchain.tools import tool

from src.database.market_repository import get_candles


@tool
def consultar_dados_mercado(
    symbol: str = "EUR/USD",
    interval: str = "1min",
    limit: int = 100,
) -> str:
    """Consulta candles e calcula estatísticas descritivas e métricas de volatilidade."""

    interval_aliases = {
        "1m": "1min",
        "1min": "1min",
        "1 minute": "1min",
        "1 minute(s)": "1min",
    }

    normalized_interval = interval_aliases.get(
        interval.strip().lower(),
        interval.strip(),
    )

    if limit < 2 or limit > 5000:
        return "O limite deve estar entre 2 e 5000 candles."

    candles = get_candles(
        symbol=symbol,
        interval=normalized_interval,
        limit=limit,
    )

    if len(candles) < 2:
        return "Dados insuficientes para realizar a análise."

    df = pd.DataFrame(candles)

    for column in ["open", "high", "low", "close"]:
        df[column] = pd.to_numeric(df[column])

    df["return"] = df["close"].pct_change() * 100
    df["candle_range"] = (
        (df["high"] - df["low"]) / df["close"]
    ) * 100

    returns = df["return"].dropna()
    ranges = df["candle_range"].dropna()

    period_return = (
        df.iloc[-1]["close"] / df.iloc[0]["close"] - 1
    ) * 100

    metrics = {
        "period_return_pct": float(period_return),
        "mean_minute_return_pct": float(returns.mean()),
        "std_minute_return_pct": float(returns.std()),
        "minimum_minute_return_pct": float(returns.min()),
        "maximum_minute_return_pct": float(returns.max()),
        "mean_candle_range_pct": float(ranges.mean()),
        "maximum_candle_range_pct": float(ranges.max()),
    }

    report = "\n".join([
        f"Ativo: {symbol}",
        f"Intervalo: {normalized_interval}",
        f"Candles analisados: {len(df)}",
        f"Retorno total do período: {metrics['period_return_pct']:.6f}%",
        f"Retorno médio por candle: {metrics['mean_minute_return_pct']:.6f}%",
        f"Desvio padrão dos retornos: {metrics['std_minute_return_pct']:.6f}%",
        f"Maior retorno por candle: {metrics['maximum_minute_return_pct']:.6f}%",
        f"Menor retorno por candle: {metrics['minimum_minute_return_pct']:.6f}%",
        f"Amplitude média dos candles: {metrics['mean_candle_range_pct']:.6f}%",
        f"Amplitude máxima dos candles: {metrics['maximum_candle_range_pct']:.6f}%",
    ])

    summary = {
        "symbol": symbol,
        "interval": normalized_interval,
        "candles_analyzed": len(df),
        "period": {
            "start": df.iloc[0]["time"],
            "end": df.iloc[-1]["time"],
        },
        "metrics": metrics,
        "formatted_report": report,
        "methodology": (
            "Retornos calculados como variação percentual entre fechamentos "
            "consecutivos. Volatilidade medida pelo desvio padrão desses "
            "retornos. Amplitude calculada pela diferença entre máxima e "
            "mínima de cada candle, dividida pelo fechamento."
        ),
    }

    print(
        f"\n[TOOL] {len(df)} candles consultados e "
        "métricas calculadas pelo Pandas."
    )

    return json.dumps(summary, ensure_ascii=False)
