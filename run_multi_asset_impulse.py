from pathlib import Path
import json
import time
from itertools import product
from concurrent.futures import ProcessPoolExecutor, as_completed
import pandas as pd

from strategies import calculate_impulse_pullback_break_strategy
from backtest import run_simple_backtest, build_equity_curve
from metrics import calculate_basic_metrics


BASE_DIR = Path.home() / "Desktop" / "Trading Lab"
SAMPLE_DIR = BASE_DIR / "Sample"
BATCH_RESULTS_DIR = BASE_DIR / "batch_results"
CAMPAIGNS_DIR = BATCH_RESULTS_DIR / "campaigns"
MASTER_SUMMARY_FILE = BATCH_RESULTS_DIR / "master_batch_summary.csv"


campaign_name = "2026-04-04_frequence_fx_ciblee_nuit_v1"
preset = "Fréquence FX ciblée"
strategy_name = "Impulse Pullback Break V1"
timeframe = "M15"

assets = ["EURUSD", "GBPUSD"]

files_map = {
    "EURUSD": SAMPLE_DIR / "EURUSD_M15.csv",
    "GBPUSD": SAMPLE_DIR / "GBPUSD_M15.csv",
    "USDJPY": SAMPLE_DIR / "USDJPY_M15.csv",
    "GBPJPY": SAMPLE_DIR / "GBPJPY_M15.csv",
    "XAUUSD": SAMPLE_DIR / "XAUUSD_M15.csv",
}
max_workers = 2

def get_impulse_grid(preset_name: str):
    if preset_name == "Test":
        return {
            "trend_lookback_values": [80, 120],
            "atr_window_values": [14],
            "min_trend_atr_multiple_values": [2.0],
            "pullback_max_bars_values": [4],
            "pullback_max_depth_atr_values": [1.0],
            "confirmation_bars_values": [1],
            "rr_values": [1.0],
        }
    elif preset_name == "Exploration courte":
        return {
            "trend_lookback_values": [80, 120],
            "atr_window_values": [14],
            "min_trend_atr_multiple_values": [2.0, 3.0],
            "pullback_max_bars_values": [4, 6],
            "pullback_max_depth_atr_values": [1.0],
            "confirmation_bars_values": [1, 2],
            "rr_values": [1.0, 1.5],
        }
    elif preset_name == "Nuit":
        return {
            "trend_lookback_values": [60, 80, 120, 160],
            "atr_window_values": [14, 20],
            "min_trend_atr_multiple_values": [2.0, 2.5, 3.0, 3.5],
            "pullback_max_bars_values": [4, 6],
            "pullback_max_depth_atr_values": [1.0, 1.5],
            "confirmation_bars_values": [1, 2],
            "rr_values": [1.0, 1.5],
        }
    elif preset_name == "Focus FX":
        return {
            "trend_lookback_values": [60, 80, 120],
            "atr_window_values": [14],
            "min_trend_atr_multiple_values": [2.5, 3.0, 3.5],
            "pullback_max_bars_values": [6],
            "pullback_max_depth_atr_values": [1.0],
            "confirmation_bars_values": [1, 2],
            "rr_values": [1.0, 1.5],
        }
    elif preset_name == "Noyau FX":
        return {
            "trend_lookback_values": [60, 80, 120],
            "atr_window_values": [14],
            "min_trend_atr_multiple_values": [3.0, 3.5],
            "pullback_max_bars_values": [6],
            "pullback_max_depth_atr_values": [1.0],
            "confirmation_bars_values": [2],
            "rr_values": [1.0, 1.5],
        }
    elif preset_name == "Fréquence contrôlée":
        return {
            "trend_lookback_values": [60, 80, 120],
            "atr_window_values": [14],
            "min_trend_atr_multiple_values": [2.5, 3.0, 3.5],
            "pullback_max_bars_values": [4, 6],
            "pullback_max_depth_atr_values": [1.0],
            "confirmation_bars_values": [1, 2],
            "rr_values": [1.0, 1.5],
        }
    elif preset_name == "Fréquence FX ciblée":
        return {
            "trend_lookback_values": [40, 50, 60, 70, 80],
            "atr_window_values": [14],
            "min_trend_atr_multiple_values": [2.0, 2.25, 2.5, 2.75, 3.0, 3.5],
            "pullback_max_bars_values": [5, 6, 7, 8],
            "pullback_max_depth_atr_values": [0.8, 1.0],
            "confirmation_bars_values": [1, 2],
            "rr_values": [1.0, 1.5],
        }
    elif preset_name == "Rapide":
        return {
            "trend_lookback_values": [80, 120],
            "atr_window_values": [14, 20],
            "min_trend_atr_multiple_values": [2.0, 3.0],
            "pullback_max_bars_values": [4, 6],
            "pullback_max_depth_atr_values": [1.0, 1.5],
            "confirmation_bars_values": [1, 2],
            "rr_values": [1.0, 2.0],
        }
    elif preset_name == "30-45 min":
        return {
            "trend_lookback_values": [80, 100, 120],
            "atr_window_values": [14, 20],
            "min_trend_atr_multiple_values": [2.0, 2.5, 3.0],
            "pullback_max_bars_values": [4, 6, 8],
            "pullback_max_depth_atr_values": [1.0, 1.2, 1.5],
            "confirmation_bars_values": [1, 2],
            "rr_values": [1.0, 1.5, 2.0],
        }
    elif preset_name == "2H / Salle":
        return {
            "trend_lookback_values": [80, 100, 120, 140],
            "atr_window_values": [10, 14, 20],
            "min_trend_atr_multiple_values": [1.5, 2.0, 2.5],
            "pullback_max_bars_values": [4, 6, 8],
            "pullback_max_depth_atr_values": [0.8, 1.0, 1.2],
            "confirmation_bars_values": [1, 2],
            "rr_values": [1.0, 1.5, 2.0, 2.5],
        }
    elif preset_name == "Nuit léger":
        return {
            "trend_lookback_values": [60, 80, 100, 120, 140, 160],
            "atr_window_values": [10, 14, 20],
            "min_trend_atr_multiple_values": [1.5, 2.0, 2.5, 3.0],
            "pullback_max_bars_values": [3, 4, 6, 8],
            "pullback_max_depth_atr_values": [0.8, 1.0, 1.2, 1.5],
            "confirmation_bars_values": [1, 2],
            "rr_values": [1.0, 1.5, 2.0, 2.5],
        }
    else:
        return {
            "trend_lookback_values": [40, 60, 80, 100, 120, 140, 160, 180],
            "atr_window_values": [8, 10, 14, 20],
            "min_trend_atr_multiple_values": [1.0, 1.5, 2.0, 2.5, 3.0],
            "pullback_max_bars_values": [2, 3, 4, 6, 8],
            "pullback_max_depth_atr_values": [0.6, 0.8, 1.0, 1.2, 1.5],
            "confirmation_bars_values": [1, 2],
            "rr_values": [1.0, 1.5, 2.0, 2.5, 3.0],
        }


