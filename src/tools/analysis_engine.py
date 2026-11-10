
import json
from typing import Literal

import pandas as pd
from pydantic import BaseModel, Field
from langchain.tools import tool

from src.database.market_repository import get_candles


Column = Literal[
    "open",
    "high",
    "low",
    "close",
    "return_pct",
    "candle_range_pct",
    "body_pct",
]

Statistic = Literal["mean", "median", "std", "min", "max", "sum"]

OperationName = Literal[
    "aggregate",
    "trend",
    "top_moves",
    "correlation",
    "group_by_hour",
]


class AnalysisOperation(BaseModel):
    operation: OperationName
    column: Column | None = None
    other_column: Column | None = None
    statistic: Statistic = "mean"
    limit: int = Field(default=5, ge=1, le=20)


class MarketAnalysisInput(BaseModel):
    symbol: str = "EUR/USD"
    interval: str = "1min"
    candles_limit: int = Field(default=100, ge=2, le=5000)
    operations: list[OperationName] = Field(min_length=1, max_length=5)
    top_moves_limit: int = Field(default=5, ge=1, le=20)
    aggregate_column: Column | None = None
    aggregate_statistic: Statistic = "mean"
    correlation_column: Column | None = None
    correlation_other_column: Column | None = None
    group_by_hour_column: Column | None = None
    group_by_hour_statistic: Statistic = "mean"


def validate_operations(
    operations,
    aggregate_column,
    correlation_column,
    correlation_other_column,
    group_by_hour_column,
):
    required_parameters = {
        "aggregate": {
            "aggregate_column": aggregate_column,
        },
        "correlation": {
            "correlation_column": correlation_column,
            "correlation_other_column": correlation_other_column,
        },
        "group_by_hour": {
            "group_by_hour_column": group_by_hour_column,
        },
    }

    errors = []

    for operation in operations:
        parameters = required_parameters.get(operation, {})

        for parameter, value in parameters.items():
            if value is None:
                errors.append(
                    f"A operação {operation} exige o parâmetro {parameter}."
                )

    if errors:
        raise ValueError(" ".join(errors))


def prepare_dataframe(candles):
    df = pd.DataFrame(candles)

    if df.empty:
        return df

    df["time"] = pd.to_datetime(df["time"], utc=True)

    price_columns = ["open", "high", "low", "close"]
    df[price_columns] = df[price_columns].apply(
        pd.to_numeric,
        errors="raise",
    )

    df = df.sort_values("time").reset_index(drop=True)

    df["return_pct"] = df["close"].pct_change() * 100
    df["candle_range_pct"] = (
        (df["high"] - df["low"]) / df["close"]
    ) * 100
    df["body_pct"] = (
        (df["close"] - df["open"]) / df["open"]
    ) * 100

    return df


def execute_operation(df, operation):
    name = operation.operation
    column = operation.column
    statistic = operation.statistic

    if name == "aggregate":
        values = df[column].dropna()

        if values.empty:
            raise ValueError(
                f"Não existem valores disponíveis para {column}."
            )

        result = getattr(values, statistic)()

        return {
            "operation": name,
            "column": column,
            "statistic": statistic,
            "value": round(float(result), 8),
        }

    if name == "trend":
        first = float(df["close"].iloc[0])
        last = float(df["close"].iloc[-1])
        variation = (last / first - 1) * 100

        if variation > 0:
            direction = "alta"
        elif variation < 0:
            direction = "baixa"
        else:
            direction = "lateral"

        return {
            "operation": name,
            "direction": direction,
            "first_close": round(first, 8),
            "last_close": round(last, 8),
            "variation_pct": round(variation, 8),
        }

    if name == "top_moves":
        moves = df[["time", "return_pct"]].dropna().copy()
        moves["absolute_return"] = moves["return_pct"].abs()
        moves = moves.nlargest(operation.limit, "absolute_return")

        return {
            "operation": name,
            "limit": operation.limit,
            "movements": [
                {
                    "time": row.time.isoformat(),
                    "return_pct": round(float(row.return_pct), 8),
                }
                for row in moves.itertuples()
            ],
        }

    if name == "correlation":
        correlation = df[column].corr(operation.other_column and df[operation.other_column])

        if pd.isna(correlation):
            raise ValueError("Não foi possível calcular a correlação.")

        return {
            "operation": name,
            "columns": [column, operation.other_column],
            "pearson_correlation": round(float(correlation), 8),
        }

    if name == "group_by_hour":
        grouped = df.assign(
            hour=df["time"].dt.hour
        ).groupby("hour")[column].agg(statistic)

        return {
            "operation": name,
            "column": column,
            "statistic": statistic,
            "values_by_hour": {
                str(int(hour)): round(float(value), 8)
                for hour, value in grouped.items()
                if pd.notna(value)
            },
        }

    raise ValueError(f"Operação não suportada: {name}")


@tool(args_schema=MarketAnalysisInput)
def analisar_dados_mercado(
    operations: list[OperationName],
    symbol: str = "EUR/USD",
    interval: str = "1min",
    candles_limit: int = 100,
    top_moves_limit: int = 5,
    aggregate_column: Column | None = None,
    aggregate_statistic: Statistic = "mean",
    correlation_column: Column | None = None,
    correlation_other_column: Column | None = None,
    group_by_hour_column: Column | None = None,
    group_by_hour_statistic: Statistic = "mean",
) -> str:
    """Executa múltiplas análises estatísticas sobre candles de mercado."""

    try:
        validate_operations(
            operations,
            aggregate_column,
            correlation_column,
            correlation_other_column,
            group_by_hour_column,
        )
    except ValueError as error:
        return f"Não foi possível executar a análise: {error}"

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

    candles = get_candles(
        symbol=symbol,
        interval=normalized_interval,
        limit=candles_limit,
    )

    if len(candles) < 2:
        return "Dados insuficientes para realizar a análise."

    df = prepare_dataframe(candles)

    analysis_operations = []

    try:
        for name in operations:
            if name == "trend":
                operation = AnalysisOperation(operation=name)

            elif name == "top_moves":
                operation = AnalysisOperation(
                    operation=name,
                    limit=top_moves_limit,
                )

            elif name == "aggregate":
                operation = AnalysisOperation(
                    operation=name,
                    column=aggregate_column,
                    statistic=aggregate_statistic,
                )

            elif name == "correlation":
                operation = AnalysisOperation(
                    operation=name,
                    column=correlation_column,
                    other_column=correlation_other_column,
                )

            elif name == "group_by_hour":
                operation = AnalysisOperation(
                    operation=name,
                    column=group_by_hour_column,
                    statistic=group_by_hour_statistic,
                )

            else:
                raise ValueError(f"Operação não suportada: {name}")

            analysis_operations.append(operation)

        results = [
            execute_operation(df, operation)
            for operation in analysis_operations
        ]

    except (ValueError, KeyError) as error:
        return f"Não foi possível executar a análise: {error}"

    response = {
        "symbol": symbol,
        "interval": normalized_interval,
        "candles_analyzed": len(df),
        "period": {
            "start": df.iloc[0]["time"].isoformat(),
            "end": df.iloc[-1]["time"].isoformat(),
        },
        "results": results,
        "methodology": (
            "Retornos e amplitudes expressos em percentual. "
            "Correlação calculada pelo coeficiente de Pearson. "
            "Agrupamentos horários utilizam UTC."
        ),
    }

    print(
        f"\n[TOOL] {len(df)} candles consultados. "
        f"{len(results)} operações executadas pelo Pandas."
    )

    return json.dumps(response, ensure_ascii=False)
