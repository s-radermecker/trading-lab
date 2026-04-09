import pandas as pd


def _calculate_atr(df: pd.DataFrame, atr_window: int) -> pd.Series:
    prev_close = df["Close"].shift(1)

    tr1 = df["High"] - df["Low"]
    tr2 = (df["High"] - prev_close).abs()
    tr3 = (df["Low"] - prev_close).abs()

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.rolling(window=atr_window).mean()

    return atr


def _calculate_adx(df: pd.DataFrame, adx_window: int) -> pd.Series:
    high_diff = df["High"].diff()
    low_diff = df["Low"].shift(1) - df["Low"]

    plus_dm = high_diff.where((high_diff > low_diff) & (high_diff > 0), 0.0)
    minus_dm = low_diff.where((low_diff > high_diff) & (low_diff > 0), 0.0)

    prev_close = df["Close"].shift(1)

    tr1 = df["High"] - df["Low"]
    tr2 = (df["High"] - prev_close).abs()
    tr3 = (df["Low"] - prev_close).abs()

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.rolling(window=adx_window).mean()

    plus_di = 100 * (plus_dm.rolling(window=adx_window).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(window=adx_window).mean() / atr)

    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di))
    adx = dx.rolling(window=adx_window).mean()

    return adx


def _is_in_session(hour_series: pd.Series, start_hour: int, end_hour: int) -> pd.Series:
    if start_hour == end_hour:
        return pd.Series(True, index=hour_series.index)

    if start_hour < end_hour:
        return (hour_series >= start_hour) & (hour_series < end_hour)

    return (hour_series >= start_hour) | (hour_series < end_hour)


def calculate_sma_strategy(
    df: pd.DataFrame,
    short_window: int,
    long_window: int,
    trend_filter_enabled: bool = False,
    trend_filter_window: int = 50,
    volatility_filter_enabled: bool = False,
    atr_window: int = 14,
    min_atr_pct: float = 0.20,
    regime_filter_enabled: bool = False,
    adx_window: int = 14,
    min_adx: float = 20.0,
    session_filter_enabled: bool = False,
    session_start_hour: int = 8,
    session_end_hour: int = 17,
    strategy_mode: str = "normal"
) -> pd.DataFrame:
    df = df.copy()

    df["SMA_Courte"] = df["Close"].rolling(window=short_window).mean()
    df["SMA_Longue"] = df["Close"].rolling(window=long_window).mean()

    if trend_filter_enabled:
        df["SMA_Filtre"] = df["Close"].rolling(window=trend_filter_window).mean()
    else:
        df["SMA_Filtre"] = pd.NA

    df["ATR"] = _calculate_atr(df, atr_window)
    df["ATR_Pct"] = (df["ATR"] / df["Close"]) * 100
    df["ADX"] = _calculate_adx(df, adx_window)

    df["Signal"] = 0
    df.loc[df["SMA_Courte"] > df["SMA_Longue"], "Signal"] = 1
    df.loc[df["SMA_Courte"] < df["SMA_Longue"], "Signal"] = -1

    if trend_filter_enabled:
        df.loc[(df["Signal"] == 1) & (df["Close"] <= df["SMA_Filtre"]), "Signal"] = 0
        df.loc[(df["Signal"] == -1) & (df["Close"] >= df["SMA_Filtre"]), "Signal"] = 0

    if volatility_filter_enabled:
        df.loc[df["ATR_Pct"].isna(), "Signal"] = 0
        df.loc[df["ATR_Pct"] < min_atr_pct, "Signal"] = 0

    if regime_filter_enabled:
        df.loc[df["ADX"].isna(), "Signal"] = 0
        df.loc[df["ADX"] < min_adx, "Signal"] = 0

    if session_filter_enabled:
        hours = df["Date"].dt.hour
        in_session = _is_in_session(hours, session_start_hour, session_end_hour)
        df.loc[~in_session, "Signal"] = 0



    df["Position_Change"] = df["Signal"].diff().fillna(0)

    return df

def calculate_impulse_pullback_break_strategy(
    df: pd.DataFrame,
    trend_lookback_bars: int = 100,
    atr_window: int = 14,
    min_trend_atr_multiple: float = 3.0,
    pullback_max_bars: int = 6,
    pullback_max_depth_atr: float = 1.5,
    confirmation_bars: int = 1
) -> pd.DataFrame:
    df = df.copy()

    df["ATR"] = _calculate_atr(df, atr_window)

    df["Trend_Move"] = df["Close"] - df["Close"].shift(trend_lookback_bars)
    df["Trend_Move_ATR"] = df["Trend_Move"] / df["ATR"]

    df["Impulse_Direction"] = 0
    df.loc[df["Trend_Move_ATR"] >= min_trend_atr_multiple, "Impulse_Direction"] = 1
    df.loc[df["Trend_Move_ATR"] <= -min_trend_atr_multiple, "Impulse_Direction"] = -1

    df["Pullback_High"] = pd.NA
    df["Pullback_Low"] = pd.NA
    df["Pullback_Depth"] = pd.NA
    df["Pullback_Valid"] = False

    df["Signal"] = 0

    for i in range(trend_lookback_bars + pullback_max_bars + confirmation_bars, len(df)):
        impulse_direction = int(df.iloc[i]["Impulse_Direction"])

        if impulse_direction == 0:
            continue

        pullback_slice = df.iloc[i - confirmation_bars - pullback_max_bars:i - confirmation_bars].copy()

        if pullback_slice.empty:
            continue

        pullback_high = float(pullback_slice["High"].max())
        pullback_low = float(pullback_slice["Low"].min())
        pullback_depth = pullback_high - pullback_low

        current_atr = df.iloc[i]["ATR"]
        if pd.isna(current_atr) or current_atr <= 0:
            continue

        pullback_depth_atr = pullback_depth / current_atr

        if pullback_depth_atr > pullback_max_depth_atr:
            continue

        df.at[df.index[i], "Pullback_High"] = pullback_high
        df.at[df.index[i], "Pullback_Low"] = pullback_low
        df.at[df.index[i], "Pullback_Depth"] = pullback_depth
        df.at[df.index[i], "Pullback_Valid"] = True

        confirmation_slice = df.iloc[i - confirmation_bars:i].copy()

        if confirmation_slice.empty or len(confirmation_slice) < confirmation_bars:
            continue

        if impulse_direction == 1:
            breakout_level = pullback_high
            if (confirmation_slice["Close"] > breakout_level).all():
                df.at[df.index[i], "Signal"] = 1

        elif impulse_direction == -1:
            breakout_level = pullback_low
            if (confirmation_slice["Close"] < breakout_level).all():
                df.at[df.index[i], "Signal"] = -1

    df["Position_Change"] = df["Signal"].diff().fillna(0)

    return df