def run_impulse_batch_optimization(df: pd.DataFrame, preset_name: str, asset_name: str = ""):
    grid = get_impulse_grid(preset_name)

    combinations = list(product(
        grid["trend_lookback_values"],
        grid["atr_window_values"],
        grid["min_trend_atr_multiple_values"],
        grid["pullback_max_bars_values"],
        grid["pullback_max_depth_atr_values"],
        grid["confirmation_bars_values"],
        grid["rr_values"],
    ))

    total_combinations = len(combinations)
    results = []

    for idx, (
        trend_lookback,
        atr_window,
        min_trend_atr_multiple,
        pullback_max_bars,
        pullback_max_depth_atr,
        confirmation_bars,
        rr_target,
    ) in enumerate(combinations, start=1):
        if idx == 1 or idx % 100 == 0 or idx == total_combinations:
            print(f"[PROGRESSION {asset_name}] {idx}/{total_combinations}")
        strat_df = calculate_impulse_pullback_break_strategy(
            df.copy(),
            trend_lookback_bars=trend_lookback,
            atr_window=atr_window,
            min_trend_atr_multiple=min_trend_atr_multiple,
            pullback_max_bars=pullback_max_bars,
            pullback_max_depth_atr=pullback_max_depth_atr,
            confirmation_bars=confirmation_bars
        )

        trades = run_simple_backtest(
            strat_df,
            rr_target=rr_target,
            trade_mode="both",
            cost_per_trade_r=0.0,
            strategy_mode="normal"
        )

        equity = build_equity_curve(trades, starting_r=0.0)
        metrics = calculate_basic_metrics(trades, equity)

        pnl_values = extract_trade_pnl_values(trades)

        wins = [x for x in pnl_values if x > 0]
        losses = [x for x in pnl_values if x < 0]

        if len(pnl_values) > 0:
            win_rate = round((len(wins) / len(pnl_values)) * 100, 2)
            avg_trade_r = round(sum(pnl_values) / len(pnl_values), 4)
        else:
            win_rate = 0.0
            avg_trade_r = 0.0

        avg_win_r = round(sum(wins) / len(wins), 4) if wins else 0.0
        avg_loss_r = round(sum(losses) / len(losses), 4) if losses else 0.0

        gross_profit = sum(wins) if wins else 0.0
        gross_loss_abs = abs(sum(losses)) if losses else 0.0

        if gross_loss_abs > 0:
            profit_factor = round(gross_profit / gross_loss_abs, 4)
        elif gross_profit > 0:
            profit_factor = 999.0
        else:
            profit_factor = 0.0

        results.append({
            "trend_lookback": trend_lookback,
            "atr_window": atr_window,
            "min_trend_atr_multiple": min_trend_atr_multiple,
            "pullback_max_bars": pullback_max_bars,
            "pullback_max_depth_atr": pullback_max_depth_atr,
            "confirmation_bars": confirmation_bars,
            "rr_target": rr_target,
            "trades": metrics["number_of_trades"],
            "expectancy": metrics["expectancy"],
            "total_r": metrics["total_pnl"],
            "max_dd": metrics["max_drawdown"],
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "avg_win_r": avg_win_r,
            "avg_loss_r": avg_loss_r,
            "avg_trade_r": avg_trade_r,
        })

    results_df = pd.DataFrame(results).sort_values(
        by=["expectancy", "total_r"],
        ascending=[False, False]
    ).reset_index(drop=True)

    return results_df
