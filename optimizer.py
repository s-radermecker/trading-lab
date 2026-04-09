import pandas as pd

from strategies import calculate_sma_strategy, calculate_impulse_pullback_break_strategy
from backtest import run_simple_backtest, build_equity_curve
from metrics import calculate_basic_metrics


def optimize_parameters(
    df_insample: pd.DataFrame,
    short_values,
    long_values,
    rr_values,
    trade_mode: str = "both",
    cost_per_trade_r: float = 0.0,
    min_trades: int = 10,
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
    session_names_to_test=None,
    session_presets=None,
    atr_window_values=None,
    min_atr_pct_values=None,
    trend_filter_window_values=None,
    adx_window_values=None,
    min_adx_values=None,
    strategy_mode: str = "normal",
    progress_callback=None
) -> pd.DataFrame:
    results = []

    if trend_filter_enabled:
        trend_windows_to_test = (
            trend_filter_window_values
            if trend_filter_window_values is not None
            else [trend_filter_window]
        )
    else:
        trend_windows_to_test = [trend_filter_window]

    if volatility_filter_enabled:
        atr_windows_to_test = (
            atr_window_values if atr_window_values is not None else [atr_window]
        )
        min_atr_pct_to_test = (
            min_atr_pct_values if min_atr_pct_values is not None else [min_atr_pct]
        )
    else:
        atr_windows_to_test = [atr_window]
        min_atr_pct_to_test = [min_atr_pct]

    if regime_filter_enabled:
        adx_windows_to_test = (
            adx_window_values if adx_window_values is not None else [adx_window]
        )
        min_adx_to_test = (
            min_adx_values if min_adx_values is not None else [min_adx]
        )
    else:
        adx_windows_to_test = [adx_window]
        min_adx_to_test = [min_adx]

    if session_names_to_test is None:
        session_names_to_test = ["Aucune"]

    if session_presets is None:
        session_presets = {}

    total_iterations = (
        len(short_values)
        * len(long_values)
        * len(rr_values)
        * len(trend_windows_to_test)
        * len(atr_windows_to_test)
        * len(min_atr_pct_to_test)
        * len(adx_windows_to_test)
        * len(min_adx_to_test)
        * len(session_names_to_test)
    )
    completed_iterations = 0

    for short_window in short_values:
        for long_window in long_values:
            if short_window >= long_window:
                continue

            for rr_target in rr_values:
                for tested_trend_filter_window in trend_windows_to_test:
                    for tested_atr_window in atr_windows_to_test:
                        for tested_min_atr_pct in min_atr_pct_to_test:
                            for tested_adx_window in adx_windows_to_test:
                                for tested_min_adx in min_adx_to_test:
                                    for tested_session_name in session_names_to_test:
                                        completed_iterations += 1
                                        if progress_callback is not None:
                                            progress_callback(completed_iterations, total_iterations)

                                        if tested_session_name == "Aucune":
                                            tested_session_filter_enabled = False
                                            tested_session_start_hour = 8
                                            tested_session_end_hour = 17
                                        else:
                                            tested_session_filter_enabled = True
                                            tested_session_start_hour, tested_session_end_hour = session_presets[tested_session_name]

                                        test_df = calculate_sma_strategy(
                                            df_insample.copy(),
                                            short_window,
                                            long_window,
                                            trend_filter_enabled=trend_filter_enabled,
                                            trend_filter_window=tested_trend_filter_window,
                                            volatility_filter_enabled=volatility_filter_enabled,
                                            atr_window=tested_atr_window,
                                            min_atr_pct=tested_min_atr_pct,
                                            regime_filter_enabled=regime_filter_enabled,
                                            adx_window=tested_adx_window,
                                            min_adx=tested_min_adx,
                                            session_filter_enabled=tested_session_filter_enabled,
                                            session_start_hour=tested_session_start_hour,
                                            session_end_hour=tested_session_end_hour,
                                            strategy_mode=strategy_mode
                                        )

                                        trades_df = run_simple_backtest(
                                            test_df,
                                            rr_target=rr_target,
                                            trade_mode=trade_mode,
                                            cost_per_trade_r=cost_per_trade_r,
                                            strategy_mode=strategy_mode
                                        )

                                        if trades_df.empty:
                                            continue

                                        if len(trades_df) < min_trades:
                                            continue

                                        equity_df = build_equity_curve(trades_df, starting_r=0.0)
                                        metrics = calculate_basic_metrics(trades_df, equity_df)

                                        robustness_score = 0.0
                                        robustness_score += metrics["expectancy"] * 100
                                        robustness_score += min(metrics["number_of_trades"], 300) * 0.2
                                        robustness_score += metrics["total_pnl"] * 2
                                        robustness_score -= abs(metrics["max_drawdown"]) * 5

                                        if metrics["number_of_trades"] >= 200:
                                            robustness_score += 10
                                        elif metrics["number_of_trades"] >= 150:
                                            robustness_score += 5

                                        robustness_score = round(robustness_score, 2)

                                        results.append({
                                            "Short Window": short_window,
                                            "Long Window": long_window,
                                            "RR Target": rr_target,
                                            "Trend Filter Window": (
                                                tested_trend_filter_window if trend_filter_enabled else None
                                            ),
                                            "ATR Window": tested_atr_window if volatility_filter_enabled else None,
                                            "Min ATR %": round(tested_min_atr_pct, 2) if volatility_filter_enabled else None,
                                            "ADX Window": tested_adx_window if regime_filter_enabled else None,
                                            "Min ADX": round(tested_min_adx, 2) if regime_filter_enabled else None,
                                            "Session Name": tested_session_name,
                                            "Session Start": tested_session_start_hour if tested_session_filter_enabled else None,
                                            "Session End": tested_session_end_hour if tested_session_filter_enabled else None,
                                            "Trades": metrics["number_of_trades"],
                                            "Win Rate %": metrics["win_rate"],
                                            "Total R": metrics["total_pnl"],
                                            "Expectancy (R)": metrics["expectancy"],
                                            "Avg Gain (R)": metrics["average_gain"],
                                            "Avg Loss (R)": metrics["average_loss"],
                                            "Max Drawdown (R)": metrics["max_drawdown"],
                                            "Score robustesse IS": robustness_score
                                        })

    if not results:
        return pd.DataFrame(columns=[
            "Short Window",
            "Long Window",
            "RR Target",
            "Trend Filter Window",
            "ATR Window",
            "Min ATR %",
            "ADX Window",
            "Min ADX",
            "Session Name",
            "Session Start",
            "Session End",
            "Trades",
            "Win Rate %",
            "Total R",
            "Expectancy (R)",
            "Avg Gain (R)",
            "Avg Loss (R)",
            "Max Drawdown (R)",
            "Score robustesse IS"
        ])
    results_df = pd.DataFrame(results)

    results_df = results_df.sort_values(
        by=["Expectancy (R)", "Score robustesse IS", "Total R", "Trades", "Max Drawdown (R)"],
        ascending=[False, False, False, False, False]
    ).reset_index(drop=True)

    return results_df

