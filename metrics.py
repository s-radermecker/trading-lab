import pandas as pd


def _calculate_streaks(trades_df: pd.DataFrame, pnl_col: str) -> tuple[int, int]:
    max_winning_streak = 0
    max_losing_streak = 0

    current_winning_streak = 0
    current_losing_streak = 0

    for pnl in trades_df[pnl_col]:
        if pnl > 0:
            current_winning_streak += 1
            current_losing_streak = 0
        elif pnl < 0:
            current_losing_streak += 1
            current_winning_streak = 0
        else:
            current_winning_streak = 0
            current_losing_streak = 0

        max_winning_streak = max(max_winning_streak, current_winning_streak)
        max_losing_streak = max(max_losing_streak, current_losing_streak)

    return max_winning_streak, max_losing_streak


def calculate_basic_metrics(trades_df: pd.DataFrame, equity_df: pd.DataFrame | None = None) -> dict:
    if trades_df.empty:
        return {
            "number_of_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "breakeven_trades": 0,
            "win_rate": 0,
            "total_pnl": 0,
            "average_return": 0,
            "average_gain": 0,
            "average_loss": 0,
            "expectancy": 0,
            "profit_factor": 0,
            "max_winning_streak": 0,
            "max_losing_streak": 0,
            "max_drawdown": 0
        }

    pnl_col = "PnL_R" if "PnL_R" in trades_df.columns else "PnL"

    number_of_trades = len(trades_df)
    winning_trades = len(trades_df[trades_df[pnl_col] > 0])
    losing_trades = len(trades_df[trades_df[pnl_col] < 0])
    breakeven_trades = len(trades_df[trades_df[pnl_col] == 0])

    win_rate = (winning_trades / number_of_trades) * 100 if number_of_trades > 0 else 0
    total_pnl = trades_df[pnl_col].sum()
    average_return = trades_df[pnl_col].mean()

    gains = trades_df[trades_df[pnl_col] > 0][pnl_col]
    losses = trades_df[trades_df[pnl_col] < 0][pnl_col]

    average_gain = gains.mean() if not gains.empty else 0
    average_loss = losses.mean() if not losses.empty else 0
    expectancy = trades_df[pnl_col].mean() if number_of_trades > 0 else 0

    gross_profit = gains.sum() if not gains.empty else 0
    gross_loss = abs(losses.sum()) if not losses.empty else 0

    if gross_loss == 0:
        profit_factor = 0 if gross_profit == 0 else float("inf")
    else:
        profit_factor = gross_profit / gross_loss

    max_winning_streak, max_losing_streak = _calculate_streaks(trades_df, pnl_col)

    max_drawdown = 0
    if equity_df is not None and not equity_df.empty:
        running_max = equity_df["Equity"].cummax()
        drawdown = equity_df["Equity"] - running_max
        max_drawdown = drawdown.min()

    return {
        "number_of_trades": number_of_trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "breakeven_trades": breakeven_trades,
        "win_rate": round(win_rate, 2),
        "total_pnl": round(total_pnl, 2),
        "average_return": round(average_return, 2),
        "average_gain": round(average_gain, 2),
        "average_loss": round(average_loss, 2),
        "expectancy": round(expectancy, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else "inf",
        "max_winning_streak": max_winning_streak,
        "max_losing_streak": max_losing_streak,
        "max_drawdown": round(max_drawdown, 2)
    }