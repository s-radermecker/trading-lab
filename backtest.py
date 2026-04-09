import pandas as pd


def _open_trade(side: str, row: pd.Series, prev_row: pd.Series, rr_target: float, strategy_mode: str = "normal"):
    entry_price = float(row["Close"])
    entry_date = row["Date"]

    if side == "long":
        normal_stop_price = float(prev_row["Low"])
        normal_risk_distance = entry_price - normal_stop_price
        normal_target_price = entry_price + (normal_risk_distance * rr_target)

        if normal_risk_distance <= 0:
            return None

        if strategy_mode == "inverse":
            executed_side = "short"
            stop_price = normal_target_price
            target_price = normal_stop_price
            risk_distance = stop_price - entry_price
        else:
            executed_side = "long"
            stop_price = normal_stop_price
            target_price = normal_target_price
            risk_distance = entry_price - stop_price

    else:
        normal_stop_price = float(prev_row["High"])
        normal_risk_distance = normal_stop_price - entry_price
        normal_target_price = entry_price - (normal_risk_distance * rr_target)

        if normal_risk_distance <= 0:
            return None

        if strategy_mode == "inverse":
            executed_side = "long"
            stop_price = normal_target_price
            target_price = normal_stop_price
            risk_distance = entry_price - stop_price
        else:
            executed_side = "short"
            stop_price = normal_stop_price
            target_price = normal_target_price
            risk_distance = stop_price - entry_price

    if risk_distance <= 0:
        return None

    return {
        "Side": executed_side,
        "Entry Date": entry_date,
        "Entry Price": entry_price,
        "Stop Price": stop_price,
        "Target Price": target_price,
        "Risk Distance": risk_distance
    }


def _close_trade(current_trade: dict, exit_price: float, exit_date, exit_reason: str, cost_per_trade_r: float = 0.0):
    entry_price = current_trade["Entry Price"]
    risk_distance = current_trade["Risk Distance"]
    side = current_trade["Side"]

    if side == "long":
        price_move = exit_price - entry_price
    else:
        price_move = entry_price - exit_price

    gross_r_multiple = price_move / risk_distance if risk_distance != 0 else 0
    net_r_multiple = gross_r_multiple - cost_per_trade_r
    return_pct = (price_move / entry_price) * 100 if entry_price != 0 else 0

    return {
        "Side": side,
        "Entry Date": current_trade["Entry Date"],
        "Entry Price": round(entry_price, 5),
        "Stop Price": round(current_trade["Stop Price"], 5),
        "Target Price": round(current_trade["Target Price"], 5),
        "Risk Distance": round(risk_distance, 5),
        "Exit Date": exit_date,
        "Exit Price": round(exit_price, 5),
        "Exit Reason": exit_reason,
        "Price Move": round(price_move, 5),
        "Gross R": round(gross_r_multiple, 4),
        "Cost R": round(cost_per_trade_r, 4),
        "PnL": round(net_r_multiple, 4),
        "PnL_R": round(net_r_multiple, 4),
        "R Multiple": round(net_r_multiple, 4),
        "Return %": round(return_pct, 4)
    }


def run_simple_backtest(
    df: pd.DataFrame,
    rr_target: float = 2.0,
    trade_mode: str = "both",
    cost_per_trade_r: float = 0.0,
    strategy_mode: str = "normal"
) -> pd.DataFrame:
    trades = []
    current_trade = None

    for i in range(1, len(df)):
        row = df.iloc[i]
        prev_row = df.iloc[i - 1]
        signal = int(row["Signal"])
        prev_signal = int(prev_row["Signal"])

        if current_trade is None:
            long_cross = prev_signal != 1 and signal == 1
            short_cross = prev_signal != -1 and signal == -1

            can_open_long = long_cross and trade_mode in ["both", "long_only"]
            can_open_short = short_cross and trade_mode in ["both", "short_only"]

            if can_open_long:
                current_trade = _open_trade("long", row, prev_row, rr_target, strategy_mode=strategy_mode)
            elif can_open_short:
                current_trade = _open_trade("short", row, prev_row, rr_target, strategy_mode=strategy_mode)

        else:
            side = current_trade["Side"]
            stop_price = current_trade["Stop Price"]
            target_price = current_trade["Target Price"]

            if side == "long":
                stop_hit = float(row["Low"]) <= stop_price
                target_hit = float(row["High"]) >= target_price
                reverse_signal = signal == -1

                both_hit = stop_hit and target_hit

                if both_hit:
                    trades.append(
                        _close_trade(current_trade, stop_price, row["Date"], "Stop Loss (Conflit OHLC)", cost_per_trade_r)
                    )
                    current_trade = None

                elif stop_hit:
                    trades.append(
                        _close_trade(current_trade, stop_price, row["Date"], "Stop Loss", cost_per_trade_r)
                    )
                    current_trade = None

                elif target_hit:
                    trades.append(
                        _close_trade(current_trade, target_price, row["Date"], "Take Profit", cost_per_trade_r)
                    )
                    current_trade = None

                elif reverse_signal:
                    trades.append(
                        _close_trade(current_trade, float(row["Close"]), row["Date"], "Signal Inverse", cost_per_trade_r)
                    )
                    current_trade = None

            elif side == "short":
                stop_hit = float(row["High"]) >= stop_price
                target_hit = float(row["Low"]) <= target_price
                reverse_signal = signal == 1

                both_hit = stop_hit and target_hit

                if both_hit:
                    trades.append(
                        _close_trade(current_trade, stop_price, row["Date"], "Stop Loss (Conflit OHLC)", cost_per_trade_r)
                    )
                    current_trade = None

                elif stop_hit:
                    trades.append(
                        _close_trade(current_trade, stop_price, row["Date"], "Stop Loss", cost_per_trade_r)
                    )
                    current_trade = None

                elif target_hit:
                    trades.append(
                        _close_trade(current_trade, target_price, row["Date"], "Take Profit", cost_per_trade_r)
                    )
                    current_trade = None

                elif reverse_signal:
                    trades.append(
                        _close_trade(current_trade, float(row["Close"]), row["Date"], "Signal Inverse", cost_per_trade_r)
                    )
                    current_trade = None

    if current_trade is not None:
        last_row = df.iloc[-1]
        trades.append(
            _close_trade(
                current_trade,
                float(last_row["Close"]),
                last_row["Date"],
                "Fin de Données",
                cost_per_trade_r
            )
        )

    return pd.DataFrame(trades)


def build_equity_curve(trades_df: pd.DataFrame, starting_r: float = 0.0) -> pd.DataFrame:
    equity = starting_r
    equity_points = [{"Step": 0, "Equity": equity}]

    pnl_col = "PnL_R" if "PnL_R" in trades_df.columns else "PnL"

    for i in range(len(trades_df)):
        equity += float(trades_df.iloc[i][pnl_col])
        equity_points.append({
            "Step": i + 1,
            "Equity": round(equity, 4)
        })

    return pd.DataFrame(equity_points)