def optimize_impulse_parameters(
    df_insample: pd.DataFrame,
    trend_lookback_values,
    atr_window_values,
    min_trend_atr_multiple_values,
    pullback_max_bars_values,
    pullback_max_depth_atr_values,
    confirmation_bars_values,
    rr_values,
    trade_mode: str = "both",
    cost_per_trade_r: float = 0.0,
    min_trades: int = 10,
    strategy_mode: str = "normal",
    progress_callback=None
) -> pd.DataFrame:
    results = []

    total_iterations = (
        len(trend_lookback_values)
        * len(atr_window_values)
        * len(min_trend_atr_multiple_values)
        * len(pullback_max_bars_values)
        * len(pullback_max_depth_atr_values)
        * len(confirmation_bars_values)
        * len(rr_values)
    )
    completed_iterations = 0

    for trend_lookback_bars in trend_lookback_values:
        for atr_window in atr_window_values:
            for min_trend_atr_multiple in min_trend_atr_multiple_values:
                for pullback_max_bars in pullback_max_bars_values:
                    for pullback_max_depth_atr in pullback_max_depth_atr_values:
                        for confirmation_bars in confirmation_bars_values:
                            for rr_target in rr_values:
                                completed_iterations += 1
                                if progress_callback is not None:
                                    progress_callback(completed_iterations, total_iterations)

                                test_df = calculate_impulse_pullback_break_strategy(
                                    df_insample.copy(),
                                    trend_lookback_bars=trend_lookback_bars,
                                    atr_window=atr_window,
                                    min_trend_atr_multiple=min_trend_atr_multiple,
                                    pullback_max_bars=pullback_max_bars,
                                    pullback_max_depth_atr=pullback_max_depth_atr,
                                    confirmation_bars=confirmation_bars
                                )

                                trades_df = run_simple_backtest(
                                    test_df,
                                    rr_target=rr_target,
                                    trade_mode=trade_mode,
                                    cost_per_trade_r=cost_per_trade_r,
                                    strategy_mode=strategy_mode
                                )

                                if trades_df.empty:
                                    continue

                                if len(trades_df) < min_trades:
                                    continue

                                equity_df = build_equity_curve(trades_df, starting_r=0.0)
                                metrics = calculate_basic_metrics(trades_df, equity_df)

                                robustness_score = 0.0
                                robustness_score += metrics["expectancy"] * 100
                                robustness_score += min(metrics["number_of_trades"], 300) * 0.2
                                robustness_score += metrics["total_pnl"] * 2
                                robustness_score -= abs(metrics["max_drawdown"]) * 5

                                if metrics["number_of_trades"] >= 200:
                                    robustness_score += 10
                                elif metrics["number_of_trades"] >= 150:
                                    robustness_score += 5

                                robustness_score = round(robustness_score, 2)

                                results.append({
                                    "Trend Lookback": trend_lookback_bars,
                                    "ATR Window": atr_window,
                                    "Min Trend ATR Multiple": round(min_trend_atr_multiple, 2),
                                    "Pullback Max Bars": pullback_max_bars,
                                    "Pullback Max Depth ATR": round(pullback_max_depth_atr, 2),
                                    "Confirmation Bars": confirmation_bars,
                                    "RR Target": rr_target,
                                    "Trades": metrics["number_of_trades"],
                                    "Win Rate %": metrics["win_rate"],
                                    "Total R": metrics["total_pnl"],
                                    "Expectancy (R)": metrics["expectancy"],
                                    "Avg Gain (R)": metrics["average_gain"],
                                    "Avg Loss (R)": metrics["average_loss"],
                                    "Max Drawdown (R)": metrics["max_drawdown"],
                                    "Score robustesse IS": robustness_score
                                })

    if not results:
        return pd.DataFrame(columns=[
            "Trend Lookback",
            "ATR Window",
            "Min Trend ATR Multiple",
            "Pullback Max Bars",
            "Pullback Max Depth ATR",
            "Confirmation Bars",
            "RR Target",
            "Trades",
            "Win Rate %",
            "Total R",
            "Expectancy (R)",
            "Avg Gain (R)",
            "Avg Loss (R)",
            "Max Drawdown (R)",
            "Score robustesse IS"
        ])

    results_df = pd.DataFrame(results)

    results_df = results_df.sort_values(
        by=["Expectancy (R)", "Score robustesse IS", "Total R", "Trades", "Max Drawdown (R)"],
        ascending=[False, False, False, False, False]
    ).reset_index(drop=True)

    return results_df