def extract_trade_pnl_values(trades):
    pnl_values = []

    if trades is None:
        return pnl_values

    if isinstance(trades, pd.DataFrame):
        candidate_cols = [
            "pnl_r", "PnL_R", "PnL r", "pnl", "PnL", "profit_r", "Profit_R", "R"
        ]
        for col in candidate_cols:
            if col in trades.columns:
                series = pd.to_numeric(trades[col], errors="coerce").dropna()
                return series.tolist()
        return pnl_values

    if isinstance(trades, list):
        for trade in trades:
            if isinstance(trade, dict):
                for key in ["pnl_r", "PnL_R", "PnL r", "pnl", "PnL", "profit_r", "Profit_R", "R"]:
                    if key in trade:
                        try:
                            pnl_values.append(float(trade[key]))
                            break
                        except Exception:
                            pass
            elif isinstance(trade, (int, float)):
                pnl_values.append(float(trade))

    return pnl_values
def evaluate_best_set_oos(df: pd.DataFrame, best_row: dict, split_ratio: float = 0.7):
    split_idx = int(len(df) * split_ratio)

    df_is = df.iloc[:split_idx].copy()
    df_oos = df.iloc[split_idx:].copy()

    strat_oos = calculate_impulse_pullback_break_strategy(
        df_oos.copy(),
        trend_lookback_bars=int(best_row["trend_lookback"]),
        atr_window=int(best_row["atr_window"]),
        min_trend_atr_multiple=float(best_row["min_trend_atr_multiple"]),
        pullback_max_bars=int(best_row["pullback_max_bars"]),
        pullback_max_depth_atr=float(best_row["pullback_max_depth_atr"]),
        confirmation_bars=int(best_row["confirmation_bars"])
    )

    trades_oos = run_simple_backtest(
        strat_oos,
        rr_target=float(best_row["rr_target"]),
        trade_mode="both",
        cost_per_trade_r=0.0,
        strategy_mode="normal"
    )

    equity_oos = build_equity_curve(trades_oos, starting_r=0.0)
    metrics_oos = calculate_basic_metrics(trades_oos, equity_oos)

    return {
        "split_ratio": split_ratio,
        "is_rows": len(df_is),
        "oos_rows": len(df_oos),
        "oos_trades": int(metrics_oos["number_of_trades"]),
        "oos_expectancy": float(metrics_oos["expectancy"]),
        "oos_total_r": float(metrics_oos["total_pnl"]),
        "oos_max_dd": float(metrics_oos["max_drawdown"]),
    }
def evaluate_best_set_multi_splits(df: pd.DataFrame, best_row: dict):
    split_ratios = [0.6, 0.7, 0.8]
    split_results = []

    for ratio in split_ratios:
        result = evaluate_best_set_oos(df, best_row, split_ratio=ratio)
        split_results.append(result)

    surviving_splits = sum(1 for r in split_results if r["oos_expectancy"] > 0)
    split_count = len(split_results)
    survival_ratio = round(surviving_splits / split_count, 4) if split_count > 0 else 0.0

    if surviving_splits == split_count:
        multi_split_status = "Robuste"
    elif surviving_splits >= 1:
        multi_split_status = "Limité"
    else:
        multi_split_status = "Fragile"

    return {
        "split_results": split_results,
        "surviving_splits": surviving_splits,
        "split_count": split_count,
        "survival_ratio": survival_ratio,
        "multi_split_status": multi_split_status
    }
