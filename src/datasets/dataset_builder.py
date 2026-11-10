import pandas as pd

def build_dataset(candles, horizon=5, threshold=0.00005):
    if horizon < 1:
        raise ValueError("o horizonte deve ser maior que zero")
    if threshold < 0:
        raise ValueError("O threshold não pode ser negativo.")

    df = pd.DataFrame(candles)

    if df.empty:
        return df

    df["time"] = pd.to_datetime(df["time"], utc=True)

    price_columns = ["open", "high", "low", "close"]
    df[price_columns] = df[price_columns].astype(float)

    df = df.sort_values("time").drop_duplicates("time")
    df = df.reset_index(drop=True)

    df["return_1"] = df["close"].pct_change()
    df["return_5"] = df["close"].pct_change(5)
    df["volatility"] = df["return_1"].rolling(5).std()
    df["candle_range"] = (df["high"] - df["low"]) / df["close"]

    future = df[["time", "close"]].copy()
    future["time"] = future["time"] - pd.Timedelta(minutes=horizon)
    future = future.rename(columns={"close": "future_close"})

    df = df.merge(future, on="time", how="left")

    future_return = (df["future_close"] - df["close"]) / df["close"]
   
    df["target"] = 0
    df.loc[future_return > threshold, "target"] = 1
    df.loc[future_return< -threshold, "target"] = -1

    return df.dropna().drop(columns=["future_close"]).reset_index(drop=True)


