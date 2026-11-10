
import os
from datetime import datetime, timezone

import psycopg
from dotenv import load_dotenv

load_dotenv()


def save_candles(candles, symbol="EUR/USD", interval="1min"):
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL não configurada.")

    if not candles:
        return 0

    now = datetime.now(timezone.utc)
    values = []

    for candle in candles:
        candle_time = datetime.fromisoformat(
            candle["datetime"].replace("Z", "+00:00")
        )

        if candle_time.tzinfo is None:
            candle_time = candle_time.replace(tzinfo=timezone.utc)
        else:
            candle_time = candle_time.astimezone(timezone.utc)

        if candle_time > now:
            continue

        values.append(
            (
                symbol,
                interval,
                candle_time,
                candle["open"],
                candle["high"],
                candle["low"],
                candle["close"],
                "Twelve Data",
            )
        )

    if not values:
        return 0

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO market_candles (
                    symbol,
                    "interval",
                    candle_time,
                    open,
                    high,
                    low,
                    close,
                    source
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (symbol, "interval", candle_time, source)
                DO NOTHING
                """,
                values,
            )

            inserted = cursor.rowcount

    return inserted


def get_candles(symbol="EUR/USD", interval="1min", limit=100):
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL não configurada.")

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT candle_time, open, high, low, close
                FROM market_candles
                WHERE symbol = %s
                  AND "interval" = %s
                ORDER BY candle_time DESC
                LIMIT %s
                """,
                (symbol, interval, limit),
            )

            candles = cursor.fetchall()

    return [
        {
            "time": candle[0].isoformat(),
            "open": float(candle[1]),
            "high": float(candle[2]),
            "low": float(candle[3]),
            "close": float(candle[4]),
        }
        for candle in reversed(candles)
    ]