def evaluate_best_set_with_cost(df: pd.DataFrame, best_row: dict, cost_per_trade_r: float = 0.05):
    strat_df = calculate_impulse_pullback_break_strategy(
        df.copy(),
        trend_lookback_bars=int(best_row["trend_lookback"]),
        atr_window=int(best_row["atr_window"]),
        min_trend_atr_multiple=float(best_row["min_trend_atr_multiple"]),
        pullback_max_bars=int(best_row["pullback_max_bars"]),
        pullback_max_depth_atr=float(best_row["pullback_max_depth_atr"]),
        confirmation_bars=int(best_row["confirmation_bars"])
    )

    trades_cost = run_simple_backtest(
        strat_df,
        rr_target=float(best_row["rr_target"]),
        trade_mode="both",
        cost_per_trade_r=cost_per_trade_r,
        strategy_mode="normal"
    )

    equity_cost = build_equity_curve(trades_cost, starting_r=0.0)
    metrics_cost = calculate_basic_metrics(trades_cost, equity_cost)

    return {
        "cost_per_trade_r": cost_per_trade_r,
        "cost_trades": int(metrics_cost["number_of_trades"]),
        "cost_expectancy": float(metrics_cost["expectancy"]),
        "cost_total_r": float(metrics_cost["total_pnl"]),
        "cost_max_dd": float(metrics_cost["max_drawdown"]),
    }




def run_parallel_asset_batch(asset: str, file_path: str, preset_name: str, timeframe_value: str, strategy_name_value: str):
    df = pd.read_csv(file_path)

    required_cols = ["Date", "Open", "High", "Low", "Close"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"{asset}: colonnes manquantes {missing_cols}")

    df["Date"] = pd.to_datetime(df["Date"], format="%Y.%m.%d %H:%M", errors="coerce")

    for col in ["Open", "High", "Low", "Close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["Date", "Open", "High", "Low", "Close"]).copy()
    df = df.sort_values("Date").reset_index(drop=True)

    if df.empty:
        raise ValueError(f"{asset}: dataframe vide après nettoyage")

    optimization_results = run_impulse_batch_optimization(df, preset_name, asset)
    best_row = optimization_results.iloc[0].to_dict()

    combo_count = int(len(optimization_results))
    profitable_combo_count = int((optimization_results["expectancy"] > 0).sum())
    non_negative_combo_count = int((optimization_results["expectancy"] >= 0).sum())
    avg_expectancy_all_combos = float(round(optimization_results["expectancy"].mean(), 4))
    median_expectancy_all_combos = float(round(optimization_results["expectancy"].median(), 4))

    top5_df = optimization_results.head(5).copy()

    top5_dominant_trend_lookback = int(top5_df["trend_lookback"].mode().iloc[0])
    top5_dominant_rr_target = float(top5_df["rr_target"].mode().iloc[0])

    trend_impact_df = (
        optimization_results.groupby("trend_lookback", dropna=False)
        .agg(
            avg_expectancy=("expectancy", "mean"),
            median_expectancy=("expectancy", "median"),
            avg_total_r=("total_r", "mean"),
            avg_max_dd=("max_dd", "mean"),
            avg_trades=("trades", "mean"),
            count=("trend_lookback", "size")
        )
        .reset_index()
        .sort_values(by=["avg_expectancy", "avg_total_r"], ascending=[False, False])
        .reset_index(drop=True)
    )

    rr_impact_df = (
        optimization_results.groupby("rr_target", dropna=False)
        .agg(
            avg_expectancy=("expectancy", "mean"),
            median_expectancy=("expectancy", "median"),
            avg_total_r=("total_r", "mean"),
            avg_max_dd=("max_dd", "mean"),
            avg_trades=("trades", "mean"),
            count=("rr_target", "size")
        )
        .reset_index()
        .sort_values(by=["avg_expectancy", "avg_total_r"], ascending=[False, False])
        .reset_index(drop=True)
    )

    confirmation_impact_df = (
        optimization_results.groupby("confirmation_bars", dropna=False)
        .agg(
            avg_expectancy=("expectancy", "mean"),
            median_expectancy=("expectancy", "median"),
            avg_total_r=("total_r", "mean"),
            avg_max_dd=("max_dd", "mean"),
            avg_trades=("trades", "mean"),
            count=("confirmation_bars", "size")
        )
        .reset_index()
        .sort_values(by=["avg_expectancy", "avg_total_r"], ascending=[False, False])
        .reset_index(drop=True)
    )

    pullback_bars_impact_df = (
        optimization_results.groupby("pullback_max_bars", dropna=False)
        .agg(
            avg_expectancy=("expectancy", "mean"),
            median_expectancy=("expectancy", "median"),
            avg_total_r=("total_r", "mean"),
            avg_max_dd=("max_dd", "mean"),
            avg_trades=("trades", "mean"),
            count=("pullback_max_bars", "size")
        )
        .reset_index()
        .sort_values(by=["avg_expectancy", "avg_total_r"], ascending=[False, False])
        .reset_index(drop=True)
    )

    mta_impact_df = (
        optimization_results.groupby("min_trend_atr_multiple", dropna=False)
        .agg(
            avg_expectancy=("expectancy", "mean"),
            median_expectancy=("expectancy", "median"),
            avg_total_r=("total_r", "mean"),
            avg_max_dd=("max_dd", "mean"),
            avg_trades=("trades", "mean"),
            count=("min_trend_atr_multiple", "size")
        )
        .reset_index()
        .sort_values(by=["avg_expectancy", "avg_total_r"], ascending=[False, False])
        .reset_index(drop=True)
    )

    depth_impact_df = (
        optimization_results.groupby("pullback_max_depth_atr", dropna=False)
        .agg(
            avg_expectancy=("expectancy", "mean"),
            median_expectancy=("expectancy", "median"),
            avg_total_r=("total_r", "mean"),
            avg_max_dd=("max_dd", "mean"),
            avg_trades=("trades", "mean"),
            count=("pullback_max_depth_atr", "size")
        )
        .reset_index()
        .sort_values(by=["avg_expectancy", "avg_total_r"], ascending=[False, False])
        .reset_index(drop=True)
    )

    best_trend_impact_row = trend_impact_df.iloc[0].to_dict()
    best_rr_impact_row = rr_impact_df.iloc[0].to_dict()
    best_confirmation_impact_row = confirmation_impact_df.iloc[0].to_dict()
    best_pullback_bars_impact_row = pullback_bars_impact_df.iloc[0].to_dict()
    best_mta_impact_row = mta_impact_df.iloc[0].to_dict()
    best_depth_impact_row = depth_impact_df.iloc[0].to_dict()

    top5_avg_expectancy = float(round(optimization_results.head(5)["expectancy"].mean(), 4))
    top10_avg_expectancy = float(round(optimization_results.head(10)["expectancy"].mean(), 4))
    top5_avg_total_r = float(round(optimization_results.head(5)["total_r"].mean(), 4))
    top10_avg_total_r = float(round(optimization_results.head(10)["total_r"].mean(), 4))
    top5_profitable_count = int((optimization_results.head(5)["expectancy"] > 0).sum())
    top10_profitable_count = int((optimization_results.head(10)["expectancy"] > 0).sum())

    top10_df = optimization_results.head(10).copy()

    top10_dominant_tlb = int(top10_df["trend_lookback"].mode().iloc[0])
    top10_dominant_rr = float(top10_df["rr_target"].mode().iloc[0])
    top10_dominant_conf = int(top10_df["confirmation_bars"].mode().iloc[0])
    top10_dominant_pb = int(top10_df["pullback_max_bars"].mode().iloc[0])
    top10_dominant_mta = float(top10_df["min_trend_atr_multiple"].mode().iloc[0])
    top10_dominant_depth = float(top10_df["pullback_max_depth_atr"].mode().iloc[0])

    first_close = float(df["Close"].iloc[0])
    last_close = float(df["Close"].iloc[-1])
    highest_high = float(df["High"].max())
    lowest_low = float(df["Low"].min())

    total_days = max((df["Date"].max() - df["Date"].min()).days, 1)
    total_years = round(total_days / 365.25, 4)

    if first_close != 0:
        price_change_pct = round(((last_close - first_close) / first_close) * 100, 4)
        total_range_pct = round(((highest_high - lowest_low) / first_close) * 100, 4)
    else:
        price_change_pct = None
        total_range_pct = None

    best_params_signature = (
        f"TLB{int(best_row['trend_lookback'])}_"
        f"ATR{int(best_row['atr_window'])}_"
        f"MTA{float(best_row['min_trend_atr_multiple'])}_"
        f"PB{int(best_row['pullback_max_bars'])}_"
        f"DEPTH{float(best_row['pullback_max_depth_atr'])}_"
        f"CONF{int(best_row['confirmation_bars'])}_"
        f"RR{float(best_row['rr_target'])}"
    )

    oos_eval = evaluate_best_set_oos(df, best_row, split_ratio=0.7)
    delta_is_oos_expectancy = round(float(best_row["expectancy"]) - oos_eval["oos_expectancy"], 4)
    delta_is_oos_total_r = round(float(best_row["total_r"]) - oos_eval["oos_total_r"], 4)

    multi_split_eval = evaluate_best_set_multi_splits(df, best_row)

    cost_eval = evaluate_best_set_with_cost(df, best_row, cost_per_trade_r=0.05)
    delta_cost_expectancy = round(float(best_row["expectancy"]) - cost_eval["cost_expectancy"], 4)
    delta_cost_total_r = round(float(best_row["total_r"]) - cost_eval["cost_total_r"], 4)

    summary_row = {
        "timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        "asset": asset,
        "timeframe": timeframe_value,
        "strategy_name": strategy_name_value,
        "preset": preset_name,
        "file_used": file_path,
        "date_start": df["Date"].min().strftime("%Y-%m-%d %H:%M:%S"),
        "date_end": df["Date"].max().strftime("%Y-%m-%d %H:%M:%S"),
        "row_count": len(df),
        "first_close": first_close,
        "last_close": last_close,
        "price_change_pct": price_change_pct,
        "highest_high": highest_high,
        "lowest_low": lowest_low,
        "total_range_pct": total_range_pct,
        "combo_count": combo_count,
        "profitable_combo_count": profitable_combo_count,
        "non_negative_combo_count": non_negative_combo_count,
        "avg_expectancy_all_combos": avg_expectancy_all_combos,
        "median_expectancy_all_combos": median_expectancy_all_combos,
        "top5_dominant_trend_lookback": top5_dominant_trend_lookback,
        "top5_dominant_rr_target": top5_dominant_rr_target,
        "best_trend_impact_value": int(best_trend_impact_row["trend_lookback"]),
        "best_trend_impact_avg_expectancy": float(round(best_trend_impact_row["avg_expectancy"], 4)),
        "best_trend_impact_avg_total_r": float(round(best_trend_impact_row["avg_total_r"], 4)),
        "best_rr_impact_value": float(best_rr_impact_row["rr_target"]),
        "best_rr_impact_avg_expectancy": float(round(best_rr_impact_row["avg_expectancy"], 4)),
        "best_rr_impact_avg_total_r": float(round(best_rr_impact_row["avg_total_r"], 4)),
        "best_confirmation_impact_value": int(best_confirmation_impact_row["confirmation_bars"]),
        "best_confirmation_impact_avg_expectancy": float(round(best_confirmation_impact_row["avg_expectancy"], 4)),
        "best_pullback_bars_impact_value": int(best_pullback_bars_impact_row["pullback_max_bars"]),
        "best_pullback_bars_impact_avg_expectancy": float(round(best_pullback_bars_impact_row["avg_expectancy"], 4)),
        "best_mta_impact_value": float(best_mta_impact_row["min_trend_atr_multiple"]),
        "best_mta_impact_avg_expectancy": float(round(best_mta_impact_row["avg_expectancy"], 4)),
        "best_depth_impact_value": float(best_depth_impact_row["pullback_max_depth_atr"]),
        "best_depth_impact_avg_expectancy": float(round(best_depth_impact_row["avg_expectancy"], 4)),
        "top5_avg_expectancy": top5_avg_expectancy,
        "top10_avg_expectancy": top10_avg_expectancy,
        "top5_avg_total_r": top5_avg_total_r,
        "top10_avg_total_r": top10_avg_total_r,
        "top5_profitable_count": top5_profitable_count,
        "top10_profitable_count": top10_profitable_count,
        "best_trades": int(best_row["trades"]),
        "best_trades_per_year": round(int(best_row["trades"]) / total_years, 2) if total_years > 0 else None,
        "best_expectancy": float(best_row["expectancy"]),
        "best_total_r": float(best_row["total_r"]),
        "best_max_dd": float(best_row["max_dd"]),
        "oos_trades": oos_eval["oos_trades"],
        "oos_trades_per_year": round(oos_eval["oos_trades"] / total_years, 2) if total_years > 0 else None,
        "oos_expectancy": oos_eval["oos_expectancy"],
        "oos_total_r": oos_eval["oos_total_r"],
        "oos_max_dd": oos_eval["oos_max_dd"],
        "best_win_rate": float(best_row["win_rate"]),
        "best_profit_factor": float(best_row["profit_factor"]),
        "best_avg_win_r": float(best_row["avg_win_r"]),
        "best_avg_loss_r": float(best_row["avg_loss_r"]),
        "best_avg_trade_r": float(best_row["avg_trade_r"]),
        "delta_is_oos_expectancy": delta_is_oos_expectancy,
        "delta_is_oos_total_r": delta_is_oos_total_r,
        "multi_split_surviving_count": multi_split_eval["surviving_splits"],
        "multi_split_total_count": multi_split_eval["split_count"],
        "multi_split_ratio": multi_split_eval["survival_ratio"],
        "multi_split_status": multi_split_eval["multi_split_status"],
        "cost_trades": cost_eval["cost_trades"],
        "cost_trades_per_year": round(cost_eval["cost_trades"] / total_years, 2) if total_years > 0 else None,
        "cost_expectancy": cost_eval["cost_expectancy"],
        "cost_total_r": cost_eval["cost_total_r"],
        "cost_max_dd": cost_eval["cost_max_dd"],
        "delta_cost_expectancy": delta_cost_expectancy,
        "delta_cost_total_r": delta_cost_total_r,
        "best_params_signature": best_params_signature,
        "status": "data_loaded_ok"
    }

    asset_json = {
        "meta": {
            "timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
            "asset": asset,
            "timeframe": timeframe_value,
            "strategy_name": strategy_name_value,
            "preset": preset_name,
            "file_used": file_path,
            "date_start": df["Date"].min().strftime("%Y-%m-%d %H:%M:%S"),
            "date_end": df["Date"].max().strftime("%Y-%m-%d %H:%M:%S")
        },
        "summary": {
            "global_status": "batch_optimization_done",
            "global_score": None,
            "run_survivor": None,
            "multi_split_status": None,
            "multi_split_ratio": None,
            "reference_selection_mode": "best_expectancy",
            "reference_is_rank": 1,
            "combo_count": combo_count,
            "profitable_combo_count": profitable_combo_count,
            "non_negative_combo_count": non_negative_combo_count,
            "avg_expectancy_all_combos": avg_expectancy_all_combos,
            "median_expectancy_all_combos": median_expectancy_all_combos,
            "top5_dominant_trend_lookback": top5_dominant_trend_lookback,
            "top5_dominant_rr_target": top5_dominant_rr_target,
            "top5_avg_expectancy": top5_avg_expectancy,
            "top10_avg_expectancy": top10_avg_expectancy,
            "top5_avg_total_r": top5_avg_total_r,
            "top10_avg_total_r": top10_avg_total_r,
            "top5_profitable_count": top5_profitable_count,
            "top10_profitable_count": top10_profitable_count,
            "top10_dominant_tlb": top10_dominant_tlb,
            "top10_dominant_rr": top10_dominant_rr,
            "top10_dominant_conf": top10_dominant_conf,
            "top10_dominant_pb": top10_dominant_pb,
            "top10_dominant_mta": top10_dominant_mta,
            "top10_dominant_depth": top10_dominant_depth,
            "best_trades": int(best_row["trades"]),
            "best_trades_per_year": round(int(best_row["trades"]) / total_years, 2) if total_years > 0 else None,
            "best_expectancy": float(best_row["expectancy"]),
            "best_total_r": float(best_row["total_r"]),
            "best_max_dd": float(best_row["max_dd"]),
            "best_win_rate": float(best_row["win_rate"]),
            "best_profit_factor": float(best_row["profit_factor"]),
            "best_avg_win_r": float(best_row["avg_win_r"]),
            "best_avg_loss_r": float(best_row["avg_loss_r"]),
            "best_avg_trade_r": float(best_row["avg_trade_r"]),
            "oos_trades": oos_eval["oos_trades"],
            "oos_trades_per_year": round(oos_eval["oos_trades"] / total_years, 2) if total_years > 0 else None,
            "oos_expectancy": oos_eval["oos_expectancy"],
            "oos_total_r": oos_eval["oos_total_r"],
            "oos_max_dd": oos_eval["oos_max_dd"],
            "delta_is_oos_expectancy": delta_is_oos_expectancy,
            "delta_is_oos_total_r": delta_is_oos_total_r,
            "multi_split_surviving_count": multi_split_eval["surviving_splits"],
            "multi_split_total_count": multi_split_eval["split_count"],
            "multi_split_ratio": multi_split_eval["survival_ratio"],
            "multi_split_status": multi_split_eval["multi_split_status"],
            "cost_trades": cost_eval["cost_trades"],
            "cost_trades_per_year": round(cost_eval["cost_trades"] / total_years, 2) if total_years > 0 else None,
            "cost_expectancy": cost_eval["cost_expectancy"],
            "cost_total_r": cost_eval["cost_total_r"],
            "cost_max_dd": cost_eval["cost_max_dd"],
            "delta_cost_expectancy": delta_cost_expectancy,
            "delta_cost_total_r": delta_cost_total_r,
            "run_signature": best_params_signature,
            "signature_short": best_params_signature
        },
        "best_candidate": {
            "trend_lookback": int(best_row["trend_lookback"]),
            "atr_window": int(best_row["atr_window"]),
            "min_trend_atr_multiple": float(best_row["min_trend_atr_multiple"]),
            "pullback_max_bars": int(best_row["pullback_max_bars"]),
            "pullback_max_depth_atr": float(best_row["pullback_max_depth_atr"]),
            "confirmation_bars": int(best_row["confirmation_bars"]),
            "rr_target": float(best_row["rr_target"])
        },
        "parameter_impact": {
            "trend_lookback": trend_impact_df.to_dict(orient="records"),
            "rr_target": rr_impact_df.to_dict(orient="records"),
            "confirmation_bars": confirmation_impact_df.to_dict(orient="records"),
            "pullback_max_bars": pullback_bars_impact_df.to_dict(orient="records"),
            "min_trend_atr_multiple": mta_impact_df.to_dict(orient="records"),
            "pullback_max_depth_atr": depth_impact_df.to_dict(orient="records")
        },
        "multi_split_detail": multi_split_eval["split_results"],
        "top_optimization": optimization_results.head(10).to_dict(orient="records")
    }

    return {
        "asset": asset,
        "summary_row": summary_row,
        "asset_json": asset_json,
        "best_row": best_row,
        "combo_count": len(optimization_results)
    }



def main():
    batch_start_time = time.time()

    print("=== Batch multi-actifs Impulse ===")
    print(f"Campagne : {campaign_name}")
    print(f"Preset : {preset}")
    print(f"Stratégie : {strategy_name}")
    print(f"Timeframe : {timeframe}")
    print("Actifs :")
    for asset in assets:
        print(f" - {asset} -> {files_map[asset]}")

    BATCH_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    CAMPAIGNS_DIR.mkdir(parents=True, exist_ok=True)

    campaign_dir = CAMPAIGNS_DIR / campaign_name

    if campaign_dir.exists():
        raise FileExistsError(
            f"La campagne existe déjà : {campaign_dir}"
        )

    campaign_dir.mkdir(parents=True, exist_ok=False)

    print("\nDossier de campagne créé :")
    print(campaign_dir)
    print("\nLancement du batch parallèle multi-actifs...")

    completed_results = []
    batch_summary_rows = []

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                run_parallel_asset_batch,
                asset,
                str(files_map[asset]),
                preset,
                timeframe,
                strategy_name
            ): asset
            for asset in assets
        }

        for future in as_completed(futures):
            asset = futures[future]

            try:
                result = future.result()
                completed_results.append(result)
                batch_summary_rows.append(result["summary_row"])

                print(
                    f"[OK PARALLELE] {asset} | "
                    f"combinaisons = {result['combo_count']} | "
                    f"profitables = {result['summary_row']['profitable_combo_count']} | "
                    f"best exp = {result['best_row']['expectancy']} | "
                    f"oos exp = {result['summary_row']['oos_expectancy']} | "
                    f"cost exp = {result['summary_row']['cost_expectancy']} | "
                    f"delta cost = {result['summary_row']['delta_cost_expectancy']} | "
                    f"multi-split = {result['summary_row']['multi_split_status']} "
                    f"({result['summary_row']['multi_split_surviving_count']}/{result['summary_row']['multi_split_total_count']}) | "
                    f"TLB = {int(result['best_row']['trend_lookback'])} | "
                    f"RR = {float(result['best_row']['rr_target'])} | "
                    f"CONF = {int(result['best_row']['confirmation_bars'])} | "
                    f"PB = {int(result['best_row']['pullback_max_bars'])} | "
                    f"MTA = {float(result['best_row']['min_trend_atr_multiple'])} | "
                    f"DEPTH = {float(result['best_row']['pullback_max_depth_atr'])}"
                )
            except Exception as e:
                print(f"[ERREUR PARALLELE] {asset} | {e}")

    print("\nConstruction du batch_summary...")

    batch_summary_df = pd.DataFrame(batch_summary_rows)

    print("\nCréation des JSON par actif...")

    for result in completed_results:
        asset = result["asset"]
        asset_json = result["asset_json"]

        json_file = campaign_dir / f"{asset}.json"

        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(asset_json, f, indent=2, ensure_ascii=False)

        print(f"[JSON OK] {json_file}")

    batch_summary_file = campaign_dir / "batch_summary.csv"
    batch_summary_df.to_csv(batch_summary_file, index=False)

    print("\nFichier batch_summary.csv créé :")
    print(batch_summary_file)

    print("\nAperçu batch_summary :")
    print(batch_summary_df)
    print("\nMise à jour du master_batch_summary.csv...")

    if MASTER_SUMMARY_FILE.exists():
        master_df = pd.read_csv(MASTER_SUMMARY_FILE)
        master_df = pd.concat([master_df, batch_summary_df], ignore_index=True)
    else:
        master_df = batch_summary_df.copy()

    master_df.to_csv(MASTER_SUMMARY_FILE, index=False)

    print("[MASTER OK]")
    print(MASTER_SUMMARY_FILE)

    elapsed_seconds = round(time.time() - batch_start_time, 2)
    print(f"\nDurée totale batch : {elapsed_seconds} secondes")


if __name__ == "__main__":
    main()