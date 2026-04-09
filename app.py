import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io
import os
import time

RUN_HISTORY_FILE = "run_history.csv"

from strategies import calculate_sma_strategy, calculate_impulse_pullback_break_strategy
from backtest import run_simple_backtest, build_equity_curve
from metrics import calculate_basic_metrics
from optimizer import optimize_parameters, optimize_impulse_parameters


def load_price_file(uploaded_file):
    raw = uploaded_file.getvalue()

    decoded_text = None
    used_encoding = None

    for encoding in ["utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "cp1252", "latin1"]:
        try:
            decoded_text = raw.decode(encoding)
            used_encoding = encoding
            break
        except UnicodeDecodeError:
            continue

    if decoded_text is None:
        raise ValueError("Impossible de lire le fichier : encodage non reconnu.")

    first_line = decoded_text.splitlines()[0].strip()

    if "\t" in first_line:
        sep = "\t"
    elif ";" in first_line:
        sep = ";"
    else:
        sep = ","

    text_buffer = io.StringIO(decoded_text)

    if first_line.lower().startswith("date") or first_line.lower().startswith("<date>"):
        df = pd.read_csv(text_buffer, sep=sep)
    else:
        df = pd.read_csv(text_buffer, sep=sep, header=None)

    # Cas MT5 avec colonnes <DATE> <TIME> <OPEN> ...
    rename_map = {
        "<DATE>": "DatePart",
        "<TIME>": "TimePart",
        "<OPEN>": "Open",
        "<HIGH>": "High",
        "<LOW>": "Low",
        "<CLOSE>": "Close",
        "<TICKVOL>": "TickVolume",
        "<VOL>": "Volume",
        "<SPREAD>": "Spread",
        "DATE": "DatePart",
        "TIME": "TimePart",
        "OPEN": "Open",
        "HIGH": "High",
        "LOW": "Low",
        "CLOSE": "Close",
        "TICKVOL": "TickVolume",
        "VOL": "Volume",
        "SPREAD": "Spread",
    }

    df.columns = [str(col).strip() for col in df.columns]
    df = df.rename(columns=rename_map)

    # Si le fichier n'a pas d'en-tête
    if "Open" not in df.columns:
        if df.shape[1] >= 8:
            df.columns = ["DatePart", "TimePart", "Open", "High", "Low", "Close", "TickVolume", "Volume"] + [
                f"Extra_{i}" for i in range(df.shape[1] - 8)
            ]
        elif df.shape[1] >= 7:
            first_col_sample = str(df.iloc[0, 0]).strip()

            if " " in first_col_sample and ":" in first_col_sample:
                df.columns = ["Date", "Open", "High", "Low", "Close", "TickVolume", "Spread"] + [
                    f"Extra_{i}" for i in range(df.shape[1] - 7)
                ]
            else:
                df.columns = ["DatePart", "TimePart", "Open", "High", "Low", "Close", "Volume"] + [
                    f"Extra_{i}" for i in range(df.shape[1] - 7)
                ]
        elif df.shape[1] >= 6:
            first_col_sample = str(df.iloc[0, 0]).strip()

            if " " in first_col_sample and ":" in first_col_sample:
                df.columns = ["Date", "Open", "High", "Low", "Close", "Volume"] + [
                    f"Extra_{i}" for i in range(df.shape[1] - 6)
                ]
            else:
                raise ValueError("Format CSV non reconnu.")
        else:
            raise ValueError("Format CSV non reconnu.")

    if "DatePart" in df.columns and "TimePart" in df.columns:
        df["Date"] = df["DatePart"].astype(str).str.strip() + " " + df["TimePart"].astype(str).str.strip()

    if "Date" in df.columns:
        df["Date"] = df["Date"].astype(str).str.strip()

    keep_cols = [col for col in ["Date", "Open", "High", "Low", "Close", "TickVolume", "Volume", "Spread"] if col in df.columns]
    df = df[keep_cols].copy()

    return df


def show_impulse_filter_mask_message():
    st.info(
        "Impulse Pullback Break V1 n’intègre pas encore réellement les filtres de tendance, volatilité, régime et session dans sa logique. "
        "Les comparaisons OFF/ON et les lectures automatiques associées sont donc masquées temporairement pour éviter des diagnostics trompeurs."
    )


def run_analysis(
    price_df: pd.DataFrame,
    strategy_name: str,
    short_window: int,
    long_window: int,
    rr_target: float,
    trade_mode: str,
    cost_per_trade_r: float,
    starting_r: float,
    split_ratio: int,
    trend_filter_enabled: bool,
    trend_filter_window: int,
    volatility_filter_enabled: bool,
    atr_window: int,
    min_atr_pct: float,
    regime_filter_enabled: bool,
    adx_window: int,
    min_adx: float,
    session_filter_enabled: bool,
    session_start_hour: int,
    session_end_hour: int,
    strategy_mode: str = "normal",
    trend_lookback_bars: int = 100,
    min_trend_atr_multiple: float = 3.0,
    pullback_max_bars: int = 6,
    pullback_max_depth_atr: float = 1.5,
    confirmation_bars: int = 1
):
    if strategy_name == "SMA":
        df_calc = calculate_sma_strategy(
            price_df.copy(),
            short_window,
            long_window,
            trend_filter_enabled=trend_filter_enabled,
            trend_filter_window=trend_filter_window,
            volatility_filter_enabled=volatility_filter_enabled,
            atr_window=atr_window,
            min_atr_pct=min_atr_pct,
            regime_filter_enabled=regime_filter_enabled,
            adx_window=adx_window,
            min_adx=min_adx,
            session_filter_enabled=session_filter_enabled,
            session_start_hour=session_start_hour,
            session_end_hour=session_end_hour,
            strategy_mode=strategy_mode
        )
    else:
        df_calc = calculate_impulse_pullback_break_strategy(
            price_df.copy(),
            trend_lookback_bars=trend_lookback_bars,
            atr_window=atr_window,
            min_trend_atr_multiple=min_trend_atr_multiple,
            pullback_max_bars=pullback_max_bars,
            pullback_max_depth_atr=pullback_max_depth_atr,
            confirmation_bars=confirmation_bars
        )
    split_index = int(len(df_calc) * (split_ratio / 100))
    df_insample = df_calc.iloc[:split_index].copy()
    df_outsample = df_calc.iloc[split_index:].copy()

    trades_df = run_simple_backtest(
        df_calc,
        rr_target=rr_target,
        trade_mode=trade_mode,
        cost_per_trade_r=cost_per_trade_r,
        strategy_mode=strategy_mode
    )
    equity_df = build_equity_curve(trades_df, starting_r=starting_r)
    metrics = calculate_basic_metrics(trades_df, equity_df)

    trades_insample = run_simple_backtest(
        df_insample,
        rr_target=rr_target,
        trade_mode=trade_mode,
        cost_per_trade_r=cost_per_trade_r,
        strategy_mode=strategy_mode
    )
    equity_insample = build_equity_curve(trades_insample, starting_r=starting_r)
    metrics_insample = calculate_basic_metrics(trades_insample, equity_insample)

    trades_outsample = run_simple_backtest(
        df_outsample,
        rr_target=rr_target,
        trade_mode=trade_mode,
        cost_per_trade_r=cost_per_trade_r,
        strategy_mode=strategy_mode
    )
    equity_outsample = build_equity_curve(trades_outsample, starting_r=starting_r)
    metrics_outsample = calculate_basic_metrics(trades_outsample, equity_outsample)

    return {
        "df": df_calc,
        "df_insample": df_insample,
        "df_outsample": df_outsample,
        "trades_df": trades_df,
        "equity_df": equity_df,
        "metrics": metrics,
        "trades_insample": trades_insample,
        "equity_insample": equity_insample,
        "metrics_insample": metrics_insample,
        "trades_outsample": trades_outsample,
        "equity_outsample": equity_outsample,
        "metrics_outsample": metrics_outsample,
    }

st.title("Trading Strategy Lab")
st.write("Prototype V1 - Mini backtest et métriques")

uploaded_file = st.file_uploader("Charge un fichier CSV", type=["csv"])

if uploaded_file is not None:
    df = load_price_file(uploaded_file)

    required_columns = ["Date", "Open", "High", "Low", "Close"]
    missing_columns = [col for col in required_columns if col not in df.columns]

    if missing_columns:
        st.error(f"Colonnes manquantes : {missing_columns}")
    else:
        df["Date"] = pd.to_datetime(df["Date"], format="%Y.%m.%d %H:%M", errors="coerce")

        if df["Date"].isna().all():
            df["Date"] = pd.to_datetime(df["Date"].astype(str).str.strip(), errors="coerce")

        for col in ["Open", "High", "Low", "Close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.dropna(subset=["Date", "Open", "High", "Low", "Close"])
        df = df.drop_duplicates(subset=["Date"])
        df = df.sort_values("Date").reset_index(drop=True)
        st.subheader("Filtre de période")

        min_date = df["Date"].min().date()
        max_date = df["Date"].max().date()

        col_date1, col_date2 = st.columns(2)
        start_date = col_date1.date_input("Date de début", value=min_date, min_value=min_date, max_value=max_date)
        end_date = col_date2.date_input("Date de fin", value=max_date, min_value=min_date, max_value=max_date)

        if start_date > end_date:
            st.error("La date de début doit être antérieure ou égale à la date de fin.")
        else:
            df = df[
                (df["Date"] >= pd.to_datetime(start_date)) &
                (df["Date"] < pd.to_datetime(end_date) + pd.Timedelta(days=1))
            ].copy()

            df = df.reset_index(drop=True)

            if df.empty:
                st.error("Aucune donnée disponible sur cette période.")
            else:
                strategy_name = st.selectbox(
                    "Stratégie",
                    options=["SMA", "Impulse Pullback Break V1"]
                )

                is_sma_strategy = strategy_name == "SMA"
                is_impulse_strategy = strategy_name == "Impulse Pullback Break V1"

                if is_sma_strategy:
                    short_window = st.slider("Moyenne mobile courte", min_value=2, max_value=20, value=3)
                    long_window = st.slider("Moyenne mobile longue", min_value=3, max_value=50, value=5)
                else:
                    short_window = 3
                    long_window = 5

                trend_filter_enabled = st.checkbox("Activer le filtre de tendance de fond", value=False)
                trend_filter_window = st.slider("Moyenne mobile du filtre", min_value=20, max_value=200, value=50, step=5)

                volatility_filter_enabled = st.checkbox("Activer le filtre de volatilité", value=False)
                atr_window = st.slider("Fenêtre ATR", min_value=5, max_value=50, value=14, step=1)
                min_atr_pct = st.slider("Volatilité minimale ATR %", min_value=0.01, max_value=2.00, value=0.20, step=0.01)

                regime_filter_enabled = st.checkbox("Activer le filtre de régime de marché (ADX)", value=False)
                adx_window = st.slider("Fenêtre ADX", min_value=5, max_value=50, value=14, step=1)
                min_adx = st.slider("ADX minimal", min_value=5.0, max_value=50.0, value=20.0, step=1.0)

                session_mode = st.selectbox(
                    "Session de trading",
                    options=[
                        "Aucune",
                        "Custom",
                        "Londres matin",
                        "Londres large",
                        "Overlap Londres/New York",
                        "US après-midi"
                    ]
                )

                session_presets = {
                    "Londres matin": (7, 10),
                    "Londres large": (7, 12),
                    "Overlap Londres/New York": (13, 17),
                    "US après-midi": (14, 18),
                }

                optimization_session_names = [
                    "Aucune",
                    "Londres matin",
                    "Londres large",
                    "Overlap Londres/New York",
                    "US après-midi"
                ]

                if session_mode == "Aucune":
                    session_filter_enabled = False
                    session_start_hour = 8
                    session_end_hour = 17

                elif session_mode == "Custom":
                    session_filter_enabled = True
                    session_start_hour = st.slider("Heure début session", min_value=0, max_value=23, value=8, step=1)
                    session_end_hour = st.slider("Heure fin session", min_value=0, max_value=23, value=17, step=1)

                else:
                    session_filter_enabled = True
                    session_start_hour, session_end_hour = session_presets[session_mode]
                    st.caption(
                        f"Session sélectionnée : {session_mode} "
                        f"({session_start_hour}h - {session_end_hour}h)"
                    )

                rr_target = st.slider("RR cible", min_value=0.5, max_value=5.0, value=2.0, step=0.5)
                starting_r = st.number_input("Base de l'equity curve (R)", value=0.0, step=1.0)
                split_ratio = st.slider("Part in-sample (%)", min_value=1, max_value=90, value=70, step=5)

                cost_per_trade_r = st.number_input(
                    "Coût par trade (R)",
                    min_value=0.0,
                    value=0.0,
                    step=0.05,
                    format="%.2f"
                )

                trade_mode = st.selectbox(
                    "Mode de trading",
                    options=["both", "long_only", "short_only"],
                    format_func=lambda x: {
                        "both": "Long + Short",
                        "long_only": "Long only",
                        "short_only": "Short only"
                    }[x]
                )

                strategy_mode = st.selectbox(
                    "Sens de la stratégie",
                    options=["normal", "inverse"],
                    format_func=lambda x: {
                        "normal": "Normal",
                        "inverse": "Inverse"
                    }[x]
                )

                if is_impulse_strategy:
                    st.subheader("Paramètres Impulse Pullback Break V1")

                    impulse_optimization_preset = st.selectbox(
                        "Preset optimisation Impulse",
                        options=["Rapide", "30-45 min", "2H / Salle", "Nuit léger", "Nuit profonde"],
                        index=2
                    )

                    trend_lookback_bars = 100

                    min_trend_atr_multiple = st.slider(
                        "Seuil minimum d'impulsion (ATR multiples)",
                        min_value=0.5,
                        max_value=10.0,
                        value=3.0,
                        step=0.5
                    )

                    pullback_max_bars = st.slider(
                        "Nombre max de bougies du retracement",
                        min_value=2,
                        max_value=12,
                        value=6,
                        step=1
                    )

                    pullback_max_depth_atr = st.slider(
                        "Profondeur max du retracement (ATR multiples)",
                        min_value=0.5,
                        max_value=5.0,
                        value=1.5,
                        step=0.1
                    )

                    confirmation_bars = st.slider(
                        "Bougies de confirmation",
                        min_value=1,
                        max_value=2,
                        value=1,
                        step=1
                    )
                else:
                    trend_lookback_bars = 100
                    min_trend_atr_multiple = 3.0
                    pullback_max_bars = 6
                    pullback_max_depth_atr = 1.5
                    confirmation_bars = 1

                optimizer_min_trades = st.number_input(
                    "Trades minimum pour l'optimisation",
                    min_value=10,
                    max_value=1000,
                    value=100,
                    step=10
                )

                if "optimization_results" not in st.session_state:
                    st.session_state.optimization_results = pd.DataFrame()

                if "run_history" not in st.session_state:
                    if os.path.exists(RUN_HISTORY_FILE):
                        try:
                            st.session_state.run_history = pd.read_csv(RUN_HISTORY_FILE).to_dict("records")
                        except Exception:
                            st.session_state.run_history = []
                    else:
                        st.session_state.run_history = []

                if is_sma_strategy:
                    run_optimization = st.button("Lancer l'optimisation des paramètres")
                else:
                    run_optimization = st.button("Lancer l'optimisation Impulse V1")
                    st.info(
                        "Optimiseur provisoire Impulse V1 : il sert à explorer rapidement le comportement de la stratégie "
                        "sur un premier espace de recherche dédié, sans prétendre encore valider une vraie robustesse structurelle."
                    )
            


                run_analysis_button = st.button("Lancer l'analyse")

                should_run_main_block = (
                    run_analysis_button
                    or run_optimization
                    or ("last_impulse_history_row" in st.session_state)
                )

                if is_sma_strategy and short_window >= long_window:
                    st.error("La moyenne mobile courte doit être inférieure à la longue.")
                elif not should_run_main_block:
                    st.info("Configure les paramètres puis clique sur 'Lancer l'analyse'.")
                else:
                    analysis_selected = run_analysis(
                        price_df=df,
                        strategy_name=strategy_name,
                        short_window=short_window,
                        long_window=long_window,
                        rr_target=rr_target,
                        trade_mode=trade_mode,
                        cost_per_trade_r=cost_per_trade_r,
                        starting_r=starting_r,
                        split_ratio=split_ratio,
                        trend_filter_enabled=trend_filter_enabled,
                        trend_filter_window=trend_filter_window,
                        volatility_filter_enabled=volatility_filter_enabled,
                        atr_window=atr_window,
                        min_atr_pct=min_atr_pct,
                        regime_filter_enabled=regime_filter_enabled,
                        adx_window=adx_window,
                        min_adx=min_adx,
                        session_filter_enabled=session_filter_enabled,
                        session_start_hour=session_start_hour,
                        session_end_hour=session_end_hour,
                        strategy_mode=strategy_mode,
                        trend_lookback_bars=trend_lookback_bars,
                        min_trend_atr_multiple=min_trend_atr_multiple,
                        pullback_max_bars=pullback_max_bars,
                        pullback_max_depth_atr=pullback_max_depth_atr,
                        confirmation_bars=confirmation_bars
                    )

                    if is_sma_strategy:
                        volatility_analysis_off = run_analysis(
                            price_df=df,
                            strategy_name=strategy_name,
                            short_window=short_window,
                            long_window=long_window,
                            rr_target=rr_target,
                            trade_mode=trade_mode,
                            cost_per_trade_r=cost_per_trade_r,
                            starting_r=starting_r,
                            split_ratio=split_ratio,
                            trend_filter_enabled=trend_filter_enabled,
                            trend_filter_window=trend_filter_window,
                            volatility_filter_enabled=False,
                            atr_window=atr_window,
                            min_atr_pct=min_atr_pct,
                            regime_filter_enabled=regime_filter_enabled,
                            adx_window=adx_window,
                            min_adx=min_adx,
                            session_filter_enabled=session_filter_enabled,
                            session_start_hour=session_start_hour,
                            session_end_hour=session_end_hour,
                            strategy_mode=strategy_mode,
                            trend_lookback_bars=trend_lookback_bars,
                            min_trend_atr_multiple=min_trend_atr_multiple,
                            pullback_max_bars=pullback_max_bars,
                            pullback_max_depth_atr=pullback_max_depth_atr,
                            confirmation_bars=confirmation_bars
                        )

                        volatility_analysis_on = run_analysis(
                            price_df=df,
                            strategy_name=strategy_name,
                            short_window=short_window,
                            long_window=long_window,
                            rr_target=rr_target,
                            trade_mode=trade_mode,
                            cost_per_trade_r=cost_per_trade_r,
                            starting_r=starting_r,
                            split_ratio=split_ratio,
                            trend_filter_enabled=trend_filter_enabled,
                            trend_filter_window=trend_filter_window,
                            volatility_filter_enabled=True,
                            atr_window=atr_window,
                            min_atr_pct=min_atr_pct,
                            regime_filter_enabled=regime_filter_enabled,
                            adx_window=adx_window,
                            min_adx=min_adx,
                            session_filter_enabled=session_filter_enabled,
                            session_start_hour=session_start_hour,
                            session_end_hour=session_end_hour,
                            strategy_mode=strategy_mode,
                            trend_lookback_bars=trend_lookback_bars,
                            min_trend_atr_multiple=min_trend_atr_multiple,
                            pullback_max_bars=pullback_max_bars,
                            pullback_max_depth_atr=pullback_max_depth_atr,
                            confirmation_bars=confirmation_bars
                        )

                        trend_analysis_off = run_analysis(
                            price_df=df,
                            strategy_name=strategy_name,
                            short_window=short_window,
                            long_window=long_window,
                            rr_target=rr_target,
                            trade_mode=trade_mode,
                            cost_per_trade_r=cost_per_trade_r,
                            starting_r=starting_r,
                            split_ratio=split_ratio,
                            trend_filter_enabled=False,
                            trend_filter_window=trend_filter_window,
                            volatility_filter_enabled=volatility_filter_enabled,
                            atr_window=atr_window,
                            min_atr_pct=min_atr_pct,
                            regime_filter_enabled=regime_filter_enabled,
                            adx_window=adx_window,
                            min_adx=min_adx,
                            session_filter_enabled=session_filter_enabled,
                            session_start_hour=session_start_hour,
                            session_end_hour=session_end_hour,
                            strategy_mode=strategy_mode,
                            trend_lookback_bars=trend_lookback_bars,
                            min_trend_atr_multiple=min_trend_atr_multiple,
                            pullback_max_bars=pullback_max_bars,
                            pullback_max_depth_atr=pullback_max_depth_atr,
                            confirmation_bars=confirmation_bars
                        )

                        trend_analysis_on = run_analysis(
                            price_df=df,
                            strategy_name=strategy_name,
                            short_window=short_window,
                            long_window=long_window,
                            rr_target=rr_target,
                            trade_mode=trade_mode,
                            cost_per_trade_r=cost_per_trade_r,
                            starting_r=starting_r,
                            split_ratio=split_ratio,
                            trend_filter_enabled=True,
                            trend_filter_window=trend_filter_window,
                            volatility_filter_enabled=volatility_filter_enabled,
                            atr_window=atr_window,
                            min_atr_pct=min_atr_pct,
                            regime_filter_enabled=regime_filter_enabled,
                            adx_window=adx_window,
                            min_adx=min_adx,
                            session_filter_enabled=session_filter_enabled,
                            session_start_hour=session_start_hour,
                            session_end_hour=session_end_hour,
                            strategy_mode=strategy_mode,
                            trend_lookback_bars=trend_lookback_bars,
                            min_trend_atr_multiple=min_trend_atr_multiple,
                            pullback_max_bars=pullback_max_bars,
                            pullback_max_depth_atr=pullback_max_depth_atr,
                            confirmation_bars=confirmation_bars
                        )

                        regime_analysis_off = run_analysis(
                            price_df=df,
                            strategy_name=strategy_name,
                            short_window=short_window,
                            long_window=long_window,
                            rr_target=rr_target,
                            trade_mode=trade_mode,
                            cost_per_trade_r=cost_per_trade_r,
                            starting_r=starting_r,
                            split_ratio=split_ratio,
                            trend_filter_enabled=trend_filter_enabled,
                            trend_filter_window=trend_filter_window,
                            volatility_filter_enabled=volatility_filter_enabled,
                            atr_window=atr_window,
                            min_atr_pct=min_atr_pct,
                            regime_filter_enabled=False,
                            adx_window=adx_window,
                            min_adx=min_adx,
                            session_filter_enabled=session_filter_enabled,
                            session_start_hour=session_start_hour,
                            session_end_hour=session_end_hour,
                            strategy_mode=strategy_mode,
                            trend_lookback_bars=trend_lookback_bars,
                            min_trend_atr_multiple=min_trend_atr_multiple,
                            pullback_max_bars=pullback_max_bars,
                            pullback_max_depth_atr=pullback_max_depth_atr,
                            confirmation_bars=confirmation_bars
                        )

                        regime_analysis_on = run_analysis(
                            price_df=df,
                            strategy_name=strategy_name,
                            short_window=short_window,
                            long_window=long_window,
                            rr_target=rr_target,
                            trade_mode=trade_mode,
                            cost_per_trade_r=cost_per_trade_r,
                            starting_r=starting_r,
                            split_ratio=split_ratio,
                            trend_filter_enabled=trend_filter_enabled,
                            trend_filter_window=trend_filter_window,
                            volatility_filter_enabled=volatility_filter_enabled,
                            atr_window=atr_window,
                            min_atr_pct=min_atr_pct,
                            regime_filter_enabled=True,
                            adx_window=adx_window,
                            min_adx=min_adx,
                            session_filter_enabled=session_filter_enabled,
                            session_start_hour=session_start_hour,
                            session_end_hour=session_end_hour,
                            strategy_mode=strategy_mode,
                            trend_lookback_bars=trend_lookback_bars,
                            min_trend_atr_multiple=min_trend_atr_multiple,
                            pullback_max_bars=pullback_max_bars,
                            pullback_max_depth_atr=pullback_max_depth_atr,
                            confirmation_bars=confirmation_bars
                        )

                        session_analysis_off = run_analysis(
                            price_df=df,
                            strategy_name=strategy_name,
                            short_window=short_window,
                            long_window=long_window,
                            rr_target=rr_target,
                            trade_mode=trade_mode,
                            cost_per_trade_r=cost_per_trade_r,
                            starting_r=starting_r,
                            split_ratio=split_ratio,
                            trend_filter_enabled=trend_filter_enabled,
                            trend_filter_window=trend_filter_window,
                            volatility_filter_enabled=volatility_filter_enabled,
                            atr_window=atr_window,
                            min_atr_pct=min_atr_pct,
                            regime_filter_enabled=regime_filter_enabled,
                            adx_window=adx_window,
                            min_adx=min_adx,
                            session_filter_enabled=False,
                            session_start_hour=session_start_hour,
                            session_end_hour=session_end_hour,
                            strategy_mode=strategy_mode,
                            trend_lookback_bars=trend_lookback_bars,
                            min_trend_atr_multiple=min_trend_atr_multiple,
                            pullback_max_bars=pullback_max_bars,
                            pullback_max_depth_atr=pullback_max_depth_atr,
                            confirmation_bars=confirmation_bars
                        )

                        session_analysis_on = run_analysis(
                            price_df=df,
                            strategy_name=strategy_name,
                            short_window=short_window,
                            long_window=long_window,
                            rr_target=rr_target,
                            trade_mode=trade_mode,
                            cost_per_trade_r=cost_per_trade_r,
                            starting_r=starting_r,
                            split_ratio=split_ratio,
                            trend_filter_enabled=trend_filter_enabled,
                            trend_filter_window=trend_filter_window,
                            volatility_filter_enabled=volatility_filter_enabled,
                            atr_window=atr_window,
                            min_atr_pct=min_atr_pct,
                            regime_filter_enabled=regime_filter_enabled,
                            adx_window=adx_window,
                            min_adx=min_adx,
                            session_filter_enabled=True,
                            session_start_hour=session_start_hour,
                            session_end_hour=session_end_hour,
                            strategy_mode=strategy_mode,
                            trend_lookback_bars=trend_lookback_bars,
                            min_trend_atr_multiple=min_trend_atr_multiple,
                            pullback_max_bars=pullback_max_bars,
                            pullback_max_depth_atr=pullback_max_depth_atr,
                            confirmation_bars=confirmation_bars
                        )
                    else:
                        volatility_analysis_off = None
                        volatility_analysis_on = None
                        trend_analysis_off = None
                        trend_analysis_on = None
                        regime_analysis_off = None
                        regime_analysis_on = None
                        session_analysis_off = None
                        session_analysis_on = None

                    pass

                    df = analysis_selected["df"]
                    df_insample = analysis_selected["df_insample"]
                    df_outsample = analysis_selected["df_outsample"]

                    trades_df = analysis_selected["trades_df"]
                    equity_df = analysis_selected["equity_df"]
                    metrics = analysis_selected["metrics"]

                    trades_insample = analysis_selected["trades_insample"]
                    equity_insample = analysis_selected["equity_insample"]
                    metrics_insample = analysis_selected["metrics_insample"]

                    trades_outsample = analysis_selected["trades_outsample"]
                    equity_outsample = analysis_selected["equity_outsample"]
                    metrics_outsample = analysis_selected["metrics_outsample"]

                    session_oos_robustness_df = pd.DataFrame()

                    if is_sma_strategy:
                        comparison_volatility_df = pd.DataFrame([
                            {
                                "Filtre volatilité": "OFF",
                                "Trades Total": volatility_analysis_off["metrics"]["number_of_trades"],
                                "Total R": volatility_analysis_off["metrics"]["total_pnl"],
                                "Expectancy": volatility_analysis_off["metrics"]["expectancy"],
                                "Max Drawdown": volatility_analysis_off["metrics"]["max_drawdown"],
                                "Trades IS": volatility_analysis_off["metrics_insample"]["number_of_trades"],
                                "Total R IS": volatility_analysis_off["metrics_insample"]["total_pnl"],
                                "Expectancy IS": volatility_analysis_off["metrics_insample"]["expectancy"],
                                "Trades OOS": volatility_analysis_off["metrics_outsample"]["number_of_trades"],
                                "Total R OOS": volatility_analysis_off["metrics_outsample"]["total_pnl"],
                                "Expectancy OOS": volatility_analysis_off["metrics_outsample"]["expectancy"],
                            },
                            {
                                "Filtre volatilité": "ON",
                                "Trades Total": volatility_analysis_on["metrics"]["number_of_trades"],
                                "Total R": volatility_analysis_on["metrics"]["total_pnl"],
                                "Expectancy": volatility_analysis_on["metrics"]["expectancy"],
                                "Max Drawdown": volatility_analysis_on["metrics"]["max_drawdown"],
                                "Trades IS": volatility_analysis_on["metrics_insample"]["number_of_trades"],
                                "Total R IS": volatility_analysis_on["metrics_insample"]["total_pnl"],
                                "Expectancy IS": volatility_analysis_on["metrics_insample"]["expectancy"],
                                "Trades OOS": volatility_analysis_on["metrics_outsample"]["number_of_trades"],
                                "Total R OOS": volatility_analysis_on["metrics_outsample"]["total_pnl"],
                                "Expectancy OOS": volatility_analysis_on["metrics_outsample"]["expectancy"],
                            }
                        ])

                        comparison_trend_df = pd.DataFrame([
                            {
                                "Filtre tendance": "OFF",
                                "Trades Total": trend_analysis_off["metrics"]["number_of_trades"],
                                "Total R": trend_analysis_off["metrics"]["total_pnl"],
                                "Expectancy": trend_analysis_off["metrics"]["expectancy"],
                                "Max Drawdown": trend_analysis_off["metrics"]["max_drawdown"],
                                "Trades IS": trend_analysis_off["metrics_insample"]["number_of_trades"],
                                "Total R IS": trend_analysis_off["metrics_insample"]["total_pnl"],
                                "Expectancy IS": trend_analysis_off["metrics_insample"]["expectancy"],
                                "Trades OOS": trend_analysis_off["metrics_outsample"]["number_of_trades"],
                                "Total R OOS": trend_analysis_off["metrics_outsample"]["total_pnl"],
                                "Expectancy OOS": trend_analysis_off["metrics_outsample"]["expectancy"],
                            },
                            {
                                "Filtre tendance": "ON",
                                "Trades Total": trend_analysis_on["metrics"]["number_of_trades"],
                                "Total R": trend_analysis_on["metrics"]["total_pnl"],
                                "Expectancy": trend_analysis_on["metrics"]["expectancy"],
                                "Max Drawdown": trend_analysis_on["metrics"]["max_drawdown"],
                                "Trades IS": trend_analysis_on["metrics_insample"]["number_of_trades"],
                                "Total R IS": trend_analysis_on["metrics_insample"]["total_pnl"],
                                "Expectancy IS": trend_analysis_on["metrics_insample"]["expectancy"],
                                "Trades OOS": trend_analysis_on["metrics_outsample"]["number_of_trades"],
                                "Total R OOS": trend_analysis_on["metrics_outsample"]["total_pnl"],
                                "Expectancy OOS": trend_analysis_on["metrics_outsample"]["expectancy"],
                            }
                        ])

                        comparison_regime_df = pd.DataFrame([
                            {
                                "Filtre régime": "OFF",
                                "Trades Total": regime_analysis_off["metrics"]["number_of_trades"],
                                "Total R": regime_analysis_off["metrics"]["total_pnl"],
                                "Expectancy": regime_analysis_off["metrics"]["expectancy"],
                                "Max Drawdown": regime_analysis_off["metrics"]["max_drawdown"],
                                "Trades IS": regime_analysis_off["metrics_insample"]["number_of_trades"],
                                "Total R IS": regime_analysis_off["metrics_insample"]["total_pnl"],
                                "Expectancy IS": regime_analysis_off["metrics_insample"]["expectancy"],
                                "Trades OOS": regime_analysis_off["metrics_outsample"]["number_of_trades"],
                                "Total R OOS": regime_analysis_off["metrics_outsample"]["total_pnl"],
                                "Expectancy OOS": regime_analysis_off["metrics_outsample"]["expectancy"],
                            },
                            {
                                "Filtre régime": "ON",
                                "Trades Total": regime_analysis_on["metrics"]["number_of_trades"],
                                "Total R": regime_analysis_on["metrics"]["total_pnl"],
                                "Expectancy": regime_analysis_on["metrics"]["expectancy"],
                                "Max Drawdown": regime_analysis_on["metrics"]["max_drawdown"],
                                "Trades IS": regime_analysis_on["metrics_insample"]["number_of_trades"],
                                "Total R IS": regime_analysis_on["metrics_insample"]["total_pnl"],
                                "Expectancy IS": regime_analysis_on["metrics_insample"]["expectancy"],
                                "Trades OOS": regime_analysis_on["metrics_outsample"]["number_of_trades"],
                                "Total R OOS": regime_analysis_on["metrics_outsample"]["total_pnl"],
                                "Expectancy OOS": regime_analysis_on["metrics_outsample"]["expectancy"],
                            }
                        ])

                        comparison_session_df = pd.DataFrame([
                            {
                                "Filtre horaire": "OFF",
                                "Trades Total": session_analysis_off["metrics"]["number_of_trades"],
                                "Total R": session_analysis_off["metrics"]["total_pnl"],
                                "Expectancy": session_analysis_off["metrics"]["expectancy"],
                                "Max Drawdown": session_analysis_off["metrics"]["max_drawdown"],
                                "Trades IS": session_analysis_off["metrics_insample"]["number_of_trades"],
                                "Total R IS": session_analysis_off["metrics_insample"]["total_pnl"],
                                "Expectancy IS": session_analysis_off["metrics_insample"]["expectancy"],
                                "Trades OOS": session_analysis_off["metrics_outsample"]["number_of_trades"],
                                "Total R OOS": session_analysis_off["metrics_outsample"]["total_pnl"],
                                "Expectancy OOS": session_analysis_off["metrics_outsample"]["expectancy"],
                            },
                            {
                                "Filtre horaire": "ON",
                                "Trades Total": session_analysis_on["metrics"]["number_of_trades"],
                                "Total R": session_analysis_on["metrics"]["total_pnl"],
                                "Expectancy": session_analysis_on["metrics"]["expectancy"],
                                "Max Drawdown": session_analysis_on["metrics"]["max_drawdown"],
                                "Trades IS": session_analysis_on["metrics_insample"]["number_of_trades"],
                                "Total R IS": session_analysis_on["metrics_insample"]["total_pnl"],
                                "Expectancy IS": session_analysis_on["metrics_insample"]["expectancy"],
                                "Trades OOS": session_analysis_on["metrics_outsample"]["number_of_trades"],
                                "Total R OOS": session_analysis_on["metrics_outsample"]["total_pnl"],
                                "Expectancy OOS": session_analysis_on["metrics_outsample"]["expectancy"],
                            }
                        ])

                        context_filters_rows = []

                        context_filters_inputs = [
                            ("Tendance", trend_analysis_off, trend_analysis_on),
                            ("Volatilité", volatility_analysis_off, volatility_analysis_on),
                            ("Régime", regime_analysis_off, regime_analysis_on),
                            ("Session", session_analysis_off, session_analysis_on),
                        ]

                        for filter_name, analysis_off, analysis_on in context_filters_inputs:
                            is_expectancy_off = analysis_off["metrics_insample"]["expectancy"]
                            is_expectancy_on = analysis_on["metrics_insample"]["expectancy"]
                            oos_expectancy_off = analysis_off["metrics_outsample"]["expectancy"]
                            oos_expectancy_on = analysis_on["metrics_outsample"]["expectancy"]
                            oos_dd_off = analysis_off["metrics_outsample"]["max_drawdown"]
                            oos_dd_on = analysis_on["metrics_outsample"]["max_drawdown"]

                            delta_is_expectancy = round(is_expectancy_on - is_expectancy_off, 2)
                            delta_oos_expectancy = round(oos_expectancy_on - oos_expectancy_off, 2)
                            delta_oos_dd_abs = round(abs(oos_dd_on) - abs(oos_dd_off), 2)

                            if analysis_on["metrics_outsample"]["number_of_trades"] < 5:
                                context_diagnostic = "OOS ON trop faible"
                            elif delta_oos_expectancy > 0 and delta_oos_dd_abs <= 0:
                                context_diagnostic = "Amélioration robuste"
                            elif delta_oos_expectancy > 0 and delta_oos_dd_abs > 0:
                                context_diagnostic = "Amélioration avec risque"
                            elif delta_oos_expectancy == 0:
                                context_diagnostic = "Impact neutre"
                            else:
                                context_diagnostic = "Dégradation OOS"

                            context_score = 0.0
                            context_score += delta_oos_expectancy * 100
                            context_score += delta_is_expectancy * 30
                            context_score -= max(delta_oos_dd_abs, 0) * 10
                            context_score += min(analysis_on["metrics_outsample"]["number_of_trades"], 20)

                            if context_diagnostic == "Amélioration robuste":
                                context_score += 20
                            elif context_diagnostic == "Amélioration avec risque":
                                context_score += 5
                            elif context_diagnostic == "OOS ON trop faible":
                                context_score -= 15
                            elif context_diagnostic == "Dégradation OOS":
                                context_score -= 20

                            context_score = round(context_score, 2)

                            context_filters_rows.append({
                                "Filtre": filter_name,
                                "Score contexte": context_score,
                                "Diagnostic": context_diagnostic,
                                "Trades OOS OFF": analysis_off["metrics_outsample"]["number_of_trades"],
                                "Trades OOS ON": analysis_on["metrics_outsample"]["number_of_trades"],
                                "Expectancy IS OFF": is_expectancy_off,
                                "Expectancy IS ON": is_expectancy_on,
                                "Delta Expectancy IS": delta_is_expectancy,
                                "Expectancy OOS OFF": oos_expectancy_off,
                                "Expectancy OOS ON": oos_expectancy_on,
                                "Delta Expectancy OOS": delta_oos_expectancy,
                                "Max DD OOS OFF": oos_dd_off,
                                "Max DD OOS ON": oos_dd_on,
                                "Delta DD OOS (abs)": delta_oos_dd_abs
                            })

                        context_filters_summary_df = pd.DataFrame(context_filters_rows)

                        if not context_filters_summary_df.empty:
                            context_filters_summary_df = context_filters_summary_df.sort_values(
                                by=["Score contexte", "Delta Expectancy OOS", "Delta DD OOS (abs)", "Delta Expectancy IS"],
                                ascending=[False, False, True, False]
                            ).reset_index(drop=True)

                            context_filters_summary_df = context_filters_summary_df[
                                [
                                    "Filtre",
                                    "Score contexte",
                                    "Diagnostic",
                                    "Trades OOS OFF",
                                    "Trades OOS ON",
                                    "Expectancy IS OFF",
                                    "Expectancy IS ON",
                                    "Delta Expectancy IS",
                                    "Expectancy OOS OFF",
                                    "Expectancy OOS ON",
                                    "Delta Expectancy OOS",
                                    "Max DD OOS OFF",
                                    "Max DD OOS ON",
                                    "Delta DD OOS (abs)"
                                ]
                            ]
                    else:
                        comparison_volatility_df = pd.DataFrame()
                        comparison_trend_df = pd.DataFrame()
                        comparison_regime_df = pd.DataFrame()
                        comparison_session_df = pd.DataFrame()
                        context_filters_summary_df = pd.DataFrame()
                    if run_optimization or (is_impulse_strategy and not st.session_state.optimization_results.empty):
                        progress_bar = st.progress(0)
                        progress_text = st.empty()
                        progress_meta = st.empty()

                        optimization_start_time = time.perf_counter()

                        if is_sma_strategy:
                            estimated_total_combinations = (
                                len([4, 6, 8, 10])
                                * len([12, 18, 24])
                                * len([1.0, 2.0, 3.0])
                                * len(([50, 100] if trend_filter_enabled else [trend_filter_window]))
                                * len(([10, 20] if volatility_filter_enabled else [atr_window]))
                                * len(([0.10, 0.20] if volatility_filter_enabled else [min_atr_pct]))
                                * len(([10, 20] if regime_filter_enabled else [adx_window]))
                                * len(([15.0, 25.0] if regime_filter_enabled else [min_adx]))
                                * len(optimization_session_names)
                            )
                        else:
                            if impulse_optimization_preset == "Rapide":
                                estimated_total_combinations = (
                                    len([80, 120])
                                    * len([14, 20])
                                    * len([2.0, 3.0])
                                    * len([4, 6])
                                    * len([1.0, 1.5])
                                    * len([1, 2])
                                    * len([1.0, 2.0])
                                )
                            elif impulse_optimization_preset == "30-45 min":
                                estimated_total_combinations = (
                                    len([80, 100, 120])
                                    * len([14, 20])
                                    * len([2.0, 2.5, 3.0])
                                    * len([4, 6, 8])
                                    * len([1.0, 1.2, 1.5])
                                    * len([1, 2])
                                    * len([1.0, 1.5, 2.0])
                                )
                            elif impulse_optimization_preset == "2H / Salle":
                                estimated_total_combinations = (
                                    len([80, 100, 120, 140])
                                    * len([10, 14, 20])
                                    * len([1.5, 2.0, 2.5])
                                    * len([4, 6, 8])
                                    * len([0.8, 1.0, 1.2])
                                    * len([1, 2])
                                    * len([1.0, 1.5, 2.0, 2.5])
                                )
                            elif impulse_optimization_preset == "Nuit léger":
                                estimated_total_combinations = (
                                    len([60, 80, 100, 120, 140, 160])
                                    * len([10, 14, 20])
                                    * len([1.5, 2.0, 2.5, 3.0])
                                    * len([3, 4, 6, 8])
                                    * len([0.8, 1.0, 1.2, 1.5])
                                    * len([1, 2])
                                    * len([1.0, 1.5, 2.0, 2.5])
                                )
                            else:
                                estimated_total_combinations = (
                                    len([40, 60, 80, 100, 120, 140, 160, 180])
                                    * len([8, 10, 14, 20])
                                    * len([1.0, 1.5, 2.0, 2.5, 3.0])
                                    * len([2, 3, 4, 6, 8])
                                    * len([0.6, 0.8, 1.0, 1.2, 1.5])
                                    * len([1, 2])
                                    * len([1.0, 1.5, 2.0, 2.5, 3.0])
                                )

                        if is_impulse_strategy:
                            if impulse_optimization_preset == "Rapide":
                                impulse_preset_read = "test direct"
                            elif impulse_optimization_preset == "30-45 min":
                                impulse_preset_read = "run tactique"
                            elif impulse_optimization_preset == "2H / Salle":
                                impulse_preset_read = "run intermédiaire"
                            elif impulse_optimization_preset == "Nuit léger":
                                impulse_preset_read = "run long"
                            else:
                                impulse_preset_read = "run de nuit"

                            st.info(
                                f"Optimisation Impulse lancée | Preset = {impulse_optimization_preset} | "
                                f"Type = {impulse_preset_read} | "
                                f"Combinaisons estimées = {estimated_total_combinations}."
                            )
                        else:
                            st.info(
                                f"Optimisation lancée : environ {estimated_total_combinations} combinaisons à tester."
                            )

                        def update_progress(completed, total):
                            elapsed = time.perf_counter() - optimization_start_time

                            if total <= 0:
                                progress_ratio = 0.0
                            else:
                                progress_ratio = completed / total

                            progress_bar.progress(min(int(progress_ratio * 100), 100))

                            if completed > 0:
                                avg_time_per_iteration = elapsed / completed
                                remaining_iterations = max(total - completed, 0)
                                estimated_remaining_seconds = avg_time_per_iteration * remaining_iterations
                            else:
                                estimated_remaining_seconds = 0.0

                            elapsed_minutes = int(elapsed // 60)
                            elapsed_seconds = int(elapsed % 60)

                            remaining_minutes = int(estimated_remaining_seconds // 60)
                            remaining_seconds = int(estimated_remaining_seconds % 60)

                            progress_text.text(
                                f"Progression : {completed}/{total} combinaisons"
                            )
                            progress_meta.text(
                                f"Temps écoulé : {elapsed_minutes:02d}:{elapsed_seconds:02d} | "
                                f"Temps restant estimé : {remaining_minutes:02d}:{remaining_seconds:02d}"
                            )

                        if is_sma_strategy:
                            st.session_state.optimization_results = optimize_parameters(
                                df_insample=df_insample,
                                short_values=[4, 6, 8, 10],
                                long_values=[12, 18, 24],
                                rr_values=[1.0, 2.0, 3.0],
                                trade_mode=trade_mode,
                                cost_per_trade_r=cost_per_trade_r,
                                min_trades=optimizer_min_trades,
                                trend_filter_enabled=trend_filter_enabled,
                                trend_filter_window=trend_filter_window,
                                volatility_filter_enabled=volatility_filter_enabled,
                                atr_window=atr_window,
                                min_atr_pct=min_atr_pct,
                                regime_filter_enabled=regime_filter_enabled,
                                adx_window=adx_window,
                                min_adx=min_adx,
                                session_filter_enabled=session_filter_enabled,
                                session_start_hour=session_start_hour,
                                session_end_hour=session_end_hour,
                                session_names_to_test=optimization_session_names,
                                session_presets=session_presets,
                                atr_window_values=[10, 20],
                                min_atr_pct_values=[0.10, 0.20],
                                trend_filter_window_values=[50, 100],
                                adx_window_values=[10, 20],
                                min_adx_values=[15.0, 25.0],
                                strategy_mode=strategy_mode,
                                progress_callback=update_progress
                            )
                        else:
                            if impulse_optimization_preset == "Rapide":
                                impulse_trend_lookback_values = [80, 120]
                                impulse_atr_window_values = [14, 20]
                                impulse_min_trend_atr_multiple_values = [2.0, 3.0]
                                impulse_pullback_max_bars_values = [4, 6]
                                impulse_pullback_max_depth_atr_values = [1.0, 1.5]
                                impulse_confirmation_bars_values = [1, 2]
                                impulse_rr_values = [1.0, 2.0]

                            elif impulse_optimization_preset == "30-45 min":
                                impulse_trend_lookback_values = [80, 100, 120]
                                impulse_atr_window_values = [14, 20]
                                impulse_min_trend_atr_multiple_values = [2.0, 2.5, 3.0]
                                impulse_pullback_max_bars_values = [4, 6, 8]
                                impulse_pullback_max_depth_atr_values = [1.0, 1.2, 1.5]
                                impulse_confirmation_bars_values = [1, 2]
                                impulse_rr_values = [1.0, 1.5, 2.0]

                            elif impulse_optimization_preset == "2H / Salle":
                                impulse_trend_lookback_values = [80, 100, 120, 140]
                                impulse_atr_window_values = [10, 14, 20]
                                impulse_min_trend_atr_multiple_values = [1.5, 2.0, 2.5]
                                impulse_pullback_max_bars_values = [4, 6, 8]
                                impulse_pullback_max_depth_atr_values = [0.8, 1.0, 1.2]
                                impulse_confirmation_bars_values = [1, 2]
                                impulse_rr_values = [1.0, 1.5, 2.0, 2.5]

                            elif impulse_optimization_preset == "Nuit léger":
                                impulse_trend_lookback_values = [60, 80, 100, 120, 140, 160]
                                impulse_atr_window_values = [10, 14, 20]
                                impulse_min_trend_atr_multiple_values = [1.5, 2.0, 2.5, 3.0]
                                impulse_pullback_max_bars_values = [3, 4, 6, 8]
                                impulse_pullback_max_depth_atr_values = [0.8, 1.0, 1.2, 1.5]
                                impulse_confirmation_bars_values = [1, 2]
                                impulse_rr_values = [1.0, 1.5, 2.0, 2.5]

                            else:
                                impulse_trend_lookback_values = [40, 60, 80, 100, 120, 140, 160, 180]
                                impulse_atr_window_values = [8, 10, 14, 20]
                                impulse_min_trend_atr_multiple_values = [1.0, 1.5, 2.0, 2.5, 3.0]
                                impulse_pullback_max_bars_values = [2, 3, 4, 6, 8]
                                impulse_pullback_max_depth_atr_values = [0.6, 0.8, 1.0, 1.2, 1.5]
                                impulse_confirmation_bars_values = [1, 2]
                                impulse_rr_values = [1.0, 1.5, 2.0, 2.5, 3.0]

                            st.session_state.optimization_results = optimize_impulse_parameters(
                                df_insample=df_insample,
                                trend_lookback_values=impulse_trend_lookback_values,
                                atr_window_values=impulse_atr_window_values,
                                min_trend_atr_multiple_values=impulse_min_trend_atr_multiple_values,
                                pullback_max_bars_values=impulse_pullback_max_bars_values,
                                pullback_max_depth_atr_values=impulse_pullback_max_depth_atr_values,
                                confirmation_bars_values=impulse_confirmation_bars_values,
                                rr_values=impulse_rr_values,
                                trade_mode=trade_mode,
                                cost_per_trade_r=cost_per_trade_r,
                                min_trades=optimizer_min_trades,
                                strategy_mode=strategy_mode,
                                progress_callback=update_progress
                            )

                        progress_bar.progress(100)

                        total_elapsed = time.perf_counter() - optimization_start_time
                        total_elapsed_minutes = int(total_elapsed // 60)
                        total_elapsed_seconds = int(total_elapsed % 60)

                        progress_text.text("Optimisation terminée.")
                        progress_meta.text(
                            f"Temps total : {total_elapsed_minutes:02d}:{total_elapsed_seconds:02d}"
                        )

                    optimization_results = st.session_state.optimization_results.copy()

                    if run_optimization or (is_impulse_strategy and not st.session_state.optimization_results.empty):
                        if not optimization_results.empty:
                            optimization_results = optimization_results.sort_values(
                                by=["Expectancy (R)", "Score robustesse IS", "Total R", "Trades", "Max Drawdown (R)"],
                                ascending=[False, False, False, False, False]
                            ).reset_index(drop=True)

                            st.session_state.optimization_results = optimization_results

                            optimization_display_df = optimization_results.head(10).copy()

                            if is_sma_strategy:
                                display_columns = [
                                    "Short Window",
                                    "Long Window",
                                    "RR Target",
                                    "Trades",
                                    "Expectancy (R)",
                                    "Score robustesse IS",
                                    "Total R",
                                    "Max Drawdown (R)",
                                    "Trend Filter Window",
                                    "ATR Window",
                                    "Min ATR %",
                                    "ADX Window",
                                    "Min ADX",
                                    "Session Name",
                                    "Session Start",
                                    "Session End"
                                ]
                            else:
                                display_columns = [
                                    "Trend Lookback",
                                    "ATR Window",
                                    "Min Trend ATR Multiple",
                                    "Pullback Max Bars",
                                    "Pullback Max Depth ATR",
                                    "Confirmation Bars",
                                    "RR Target",
                                    "Trades",
                                    "Expectancy (R)",
                                    "Score robustesse IS",
                                    "Total R",
                                    "Max Drawdown (R)"
                                ]

                            available_display_columns = [
                                col for col in display_columns if col in optimization_display_df.columns
                            ]

                            optimization_display_df = optimization_display_df[available_display_columns]

                            st.subheader("Top 10 optimisation")
                            st.dataframe(optimization_display_df, use_container_width=True)
                            if is_impulse_strategy:
                                top_n_is_to_validate = min(5, len(optimization_results))
                                top_n_is_rows = optimization_results.head(top_n_is_to_validate).copy()

                                top_n_oos_validation_rows = []

                                for is_rank, top_n_row in top_n_is_rows.reset_index(drop=True).iterrows():
                                    candidate_trend_lookback = int(top_n_row["Trend Lookback"])
                                    candidate_atr_window = int(top_n_row["ATR Window"])
                                    candidate_min_trend_atr_multiple = float(top_n_row["Min Trend ATR Multiple"])
                                    candidate_pullback_max_bars = int(top_n_row["Pullback Max Bars"])
                                    candidate_pullback_max_depth_atr = float(top_n_row["Pullback Max Depth ATR"])
                                    candidate_confirmation_bars = int(top_n_row["Confirmation Bars"])
                                    candidate_rr_target = float(top_n_row["RR Target"])

                                    candidate_oos_price_df = df_outsample[["Date", "Open", "High", "Low", "Close"]].copy()

                                    candidate_oos_df = calculate_impulse_pullback_break_strategy(
                                        candidate_oos_price_df,
                                        trend_lookback_bars=candidate_trend_lookback,
                                        atr_window=candidate_atr_window,
                                        min_trend_atr_multiple=candidate_min_trend_atr_multiple,
                                        pullback_max_bars=candidate_pullback_max_bars,
                                        pullback_max_depth_atr=candidate_pullback_max_depth_atr,
                                        confirmation_bars=candidate_confirmation_bars
                                    )

                                    candidate_oos_trades = run_simple_backtest(
                                        candidate_oos_df,
                                        rr_target=candidate_rr_target,
                                        trade_mode=trade_mode,
                                        cost_per_trade_r=cost_per_trade_r,
                                        strategy_mode=strategy_mode
                                    )

                                    candidate_oos_equity = build_equity_curve(candidate_oos_trades, starting_r=starting_r)
                                    candidate_oos_metrics = calculate_basic_metrics(candidate_oos_trades, candidate_oos_equity)

                                    candidate_is_trades = int(top_n_row["Trades"]) if pd.notna(top_n_row["Trades"]) else 0
                                    candidate_is_total_r = float(top_n_row["Total R"]) if pd.notna(top_n_row["Total R"]) else 0.0
                                    candidate_is_expectancy = float(top_n_row["Expectancy (R)"]) if pd.notna(top_n_row["Expectancy (R)"]) else 0.0
                                    candidate_is_max_dd = float(top_n_row["Max Drawdown (R)"]) if pd.notna(top_n_row["Max Drawdown (R)"]) else 0.0

                                    delta_expectancy = round(candidate_oos_metrics["expectancy"] - candidate_is_expectancy, 2)
                                    delta_total_r = round(candidate_oos_metrics["total_pnl"] - candidate_is_total_r, 2)

                                    if candidate_oos_metrics["number_of_trades"] < 5:
                                        candidate_oos_diagnostic = "OOS trop faible"
                                    elif candidate_oos_metrics["expectancy"] > 0 and delta_expectancy >= -0.10:
                                        candidate_oos_diagnostic = "Robuste"
                                    elif candidate_oos_metrics["expectancy"] > 0 and delta_expectancy >= -0.25:
                                        candidate_oos_diagnostic = "Dégradée mais positive"
                                    else:
                                        candidate_oos_diagnostic = "Fragile / non validée OOS"

                                    top_n_oos_validation_rows.append({
                                        "Rang IS": is_rank + 1,
                                        "Trend Lookback": candidate_trend_lookback,
                                        "ATR Window": candidate_atr_window,
                                        "Min Trend ATR Multiple": candidate_min_trend_atr_multiple,
                                        "Pullback Max Bars": candidate_pullback_max_bars,
                                        "Pullback Max Depth ATR": candidate_pullback_max_depth_atr,
                                        "Confirmation Bars": candidate_confirmation_bars,
                                        "RR": candidate_rr_target,
                                        "Trades IS": candidate_is_trades,
                                        "Expectancy IS": candidate_is_expectancy,
                                        "Total R IS": candidate_is_total_r,
                                        "Max DD IS": candidate_is_max_dd,
                                        "Trades OOS": candidate_oos_metrics["number_of_trades"],
                                        "Expectancy OOS": candidate_oos_metrics["expectancy"],
                                        "Total R OOS": candidate_oos_metrics["total_pnl"],
                                        "Max DD OOS": candidate_oos_metrics["max_drawdown"],
                                        "Delta Expectancy": delta_expectancy,
                                        "Delta Total R": delta_total_r,
                                        "Diagnostic OOS": candidate_oos_diagnostic
                                    })

                                top_n_oos_validation_df = pd.DataFrame(top_n_oos_validation_rows)

                                st.subheader(f"Validation OOS du Top {top_n_is_to_validate} IS - Impulse")
                                st.dataframe(top_n_oos_validation_df, use_container_width=True)
                                st.caption(
                                    "Ce tableau reteste en Out-of-Sample les meilleurs sets In-Sample de la stratégie Impulse, "
                                    "pour voir si le winner IS est isolé ou si plusieurs candidats survivent."
                                )

                                if top_n_oos_validation_df.empty:
                                    st.info("Aucune validation OOS Impulse disponible pour le moment.")
                                else:
                                    impulse_survivors_df = top_n_oos_validation_df[
                                        top_n_oos_validation_df["Diagnostic OOS"].isin(["Robuste", "Dégradée mais positive"])
                                    ].copy()

                                    impulse_reference_is_rank = 1
                                    impulse_reference_selection_mode = "winner_is"

                                    if impulse_survivors_df.empty:
                                        st.warning(
                                            "Lecture automatique Impulse : aucun des meilleurs sets IS ne semble vraiment validé en OOS sur ce test."
                                        )
                                    else:
                                        best_impulse_survivor_row = impulse_survivors_df.sort_values(
                                            by=["Expectancy OOS", "Total R OOS", "Trades OOS", "Delta Expectancy"],
                                            ascending=[False, False, False, False]
                                        ).reset_index(drop=True).iloc[0]

                                        impulse_reference_is_rank = int(best_impulse_survivor_row["Rang IS"])
                                        impulse_reference_selection_mode = "best_oos_survivor"

                                        if best_impulse_survivor_row["Diagnostic OOS"] == "Robuste":
                                            st.success(
                                                f"Lecture automatique Impulse : le meilleur survivant OOS actuel est le rang IS {best_impulse_survivor_row['Rang IS']} "
                                                f"avec Expectancy OOS = {best_impulse_survivor_row['Expectancy OOS']} "
                                                f"et Total R OOS = {best_impulse_survivor_row['Total R OOS']}."
                                            )
                                        else:
                                            st.info(
                                                f"Lecture automatique Impulse : au moins un set reste positif mais dégradé en OOS. "
                                                f"Le meilleur survivant actuel est le rang IS {best_impulse_survivor_row['Rang IS']} "
                                                f"avec Expectancy OOS = {best_impulse_survivor_row['Expectancy OOS']}."
                                            )

                                    st.subheader("Candidat de référence Impulse")

                                    if impulse_reference_selection_mode == "best_oos_survivor":
                                        st.success(
                                            f"Le candidat de référence Impulse pour la suite du run est le rang IS {impulse_reference_is_rank}, "
                                            "car c'est actuellement le meilleur survivant OOS parmi le Top 5 IS."
                                        )
                                    else:
                                        st.info(
                                            "Aucun survivant OOS convaincant n'a été trouvé dans le Top 5 IS Impulse. "
                                            "Le candidat de référence reste donc le winner IS (rang 1)."
                                        )

                                    impulse_best_row = optimization_results.iloc[impulse_reference_is_rank - 1]

                                    impulse_best_trend_lookback = int(impulse_best_row["Trend Lookback"])
                                    impulse_best_atr_window = int(impulse_best_row["ATR Window"])
                                    impulse_best_min_trend_atr_multiple = float(impulse_best_row["Min Trend ATR Multiple"])
                                    impulse_best_pullback_max_bars = int(impulse_best_row["Pullback Max Bars"])
                                    impulse_best_pullback_max_depth_atr = float(impulse_best_row["Pullback Max Depth ATR"])
                                    impulse_best_confirmation_bars = int(impulse_best_row["Confirmation Bars"])
                                    impulse_best_rr_target = float(impulse_best_row["RR Target"])

                                    impulse_best_oos_price_df = df_outsample[["Date", "Open", "High", "Low", "Close"]].copy()

                                    impulse_best_oos_df = calculate_impulse_pullback_break_strategy(
                                        impulse_best_oos_price_df,
                                        trend_lookback_bars=impulse_best_trend_lookback,
                                        atr_window=impulse_best_atr_window,
                                        min_trend_atr_multiple=impulse_best_min_trend_atr_multiple,
                                        pullback_max_bars=impulse_best_pullback_max_bars,
                                        pullback_max_depth_atr=impulse_best_pullback_max_depth_atr,
                                        confirmation_bars=impulse_best_confirmation_bars
                                    )

                                    impulse_best_oos_trades = run_simple_backtest(
                                        impulse_best_oos_df,
                                        rr_target=impulse_best_rr_target,
                                        trade_mode=trade_mode,
                                        cost_per_trade_r=cost_per_trade_r,
                                        strategy_mode=strategy_mode
                                    )

                                    impulse_best_oos_equity = build_equity_curve(impulse_best_oos_trades, starting_r=starting_r)
                                    impulse_best_oos_metrics = calculate_basic_metrics(impulse_best_oos_trades, impulse_best_oos_equity)

                                    impulse_best_is_oos_comparison_df = pd.DataFrame([
                                        {
                                            "Période": "In-Sample",
                                            "Trades": int(impulse_best_row["Trades"]) if pd.notna(impulse_best_row["Trades"]) else 0,
                                            "Total R": float(impulse_best_row["Total R"]) if pd.notna(impulse_best_row["Total R"]) else 0.0,
                                            "Expectancy": float(impulse_best_row["Expectancy (R)"]) if pd.notna(impulse_best_row["Expectancy (R)"]) else 0.0,
                                            "Max Drawdown": float(impulse_best_row["Max Drawdown (R)"]) if pd.notna(impulse_best_row["Max Drawdown (R)"]) else 0.0,
                                        },
                                        {
                                            "Période": "Out-of-Sample",
                                            "Trades": impulse_best_oos_metrics["number_of_trades"],
                                            "Total R": impulse_best_oos_metrics["total_pnl"],
                                            "Expectancy": impulse_best_oos_metrics["expectancy"],
                                            "Max Drawdown": impulse_best_oos_metrics["max_drawdown"],
                                        }
                                    ])

                                    st.subheader("Validation OOS du candidat de référence Impulse")
                                    st.caption(
                                        f"Rang IS de référence = {impulse_reference_is_rank} | "
                                        f"Trend Lookback = {impulse_best_trend_lookback} | "
                                        f"ATR Window = {impulse_best_atr_window} | "
                                        f"Min Trend ATR Multiple = {impulse_best_min_trend_atr_multiple} | "
                                        f"Pullback Max Bars = {impulse_best_pullback_max_bars} | "
                                        f"Pullback Max Depth ATR = {impulse_best_pullback_max_depth_atr} | "
                                        f"Confirmation Bars = {impulse_best_confirmation_bars} | "
                                        f"RR = {impulse_best_rr_target}"
                                    )

                                    impulse_oos_col1, impulse_oos_col2, impulse_oos_col3, impulse_oos_col4 = st.columns(4)
                                    impulse_oos_col1.metric("Trades OOS", impulse_best_oos_metrics["number_of_trades"])
                                    impulse_oos_col2.metric("Total R OOS", impulse_best_oos_metrics["total_pnl"])
                                    impulse_oos_col3.metric("Expectancy OOS", impulse_best_oos_metrics["expectancy"])
                                    impulse_oos_col4.metric("Max Drawdown OOS", impulse_best_oos_metrics["max_drawdown"])

                                    st.subheader("Comparaison IS vs OOS du candidat de référence Impulse")
                                    st.dataframe(impulse_best_is_oos_comparison_df, use_container_width=True)

                                    impulse_best_is_expectancy = float(impulse_best_row["Expectancy (R)"]) if pd.notna(impulse_best_row["Expectancy (R)"]) else 0.0
                                    impulse_best_delta_expectancy = round(
                                        impulse_best_oos_metrics["expectancy"] - impulse_best_is_expectancy,
                                        2
                                    )

                                    if impulse_best_oos_metrics["number_of_trades"] < 5:
                                        impulse_reference_oos_diagnostic = "OOS trop faible"
                                    elif impulse_best_oos_metrics["expectancy"] > 0 and impulse_best_delta_expectancy >= -0.10:
                                        impulse_reference_oos_diagnostic = "Robuste"
                                    elif impulse_best_oos_metrics["expectancy"] > 0 and impulse_best_delta_expectancy >= -0.25:
                                        impulse_reference_oos_diagnostic = "Dégradée mais positive"
                                    else:
                                        impulse_reference_oos_diagnostic = "Fragile / non validée OOS"

                                    if impulse_reference_oos_diagnostic == "Robuste":
                                        st.success(
                                            f"Lecture automatique Impulse : le candidat de référence semble robuste en OOS | "
                                            f"Expectancy OOS = {impulse_best_oos_metrics['expectancy']} | "
                                            f"Delta Expectancy = {impulse_best_delta_expectancy} | "
                                            f"Trades OOS = {impulse_best_oos_metrics['number_of_trades']}."
                                        )
                                    elif impulse_reference_oos_diagnostic == "Dégradée mais positive":
                                        st.info(
                                            f"Lecture automatique Impulse : le candidat de référence reste positif mais dégradé en OOS | "
                                            f"Expectancy OOS = {impulse_best_oos_metrics['expectancy']} | "
                                            f"Delta Expectancy = {impulse_best_delta_expectancy} | "
                                            f"Trades OOS = {impulse_best_oos_metrics['number_of_trades']}."
                                        )
                                    elif impulse_reference_oos_diagnostic == "OOS trop faible":
                                        st.warning(
                                            f"Lecture automatique Impulse : le nombre de trades OOS reste trop faible pour conclure sérieusement | "
                                            f"Trades OOS = {impulse_best_oos_metrics['number_of_trades']} | "
                                            f"Expectancy OOS = {impulse_best_oos_metrics['expectancy']}."
                                        )
                                    else:
                                        st.warning(
                                            f"Lecture automatique Impulse : le candidat de référence ne semble pas validé en OOS à ce stade | "
                                            f"Expectancy OOS = {impulse_best_oos_metrics['expectancy']} | "
                                            f"Delta Expectancy = {impulse_best_delta_expectancy} | "
                                            f"Trades OOS = {impulse_best_oos_metrics['number_of_trades']}."
                                        )
                                    impulse_multi_split_rows = []

                                    for tested_split_ratio in [60, 70, 80]:
                                        impulse_reference_analysis = run_analysis(
                                            price_df=df[["Date", "Open", "High", "Low", "Close"]].copy(),
                                            strategy_name=strategy_name,
                                            short_window=short_window,
                                            long_window=long_window,
                                            rr_target=impulse_best_rr_target,
                                            trade_mode=trade_mode,
                                            cost_per_trade_r=cost_per_trade_r,
                                            starting_r=starting_r,
                                            split_ratio=tested_split_ratio,
                                            trend_filter_enabled=trend_filter_enabled,
                                            trend_filter_window=trend_filter_window,
                                            volatility_filter_enabled=volatility_filter_enabled,
                                            atr_window=impulse_best_atr_window,
                                            min_atr_pct=min_atr_pct,
                                            regime_filter_enabled=regime_filter_enabled,
                                            adx_window=adx_window,
                                            min_adx=min_adx,
                                            session_filter_enabled=session_filter_enabled,
                                            session_start_hour=session_start_hour,
                                            session_end_hour=session_end_hour,
                                            strategy_mode=strategy_mode,
                                            trend_lookback_bars=impulse_best_trend_lookback,
                                            min_trend_atr_multiple=impulse_best_min_trend_atr_multiple,
                                            pullback_max_bars=impulse_best_pullback_max_bars,
                                            pullback_max_depth_atr=impulse_best_pullback_max_depth_atr,
                                            confirmation_bars=impulse_best_confirmation_bars
                                        )

                                        impulse_split_metrics_is = impulse_reference_analysis["metrics_insample"]
                                        impulse_split_metrics_oos = impulse_reference_analysis["metrics_outsample"]

                                        if impulse_split_metrics_oos["number_of_trades"] < 5:
                                            impulse_split_diagnostic = "OOS trop faible"
                                        elif impulse_split_metrics_oos["expectancy"] > 0 and impulse_split_metrics_oos["total_pnl"] > 0:
                                            impulse_split_diagnostic = "Robuste"
                                        elif impulse_split_metrics_oos["expectancy"] > 0:
                                            impulse_split_diagnostic = "Dégradée mais positive"
                                        else:
                                            impulse_split_diagnostic = "Fragile / non validée OOS"

                                        impulse_multi_split_rows.append({
                                            "Split IS %": tested_split_ratio,
                                            "Split OOS %": 100 - tested_split_ratio,
                                            "Trades IS": impulse_split_metrics_is["number_of_trades"],
                                            "Expectancy IS": impulse_split_metrics_is["expectancy"],
                                            "Total R IS": impulse_split_metrics_is["total_pnl"],
                                            "Trades OOS": impulse_split_metrics_oos["number_of_trades"],
                                            "Expectancy OOS": impulse_split_metrics_oos["expectancy"],
                                            "Total R OOS": impulse_split_metrics_oos["total_pnl"],
                                            "Max DD OOS": impulse_split_metrics_oos["max_drawdown"],
                                            "Diagnostic": impulse_split_diagnostic
                                        })

                                    impulse_multi_split_df = pd.DataFrame(impulse_multi_split_rows)

                                    st.subheader("Robustesse multi-splits du candidat de référence Impulse")
                                    st.dataframe(impulse_multi_split_df, use_container_width=True)
                                    st.caption(
                                        "Ce tableau reteste le même candidat de référence Impulse sur plusieurs découpages IS/OOS, "
                                        "pour vérifier s'il tient seulement sur un split ou sur plusieurs."
                                    )

                                    impulse_total_splits = len(impulse_multi_split_df)
                                    impulse_survival_count = 0
                                    impulse_multi_split_ratio = "0/0"
                                    impulse_multi_split_status = "Indisponible"

                                    if impulse_multi_split_df.empty:
                                        st.info("Aucune lecture multi-splits Impulse disponible pour le moment.")
                                    else:
                                        impulse_survival_count = len(
                                            impulse_multi_split_df[
                                                impulse_multi_split_df["Diagnostic"].isin(["Robuste", "Dégradée mais positive"])
                                            ]
                                        )
                                        impulse_multi_split_ratio = f"{impulse_survival_count}/{impulse_total_splits}"

                                        if impulse_survival_count == impulse_total_splits and impulse_total_splits > 0:
                                            impulse_multi_split_status = "Robuste"
                                            st.success(
                                                f"Lecture automatique Impulse : le candidat de référence tient sur {impulse_multi_split_ratio} splits testés. "
                                                "La robustesse devient plus crédible."
                                            )
                                        elif impulse_survival_count >= 2:
                                            impulse_multi_split_status = "Encourageant mais prudent"
                                            st.info(
                                                f"Lecture automatique Impulse : le candidat de référence tient sur {impulse_multi_split_ratio} splits testés. "
                                                "C'est encourageant, mais encore prudent."
                                            )
                                        elif impulse_survival_count == 1:
                                            impulse_multi_split_status = "Limité"
                                            st.warning(
                                                f"Lecture automatique Impulse : le candidat de référence ne tient que sur {impulse_multi_split_ratio} split testé. "
                                                "La robustesse reste limitée."
                                            )
                                        else:
                                            impulse_multi_split_status = "Faible / non validé"
                                            st.warning(
                                                f"Lecture automatique Impulse : le candidat de référence ne tient sur aucun des {impulse_total_splits} splits testés. "
                                                "Le run reste fragile."
                                            )
                                    st.subheader("Verdict global Impulse")

                                    impulse_run_survivor = (
                                        impulse_best_oos_metrics["expectancy"] > 0
                                        and impulse_best_oos_metrics["number_of_trades"] >= 5
                                        and impulse_survival_count >= 1
                                    )

                                    if impulse_run_survivor and impulse_survival_count == impulse_total_splits and impulse_total_splits > 0:
                                        impulse_global_status = "Robuste"
                                    elif impulse_run_survivor and impulse_survival_count >= 2:
                                        impulse_global_status = "Encourageant mais prudent"
                                    elif impulse_run_survivor:
                                        impulse_global_status = "Survivant fragile"
                                    elif impulse_best_oos_metrics["number_of_trades"] < 5:
                                        impulse_global_status = "OOS trop faible"
                                    else:
                                        impulse_global_status = "Faible / non validé"

                                    impulse_global_score = 0.0

                                    impulse_global_score += impulse_best_oos_metrics["expectancy"] * 250
                                    impulse_global_score += min(impulse_best_oos_metrics["number_of_trades"], 300) * 0.08
                                    impulse_global_score += max(impulse_best_oos_metrics["total_pnl"], 0) * 0.80
                                    impulse_global_score -= max(abs(impulse_best_oos_metrics["max_drawdown"]) - 10, 0) * 1.2

                                    if impulse_multi_split_status == "Robuste":
                                        impulse_global_score += 15
                                    elif impulse_multi_split_status == "Encourageant mais prudent":
                                        impulse_global_score += 5
                                    elif impulse_multi_split_status == "Limité":
                                        impulse_global_score -= 5
                                    elif impulse_multi_split_status == "Faible / non validé":
                                        impulse_global_score -= 15

                                    if impulse_global_status == "Robuste":
                                        impulse_global_score += 20
                                    elif impulse_global_status == "Encourageant mais prudent":
                                        impulse_global_score += 8
                                    elif impulse_global_status == "Survivant fragile":
                                        impulse_global_score -= 5
                                    elif impulse_global_status == "OOS trop faible":
                                        impulse_global_score -= 12
                                    else:
                                        impulse_global_score -= 20

                                    impulse_global_score = round(impulse_global_score, 2)

                                    impulse_run_signature = (
                                        f"IMP-TLB{impulse_best_trend_lookback}"
                                        f"-ATR{impulse_best_atr_window}"
                                        f"-MTA{impulse_best_min_trend_atr_multiple}"
                                        f"-PB{impulse_best_pullback_max_bars}"
                                        f"-DEPTH{impulse_best_pullback_max_depth_atr}"
                                        f"-CONF{impulse_best_confirmation_bars}"
                                        f"-RR{impulse_best_rr_target}"
                                        f"-MODE{strategy_mode}"
                                    )

                                    impulse_verdict_df = pd.DataFrame([
                                        {
                                            "Statut global": impulse_global_status,
                                            "Score global Impulse": impulse_global_score,
                                            "Run survivant": "Oui" if impulse_run_survivor else "Non",
                                            "Robustesse multi-splits": impulse_multi_split_status,
                                            "Splits survécus": impulse_multi_split_ratio,
                                            "Signature run": impulse_run_signature,
                                            "Trades OOS": impulse_best_oos_metrics["number_of_trades"],
                                            "Expectancy OOS": impulse_best_oos_metrics["expectancy"],
                                            "Total R OOS": impulse_best_oos_metrics["total_pnl"],
                                            "Max DD OOS": impulse_best_oos_metrics["max_drawdown"]
                                        }
                                    ])

                                    st.dataframe(impulse_verdict_df, use_container_width=True)
                                    impulse_alignment_count = 0
                                    impulse_keep_list = "Diagnostic moteur non calculé encore"
                                    impulse_rework_list = "Diagnostic moteur non calculé encore"

                                    impulse_best_trend_family = pd.Series({
                                        "Trend Lookback": "N/A"
                                    })
                                    impulse_stablest_trend_family = pd.Series({
                                        "Trend Lookback": "N/A"
                                    })

                                    impulse_best_rr_family = pd.Series({
                                        "RR Target": "N/A"
                                    })
                                    impulse_stablest_rr_family = pd.Series({
                                        "RR Target": "N/A"
                                    })

                                    impulse_best_confirmation_family = pd.Series({
                                        "Confirmation Bars": "N/A"
                                    })
                                    impulse_stablest_confirmation_family = pd.Series({
                                        "Confirmation Bars": "N/A"
                                    })

                                    impulse_best_min_trend_multiple_family = pd.Series({
                                        "Min Trend ATR Multiple": "N/A"
                                    })
                                    impulse_stablest_min_trend_multiple_family = pd.Series({
                                        "Min Trend ATR Multiple": "N/A"
                                    })

                                    impulse_best_pullback_bars_family = pd.Series({
                                        "Pullback Max Bars": "N/A"
                                    })
                                    impulse_stablest_pullback_bars_family = pd.Series({
                                        "Pullback Max Bars": "N/A"
                                    })

                                    impulse_best_pullback_depth_family = pd.Series({
                                        "Pullback Max Depth ATR": "N/A"
                                    })
                                    impulse_stablest_pullback_depth_family = pd.Series({
                                        "Pullback Max Depth ATR": "N/A"
                                    })


                                    impulse_structured_summary_df = pd.DataFrame([
                                        {
                                            "Statut global": impulse_global_status,
                                            "Dernier statut": impulse_global_status,
                                            "Score global du run": impulse_global_score,
                                            "Score global Impulse": impulse_global_score,
                                            "Score moyen": impulse_global_score,
                                            "Meilleur score": impulse_global_score,
                                            "Run survivant": "Oui" if impulse_run_survivor else "Non",
                                            "Robustesse multi-splits": impulse_multi_split_status,
                                            "Splits survécus": impulse_multi_split_ratio,
                                            "Dominance": "Impulse",
                                            "Preset optimisation": impulse_optimization_preset,
                                            "Combinaisons estimées": estimated_total_combinations,
                                            "Signature run": impulse_run_signature,
                                            "Signature courte": impulse_run_signature,
                                            "Mode sélection référence": impulse_reference_selection_mode,
                                            "Rang IS de référence": impulse_reference_is_rank,
                                            "Best Session": "Impulse",
                                            "Best Context": "Impulse",
                                            "Exploitable recherche": "Oui" if impulse_run_survivor else "Non",
                                            "Préparation hedge": "Non exploitable à ce stade",
                                            "Lecture structurelle": impulse_global_status,
                                            "Expectancy OOS": impulse_best_oos_metrics["expectancy"],
                                            "Total R OOS": impulse_best_oos_metrics["total_pnl"],
                                            "Max DD OOS": impulse_best_oos_metrics["max_drawdown"]
                                        }
                                    ])

                                    impulse_family_trend_df = (
                                        optimization_results.groupby("Trend Lookback", dropna=False)
                                        .agg(
                                            Occurrences=("Trend Lookback", "size"),
                                            Best_Expectancy=("Expectancy (R)", "max"),
                                            Avg_Expectancy=("Expectancy (R)", "mean"),
                                            Best_Total_R=("Total R", "max")
                                        )
                                        .reset_index()
                                        .sort_values(
                                            by=["Best_Expectancy", "Avg_Expectancy", "Occurrences"],
                                            ascending=[False, False, False]
                                        )
                                        .reset_index(drop=True)
                                    )

                                    impulse_family_rr_df = (
                                        optimization_results.groupby("RR Target", dropna=False)
                                        .agg(
                                            Occurrences=("RR Target", "size"),
                                            Best_Expectancy=("Expectancy (R)", "max"),
                                            Avg_Expectancy=("Expectancy (R)", "mean"),
                                            Best_Total_R=("Total R", "max")
                                        )
                                        .reset_index()
                                        .sort_values(
                                            by=["Best_Expectancy", "Avg_Expectancy", "Occurrences"],
                                            ascending=[False, False, False]
                                        )
                                        .reset_index(drop=True)
                                    )

                                    impulse_family_confirmation_df = (
                                        optimization_results.groupby("Confirmation Bars", dropna=False)
                                        .agg(
                                            Occurrences=("Confirmation Bars", "size"),
                                            Best_Expectancy=("Expectancy (R)", "max"),
                                            Avg_Expectancy=("Expectancy (R)", "mean"),
                                            Best_Total_R=("Total R", "max")
                                        )
                                        .reset_index()
                                        .sort_values(
                                            by=["Best_Expectancy", "Avg_Expectancy", "Occurrences"],
                                            ascending=[False, False, False]
                                        )
                                        .reset_index(drop=True)
                                    )

                                    impulse_family_min_trend_multiple_df = (
                                        optimization_results.groupby("Min Trend ATR Multiple", dropna=False)
                                        .agg(
                                            Occurrences=("Min Trend ATR Multiple", "size"),
                                            Best_Expectancy=("Expectancy (R)", "max"),
                                            Avg_Expectancy=("Expectancy (R)", "mean"),
                                            Best_Total_R=("Total R", "max")
                                        )
                                        .reset_index()
                                        .sort_values(
                                            by=["Best_Expectancy", "Avg_Expectancy", "Occurrences"],
                                            ascending=[False, False, False]
                                        )
                                        .reset_index(drop=True)
                                    )

                                    impulse_family_pullback_bars_df = (
                                        optimization_results.groupby("Pullback Max Bars", dropna=False)
                                        .agg(
                                            Occurrences=("Pullback Max Bars", "size"),
                                            Best_Expectancy=("Expectancy (R)", "max"),
                                            Avg_Expectancy=("Expectancy (R)", "mean"),
                                            Best_Total_R=("Total R", "max")
                                        )
                                        .reset_index()
                                        .sort_values(
                                            by=["Best_Expectancy", "Avg_Expectancy", "Occurrences"],
                                            ascending=[False, False, False]
                                        )
                                        .reset_index(drop=True)
                                    )

                                    impulse_family_pullback_depth_df = (
                                        optimization_results.groupby("Pullback Max Depth ATR", dropna=False)
                                        .agg(
                                            Occurrences=("Pullback Max Depth ATR", "size"),
                                            Best_Expectancy=("Expectancy (R)", "max"),
                                            Avg_Expectancy=("Expectancy (R)", "mean"),
                                            Best_Total_R=("Total R", "max")
                                        )
                                        .reset_index()
                                        .sort_values(
                                            by=["Best_Expectancy", "Avg_Expectancy", "Occurrences"],
                                            ascending=[False, False, False]
                                        )
                                        .reset_index(drop=True)
                                    )

                                    st.subheader("Familles de paramètres Impulse")
                                    st.caption(
                                        "Ces tableaux aident à voir quelles familles de paramètres ressortent dans l'optimisation Impulse, "
                                        "au-delà du seul meilleur set. "
                                        "Lecture actuelle calculée sur le Top 30 de l'optimisation."
                                    )

                                    impulse_family_col1, impulse_family_col2, impulse_family_col3 = st.columns(3)

                                    with impulse_family_col1:
                                        st.markdown("**Trend Lookback**")
                                        st.dataframe(impulse_family_trend_df, use_container_width=True)

                                    with impulse_family_col2:
                                        st.markdown("**RR Target**")
                                        st.dataframe(impulse_family_rr_df, use_container_width=True)

                                    with impulse_family_col3:
                                        st.markdown("**Confirmation Bars**")
                                        st.dataframe(impulse_family_confirmation_df, use_container_width=True)

                                    impulse_best_trend_family = impulse_family_trend_df.iloc[0]
                                    impulse_best_rr_family = impulse_family_rr_df.iloc[0]
                                    impulse_best_confirmation_family = impulse_family_confirmation_df.iloc[0]

                                    impulse_stablest_trend_family = impulse_family_trend_df.sort_values(
                                        by=["Avg_Expectancy", "Occurrences", "Best_Expectancy"],
                                        ascending=[False, False, False]
                                    ).reset_index(drop=True).iloc[0]

                                    impulse_stablest_rr_family = impulse_family_rr_df.sort_values(
                                        by=["Avg_Expectancy", "Occurrences", "Best_Expectancy"],
                                        ascending=[False, False, False]
                                    ).reset_index(drop=True).iloc[0]

                                    impulse_stablest_confirmation_family = impulse_family_confirmation_df.sort_values(
                                        by=["Avg_Expectancy", "Occurrences", "Best_Expectancy"],
                                        ascending=[False, False, False]
                                    ).reset_index(drop=True).iloc[0]

                                    st.subheader("Familles moteur Impulse")

                                    impulse_engine_family_col1, impulse_engine_family_col2, impulse_engine_family_col3 = st.columns(3)

                                    with impulse_engine_family_col1:
                                        st.markdown("**Min Trend ATR Multiple**")
                                        st.dataframe(impulse_family_min_trend_multiple_df, use_container_width=True)

                                    with impulse_engine_family_col2:
                                        st.markdown("**Pullback Max Bars**")
                                        st.dataframe(impulse_family_pullback_bars_df, use_container_width=True)

                                    with impulse_engine_family_col3:
                                        st.markdown("**Pullback Max Depth ATR**")
                                        st.dataframe(impulse_family_pullback_depth_df, use_container_width=True)

                                    impulse_best_min_trend_multiple_family = impulse_family_min_trend_multiple_df.iloc[0]
                                    impulse_best_pullback_bars_family = impulse_family_pullback_bars_df.iloc[0]
                                    impulse_best_pullback_depth_family = impulse_family_pullback_depth_df.iloc[0]

                                    impulse_stablest_min_trend_multiple_family = impulse_family_min_trend_multiple_df.sort_values(
                                        by=["Avg_Expectancy", "Occurrences", "Best_Expectancy"],
                                        ascending=[False, False, False]
                                    ).reset_index(drop=True).iloc[0]

                                    impulse_stablest_pullback_bars_family = impulse_family_pullback_bars_df.sort_values(
                                        by=["Avg_Expectancy", "Occurrences", "Best_Expectancy"],
                                        ascending=[False, False, False]
                                    ).reset_index(drop=True).iloc[0]

                                    impulse_stablest_pullback_depth_family = impulse_family_pullback_depth_df.sort_values(
                                        by=["Avg_Expectancy", "Occurrences", "Best_Expectancy"],
                                        ascending=[False, False, False]
                                    ).reset_index(drop=True).iloc[0]

                                    st.subheader("Synthèse finale des familles Impulse")

                                    impulse_families_summary_df = pd.DataFrame([
                                        {
                                            "Base familles": "Top 30",
                                            "Trend Lookback dominant": impulse_best_trend_family["Trend Lookback"],
                                            "Trend Lookback stable": impulse_stablest_trend_family["Trend Lookback"],
                                            "RR dominant": impulse_best_rr_family["RR Target"],
                                            "RR stable": impulse_stablest_rr_family["RR Target"],
                                            "Confirmation dominante": impulse_best_confirmation_family["Confirmation Bars"],
                                            "Confirmation stable": impulse_stablest_confirmation_family["Confirmation Bars"],
                                            "Min Trend ATR Multiple dominant": impulse_best_min_trend_multiple_family["Min Trend ATR Multiple"],
                                            "Min Trend ATR Multiple stable": impulse_stablest_min_trend_multiple_family["Min Trend ATR Multiple"],
                                            "Pullback Max Bars dominant": impulse_best_pullback_bars_family["Pullback Max Bars"],
                                            "Pullback Max Bars stable": impulse_stablest_pullback_bars_family["Pullback Max Bars"],
                                            "Pullback Max Depth ATR dominant": impulse_best_pullback_depth_family["Pullback Max Depth ATR"],
                                            "Pullback Max Depth ATR stable": impulse_stablest_pullback_depth_family["Pullback Max Depth ATR"]
                                        }
                                    ])

                                    st.dataframe(impulse_families_summary_df, use_container_width=True)

                                    impulse_trend_multiple_value = float(impulse_best_min_trend_multiple_family["Min Trend ATR Multiple"])
                                    impulse_pullback_bars_value = int(impulse_best_pullback_bars_family["Pullback Max Bars"])
                                    impulse_pullback_depth_value = float(impulse_best_pullback_depth_family["Pullback Max Depth ATR"])
                                    impulse_confirmation_value = int(impulse_best_confirmation_family["Confirmation Bars"])

                                    impulse_alignment_rows = [
                                        {
                                            "Famille": "Trend Lookback",
                                            "Dominant": impulse_best_trend_family["Trend Lookback"],
                                            "Stable": impulse_stablest_trend_family["Trend Lookback"],
                                            "Alignement": "Oui" if impulse_best_trend_family["Trend Lookback"] == impulse_stablest_trend_family["Trend Lookback"] else "Non"
                                        },
                                        {
                                            "Famille": "RR",
                                            "Dominant": impulse_best_rr_family["RR Target"],
                                            "Stable": impulse_stablest_rr_family["RR Target"],
                                            "Alignement": "Oui" if impulse_best_rr_family["RR Target"] == impulse_stablest_rr_family["RR Target"] else "Non"
                                        },
                                        {
                                            "Famille": "Confirmation",
                                            "Dominant": impulse_best_confirmation_family["Confirmation Bars"],
                                            "Stable": impulse_stablest_confirmation_family["Confirmation Bars"],
                                            "Alignement": "Oui" if impulse_best_confirmation_family["Confirmation Bars"] == impulse_stablest_confirmation_family["Confirmation Bars"] else "Non"
                                        },
                                        {
                                            "Famille": "Min Trend ATR Multiple",
                                            "Dominant": impulse_best_min_trend_multiple_family["Min Trend ATR Multiple"],
                                            "Stable": impulse_stablest_min_trend_multiple_family["Min Trend ATR Multiple"],
                                            "Alignement": "Oui" if impulse_best_min_trend_multiple_family["Min Trend ATR Multiple"] == impulse_stablest_min_trend_multiple_family["Min Trend ATR Multiple"] else "Non"
                                        },
                                        {
                                            "Famille": "Pullback Max Bars",
                                            "Dominant": impulse_best_pullback_bars_family["Pullback Max Bars"],
                                            "Stable": impulse_stablest_pullback_bars_family["Pullback Max Bars"],
                                            "Alignement": "Oui" if impulse_best_pullback_bars_family["Pullback Max Bars"] == impulse_stablest_pullback_bars_family["Pullback Max Bars"] else "Non"
                                        },
                                        {
                                            "Famille": "Pullback Max Depth ATR",
                                            "Dominant": impulse_best_pullback_depth_family["Pullback Max Depth ATR"],
                                            "Stable": impulse_stablest_pullback_depth_family["Pullback Max Depth ATR"],
                                            "Alignement": "Oui" if impulse_best_pullback_depth_family["Pullback Max Depth ATR"] == impulse_stablest_pullback_depth_family["Pullback Max Depth ATR"] else "Non"
                                        }
                                    ]

                                    impulse_alignment_df = pd.DataFrame(impulse_alignment_rows)
                                    impulse_alignment_count = int((impulse_alignment_df["Alignement"] == "Oui").sum())

                                    if impulse_trend_multiple_value >= 2.5:
                                        impulse_trend_read = "impulsions plutôt strictes"
                                    elif impulse_trend_multiple_value <= 1.5:
                                        impulse_trend_read = "impulsions plutôt souples"
                                    else:
                                        impulse_trend_read = "impulsions intermédiaires"

                                    if impulse_pullback_bars_value <= 3:
                                        impulse_pullback_bars_read = "pullbacks courts"
                                    elif impulse_pullback_bars_value >= 7:
                                        impulse_pullback_bars_read = "pullbacks assez longs"
                                    else:
                                        impulse_pullback_bars_read = "pullbacks intermédiaires"

                                    if impulse_pullback_depth_value <= 0.8:
                                        impulse_pullback_depth_read = "retracements peu profonds"
                                    elif impulse_pullback_depth_value >= 1.3:
                                        impulse_pullback_depth_read = "retracements assez profonds"
                                    else:
                                        impulse_pullback_depth_read = "retracements intermédiaires"

                                    if impulse_confirmation_value == 1:
                                        impulse_confirmation_read = "reprise rapide"
                                    else:
                                        impulse_confirmation_read = "confirmation plus patiente"

                                    st.dataframe(impulse_alignment_df, use_container_width=True)

                                    if impulse_alignment_count >= 5:
                                        st.success(
                                            f"Lecture alignement Impulse : {impulse_alignment_count}/6 familles ont un alignement "
                                            f"dominant = stable. On tient probablement une vraie piste moteur, pas seulement un pic isolé."
                                        )
                                    elif impulse_alignment_count >= 3:
                                        st.info(
                                            f"Lecture alignement Impulse : {impulse_alignment_count}/6 familles sont alignées. "
                                            f"Il y a déjà une structure exploitable, mais encore partielle."
                                        )
                                    else:
                                        st.warning(
                                            f"Lecture alignement Impulse : seulement {impulse_alignment_count}/6 familles sont alignées. "
                                            f"Le moteur semble encore dispersé ou bruité."
                                        )
                                    impulse_priority_rows = []

                                    for _, alignment_row in impulse_alignment_df.iterrows():
                                        if alignment_row["Alignement"] == "Oui":
                                            action_label = "Plutôt conserver"
                                        else:
                                            action_label = "À retravailler en priorité"

                                        impulse_priority_rows.append({
                                            "Famille": alignment_row["Famille"],
                                            "Dominant": alignment_row["Dominant"],
                                            "Stable": alignment_row["Stable"],
                                            "Action": action_label
                                        })

                                    impulse_structured_summary_df = pd.DataFrame([
                                        {
                                            "Statut global": impulse_global_status,
                                            "Dernier statut": impulse_global_status,
                                            "Score global du run": impulse_global_score,
                                            "Score global Impulse": impulse_global_score,
                                            "Score moyen": impulse_global_score,
                                            "Meilleur score": impulse_global_score,
                                            "Run survivant": "Oui" if impulse_run_survivor else "Non",
                                            "Robustesse multi-splits": impulse_multi_split_status,
                                            "Splits survécus": impulse_multi_split_ratio,
                                            "Dominance": "Impulse",
                                            "Preset optimisation": impulse_optimization_preset,
                                            "Combinaisons estimées": estimated_total_combinations,
                                            "Base familles": "Top 30",
                                            "Familles alignées": impulse_alignment_count,
                                            "Trend Lookback dominant": impulse_best_trend_family["Trend Lookback"],
                                            "Trend Lookback stable": impulse_stablest_trend_family["Trend Lookback"],
                                            "RR dominant": impulse_best_rr_family["RR Target"],
                                            "RR stable": impulse_stablest_rr_family["RR Target"],
                                            "Confirmation dominante": impulse_best_confirmation_family["Confirmation Bars"],
                                            "Confirmation stable": impulse_stablest_confirmation_family["Confirmation Bars"],
                                            "Min Trend ATR Multiple dominant": impulse_best_min_trend_multiple_family["Min Trend ATR Multiple"],
                                            "Min Trend ATR Multiple stable": impulse_stablest_min_trend_multiple_family["Min Trend ATR Multiple"],
                                            "Pullback Max Bars dominant": impulse_best_pullback_bars_family["Pullback Max Bars"],
                                            "Pullback Max Bars stable": impulse_stablest_pullback_bars_family["Pullback Max Bars"],
                                            "Pullback Max Depth ATR dominant": impulse_best_pullback_depth_family["Pullback Max Depth ATR"],
                                            "Pullback Max Depth ATR stable": impulse_stablest_pullback_depth_family["Pullback Max Depth ATR"],
                                            "Signature run": impulse_run_signature,
                                            "Signature courte": impulse_run_signature,
                                            "Mode sélection référence": impulse_reference_selection_mode,
                                            "Rang IS de référence": impulse_reference_is_rank,
                                            "Familles à conserver": impulse_keep_list,
                                            "Familles à retravailler": impulse_rework_list,
                                            "Best Session": "Impulse",
                                            "Best Context": "Impulse",
                                            "Exploitable recherche": "Oui" if impulse_run_survivor else "Non",
                                            "Préparation hedge": "Non exploitable à ce stade",
                                            "Lecture structurelle": impulse_global_status,
                                            "Expectancy OOS": impulse_best_oos_metrics["expectancy"],
                                            "Total R OOS": impulse_best_oos_metrics["total_pnl"],
                                            "Max DD OOS": impulse_best_oos_metrics["max_drawdown"]
                                        }
                                    ])


                                    st.info(
                                        f"Lecture synthétique Impulse : le moteur semble pour l'instant préférer "
                                        f"{impulse_trend_read}, "
                                        f"{impulse_pullback_bars_read}, "
                                        f"{impulse_pullback_depth_read} "
                                        f"et une logique de {impulse_confirmation_read}."
                                    )

                                    impulse_history_row = impulse_structured_summary_df.copy()

                                    impulse_history_row.insert(
                                        0,
                                        "Run ID",
                                        f"RUN_{len(st.session_state.run_history) + 1:03d}"
                                    )

                                    impulse_history_row.insert(
                                        1,
                                        "Timestamp",
                                        pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
                                    )

                                    st.session_state.last_impulse_history_row = impulse_history_row.iloc[0].to_dict()

                                    if impulse_global_status == "Robuste":
                                        st.success(
                                            f"Verdict global Impulse : run robuste | "
                                            f"Score global = {impulse_global_score} | "
                                            f"Expectancy OOS = {impulse_best_oos_metrics['expectancy']} | "
                                            f"Splits survécus = {impulse_multi_split_ratio}."
                                        )
                                    elif impulse_global_status == "Encourageant mais prudent":
                                        st.info(
                                            f"Verdict global Impulse : run encourageant mais encore prudent | "
                                            f"Score global = {impulse_global_score} | "
                                            f"Expectancy OOS = {impulse_best_oos_metrics['expectancy']} | "
                                            f"Splits survécus = {impulse_multi_split_ratio}."
                                        )
                                    elif impulse_global_status == "Survivant fragile":
                                        st.warning(
                                            f"Verdict global Impulse : run survivant mais fragile | "
                                            f"Score global = {impulse_global_score} | "
                                            f"Expectancy OOS = {impulse_best_oos_metrics['expectancy']} | "
                                            f"Splits survécus = {impulse_multi_split_ratio}."
                                        )
                                    elif impulse_global_status == "OOS trop faible":
                                        st.warning(
                                            f"Verdict global Impulse : lecture encore trop faible | "
                                            f"Score global = {impulse_global_score} | "
                                            f"Trades OOS = {impulse_best_oos_metrics['number_of_trades']}."
                                        )
                                    else:
                                        st.warning(
                                            f"Verdict global Impulse : test faible / non validé à ce stade | "
                                            f"Score global = {impulse_global_score} | "
                                            f"Expectancy OOS = {impulse_best_oos_metrics['expectancy']} | "
                                            f"Splits survécus = {impulse_multi_split_ratio}."
                                        )

                    if "last_impulse_history_row" in st.session_state:
                        st.subheader("Historique Impulse")
                        if st.button("Ajouter ce run Impulse à l'historique", key="add_impulse_run_history_button"):
                            st.session_state.run_history.append(st.session_state.last_impulse_history_row)

                            run_history_save_df = pd.DataFrame(st.session_state.run_history)
                            run_history_save_df.to_csv(RUN_HISTORY_FILE, index=False)

                            st.success("Run Impulse ajouté à l'historique et sauvegardé dans le CSV.")
                    st.success("Signal, mini backtest, métriques et equity curve calculés avec succès.")

                    st.subheader("Aperçu des données")
                    st.dataframe(df.tail(15))

                    st.subheader("Graphique du prix avec entrées / sorties")

                    fig_price = go.Figure()

                    fig_price.add_trace(go.Scatter(
                        x=df["Date"],
                        y=df["Close"],
                        mode="lines",
                        name="Close"
                    ))

                    if not trades_df.empty:
                        fig_price.add_trace(go.Scatter(
                            x=trades_df["Entry Date"],
                            y=trades_df["Entry Price"],
                            mode="markers",
                            name="Entrée",
                            marker=dict(symbol="triangle-up", size=10)
                        ))

                        fig_price.add_trace(go.Scatter(
                            x=trades_df["Exit Date"],
                            y=trades_df["Exit Price"],
                            mode="markers",
                            name="Sortie",
                            marker=dict(symbol="triangle-down", size=10)
                        ))

                    fig_price.update_layout(
                        title="Prix et entrées / sorties réelles du backtest",
                        xaxis_title="Date",
                        yaxis_title="Prix"
                    )

                    st.plotly_chart(fig_price, use_container_width=True)

                    st.subheader("Trades simulés")
                    if trades_df.empty:
                        st.warning("Aucun trade complet pour le moment. Il y a peut-être une entrée, mais pas encore de sortie.")
                    else:
                        st.dataframe(trades_df)

                    st.subheader("Résumé In-Sample / Out-of-Sample")

                    col_a, col_b, col_c = st.columns(3)

                    with col_a:
                        st.markdown("**Total**")
                        st.metric("Trades", metrics["number_of_trades"])
                        st.metric("Total R", metrics["total_pnl"])
                        st.metric("Expectancy", metrics["expectancy"])

                    with col_b:
                        st.markdown("**In-Sample**")
                        st.metric("Trades IS", metrics_insample["number_of_trades"])
                        st.metric("Total R IS", metrics_insample["total_pnl"])
                        st.metric("Expectancy IS", metrics_insample["expectancy"])

                    with col_c:
                        st.markdown("**Out-of-Sample**")
                        st.metric("Trades OOS", metrics_outsample["number_of_trades"])
                        st.metric("Total R OOS", metrics_outsample["total_pnl"])
                        st.metric("Expectancy OOS", metrics_outsample["expectancy"])
                    if is_sma_strategy:
                        st.subheader("Comparaison filtre de tendance OFF vs ON")
                        st.dataframe(comparison_trend_df, use_container_width=True)
                        st.caption(f"Le détail affiché plus haut correspond actuellement au filtre de tendance {'ON' if trend_filter_enabled else 'OFF'}.")

                        st.subheader("Comparaison filtre de volatilité OFF vs ON")
                        st.dataframe(comparison_volatility_df, use_container_width=True)
                        st.caption(f"Le détail affiché plus haut correspond actuellement au filtre de volatilité {'ON' if volatility_filter_enabled else 'OFF'}.")

                        st.subheader("Comparaison filtre de régime OFF vs ON")
                        st.dataframe(comparison_regime_df, use_container_width=True)
                        st.caption(f"Le détail affiché plus haut correspond actuellement au filtre de régime {'ON' if regime_filter_enabled else 'OFF'}.")

                        st.subheader("Comparaison filtre horaire OFF vs ON")
                        st.dataframe(comparison_session_df, use_container_width=True)
                        st.caption(
                            f"Le détail affiché plus haut correspond actuellement au filtre horaire "
                            f"{'ON' if session_filter_enabled else 'OFF'} | "
                            f"Session choisie : {session_start_hour}h - {session_end_hour}h."
                        )

                        st.subheader("Synthèse des filtres de contexte")
                        st.dataframe(context_filters_summary_df, use_container_width=True)
                        st.caption(
                            "Ce tableau compare, pour chaque filtre de contexte déjà codé, "
                            "l'effet OFF vs ON sur l'In-Sample, l'Out-of-Sample et le drawdown OOS."
                        )

                        if context_filters_summary_df.empty:
                            st.info("Aucune lecture de filtre de contexte disponible pour le moment.")
                        else:
                            best_context_row = context_filters_summary_df.iloc[0]

                            best_filter_name = best_context_row["Filtre"]
                            best_delta_oos_expectancy = best_context_row["Delta Expectancy OOS"]
                            best_delta_dd_oos_abs = best_context_row["Delta DD OOS (abs)"]
                            best_context_diagnostic = best_context_row["Diagnostic"]

                            if best_delta_oos_expectancy > 0 and best_delta_dd_oos_abs <= 0:
                                st.success(
                                    f"Lecture automatique : le filtre de contexte le plus favorable en OOS semble être "
                                    f"**{best_filter_name}** | "
                                    f"Delta Expectancy OOS = {best_delta_oos_expectancy} | "
                                    f"Delta DD OOS (abs) = {best_delta_dd_oos_abs} | "
                                    f"Diagnostic = {best_context_diagnostic}."
                                )
                            elif best_delta_oos_expectancy > 0 and best_delta_dd_oos_abs > 0:
                                st.info(
                                    f"Lecture automatique : le filtre de contexte le plus favorable en OOS semble être "
                                    f"**{best_filter_name}**, mais avec une hausse du risque | "
                                    f"Delta Expectancy OOS = {best_delta_oos_expectancy} | "
                                    f"Delta DD OOS (abs) = {best_delta_dd_oos_abs} | "
                                    f"Diagnostic = {best_context_diagnostic}."
                                )
                            elif best_delta_oos_expectancy == 0:
                                st.info(
                                    f"Lecture automatique : aucun filtre ne se détache clairement en OOS. "
                                    f"Le meilleur au classement actuel est **{best_filter_name}**, mais l'impact OOS reste neutre | "
                                    f"Delta Expectancy OOS = {best_delta_oos_expectancy} | "
                                    f"Delta DD OOS (abs) = {best_delta_dd_oos_abs} | "
                                    f"Diagnostic = {best_context_diagnostic}."
                                )
                            else:
                                st.warning(
                                    f"Lecture automatique : aucun filtre de contexte ne semble améliorer clairement l'OOS sur ce test. "
                                    f"Le moins dégradé au classement actuel est **{best_filter_name}** | "
                                    f"Delta Expectancy OOS = {best_delta_oos_expectancy} | "
                                    f"Delta DD OOS (abs) = {best_delta_dd_oos_abs} | "
                                    f"Diagnostic = {best_context_diagnostic}."
                                )

                        st.subheader("Lecture conjointe : sessions + filtres de contexte")

                        if session_oos_robustness_df.empty or context_filters_summary_df.empty:
                            st.info("Lecture conjointe indisponible pour le moment.")
                        else:
                            combined_best_session_row = session_oos_robustness_df.iloc[0]
                            combined_best_context_row = context_filters_summary_df.iloc[0]

                            combined_session_name = combined_best_session_row["Session"]
                            combined_session_diag = combined_best_session_row["Diagnostic robustesse"]
                            combined_session_expectancy_oos = combined_best_session_row["Expectancy OOS"]
                            combined_session_delta_expectancy = combined_best_session_row["Delta Expectancy"]
                            combined_session_score = combined_best_session_row["Score robustesse"]

                            combined_context_name = combined_best_context_row["Filtre"]
                            combined_context_diag = combined_best_context_row["Diagnostic"]
                            combined_context_delta_oos_expectancy = combined_best_context_row["Delta Expectancy OOS"]
                            combined_context_delta_dd = combined_best_context_row["Delta DD OOS (abs)"]
                            combined_context_score = combined_best_context_row["Score contexte"]

                            score_gap = round(combined_session_score - combined_context_score, 2)

                            session_is_strong = combined_session_diag in ["Robuste", "Dégradée mais positive"]
                            context_is_strong = combined_context_delta_oos_expectancy > 0

                            if session_is_strong and context_is_strong:
                                if abs(score_gap) <= 15:
                                    st.success(
                                        f"Lecture conjointe : la robustesse observée semble venir à la fois "
                                        f"des **sessions** et du **contexte**, avec un équilibre assez net entre les deux. "
                                        f"Session dominante actuelle : **{combined_session_name}** "
                                        f"(Score robustesse = {combined_session_score}, Diagnostic = {combined_session_diag}, "
                                        f"Expectancy OOS = {combined_session_expectancy_oos}, Delta Expectancy = {combined_session_delta_expectancy}) | "
                                        f"Filtre de contexte dominant : **{combined_context_name}** "
                                        f"(Score contexte = {combined_context_score}, Diagnostic = {combined_context_diag}, "
                                        f"Delta Expectancy OOS = {combined_context_delta_oos_expectancy}, Delta DD OOS (abs) = {combined_context_delta_dd})."
                                    )
                                elif score_gap > 15:
                                    st.success(
                                        f"Lecture conjointe : les **sessions** semblent actuellement dominer la robustesse observée, "
                                        f"même si le **contexte** reste aussi contributif. "
                                        f"Session dominante : **{combined_session_name}** "
                                        f"(Score robustesse = {combined_session_score}, Diagnostic = {combined_session_diag}, "
                                        f"Expectancy OOS = {combined_session_expectancy_oos}, Delta Expectancy = {combined_session_delta_expectancy}) | "
                                        f"Meilleur filtre de contexte : **{combined_context_name}** "
                                        f"(Score contexte = {combined_context_score}, Diagnostic = {combined_context_diag}, "
                                        f"Delta Expectancy OOS = {combined_context_delta_oos_expectancy}, Delta DD OOS (abs) = {combined_context_delta_dd})."
                                    )
                                else:
                                    st.success(
                                        f"Lecture conjointe : le **contexte** semble actuellement dominer la robustesse observée, "
                                        f"même si les **sessions** restent aussi contributives. "
                                        f"Filtre de contexte dominant : **{combined_context_name}** "
                                        f"(Score contexte = {combined_context_score}, Diagnostic = {combined_context_diag}, "
                                        f"Delta Expectancy OOS = {combined_context_delta_oos_expectancy}, Delta DD OOS (abs) = {combined_context_delta_dd}) | "
                                        f"Meilleure session : **{combined_session_name}** "
                                        f"(Score robustesse = {combined_session_score}, Diagnostic = {combined_session_diag}, "
                                        f"Expectancy OOS = {combined_session_expectancy_oos}, Delta Expectancy = {combined_session_delta_expectancy})."
                                    )
                            elif session_is_strong and not context_is_strong:
                                st.info(
                                    f"Lecture conjointe : sur ce test, la robustesse semble venir plutôt des **sessions** "
                                    f"que des autres filtres de contexte. "
                                    f"Session dominante : **{combined_session_name}** "
                                    f"(Score robustesse = {combined_session_score}, Diagnostic = {combined_session_diag}, "
                                    f"Expectancy OOS = {combined_session_expectancy_oos}, Delta Expectancy = {combined_session_delta_expectancy}) | "
                                    f"Filtre de contexte le moins mauvais : **{combined_context_name}** "
                                    f"(Score contexte = {combined_context_score}, Diagnostic = {combined_context_diag}, "
                                    f"Delta Expectancy OOS = {combined_context_delta_oos_expectancy})."
                                )
                            elif not session_is_strong and context_is_strong:
                                st.info(
                                    f"Lecture conjointe : sur ce test, la robustesse semble venir plutôt du **contexte** "
                                    f"que des sessions. "
                                    f"Filtre de contexte dominant : **{combined_context_name}** "
                                    f"(Score contexte = {combined_context_score}, Diagnostic = {combined_context_diag}, "
                                    f"Delta Expectancy OOS = {combined_context_delta_oos_expectancy}, Delta DD OOS (abs) = {combined_context_delta_dd}) | "
                                    f"Session la moins fragile : **{combined_session_name}** "
                                    f"(Score robustesse = {combined_session_score}, Diagnostic = {combined_session_diag}, "
                                    f"Expectancy OOS = {combined_session_expectancy_oos}, Delta Expectancy = {combined_session_delta_expectancy})."
                                )
                            else:
                                st.warning(
                                    f"Lecture conjointe : sur ce test, ni les **sessions** ni les **filtres de contexte** "
                                    f"ne semblent apporter de validation OOS vraiment claire. "
                                    f"Session la moins mauvaise : **{combined_session_name}** "
                                    f"(Score robustesse = {combined_session_score}, Diagnostic = {combined_session_diag}, "
                                    f"Expectancy OOS = {combined_session_expectancy_oos}, Delta Expectancy = {combined_session_delta_expectancy}) | "
                                    f"Filtre de contexte le moins mauvais : **{combined_context_name}** "
                                    f"(Score contexte = {combined_context_score}, Diagnostic = {combined_context_diag}, "
                                    f"Delta Expectancy OOS = {combined_context_delta_oos_expectancy}, Delta DD OOS (abs) = {combined_context_delta_dd})."
                                )
                    elif is_impulse_strategy:
                        show_impulse_filter_mask_message()


                    if is_sma_strategy:
                        st.caption(
                            f"Optimisation lancée avec : tendance={'ON' if trend_filter_enabled else 'OFF'} | "
                            f"volatilité={'ON' if volatility_filter_enabled else 'OFF'} | "
                            f"min trades={optimizer_min_trades}"
                        )
                    else:
                        st.caption(
                            "Optimisation Impulse V1 terminée ou en cours d'exploration."
                        )

                    if False:
                        st.write("DEBUG optimization_display_df shape:", optimization_display_df.shape)
                        st.write("DEBUG colonnes affichées:", available_display_columns)
                        st.caption(
                            "L'expectancy reste la métrique centrale du classement. "
                            "Le score robustesse IS sert de garde-fou complémentaire pour éviter de survaloriser des sets IS fragiles."
                        )

                        top_optimization_results = optimization_results.head(10).copy()

                        top_n_is_to_validate = min(5, len(optimization_results))
                        top_n_is_rows = optimization_results.head(top_n_is_to_validate).copy()

                        top_n_oos_validation_rows = []

                        for is_rank, top_n_row in top_n_is_rows.reset_index(drop=True).iterrows():
                            candidate_short_window = int(top_n_row["Short Window"])
                            candidate_long_window = int(top_n_row["Long Window"])
                            candidate_rr_target = float(top_n_row["RR Target"])

                            candidate_trend_filter_window = trend_filter_window
                            candidate_atr_window = atr_window
                            candidate_min_atr_pct = min_atr_pct
                            candidate_adx_window = adx_window
                            candidate_min_adx = min_adx

                            if "Trend Filter Window" in top_n_row.index and pd.notna(top_n_row["Trend Filter Window"]):
                                candidate_trend_filter_window = int(top_n_row["Trend Filter Window"])

                            if "ATR Window" in top_n_row.index and pd.notna(top_n_row["ATR Window"]):
                                candidate_atr_window = int(top_n_row["ATR Window"])

                            if "Min ATR %" in top_n_row.index and pd.notna(top_n_row["Min ATR %"]):
                                candidate_min_atr_pct = float(top_n_row["Min ATR %"])

                            if "ADX Window" in top_n_row.index and pd.notna(top_n_row["ADX Window"]):
                                candidate_adx_window = int(top_n_row["ADX Window"])

                            if "Min ADX" in top_n_row.index and pd.notna(top_n_row["Min ADX"]):
                                candidate_min_adx = float(top_n_row["Min ADX"])

                            candidate_session_name = "Aucune"
                            candidate_session_filter_enabled = False
                            candidate_session_start_hour = 8
                            candidate_session_end_hour = 17

                            if "Session Name" in top_n_row.index and pd.notna(top_n_row["Session Name"]):
                                candidate_session_name = str(top_n_row["Session Name"])

                                if candidate_session_name == "Aucune":
                                    candidate_session_filter_enabled = False
                                    candidate_session_start_hour = 8
                                    candidate_session_end_hour = 17
                                else:
                                    candidate_session_filter_enabled = True
                                    candidate_session_start_hour = int(top_n_row["Session Start"])
                                    candidate_session_end_hour = int(top_n_row["Session End"])

                            candidate_oos_price_df = df_outsample[["Date", "Open", "High", "Low", "Close"]].copy()

                            if strategy_name == "SMA":
                                candidate_oos_df = calculate_sma_strategy(
                                    candidate_oos_price_df,
                                    candidate_short_window,
                                    candidate_long_window,
                                    trend_filter_enabled=trend_filter_enabled,
                                    trend_filter_window=candidate_trend_filter_window,
                                    volatility_filter_enabled=volatility_filter_enabled,
                                    atr_window=candidate_atr_window,
                                    min_atr_pct=candidate_min_atr_pct,
                                    regime_filter_enabled=regime_filter_enabled,
                                    adx_window=candidate_adx_window,
                                    min_adx=candidate_min_adx,
                                    session_filter_enabled=candidate_session_filter_enabled,
                                    session_start_hour=candidate_session_start_hour,
                                    session_end_hour=candidate_session_end_hour,
                                    strategy_mode=strategy_mode
                                )
                            else:
                                candidate_oos_df = calculate_impulse_pullback_break_strategy(
                                    candidate_oos_price_df,
                                    trend_lookback_bars=trend_lookback_bars,
                                    atr_window=candidate_atr_window,
                                    min_trend_atr_multiple=min_trend_atr_multiple,
                                    pullback_max_bars=pullback_max_bars,
                                    pullback_max_depth_atr=pullback_max_depth_atr,
                                    confirmation_bars=confirmation_bars
                                )

                            candidate_oos_trades = run_simple_backtest(
                                candidate_oos_df,
                                rr_target=candidate_rr_target,
                                trade_mode=trade_mode,
                                cost_per_trade_r=cost_per_trade_r,
                                strategy_mode=strategy_mode
                            )

                            candidate_oos_equity = build_equity_curve(candidate_oos_trades, starting_r=starting_r)
                            candidate_oos_metrics = calculate_basic_metrics(candidate_oos_trades, candidate_oos_equity)

                            candidate_is_trades = int(top_n_row["Trades"]) if pd.notna(top_n_row["Trades"]) else 0
                            candidate_is_total_r = float(top_n_row["Total R"]) if pd.notna(top_n_row["Total R"]) else 0.0
                            candidate_is_expectancy = float(top_n_row["Expectancy (R)"]) if pd.notna(top_n_row["Expectancy (R)"]) else 0.0
                            candidate_is_max_dd = float(top_n_row["Max Drawdown (R)"]) if pd.notna(top_n_row["Max Drawdown (R)"]) else 0.0

                            delta_expectancy = round(candidate_oos_metrics["expectancy"] - candidate_is_expectancy, 2)
                            delta_total_r = round(candidate_oos_metrics["total_pnl"] - candidate_is_total_r, 2)

                            if candidate_oos_metrics["number_of_trades"] < 5:
                                candidate_oos_diagnostic = "OOS trop faible"
                            elif candidate_oos_metrics["expectancy"] > 0 and delta_expectancy >= -0.10:
                                candidate_oos_diagnostic = "Robuste"
                            elif candidate_oos_metrics["expectancy"] > 0 and delta_expectancy >= -0.25:
                                candidate_oos_diagnostic = "Dégradée mais positive"
                            else:
                                candidate_oos_diagnostic = "Fragile / non validée OOS"

                            top_n_oos_validation_rows.append({
                                "Rang IS": is_rank + 1,
                                "Short": candidate_short_window,
                                "Long": candidate_long_window,
                                "RR": candidate_rr_target,
                                "Session": candidate_session_name,
                                "Trades IS": candidate_is_trades,
                                "Expectancy IS": candidate_is_expectancy,
                                "Total R IS": candidate_is_total_r,
                                "Max DD IS": candidate_is_max_dd,
                                "Trades OOS": candidate_oos_metrics["number_of_trades"],
                                "Expectancy OOS": candidate_oos_metrics["expectancy"],
                                "Total R OOS": candidate_oos_metrics["total_pnl"],
                                "Max DD OOS": candidate_oos_metrics["max_drawdown"],
                                "Delta Expectancy": delta_expectancy,
                                "Delta Total R": delta_total_r,
                                "Diagnostic OOS": candidate_oos_diagnostic
                            })

                        top_n_oos_validation_df = pd.DataFrame(top_n_oos_validation_rows)

                        st.subheader(f"Validation OOS du Top {top_n_is_to_validate} IS")
                        st.dataframe(top_n_oos_validation_df, use_container_width=True)
                        st.caption(
                            "Ce tableau reteste en Out-of-Sample les meilleurs sets In-Sample, "
                            "pour vérifier si plusieurs candidats IS tiennent ou si le winner IS est isolé."
                        )

                        if top_n_oos_validation_df.empty:
                            st.info("Aucune validation OOS multi-candidats disponible pour le moment.")
                        else:
                            top_n_survivors_df = top_n_oos_validation_df[
                                top_n_oos_validation_df["Diagnostic OOS"].isin(["Robuste", "Dégradée mais positive"])
                            ].copy()

                            if top_n_survivors_df.empty:
                                top_n_best_oos_row = top_n_oos_validation_df.sort_values(
                                    by=["Expectancy OOS", "Total R OOS", "Trades OOS", "Delta Expectancy"],
                                    ascending=[False, False, False, False]
                                ).reset_index(drop=True).iloc[0]

                                st.warning(
                                    f"Lecture automatique : aucun des {top_n_is_to_validate} meilleurs sets IS "
                                    f"ne semble vraiment validé en OOS sur ce test. "
                                    f"Le moins mauvais actuellement est le rang IS **{top_n_best_oos_row['Rang IS']}** "
                                    f"(Short={top_n_best_oos_row['Short']}, Long={top_n_best_oos_row['Long']}, "
                                    f"RR={top_n_best_oos_row['RR']}, Session={top_n_best_oos_row['Session']}, "
                                    f"Expectancy OOS={top_n_best_oos_row['Expectancy OOS']}, "
                                    f"Total R OOS={top_n_best_oos_row['Total R OOS']}, "
                                    f"Diagnostic={top_n_best_oos_row['Diagnostic OOS']})."
                                )
                            else:
                                top_n_best_survivor_row = top_n_survivors_df.sort_values(
                                    by=["Expectancy OOS", "Total R OOS", "Trades OOS", "Delta Expectancy"],
                                    ascending=[False, False, False, False]
                                ).reset_index(drop=True).iloc[0]

                                if top_n_best_survivor_row["Diagnostic OOS"] == "Robuste":
                                    st.success(
                                        f"Lecture automatique : parmi les {top_n_is_to_validate} meilleurs sets IS, "
                                        f"au moins un candidat tient correctement en OOS. "
                                        f"Le plus convaincant actuellement est le rang IS **{top_n_best_survivor_row['Rang IS']}** "
                                        f"(Short={top_n_best_survivor_row['Short']}, Long={top_n_best_survivor_row['Long']}, "
                                        f"RR={top_n_best_survivor_row['RR']}, Session={top_n_best_survivor_row['Session']}, "
                                        f"Expectancy OOS={top_n_best_survivor_row['Expectancy OOS']}, "
                                        f"Total R OOS={top_n_best_survivor_row['Total R OOS']}, "
                                        f"Diagnostic={top_n_best_survivor_row['Diagnostic OOS']})."
                                    )
                                else:
                                    st.info(
                                        f"Lecture automatique : parmi les {top_n_is_to_validate} meilleurs sets IS, "
                                        f"au moins un candidat reste positif mais dégradé en OOS. "
                                        f"Le meilleur survivant actuel est le rang IS **{top_n_best_survivor_row['Rang IS']}** "
                                        f"(Short={top_n_best_survivor_row['Short']}, Long={top_n_best_survivor_row['Long']}, "
                                        f"RR={top_n_best_survivor_row['RR']}, Session={top_n_best_survivor_row['Session']}, "
                                        f"Expectancy OOS={top_n_best_survivor_row['Expectancy OOS']}, "
                                        f"Total R OOS={top_n_best_survivor_row['Total R OOS']}, "
                                        f"Diagnostic={top_n_best_survivor_row['Diagnostic OOS']})."
                                    )

                        reference_is_rank = 1
                        reference_selection_mode = "winner_is"

                        if not top_n_oos_validation_df.empty:
                            reference_survivors_df = top_n_oos_validation_df[
                                top_n_oos_validation_df["Diagnostic OOS"].isin(["Robuste", "Dégradée mais positive"])
                            ].copy()

                            if not reference_survivors_df.empty:
                                reference_candidate_row = reference_survivors_df.sort_values(
                                    by=["Expectancy OOS", "Total R OOS", "Trades OOS", "Delta Expectancy"],
                                    ascending=[False, False, False, False]
                                ).reset_index(drop=True).iloc[0]

                                reference_is_rank = int(reference_candidate_row["Rang IS"])
                                reference_selection_mode = "best_oos_survivor"

                        st.subheader("Candidat de référence du run")

                        if reference_selection_mode == "best_oos_survivor":
                            st.success(
                                f"Le candidat de référence pour la suite du run est le rang IS **{reference_is_rank}**, "
                                f"car c'est actuellement le meilleur survivant OOS parmi le Top {top_n_is_to_validate} IS."
                            )
                        else:
                            st.info(
                                "Aucun survivant OOS convaincant n'a été trouvé dans le Top IS. "
                                "Le candidat de référence reste donc le winner IS (rang 1)."
                            )

                        session_optimization_summary_df = (
                            top_optimization_results.groupby("Session Name", dropna=False)
                            .agg(
                                occurrences_top_10=("Session Name", "size"),
                                session_start=("Session Start", "first"),
                                session_end=("Session End", "first"),
                                best_expectancy=("Expectancy (R)", "max"),
                                best_total_r=("Total R", "max"),
                                best_max_drawdown=("Max Drawdown (R)", "max")
                            )
                            .reset_index()
                        )

                        session_optimization_summary_df["session_start"] = session_optimization_summary_df["session_start"].apply(
                            lambda x: "-" if pd.isna(x) else str(int(x))
                        )
                        session_optimization_summary_df["session_end"] = session_optimization_summary_df["session_end"].apply(
                            lambda x: "-" if pd.isna(x) else str(int(x))
                        )

                        session_optimization_summary_df = session_optimization_summary_df.rename(columns={
                            "Session Name": "Session",
                            "occurrences_top_10": "Occurrences Top 10",
                            "session_start": "Heure début",
                            "session_end": "Heure fin",
                            "best_expectancy": "Meilleure Expectancy",
                            "best_total_r": "Meilleur Total R",
                            "best_max_drawdown": "Meilleur Max Drawdown"
                        })

                        st.subheader("Synthèse des sessions dans le Top 10 optimisé")
                        st.dataframe(session_optimization_summary_df, use_container_width=True)
                        st.caption("Ce tableau résume quelles sessions reviennent le plus souvent dans les 10 meilleurs résultats In-Sample.")

                        session_oos_robustness_rows = []

                        for session_name in top_optimization_results["Session Name"].drop_duplicates():
                            session_top10_rows = top_optimization_results[
                                top_optimization_results["Session Name"] == session_name
                            ].copy()

                            session_top10_rows = session_top10_rows.sort_values(
                                by=["Expectancy (R)", "Total R", "Max Drawdown (R)"],
                                ascending=[False, False, False]
                            ).reset_index(drop=True)

                            session_best_row = session_top10_rows.iloc[0]
                            session_occurrences_top_10 = len(session_top10_rows)

                            session_best_short_window = int(session_best_row["Short Window"])
                            session_best_long_window = int(session_best_row["Long Window"])
                            session_best_rr_target = float(session_best_row["RR Target"])

                            session_best_trend_filter_window = trend_filter_window
                            session_best_atr_window = atr_window
                            session_best_min_atr_pct = min_atr_pct
                            session_best_adx_window = adx_window
                            session_best_min_adx = min_adx

                            if "Trend Filter Window" in session_best_row.index and pd.notna(session_best_row["Trend Filter Window"]):
                                session_best_trend_filter_window = int(session_best_row["Trend Filter Window"])

                            if "ATR Window" in session_best_row.index and pd.notna(session_best_row["ATR Window"]):
                                session_best_atr_window = int(session_best_row["ATR Window"])

                            if "Min ATR %" in session_best_row.index and pd.notna(session_best_row["Min ATR %"]):
                                session_best_min_atr_pct = float(session_best_row["Min ATR %"])

                            if "ADX Window" in session_best_row.index and pd.notna(session_best_row["ADX Window"]):
                                session_best_adx_window = int(session_best_row["ADX Window"])

                            if "Min ADX" in session_best_row.index and pd.notna(session_best_row["Min ADX"]):
                                session_best_min_adx = float(session_best_row["Min ADX"])

                            if session_name == "Aucune":
                                session_best_filter_enabled = False
                                session_best_start_hour = 8
                                session_best_end_hour = 17
                                session_display_start = "-"
                                session_display_end = "-"
                            else:
                                session_best_filter_enabled = True
                                session_best_start_hour = int(session_best_row["Session Start"])
                                session_best_end_hour = int(session_best_row["Session End"])
                                session_display_start = str(session_best_start_hour)
                                session_display_end = str(session_best_end_hour)

                            session_oos_price_df = df_outsample[["Date", "Open", "High", "Low", "Close"]].copy()

                            if strategy_name == "SMA":
                                session_oos_df = calculate_sma_strategy(
                                    session_oos_price_df,
                                    session_best_short_window,
                                    session_best_long_window,
                                    trend_filter_enabled=trend_filter_enabled,
                                    trend_filter_window=session_best_trend_filter_window,
                                    volatility_filter_enabled=volatility_filter_enabled,
                                    atr_window=session_best_atr_window,
                                    min_atr_pct=session_best_min_atr_pct,
                                    regime_filter_enabled=regime_filter_enabled,
                                    adx_window=session_best_adx_window,
                                    min_adx=session_best_min_adx,
                                    session_filter_enabled=session_best_filter_enabled,
                                    session_start_hour=session_best_start_hour,
                                    session_end_hour=session_best_end_hour,
                                    strategy_mode=strategy_mode
                                )
                            else:
                                session_oos_df = calculate_impulse_pullback_break_strategy(
                                    session_oos_price_df,
                                    trend_lookback_bars=trend_lookback_bars,
                                    atr_window=session_best_atr_window,
                                    min_trend_atr_multiple=min_trend_atr_multiple,
                                    pullback_max_bars=pullback_max_bars,
                                    pullback_max_depth_atr=pullback_max_depth_atr,
                                    confirmation_bars=confirmation_bars
                                )

                            session_oos_trades = run_simple_backtest(
                                session_oos_df,
                                rr_target=session_best_rr_target,
                                trade_mode=trade_mode,
                                cost_per_trade_r=cost_per_trade_r,
                                strategy_mode=strategy_mode
                            )

                            session_oos_equity = build_equity_curve(session_oos_trades, starting_r=starting_r)
                            session_oos_metrics = calculate_basic_metrics(session_oos_trades, session_oos_equity)

                            session_best_total_r = float(session_best_row["Total R"]) if pd.notna(session_best_row["Total R"]) else 0.0
                            session_best_expectancy = float(session_best_row["Expectancy (R)"]) if pd.notna(session_best_row["Expectancy (R)"]) else 0.0
                            session_best_max_dd = float(session_best_row["Max Drawdown (R)"]) if pd.notna(session_best_row["Max Drawdown (R)"]) else 0.0

                            session_oos_total_r = session_oos_metrics["total_pnl"]
                            session_oos_expectancy = session_oos_metrics["expectancy"]
                            session_oos_max_dd = session_oos_metrics["max_drawdown"]

                            delta_total_r = round(session_oos_total_r - session_best_total_r, 2)
                            delta_expectancy = round(session_oos_expectancy - session_best_expectancy, 2)
                            delta_dd_abs = round(abs(session_oos_max_dd) - abs(session_best_max_dd), 2)

                            if session_oos_metrics["number_of_trades"] < 5:
                                robustness_diagnostic = "OOS trop faible"
                            elif session_oos_expectancy > 0 and delta_expectancy >= -0.10:
                                robustness_diagnostic = "Robuste"
                            elif session_oos_expectancy > 0 and delta_expectancy >= -0.25:
                                robustness_diagnostic = "Dégradée mais positive"
                            else:
                                robustness_diagnostic = "Fragile / non validée OOS"

                            session_robustness_score = 0.0

                            session_robustness_score += session_oos_expectancy * 100
                            session_robustness_score += delta_expectancy * 50
                            session_robustness_score -= max(delta_dd_abs, 0) * 10
                            session_robustness_score += min(session_oos_metrics["number_of_trades"], 20)

                            if robustness_diagnostic == "Robuste":
                                session_robustness_score += 20
                            elif robustness_diagnostic == "Dégradée mais positive":
                                session_robustness_score += 5
                            elif robustness_diagnostic == "OOS trop faible":
                                session_robustness_score -= 15
                            else:
                                session_robustness_score -= 20

                            session_robustness_score = round(session_robustness_score, 2)

                            session_oos_robustness_rows.append({
                                "Session": session_name,
                                "Short": session_best_short_window,
                                "Long": session_best_long_window,
                                "RR": session_best_rr_target,
                                "Occurrences Top 10": session_occurrences_top_10,
                                "Heure début": session_display_start,
                                "Heure fin": session_display_end,
                                "Score robustesse": session_robustness_score,
                                "Diagnostic robustesse": robustness_diagnostic,
                                "Trades IS (best)": int(session_best_row["Trades"]) if pd.notna(session_best_row["Trades"]) else 0,
                                "Total R IS (best)": session_best_total_r,
                                "Expectancy IS (best)": session_best_expectancy,
                                "Max DD IS (best)": session_best_max_dd,
                                "Trades OOS": session_oos_metrics["number_of_trades"],
                                "Total R OOS": session_oos_total_r,
                                "Expectancy OOS": session_oos_expectancy,
                                "Max DD OOS": session_oos_max_dd,
                                "Delta DD (abs)": delta_dd_abs,
                                "Delta Total R": delta_total_r,
                                "Delta Expectancy": delta_expectancy
                            })

                        session_oos_robustness_df = pd.DataFrame(session_oos_robustness_rows)
                        if not session_oos_robustness_df.empty:
                            session_oos_robustness_df["Heure début"] = session_oos_robustness_df["Heure début"].astype(str)
                            session_oos_robustness_df["Heure fin"] = session_oos_robustness_df["Heure fin"].astype(str)                        
                        if not session_oos_robustness_df.empty:
                            session_oos_robustness_df = session_oos_robustness_df.sort_values(
                                by=["Score robustesse", "Delta Expectancy", "Expectancy OOS", "Delta DD (abs)", "Occurrences Top 10"],
                                ascending=[False, False, False, True, False]
                            ).reset_index(drop=True)

                            session_oos_robustness_df = session_oos_robustness_df[
                                [
                                    "Session",
                                    "Short",
                                    "Long",
                                    "RR",
                                    "Occurrences Top 10",
                                    "Heure début",
                                    "Heure fin",
                                    "Score robustesse",
                                    "Diagnostic robustesse",
                                    "Trades IS (best)",
                                    "Expectancy IS (best)",
                                    "Total R IS (best)",
                                    "Max DD IS (best)",
                                    "Trades OOS",
                                    "Expectancy OOS",
                                    "Total R OOS",
                                    "Max DD OOS",
                                    "Delta Expectancy",
                                    "Delta Total R",
                                    "Delta DD (abs)"
                                ]
                            ]

                        st.subheader("Robustesse OOS par session")
                        st.dataframe(session_oos_robustness_df, use_container_width=True)
                        st.caption(
                            "Ce tableau prend chaque session présente dans le Top 10 In-Sample, "
                            "retient son meilleur set IS, puis le reteste en Out-of-Sample."
                        )

                        if session_oos_robustness_df.empty:
                            st.info("Aucune lecture de robustesse par session disponible pour le moment.")
                        else:
                            best_session_row = session_oos_robustness_df.iloc[0]

                            best_session_name_auto = best_session_row["Session"]
                            best_session_diag_auto = best_session_row["Diagnostic robustesse"]
                            best_session_expectancy_oos_auto = best_session_row["Expectancy OOS"]
                            best_session_delta_expectancy_auto = best_session_row["Delta Expectancy"]
                            best_session_delta_dd_auto = best_session_row["Delta DD (abs)"]
                            best_session_total_r_oos_auto = best_session_row["Total R OOS"]

                            if best_session_diag_auto == "Robuste":
                                st.success(
                                    f"Lecture automatique : la session la plus robuste en OOS semble être "
                                    f"**{best_session_name_auto}** | "
                                    f"Expectancy OOS = {best_session_expectancy_oos_auto} | "
                                    f"Delta Expectancy = {best_session_delta_expectancy_auto} | "
                                    f"Delta DD (abs) = {best_session_delta_dd_auto} | "
                                    f"Total R OOS = {best_session_total_r_oos_auto}."
                                )
                            elif best_session_diag_auto == "Dégradée mais positive":
                                st.info(
                                    f"Lecture automatique : la session qui ressort le mieux en OOS semble être "
                                    f"**{best_session_name_auto}**, mais avec une dégradation par rapport à l'IS | "
                                    f"Expectancy OOS = {best_session_expectancy_oos_auto} | "
                                    f"Delta Expectancy = {best_session_delta_expectancy_auto} | "
                                    f"Delta DD (abs) = {best_session_delta_dd_auto} | "
                                    f"Total R OOS = {best_session_total_r_oos_auto}."
                                )
                            elif best_session_diag_auto == "OOS trop faible":
                                st.warning(
                                    f"Lecture automatique : la session en tête actuellement est **{best_session_name_auto}**, "
                                    f"mais le nombre de trades OOS reste trop faible pour conclure sérieusement | "
                                    f"Expectancy OOS = {best_session_expectancy_oos_auto} | "
                                    f"Delta Expectancy = {best_session_delta_expectancy_auto} | "
                                    f"Delta DD (abs) = {best_session_delta_dd_auto} | "
                                    f"Total R OOS = {best_session_total_r_oos_auto}."
                                )
                            else:
                                st.warning(
                                    f"Lecture automatique : aucune session ne semble vraiment validée en OOS sur ce test. "
                                    f"La moins mauvaise au classement actuel est **{best_session_name_auto}** | "
                                    f"Expectancy OOS = {best_session_expectancy_oos_auto} | "
                                    f"Delta Expectancy = {best_session_delta_expectancy_auto} | "
                                    f"Delta DD (abs) = {best_session_delta_dd_auto} | "
                                    f"Total R OOS = {best_session_total_r_oos_auto}."
                                )
                        st.subheader("Lecture conjointe : sessions + filtres de contexte")

                        if session_oos_robustness_df.empty or context_filters_summary_df.empty:
                            st.info("Lecture conjointe indisponible pour le moment.")
                        else:
                            combined_best_session_row = session_oos_robustness_df.iloc[0]
                            combined_best_context_row = context_filters_summary_df.iloc[0]

                            combined_session_name = combined_best_session_row["Session"]
                            combined_session_diag = combined_best_session_row["Diagnostic robustesse"]
                            combined_session_expectancy_oos = combined_best_session_row["Expectancy OOS"]
                            combined_session_delta_expectancy = combined_best_session_row["Delta Expectancy"]
                            combined_session_score = combined_best_session_row["Score robustesse"]

                            combined_context_name = combined_best_context_row["Filtre"]
                            combined_context_diag = combined_best_context_row["Diagnostic"]
                            combined_context_delta_oos_expectancy = combined_best_context_row["Delta Expectancy OOS"]
                            combined_context_delta_dd = combined_best_context_row["Delta DD OOS (abs)"]
                            combined_context_score = combined_best_context_row["Score contexte"]

                            score_gap = round(combined_session_score - combined_context_score, 2)

                            session_is_strong = combined_session_diag in ["Robuste", "Dégradée mais positive"]
                            context_is_strong = combined_context_delta_oos_expectancy > 0

                            if session_is_strong and context_is_strong:
                                if abs(score_gap) <= 15:
                                    st.success(
                                        f"Lecture conjointe : la robustesse observée semble venir à la fois "
                                        f"des **sessions** et du **contexte**, avec un équilibre assez net entre les deux. "
                                        f"Session dominante actuelle : **{combined_session_name}** "
                                        f"(Score robustesse = {combined_session_score}, Diagnostic = {combined_session_diag}, "
                                        f"Expectancy OOS = {combined_session_expectancy_oos}, Delta Expectancy = {combined_session_delta_expectancy}) | "
                                        f"Filtre de contexte dominant : **{combined_context_name}** "
                                        f"(Score contexte = {combined_context_score}, Diagnostic = {combined_context_diag}, "
                                        f"Delta Expectancy OOS = {combined_context_delta_oos_expectancy}, Delta DD OOS (abs) = {combined_context_delta_dd})."
                                    )
                                elif score_gap > 15:
                                    st.success(
                                        f"Lecture conjointe : les **sessions** semblent actuellement dominer la robustesse observée, "
                                        f"même si le **contexte** reste aussi contributif. "
                                        f"Session dominante : **{combined_session_name}** "
                                        f"(Score robustesse = {combined_session_score}, Diagnostic = {combined_session_diag}, "
                                        f"Expectancy OOS = {combined_session_expectancy_oos}, Delta Expectancy = {combined_session_delta_expectancy}) | "
                                        f"Meilleur filtre de contexte : **{combined_context_name}** "
                                        f"(Score contexte = {combined_context_score}, Diagnostic = {combined_context_diag}, "
                                        f"Delta Expectancy OOS = {combined_context_delta_oos_expectancy}, Delta DD OOS (abs) = {combined_context_delta_dd})."
                                    )
                                else:
                                    st.success(
                                        f"Lecture conjointe : le **contexte** semble actuellement dominer la robustesse observée, "
                                        f"même si les **sessions** restent aussi contributives. "
                                        f"Filtre de contexte dominant : **{combined_context_name}** "
                                        f"(Score contexte = {combined_context_score}, Diagnostic = {combined_context_diag}, "
                                        f"Delta Expectancy OOS = {combined_context_delta_oos_expectancy}, Delta DD OOS (abs) = {combined_context_delta_dd}) | "
                                        f"Meilleure session : **{combined_session_name}** "
                                        f"(Score robustesse = {combined_session_score}, Diagnostic = {combined_session_diag}, "
                                        f"Expectancy OOS = {combined_session_expectancy_oos}, Delta Expectancy = {combined_session_delta_expectancy})."
                                    )
                            elif session_is_strong and not context_is_strong:
                                st.info(
                                    f"Lecture conjointe : sur ce test, la robustesse semble venir plutôt des **sessions** "
                                    f"que des autres filtres de contexte. "
                                    f"Session dominante : **{combined_session_name}** "
                                    f"(Score robustesse = {combined_session_score}, Diagnostic = {combined_session_diag}, "
                                    f"Expectancy OOS = {combined_session_expectancy_oos}, Delta Expectancy = {combined_session_delta_expectancy}) | "
                                    f"Filtre de contexte le moins mauvais : **{combined_context_name}** "
                                    f"(Score contexte = {combined_context_score}, Diagnostic = {combined_context_diag}, "
                                    f"Delta Expectancy OOS = {combined_context_delta_oos_expectancy})."
                                )
                            elif not session_is_strong and context_is_strong:
                                st.info(
                                    f"Lecture conjointe : sur ce test, la robustesse semble venir plutôt du **contexte** "
                                    f"que des sessions. "
                                    f"Filtre de contexte dominant : **{combined_context_name}** "
                                    f"(Score contexte = {combined_context_score}, Diagnostic = {combined_context_diag}, "
                                    f"Delta Expectancy OOS = {combined_context_delta_oos_expectancy}, Delta DD OOS (abs) = {combined_context_delta_dd}) | "
                                    f"Session la moins fragile : **{combined_session_name}** "
                                    f"(Score robustesse = {combined_session_score}, Diagnostic = {combined_session_diag}, "
                                    f"Expectancy OOS = {combined_session_expectancy_oos}, Delta Expectancy = {combined_session_delta_expectancy})."
                                )
                            else:
                                st.warning(
                                    f"Lecture conjointe : sur ce test, ni les **sessions** ni les **filtres de contexte** "
                                    f"ne semblent apporter de validation OOS vraiment claire. "
                                    f"Session la moins mauvaise : **{combined_session_name}** "
                                    f"(Score robustesse = {combined_session_score}, Diagnostic = {combined_session_diag}, "
                                    f"Expectancy OOS = {combined_session_expectancy_oos}, Delta Expectancy = {combined_session_delta_expectancy}) | "
                                    f"Filtre de contexte le moins mauvais : **{combined_context_name}** "
                                    f"(Score contexte = {combined_context_score}, Diagnostic = {combined_context_diag}, "
                                    f"Delta Expectancy OOS = {combined_context_delta_oos_expectancy}, Delta DD OOS (abs) = {combined_context_delta_dd})."
                                )


                        best_row = optimization_results.iloc[reference_is_rank - 1]

                        best_short_window = int(best_row["Short Window"])
                        best_long_window = int(best_row["Long Window"])
                        best_rr_target = float(best_row["RR Target"])

                        best_trend_filter_window = trend_filter_window
                        best_atr_window = atr_window
                        best_min_atr_pct = min_atr_pct
                        best_adx_window = adx_window
                        best_min_adx = min_adx
                        best_session_name = "Aucune"
                        best_session_filter_enabled = False
                        best_session_start_hour = 8
                        best_session_end_hour = 17

                        if "Trend Filter Window" in best_row.index and pd.notna(best_row["Trend Filter Window"]):
                            best_trend_filter_window = int(best_row["Trend Filter Window"])

                        if "ATR Window" in best_row.index and pd.notna(best_row["ATR Window"]):
                            best_atr_window = int(best_row["ATR Window"])

                        if "Min ATR %" in best_row.index and pd.notna(best_row["Min ATR %"]):
                            best_min_atr_pct = float(best_row["Min ATR %"])

                        if "ADX Window" in best_row.index and pd.notna(best_row["ADX Window"]):
                            best_adx_window = int(best_row["ADX Window"])

                        if "Min ADX" in best_row.index and pd.notna(best_row["Min ADX"]):
                            best_min_adx = float(best_row["Min ADX"])

                        if "Session Name" in best_row.index and pd.notna(best_row["Session Name"]):
                            best_session_name = str(best_row["Session Name"])

                            if best_session_name == "Aucune":
                                best_session_filter_enabled = False
                                best_session_start_hour = 8
                                best_session_end_hour = 17
                            else:
                                best_session_filter_enabled = True
                                best_session_start_hour = int(best_row["Session Start"])
                                best_session_end_hour = int(best_row["Session End"])

                        best_oos_price_df = df_outsample[["Date", "Open", "High", "Low", "Close"]].copy()

                        if strategy_name == "SMA":
                            best_oos_df = calculate_sma_strategy(
                                best_oos_price_df,
                                best_short_window,
                                best_long_window,
                                trend_filter_enabled=trend_filter_enabled,
                                trend_filter_window=best_trend_filter_window,
                                volatility_filter_enabled=volatility_filter_enabled,
                                atr_window=best_atr_window,
                                min_atr_pct=best_min_atr_pct,
                                regime_filter_enabled=regime_filter_enabled,
                                adx_window=best_adx_window,
                                min_adx=best_min_adx,
                                session_filter_enabled=best_session_filter_enabled,
                                session_start_hour=best_session_start_hour,
                                session_end_hour=best_session_end_hour,
                                strategy_mode=strategy_mode
                            )
                        else:
                            best_oos_df = calculate_impulse_pullback_break_strategy(
                                best_oos_price_df,
                                trend_lookback_bars=trend_lookback_bars,
                                atr_window=best_atr_window,
                                min_trend_atr_multiple=min_trend_atr_multiple,
                                pullback_max_bars=pullback_max_bars,
                                pullback_max_depth_atr=pullback_max_depth_atr,
                                confirmation_bars=confirmation_bars
                            )
                        best_oos_trades = run_simple_backtest(
                            best_oos_df,
                            rr_target=best_rr_target,
                            trade_mode=trade_mode,
                            cost_per_trade_r=cost_per_trade_r,
                            strategy_mode=strategy_mode
                        )

                        best_oos_equity = build_equity_curve(best_oos_trades, starting_r=starting_r)
                        best_oos_metrics = calculate_basic_metrics(best_oos_trades, best_oos_equity)

                        best_is_oos_comparison_df = pd.DataFrame([
                            {
                                "Période": "In-Sample",
                                "Session": best_session_name,
                                "Trades": int(best_row["Trades"]) if "Trades" in best_row.index and pd.notna(best_row["Trades"]) else 0,
                                "Total R": float(best_row["Total R"]) if "Total R" in best_row.index and pd.notna(best_row["Total R"]) else 0.0,
                                "Expectancy": float(best_row["Expectancy (R)"]) if "Expectancy (R)" in best_row.index and pd.notna(best_row["Expectancy (R)"]) else 0.0,
                                "Max Drawdown": float(best_row["Max Drawdown (R)"]) if "Max Drawdown (R)" in best_row.index and pd.notna(best_row["Max Drawdown (R)"]) else 0.0,
                            },
                            {
                                "Période": "Out-of-Sample",
                                "Session": best_session_name,
                                "Trades": best_oos_metrics["number_of_trades"],
                                "Total R": best_oos_metrics["total_pnl"],
                                "Expectancy": best_oos_metrics["expectancy"],
                                "Max Drawdown": best_oos_metrics["max_drawdown"],
                            }
                        ])

                        st.subheader("Validation OOS du candidat de référence")
                        reference_label = (
                            f"Candidat de référence = meilleur survivant OOS parmi le Top {top_n_is_to_validate} IS "
                            f"(rang IS {reference_is_rank})"
                            if reference_selection_mode == "best_oos_survivor"
                            else "Candidat de référence = winner IS (rang IS 1)"
                        )

                        st.caption(
                            (
                                f"{reference_label} : short={best_short_window} | long={best_long_window} | "
                                f"trend filter={best_trend_filter_window} | RR={best_rr_target} | "
                                f"ATR window={best_atr_window} | Min ATR %={best_min_atr_pct} | "
                                f"ADX window={best_adx_window} | Min ADX={best_min_adx} | "
                                f"Session={best_session_name} | "
                                f"Heures={best_session_start_hour}h-{best_session_end_hour}h"
                            )
                            if best_session_filter_enabled
                            else
                            (
                                f"{reference_label} : short={best_short_window} | long={best_long_window} | "
                                f"trend filter={best_trend_filter_window} | RR={best_rr_target} | "
                                f"ATR window={best_atr_window} | Min ATR %={best_min_atr_pct} | "
                                f"ADX window={best_adx_window} | Min ADX={best_min_adx} | "
                                f"Session={best_session_name}"
                            )
                        )

                        col_oos1, col_oos2, col_oos3, col_oos4 = st.columns(4)
                        col_oos1.metric("Trades OOS (best IS)", best_oos_metrics["number_of_trades"])
                        col_oos2.metric("Total R OOS (best IS)", best_oos_metrics["total_pnl"])
                        col_oos3.metric("Expectancy OOS (best IS)", best_oos_metrics["expectancy"])
                        col_oos4.metric("Max Drawdown OOS", best_oos_metrics["max_drawdown"])

                        st.subheader("Comparaison IS vs OOS du candidat de référence")
                        st.dataframe(best_is_oos_comparison_df, use_container_width=True)

                        reference_multi_split_rows = []

                        for tested_split_ratio in [60, 70, 80]:
                            reference_analysis = run_analysis(
                                price_df=df[["Date", "Open", "High", "Low", "Close"]].copy(),
                                short_window=best_short_window,
                                long_window=best_long_window,
                                rr_target=best_rr_target,
                                trade_mode=trade_mode,
                                cost_per_trade_r=cost_per_trade_r,
                                starting_r=starting_r,
                                split_ratio=tested_split_ratio,
                                trend_filter_enabled=trend_filter_enabled,
                                trend_filter_window=best_trend_filter_window,
                                volatility_filter_enabled=volatility_filter_enabled,
                                atr_window=best_atr_window,
                                min_atr_pct=best_min_atr_pct,
                                regime_filter_enabled=regime_filter_enabled,
                                adx_window=best_adx_window,
                                min_adx=best_min_adx,
                                session_filter_enabled=best_session_filter_enabled,
                                session_start_hour=best_session_start_hour,
                                session_end_hour=best_session_end_hour,
                                strategy_mode=strategy_mode
                            )

                            reference_split_metrics_is = reference_analysis["metrics_insample"]
                            reference_split_metrics_oos = reference_analysis["metrics_outsample"]

                            if reference_split_metrics_oos["number_of_trades"] < 5:
                                reference_split_diagnostic = "OOS trop faible"
                            elif reference_split_metrics_oos["expectancy"] > 0 and reference_split_metrics_oos["total_pnl"] > 0:
                                reference_split_diagnostic = "Robuste"
                            elif reference_split_metrics_oos["expectancy"] > 0:
                                reference_split_diagnostic = "Dégradée mais positive"
                            else:
                                reference_split_diagnostic = "Fragile / non validée OOS"

                            reference_multi_split_rows.append({
                                "Split IS %": tested_split_ratio,
                                "Split OOS %": 100 - tested_split_ratio,
                                "Trades IS": reference_split_metrics_is["number_of_trades"],
                                "Expectancy IS": reference_split_metrics_is["expectancy"],
                                "Total R IS": reference_split_metrics_is["total_pnl"],
                                "Trades OOS": reference_split_metrics_oos["number_of_trades"],
                                "Expectancy OOS": reference_split_metrics_oos["expectancy"],
                                "Total R OOS": reference_split_metrics_oos["total_pnl"],
                                "Max DD OOS": reference_split_metrics_oos["max_drawdown"],
                                "Diagnostic": reference_split_diagnostic
                            })

                        reference_multi_split_df = pd.DataFrame(reference_multi_split_rows)

                        reference_total_splits = len(reference_multi_split_df)
                        reference_survival_count = 0
                        reference_multi_split_ratio = "0/0"
                        reference_multi_split_status = "Indisponible"
                        reference_multi_split_score = -10

                        st.subheader("Robustesse multi-splits du candidat de référence")
                        st.dataframe(reference_multi_split_df, use_container_width=True)
                        st.caption(
                            "Ce tableau reteste le même candidat de référence sur plusieurs découpages IS/OOS, "
                            "pour vérifier s'il tient seulement sur un split ou sur plusieurs."
                        )

                        if reference_multi_split_df.empty:
                            st.info("Aucune lecture multi-splits disponible pour le moment.")
                        else:
                            reference_survival_count = len(
                                reference_multi_split_df[
                                    reference_multi_split_df["Diagnostic"].isin(["Robuste", "Dégradée mais positive"])
                                ]
                            )
                            reference_multi_split_ratio = f"{reference_survival_count}/{reference_total_splits}"

                            if reference_survival_count == reference_total_splits and reference_total_splits > 0:
                                reference_multi_split_status = "Robuste"
                                reference_multi_split_score = 15
                                st.success(
                                    f"Lecture automatique : le candidat de référence tient sur "
                                    f"{reference_multi_split_ratio} splits testés. "
                                    f"La robustesse devient plus crédible."
                                )
                            elif reference_survival_count >= 2:
                                reference_multi_split_status = "Encourageant mais prudent"
                                reference_multi_split_score = 5
                                st.info(
                                    f"Lecture automatique : le candidat de référence tient sur "
                                    f"{reference_multi_split_ratio} splits testés. "
                                    f"C'est encourageant, mais encore prudent."
                                )
                            elif reference_survival_count == 1:
                                reference_multi_split_status = "Limité"
                                reference_multi_split_score = -5
                                st.warning(
                                    f"Lecture automatique : le candidat de référence ne tient que sur "
                                    f"{reference_multi_split_ratio} split testé. "
                                    f"La robustesse reste limitée."
                                )
                            else:
                                reference_multi_split_status = "Faible / non validé"
                                reference_multi_split_score = -15
                                st.warning(
                                    f"Lecture automatique : le candidat de référence ne tient sur aucun des "
                                    f"{reference_total_splits} splits testés. "
                                    f"Le run reste fragile."
                                )

                        st.subheader("Shortlist des briques candidates du run")

                        if session_oos_robustness_df.empty or context_filters_summary_df.empty:
                            st.info("Shortlist indisponible pour le moment.")
                        else:
                            shortlist_best_session_row = session_oos_robustness_df.iloc[0]
                            shortlist_best_context_row = context_filters_summary_df.iloc[0]

                            shortlist_session_diag = shortlist_best_session_row["Diagnostic robustesse"]
                            shortlist_session_score = shortlist_best_session_row["Score robustesse"]
                            shortlist_session_expectancy_oos = shortlist_best_session_row["Expectancy OOS"]

                            if shortlist_session_diag == "Robuste":
                                shortlist_session_level = "Candidate validée"
                                shortlist_session_status = "Oui"
                                shortlist_session_priority = 3
                            elif shortlist_session_diag == "Dégradée mais positive":
                                shortlist_session_level = "Candidate partielle"
                                shortlist_session_status = "Partielle"
                                shortlist_session_priority = 2
                            elif shortlist_session_diag == "OOS trop faible":
                                shortlist_session_level = "Candidate trop faible"
                                shortlist_session_status = "Faible"
                                shortlist_session_priority = 0
                            else:
                                shortlist_session_level = "Candidate faible / moins mauvaise"
                                shortlist_session_status = "Non"
                                shortlist_session_priority = 1

                            shortlist_context_diag = shortlist_best_context_row["Diagnostic"]
                            shortlist_context_score = shortlist_best_context_row["Score contexte"]
                            shortlist_context_delta_oos = shortlist_best_context_row["Delta Expectancy OOS"]

                            if (
                                shortlist_context_diag == "Amélioration robuste"
                                and shortlist_context_delta_oos > 0
                            ):
                                shortlist_context_level = "Candidate validée"
                                shortlist_context_status = "Oui"
                                shortlist_context_priority = 3
                            elif (
                                shortlist_context_diag == "Amélioration avec risque"
                                and shortlist_context_delta_oos > 0
                            ):
                                shortlist_context_level = "Candidate partielle"
                                shortlist_context_status = "Partielle"
                                shortlist_context_priority = 2
                            elif shortlist_context_diag == "OOS ON trop faible":
                                shortlist_context_level = "Candidate trop faible"
                                shortlist_context_status = "Faible"
                                shortlist_context_priority = 0
                            elif shortlist_context_diag == "Impact neutre":
                                shortlist_context_level = "Candidate neutre / moins mauvaise"
                                shortlist_context_status = "Non"
                                shortlist_context_priority = 1
                            else:
                                shortlist_context_level = "Candidate faible / dégradée"
                                shortlist_context_status = "Non"
                                shortlist_context_priority = 1

                            shortlist_rows = [
                                {
                                    "Type de brique": "Session",
                                    "Nom": shortlist_best_session_row["Session"],
                                    "Score": shortlist_session_score,
                                    "Diagnostic": shortlist_session_diag,
                                    "Mesure OOS clé": shortlist_session_expectancy_oos,
                                    "Mesure clé": "Expectancy OOS",
                                    "Niveau de candidature": shortlist_session_level,
                                    "Statut candidat": shortlist_session_status,
                                    "Priorité tri": shortlist_session_priority
                                },
                                {
                                    "Type de brique": "Contexte",
                                    "Nom": shortlist_best_context_row["Filtre"],
                                    "Score": shortlist_context_score,
                                    "Diagnostic": shortlist_context_diag,
                                    "Mesure OOS clé": shortlist_context_delta_oos,
                                    "Mesure clé": "Delta Expectancy OOS",
                                    "Niveau de candidature": shortlist_context_level,
                                    "Statut candidat": shortlist_context_status,
                                    "Priorité tri": shortlist_context_priority
                                }
                            ]

                            shortlist_df = pd.DataFrame(shortlist_rows)
                            shortlist_df = shortlist_df.sort_values(
                                by=["Priorité tri", "Score"],
                                ascending=[False, False]
                            ).reset_index(drop=True)

                            shortlist_display_df = shortlist_df[
                                [
                                    "Type de brique",
                                    "Nom",
                                    "Score",
                                    "Diagnostic",
                                    "Niveau de candidature",
                                    "Statut candidat"
                                ]
                            ]

                            st.dataframe(shortlist_display_df, use_container_width=True)
                            st.caption(
                                "Cette shortlist distingue maintenant une brique validée, partielle, faible ou simplement "
                                "moins mauvaise, pour éviter de survaloriser un faux candidat."
                            )

                            shortlist_valid_count = len(
                                shortlist_df[shortlist_df["Niveau de candidature"] == "Candidate validée"]
                            )
                            shortlist_partial_count = len(
                                shortlist_df[shortlist_df["Niveau de candidature"] == "Candidate partielle"]
                            )

                            if shortlist_valid_count >= 1:
                                st.success(
                                    "Lecture shortlist : au moins une brique ressort comme **candidate validée** sur ce run."
                                )
                            elif shortlist_partial_count >= 1:
                                st.info(
                                    "Lecture shortlist : aucune brique n'est pleinement validée, "
                                    "mais au moins une ressort comme **candidate partielle**."
                                )
                            else:
                                st.warning(
                                    "Lecture shortlist : aucune brique ne ressort comme validée. "
                                    "Le classement met surtout en avant les éléments les moins mauvais du run."
                                )
                        st.subheader("Synthèse structurée du run actuel")

                        if session_oos_robustness_df.empty or context_filters_summary_df.empty:
                            st.info("Synthèse structurée indisponible pour le moment.")
                        else:
                            structured_best_session_row = session_oos_robustness_df.iloc[0]
                            structured_best_context_row = context_filters_summary_df.iloc[0]

                            structured_best_session_score = structured_best_session_row["Score robustesse"]
                            structured_best_context_score = structured_best_context_row["Score contexte"]

                            structured_session_candidate = (
                                structured_best_session_row["Diagnostic robustesse"] in ["Robuste", "Dégradée mais positive"]
                            )
                            structured_context_candidate = (
                                structured_best_context_row["Delta Expectancy OOS"] > 0
                            )

                            structured_run_survivor = (
                                best_oos_metrics["expectancy"] > 0
                                and best_oos_metrics["number_of_trades"] >= 5
                                and reference_survival_count >= 1
                            )

                            if structured_run_survivor and structured_session_candidate and structured_context_candidate and reference_survival_count == reference_total_splits and reference_total_splits > 0:
                                structured_global_status = "Robuste et contextualisé"
                            elif structured_run_survivor and reference_survival_count >= 2 and (structured_session_candidate or structured_context_candidate):
                                structured_global_status = "Encourageant mais prudent"
                            elif structured_run_survivor and reference_survival_count >= 2:
                                structured_global_status = "Survivant peu contextualisé"
                            elif best_oos_metrics["number_of_trades"] < 5:
                                structured_global_status = "OOS trop faible"
                            else:
                                structured_global_status = "Faible / non validé"

                            structured_score_gap = round(structured_best_session_score - structured_best_context_score, 2)

                            if structured_score_gap > 15:
                                structured_dominance = "Sessions"
                            elif structured_score_gap < -15:
                                structured_dominance = "Contexte"
                            else:
                                structured_dominance = "Équilibre / indécis"

                            structured_run_score = 0.0

                            structured_run_score += best_oos_metrics["expectancy"] * 250
                            structured_run_score += min(best_oos_metrics["number_of_trades"], 300) * 0.08
                            structured_run_score += max(best_oos_metrics["total_pnl"], 0) * 0.80
                            structured_run_score += reference_multi_split_score

                            if structured_session_candidate:
                                structured_run_score += 12
                            else:
                                structured_run_score -= 8

                            if structured_context_candidate:
                                structured_run_score += 12
                            elif structured_best_context_row["Diagnostic"] == "Impact neutre":
                                structured_run_score -= 4
                            else:
                                structured_run_score -= 8

                            structured_run_score -= max(abs(best_oos_metrics["max_drawdown"]) - 10, 0) * 1.2

                            if structured_global_status == "Robuste et contextualisé":
                                structured_run_score += 20
                            elif structured_global_status == "Encourageant mais prudent":
                                structured_run_score += 8
                            elif structured_global_status == "Survivant peu contextualisé":
                                structured_run_score -= 5
                            elif structured_global_status == "OOS trop faible":
                                structured_run_score -= 12
                            else:
                                structured_run_score -= 20

                            structured_run_score = round(structured_run_score, 2)

                            structured_run_signature = (
                                f"SW{best_short_window}-LW{best_long_window}-RR{best_rr_target}"
                                f" | Sess={best_session_name}"
                                f" | TF={'ON' if trend_filter_enabled else 'OFF'}"
                                f" | VOL={'ON' if volatility_filter_enabled else 'OFF'}"
                                f" | REG={'ON' if regime_filter_enabled else 'OFF'}"
                                f" | MODE={strategy_mode}"
                            )

                            structured_run_summary_df = pd.DataFrame([
                                {
                                    "Statut global": structured_global_status,
                                    "Score global du run": structured_run_score,
                                    "Dominance": structured_dominance,
                                    "Robustesse multi-splits": reference_multi_split_status,
                                    "Splits survécus": reference_multi_split_ratio,
                                    "Score multi-splits": reference_multi_split_score,
                                    "Run survivant": "Oui" if structured_run_survivor else "Non",
                                    "Session candidate": "Oui" if structured_session_candidate else "Non",
                                    "Contexte candidate": "Oui" if structured_context_candidate else "Non",
                                    "Signature run": structured_run_signature,
                                    "Mode sélection référence": reference_selection_mode,
                                    "Rang IS de référence": reference_is_rank,
                                    "Best Global Short": best_short_window,
                                    "Best Global Long": best_long_window,
                                    "Best Global RR": best_rr_target,
                                    "Best Global OOS Trades": best_oos_metrics["number_of_trades"],
                                    "Best Global OOS Expectancy": best_oos_metrics["expectancy"],
                                    "Best Global OOS Total R": best_oos_metrics["total_pnl"],
                                    "Best Global OOS Max DD": best_oos_metrics["max_drawdown"],
                                    "Best Session": structured_best_session_row["Session"],
                                    "Best Session Score": structured_best_session_score,
                                    "Best Session Diagnostic": structured_best_session_row["Diagnostic robustesse"],
                                    "Best Session OOS Expectancy": structured_best_session_row["Expectancy OOS"],
                                    "Best Context": structured_best_context_row["Filtre"],
                                    "Best Context Score": structured_best_context_score,
                                    "Best Context Diagnostic": structured_best_context_row["Diagnostic"],
                                    "Best Context Delta OOS Expectancy": structured_best_context_row["Delta Expectancy OOS"],
                                    "Score gap Session-Contexte": structured_score_gap
                                }
                            ])

                            structured_run_summary_display_df = structured_run_summary_df[
                                [
                                    "Statut global",
                                    "Score global du run",
                                    "Dominance",
                                    "Robustesse multi-splits",
                                    "Splits survécus",
                                    "Run survivant",
                                    "Session candidate",
                                    "Contexte candidate"
                                ]
                            ]

                            st.dataframe(structured_run_summary_display_df, use_container_width=True)
                            st.caption(
                                "Cette synthèse compacte résume le run actuel dans un format plus exploitable "
                                "pour une future logique de sélection, d'archivage ou de hedge."
                            )
                            current_run_history_row = structured_run_summary_df.copy()

                            current_run_history_row.insert(
                                0,
                                "Run ID",
                                f"RUN_{len(st.session_state.run_history) + 1:03d}"
                            )

                            current_run_history_row.insert(
                                1,
                                "Timestamp",
                                pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
                            )

                            if st.button("Ajouter ce run à l'historique", key="add_run_history_button"):
                                st.session_state.run_history.append(current_run_history_row.iloc[0].to_dict())

                                run_history_save_df = pd.DataFrame(st.session_state.run_history)
                                run_history_save_df.to_csv(RUN_HISTORY_FILE, index=False)

                                st.success("Run ajouté à l'historique et sauvegardé dans le CSV.")
                        st.subheader("Profil exploitable du run")

                        if session_oos_robustness_df.empty or context_filters_summary_df.empty:
                            st.info("Profil exploitable indisponible pour le moment.")
                        else:
                            profile_best_session_row = session_oos_robustness_df.iloc[0]
                            profile_best_context_row = context_filters_summary_df.iloc[0]

                            profile_session_candidate = (
                                "Oui"
                                if profile_best_session_row["Diagnostic robustesse"] in ["Robuste", "Dégradée mais positive"]
                                else "Non"
                            )

                            profile_context_candidate = (
                                "Oui"
                                if profile_best_context_row["Delta Expectancy OOS"] > 0
                                else "Non"
                            )

                            profile_run_survivor = (
                                "Oui"
                                if (
                                    best_oos_metrics["expectancy"] > 0
                                    and best_oos_metrics["number_of_trades"] >= 5
                                    and reference_survival_count >= 1
                                )
                                else "Non"
                            )

                            if profile_run_survivor == "Oui" and reference_survival_count >= 2:
                                if profile_session_candidate == "Oui" or profile_context_candidate == "Oui":
                                    profile_research_ready = "Oui"
                                else:
                                    profile_research_ready = "À surveiller"
                            elif profile_run_survivor == "Oui":
                                profile_research_ready = "À surveiller"
                            else:
                                profile_research_ready = "Non"

                            if (
                                profile_run_survivor == "Oui"
                                and profile_session_candidate == "Oui"
                                and profile_context_candidate == "Oui"
                                and reference_survival_count >= 2
                            ):
                                profile_hedge_readiness = "Base exploitable"
                            elif (
                                profile_run_survivor == "Oui"
                                and (profile_session_candidate == "Oui" or profile_context_candidate == "Oui")
                                and reference_survival_count >= 2
                            ):
                                profile_hedge_readiness = "Partielle"
                            else:
                                profile_hedge_readiness = "Non exploitable à ce stade"

                            if profile_session_candidate == "Oui" and profile_context_candidate == "Oui":
                                profile_structural_read = "Survie contextualisée"
                            elif profile_session_candidate == "Oui" or profile_context_candidate == "Oui":
                                profile_structural_read = "Survie partiellement contextualisée"
                            elif profile_run_survivor == "Oui":
                                profile_structural_read = "Survie brute sans validation structurelle"
                            else:
                                profile_structural_read = "Non validé"

                            run_profile_df = pd.DataFrame([
                                {
                                    "Run survivant": profile_run_survivor,
                                    "Exploitable recherche": profile_research_ready,
                                    "Préparation hedge": profile_hedge_readiness,
                                    "Lecture structurelle": profile_structural_read,
                                    "Statut global": structured_global_status,
                                    "Score global du run": structured_run_score,
                                    "Dominance": structured_dominance,
                                    "Robustesse multi-splits": reference_multi_split_status,
                                    "Splits survécus": reference_multi_split_ratio,
                                    "Mode sélection référence": reference_selection_mode,
                                    "Rang IS de référence": reference_is_rank,
                                    "Best Session": profile_best_session_row["Session"],
                                    "Best Session Score": profile_best_session_row["Score robustesse"],
                                    "Best Session Candidate": profile_session_candidate,
                                    "Best Context": profile_best_context_row["Filtre"],
                                    "Best Context Score": profile_best_context_row["Score contexte"],
                                    "Best Context Candidate": profile_context_candidate,
                                    "Best Global OOS Trades": best_oos_metrics["number_of_trades"],
                                    "Best Global OOS Expectancy": best_oos_metrics["expectancy"],
                                    "Best Global OOS Total R": best_oos_metrics["total_pnl"],
                                    "Best Global OOS Max DD": best_oos_metrics["max_drawdown"]
                                }
                            ])

                            run_profile_display_df = run_profile_df[
                                [
                                    "Run survivant",
                                    "Exploitable recherche",
                                    "Préparation hedge",
                                    "Lecture structurelle",
                                    "Statut global",
                                    "Score global du run"
                                ]
                            ]

                            st.dataframe(run_profile_display_df, use_container_width=True)
                            st.caption(
                                "Ce bloc distingue maintenant le run survivant, le run exploitable en recherche "
                                "et le run assez propre pour servir plus tard de brique de hedge."
                            )
                        st.subheader("Verdict global du test")

                        if session_oos_robustness_df.empty or context_filters_summary_df.empty:
                            st.info("Verdict global indisponible pour le moment.")
                        else:
                            final_best_session_row = session_oos_robustness_df.iloc[0]
                            final_best_context_row = context_filters_summary_df.iloc[0]

                            final_session_name = final_best_session_row["Session"]
                            final_session_score = final_best_session_row["Score robustesse"]
                            final_session_diag = final_best_session_row["Diagnostic robustesse"]
                            final_session_candidate = final_session_diag in ["Robuste", "Dégradée mais positive"]

                            final_context_name = final_best_context_row["Filtre"]
                            final_context_score = final_best_context_row["Score contexte"]
                            final_context_diag = final_best_context_row["Diagnostic"]
                            final_context_candidate = final_best_context_row["Delta Expectancy OOS"] > 0

                            final_global_oos_expectancy = best_oos_metrics["expectancy"]
                            final_global_oos_total_r = best_oos_metrics["total_pnl"]
                            final_global_oos_dd = best_oos_metrics["max_drawdown"]
                            final_global_oos_trades = best_oos_metrics["number_of_trades"]

                            final_run_survivor = (
                                final_global_oos_expectancy > 0
                                and final_global_oos_trades >= 5
                                and reference_survival_count >= 1
                            )

                            if (
                                final_run_survivor
                                and final_session_candidate
                                and final_context_candidate
                                and reference_survival_count == reference_total_splits
                                and reference_total_splits > 0
                            ):
                                st.success(
                                    f"Verdict global : **run survivant, cohérent et robuste**. "
                                    f"Le meilleur set global garde une validation OOS positive "
                                    f"(Expectancy OOS = {final_global_oos_expectancy}, Total R OOS = {final_global_oos_total_r}, "
                                    f"Max DD OOS = {final_global_oos_dd}, Trades OOS = {final_global_oos_trades}) "
                                    f"et le candidat de référence tient sur **{reference_multi_split_ratio}** splits. "
                                    f"La structure du run est aussi confirmée par la session **{final_session_name}** "
                                    f"(Score robustesse = {final_session_score}, Diagnostic = {final_session_diag}) "
                                    f"et par le contexte **{final_context_name}** "
                                    f"(Score contexte = {final_context_score}, Diagnostic = {final_context_diag}). "
                                    f"Ce type de run commence à devenir une base crédible pour la suite."
                                )
                            elif (
                                final_run_survivor
                                and reference_survival_count >= 2
                                and (final_session_candidate or final_context_candidate)
                            ):
                                st.info(
                                    f"Verdict global : **run survivant et exploitable en recherche, mais encore prudent**. "
                                    f"Le meilleur set global reste positif en OOS "
                                    f"(Expectancy OOS = {final_global_oos_expectancy}, Total R OOS = {final_global_oos_total_r}, "
                                    f"Max DD OOS = {final_global_oos_dd}, Trades OOS = {final_global_oos_trades}) "
                                    f"et le candidat de référence tient sur **{reference_multi_split_ratio}** splits. "
                                    f"La validation structurelle reste seulement partielle : "
                                    f"session dominante = **{final_session_name}** "
                                    f"(Score robustesse = {final_session_score}, Diagnostic = {final_session_diag}) | "
                                    f"contexte dominant = **{final_context_name}** "
                                    f"(Score contexte = {final_context_score}, Diagnostic = {final_context_diag}). "
                                    f"Le run mérite d'être conservé pour la recherche, mais pas encore traité comme une brique de hedge."
                                )
                            elif final_run_survivor and reference_survival_count >= 2:
                                st.info(
                                    f"Verdict global : **run survivant mais peu contextualisé**. "
                                    f"Le meilleur set global reste positif en OOS "
                                    f"(Expectancy OOS = {final_global_oos_expectancy}, Total R OOS = {final_global_oos_total_r}, "
                                    f"Max DD OOS = {final_global_oos_dd}, Trades OOS = {final_global_oos_trades}) "
                                    f"et le candidat de référence tient sur **{reference_multi_split_ratio}** splits, "
                                    f"ce qui le rend intéressant pour la recherche. "
                                    f"En revanche, ni la session **{final_session_name}** "
                                    f"(Score robustesse = {final_session_score}, Diagnostic = {final_session_diag}) "
                                    f"ni le contexte **{final_context_name}** "
                                    f"(Score contexte = {final_context_score}, Diagnostic = {final_context_diag}) "
                                    f"ne valident encore une structure propre. "
                                    f"Conclusion : run à archiver et surveiller, mais pas exploitable pour une logique de hedge."
                                )
                            elif final_global_oos_trades < 5:
                                st.warning(
                                    f"Verdict global : **lecture encore trop faible**. "
                                    f"Le meilleur set global n'a que {final_global_oos_trades} trades OOS, "
                                    f"ce qui limite fortement la conclusion. "
                                    f"Robustesse multi-splits actuelle : **{reference_multi_split_ratio}** "
                                    f"({reference_multi_split_status}). "
                                    f"Session dominante : **{final_session_name}** "
                                    f"(Score robustesse = {final_session_score}, Diagnostic = {final_session_diag}) | "
                                    f"Contexte dominant : **{final_context_name}** "
                                    f"(Score contexte = {final_context_score}, Diagnostic = {final_context_diag})."
                                )
                            elif final_run_survivor and reference_survival_count == 1:
                                st.warning(
                                    f"Verdict global : **run positif mais encore trop fragile**. "
                                    f"Le meilleur set global garde quelques éléments OOS utiles "
                                    f"(Expectancy OOS = {final_global_oos_expectancy}, Total R OOS = {final_global_oos_total_r}, "
                                    f"Max DD OOS = {final_global_oos_dd}, Trades OOS = {final_global_oos_trades}), "
                                    f"mais le candidat de référence ne tient que sur **{reference_multi_split_ratio}** split. "
                                    f"Session dominante : **{final_session_name}** "
                                    f"(Score robustesse = {final_session_score}, Diagnostic = {final_session_diag}) | "
                                    f"Contexte dominant : **{final_context_name}** "
                                    f"(Score contexte = {final_context_score}, Diagnostic = {final_context_diag}). "
                                    f"Ce run reste trop fragile pour être retenu comme brique sérieuse."
                                )
                            else:
                                st.warning(
                                    f"Verdict global : **test faible / non validé à ce stade**. "
                                    f"Le meilleur set global ne garde pas de validation OOS assez convaincante "
                                    f"(Expectancy OOS = {final_global_oos_expectancy}, Total R OOS = {final_global_oos_total_r}, "
                                    f"Max DD OOS = {final_global_oos_dd}, Trades OOS = {final_global_oos_trades}) "
                                    f"et la robustesse multi-splits reste faible "
                                    f"(**{reference_multi_split_ratio}**, {reference_multi_split_status}). "
                                    f"Session la moins mauvaise : **{final_session_name}** "
                                    f"(Score robustesse = {final_session_score}, Diagnostic = {final_session_diag}) | "
                                    f"Contexte le moins mauvais : **{final_context_name}** "
                                    f"(Score contexte = {final_context_score}, Diagnostic = {final_context_diag})."
                                )

                    st.subheader("Historique des runs")

                    if st.session_state.run_history:
                        run_history_df = pd.DataFrame(st.session_state.run_history).copy()

                        if "Timestamp" in run_history_df.columns:
                            run_history_df["Timestamp_dt"] = pd.to_datetime(
                                run_history_df["Timestamp"],
                                errors="coerce"
                            )
                            run_history_df = run_history_df.sort_values(
                                by="Timestamp_dt",
                                ascending=False
                            ).reset_index(drop=True)
                        else:
                            run_history_df["Timestamp_dt"] = pd.NaT

                        if "Score global du run" in run_history_df.columns:
                            run_history_df["Score global du run"] = pd.to_numeric(
                                run_history_df["Score global du run"],
                                errors="coerce"
                            )
                        if "Signature run" in run_history_df.columns:
                            run_history_df["Signature courte"] = (
                                run_history_df["Signature run"]
                                .astype(str)
                                .str.replace(" | Sess=", " | ", regex=False)
                                .str.replace(" | TF=", " | ", regex=False)
                                .str.replace(" | VOL=", " | ", regex=False)
                                .str.replace(" | REG=", " | ", regex=False)
                            )

                        total_runs = len(run_history_df)

                        survivor_runs = 0
                        contextualized_runs = 0
                        best_score = "N/A"
                        distinct_signatures = 0
                        latest_signature_count = 0
                        latest_signature_value = None

                        if "Run survivant" in run_history_df.columns:
                            survivor_runs = int(
                                (run_history_df["Run survivant"].astype(str) == "Oui").sum()
                            )

                        if "Statut global" in run_history_df.columns:
                            contextualized_runs = int(
                                run_history_df["Statut global"].astype(str).isin(
                                    ["Robuste et contextualisé", "Encourageant mais prudent"]
                                ).sum()
                            )

                        if (
                            "Score global du run" in run_history_df.columns
                            and run_history_df["Score global du run"].notna().any()
                        ):
                            best_score = round(run_history_df["Score global du run"].max(), 2)

                        if "Signature run" in run_history_df.columns:
                            distinct_signatures = int(run_history_df["Signature run"].nunique(dropna=True))

                            if len(run_history_df) > 0:
                                latest_signature_value = run_history_df.iloc[0]["Signature run"]
                                latest_signature_count = int(
                                    (run_history_df["Signature run"] == latest_signature_value).sum()
                                )

                        hist_col1, hist_col2, hist_col3, hist_col4 = st.columns(4)

                        hist_col1.metric("Runs enregistrés", total_runs)
                        hist_col2.metric("Runs survivants", survivor_runs)
                        hist_col3.metric("Signatures distinctes", distinct_signatures if distinct_signatures > 0 else "N/A")
                        hist_col4.metric("Meilleur score", best_score)

                        if latest_signature_value is not None and latest_signature_count >= 2:
                            st.info(
                                f"Lecture historique : la signature du run le plus récent apparaît **{latest_signature_count} fois**. "
                                f"Tu explores encore surtout le même couloir de test : **{latest_signature_value}**."
                            )
                        elif survivor_runs > 0 and contextualized_runs > 0:
                            st.info(
                                "Lecture historique : certains runs survivent et quelques-uns commencent "
                                "à montrer une structure partielle, mais aucune base hedge nette ne ressort encore."
                            )
                        elif survivor_runs > 0:
                            st.info(
                                "Lecture historique : le labo trouve déjà des runs survivants, "
                                "mais ils restent surtout peu contextualisés."
                            )
                        else:
                            st.warning(
                                "Lecture historique : aucun run vraiment survivant n'a encore été enregistré."
                            )

                        st.markdown("**Position du run actuel dans l'historique**")

                        if (
                            "structured_run_summary_df" in locals()
                            and not structured_run_summary_df.empty
                            and "Signature run" in structured_run_summary_df.columns
                        ):
                            current_signature = str(structured_run_summary_df.iloc[0]["Signature run"])
                            current_status = str(structured_run_summary_df.iloc[0]["Statut global"])
                            current_score = pd.to_numeric(
                                structured_run_summary_df.iloc[0]["Score global du run"],
                                errors="coerce"
                            )

                            if "Signature run" in run_history_df.columns:
                                matching_history_df = run_history_df[
                                    run_history_df["Signature run"].astype(str) == current_signature
                                ].copy()
                            else:
                                matching_history_df = pd.DataFrame()

                            if matching_history_df.empty:
                                st.info(
                                    f"Le run actuel semble être une **nouvelle signature** dans l'historique : "
                                    f"**{current_signature}**."
                                )
                            else:
                                matching_history_df["Score global du run"] = pd.to_numeric(
                                    matching_history_df["Score global du run"],
                                    errors="coerce"
                                )

                                same_sig_count = len(matching_history_df)
                                best_same_sig_score = matching_history_df["Score global du run"].max()

                                if pd.notna(current_score) and pd.notna(best_same_sig_score):
                                    delta_same_sig = round(float(current_score) - float(best_same_sig_score), 2)
                                else:
                                    delta_same_sig = None

                                pos_col1, pos_col2, pos_col3 = st.columns(3)

                                pos_col1.metric("Occurrences même signature", same_sig_count)
                                pos_col2.metric(
                                    "Meilleur score même signature",
                                    round(best_same_sig_score, 2) if pd.notna(best_same_sig_score) else "N/A"
                                )
                                pos_col3.metric(
                                    "Delta vs meilleur score",
                                    delta_same_sig if delta_same_sig is not None else "N/A"
                                )

                                if delta_same_sig is not None and delta_same_sig > 0:
                                    st.success(
                                        f"Le run actuel (**{current_status}**) fait mieux que les runs déjà enregistrés "
                                        f"avec la même signature : **{current_signature}**."
                                    )
                                elif delta_same_sig is not None and delta_same_sig == 0:
                                    st.info(
                                        f"Le run actuel est au niveau du meilleur run déjà vu pour cette signature : "
                                        f"**{current_signature}**."
                                    )
                                else:
                                    st.warning(
                                        f"Le run actuel appartient à une signature déjà vue "
                                        f"(**{current_signature}**) mais ne dépasse pas encore le meilleur score historique."
                                    )
                        else:
                            st.info(
                                "Position du run actuel indisponible pour le moment."
                            )

                        st.markdown("**Récurrences inter-runs**")

                        recurrence_rows = []

                        def add_recurrence_row(source_df, column_name, label_name):
                            if column_name not in source_df.columns:
                                return "N/A", 0

                            series = (
                                source_df[column_name]
                                .dropna()
                                .astype(str)
                                .str.strip()
                            )
                            series = series[series != ""]

                            if series.empty:
                                return "N/A", 0

                            counts = series.value_counts()
                            top_value = counts.index[0]
                            top_count = int(counts.iloc[0])

                            recurrence_rows.append({
                                "Lecture": label_name,
                                "Élément le plus fréquent": top_value,
                                "Occurrences": top_count
                            })

                            return top_value, top_count

                        top_status_value, top_status_count = add_recurrence_row(
                            run_history_df, "Statut global", "Statut global"
                        )
                        top_dominance_value, top_dominance_count = add_recurrence_row(
                            run_history_df, "Dominance", "Dominance"
                        )
                        top_context_value, top_context_count = add_recurrence_row(
                            run_history_df, "Best Context", "Contexte dominant"
                        )
                        top_session_value, top_session_count = add_recurrence_row(
                            run_history_df, "Best Session", "Session dominante"
                        )

                        rec_col1, rec_col2, rec_col3, rec_col4 = st.columns(4)

                        rec_col1.metric(
                            "Statut le plus fréquent",
                            top_status_value,
                            delta=f"{top_status_count} run(s)" if top_status_count > 0 else None
                        )
                        rec_col2.metric(
                            "Dominance la plus fréquente",
                            top_dominance_value,
                            delta=f"{top_dominance_count} run(s)" if top_dominance_count > 0 else None
                        )
                        rec_col3.metric(
                            "Contexte le plus fréquent",
                            top_context_value,
                            delta=f"{top_context_count} run(s)" if top_context_count > 0 else None
                        )
                        rec_col4.metric(
                            "Session la plus fréquente",
                            top_session_value,
                            delta=f"{top_session_count} run(s)" if top_session_count > 0 else None
                        )

                        if recurrence_rows:
                            recurrence_summary_df = pd.DataFrame(recurrence_rows)
                            st.dataframe(recurrence_summary_df, use_container_width=True)

                            if total_runs == 1:
                                st.info(
                                    "Lecture récurrences : avec un seul run enregistré, cette vue sert surtout de point de départ. "
                                    "Elle deviendra beaucoup plus utile quand plusieurs familles de runs auront été testées."
                                )
                            else:
                                st.info(
                                    f"Lecture récurrences : pour l'instant, les runs reviennent surtout avec un statut "
                                    f"**{top_status_value}**, une dominance **{top_dominance_value}**, "
                                    f"un contexte récurrent **{top_context_value}** et une session récurrente "
                                    f"**{top_session_value}**."
                                )

                        st.markdown("**Récurrences sur runs survivants**")

                        if "Run survivant" in run_history_df.columns:
                            survivor_history_df = run_history_df[
                                run_history_df["Run survivant"].astype(str) == "Oui"
                            ].copy()
                        else:
                            survivor_history_df = pd.DataFrame()

                        if survivor_history_df.empty:
                            st.info(
                                "Aucune lecture spécifique des runs survivants n'est disponible pour le moment."
                            )
                        else:
                            survivor_recurrence_rows = []

                            def add_survivor_recurrence_row(source_df, column_name, label_name):
                                if column_name not in source_df.columns:
                                    return "N/A", 0

                                series = (
                                    source_df[column_name]
                                    .dropna()
                                    .astype(str)
                                    .str.strip()
                                )
                                series = series[series != ""]

                                if series.empty:
                                    return "N/A", 0

                                counts = series.value_counts()
                                top_value = counts.index[0]
                                top_count = int(counts.iloc[0])

                                survivor_recurrence_rows.append({
                                    "Lecture": label_name,
                                    "Élément dominant": top_value,
                                    "Occurrences": top_count
                                })

                                return top_value, top_count

                            top_survivor_dominance, top_survivor_dominance_count = add_survivor_recurrence_row(
                                survivor_history_df, "Dominance", "Dominance survivante"
                            )
                            top_survivor_context, top_survivor_context_count = add_survivor_recurrence_row(
                                survivor_history_df, "Best Context", "Contexte survivant"
                            )
                            top_survivor_session, top_survivor_session_count = add_survivor_recurrence_row(
                                survivor_history_df, "Best Session", "Session survivante"
                            )

                            survivor_signature_column = (
                                "Signature courte"
                                if "Signature courte" in survivor_history_df.columns
                                else "Signature run"
                            )

                            top_survivor_signature, top_survivor_signature_count = add_survivor_recurrence_row(
                                survivor_history_df, survivor_signature_column, "Signature survivante"
                            )

                            surv_col1, surv_col2, surv_col3, surv_col4 = st.columns(4)

                            surv_col1.metric(
                                "Dominance survivante",
                                top_survivor_dominance,
                                delta=f"{top_survivor_dominance_count} run(s)" if top_survivor_dominance_count > 0 else None
                            )
                            surv_col2.metric(
                                "Contexte survivant",
                                top_survivor_context,
                                delta=f"{top_survivor_context_count} run(s)" if top_survivor_context_count > 0 else None
                            )
                            surv_col3.metric(
                                "Session survivante",
                                top_survivor_session,
                                delta=f"{top_survivor_session_count} run(s)" if top_survivor_session_count > 0 else None
                            )
                            surv_col4.metric(
                                "Signature survivante",
                                top_survivor_signature,
                                delta=f"{top_survivor_signature_count} run(s)" if top_survivor_signature_count > 0 else None
                            )

                            if survivor_recurrence_rows:
                                survivor_recurrence_df = pd.DataFrame(survivor_recurrence_rows)
                                st.dataframe(survivor_recurrence_df, use_container_width=True)

                                if len(survivor_history_df) == 1:
                                    st.info(
                                        "Lecture survivants : un seul run survivant est enregistré pour l'instant. "
                                        "Cette vue deviendra plus parlante quand plusieurs survivants auront été accumulés."
                                    )
                                else:
                                    st.info(
                                        f"Lecture survivants : parmi les runs survivants, on retrouve surtout une dominance "
                                        f"**{top_survivor_dominance}**, un contexte **{top_survivor_context}**, "
                                        f"une session **{top_survivor_session}** et une signature récurrente "
                                        f"**{top_survivor_signature}**."
                                    )

                        st.markdown("**Top familles de runs**")

                        if (
                            "Signature run" in run_history_df.columns
                            and "Score global du run" in run_history_df.columns
                        ):
                            family_df = run_history_df.copy()

                            family_signature_col = (
                                "Signature courte"
                                if "Signature courte" in family_df.columns
                                else "Signature run"
                            )

                            family_df["Score global du run"] = pd.to_numeric(
                                family_df["Score global du run"],
                                errors="coerce"
                            )

                            if "Run survivant" in family_df.columns:
                                family_df["Run survivant flag"] = (
                                    family_df["Run survivant"].astype(str) == "Oui"
                                ).astype(int)
                            else:
                                family_df["Run survivant flag"] = 0

                            if "Statut global" not in family_df.columns:
                                family_df["Statut global"] = "N/A"

                            if "Timestamp" not in family_df.columns:
                                family_df["Timestamp"] = "N/A"

                            family_summary_df = (
                                family_df.groupby(family_signature_col, dropna=False)
                                .agg(
                                    Occurrences=(family_signature_col, "size"),
                                    Runs_survivants=("Run survivant flag", "sum"),
                                    Score_moyen=("Score global du run", "mean"),
                                    Meilleur_score=("Score global du run", "max"),
                                    Dernière_apparition=("Timestamp", "first"),
                                    Dernier_statut=("Statut global", "first")
                                )
                                .reset_index()
                            )

                            family_summary_df["Taux survie %"] = (
                                family_summary_df["Runs_survivants"]
                                / family_summary_df["Occurrences"]
                                * 100
                            ).round(1)

                            family_summary_df = family_summary_df.rename(columns={
                                family_signature_col: "Famille",
                                "Runs_survivants": "Runs survivants",
                                "Score_moyen": "Score moyen",
                                "Meilleur_score": "Meilleur score",
                                "Dernière_apparition": "Dernière apparition",
                                "Dernier_statut": "Dernier statut"
                            })

                            family_summary_df = family_summary_df.sort_values(
                                by=["Meilleur score", "Taux survie %", "Occurrences"],
                                ascending=[False, False, False]
                            ).reset_index(drop=True)

                            family_summary_display_df = family_summary_df[
                                [
                                    "Famille",
                                    "Occurrences",
                                    "Runs survivants",
                                    "Taux survie %",
                                    "Score moyen",
                                    "Meilleur score",
                                    "Dernier statut"
                                ]
                            ]

                            st.dataframe(
                                family_summary_display_df.head(8),
                                use_container_width=True
                            )

                            best_family_row = family_summary_df.iloc[0]
                            most_tested_family_row = family_summary_df.sort_values(
                                by=["Occurrences", "Meilleur score"],
                                ascending=[False, False]
                            ).reset_index(drop=True).iloc[0]

                            best_family_name = best_family_row["Famille"]
                            best_family_score = round(float(best_family_row["Meilleur score"]), 2)
                            best_family_survival_rate = best_family_row["Taux survie %"]

                            most_tested_family_name = most_tested_family_row["Famille"]
                            most_tested_family_occurrences = int(most_tested_family_row["Occurrences"])

                            if len(family_summary_df) == 1:
                                st.info(
                                    f"Lecture familles : pour l'instant, une seule famille de runs est suivie "
                                    f"(**{best_family_name}**). "
                                    f"C'est normal si tu explores encore un seul couloir."
                                )
                            elif best_family_name == most_tested_family_name:
                                st.info(
                                    f"Lecture familles : la famille la plus travaillée est aussi la plus prometteuse actuellement "
                                    f"(**{best_family_name}**), avec **{most_tested_family_occurrences} tests**, "
                                    f"un meilleur score de **{best_family_score}** et un taux de survie de "
                                    f"**{best_family_survival_rate}%**."
                                )
                            else:
                                st.info(
                                    f"Lecture familles : la famille la plus prometteuse actuellement est "
                                    f"**{best_family_name}** (meilleur score = **{best_family_score}**, "
                                    f"taux de survie = **{best_family_survival_rate}%**), "
                                    f"tandis que la plus testée est **{most_tested_family_name}** "
                                    f"avec **{most_tested_family_occurrences} occurrences**."
                                )

                        if (
                            "Run ID" in run_history_df.columns
                            and "Score global du run" in run_history_df.columns
                            and "Statut global" in run_history_df.columns
                        ):
                            history_chart_df = run_history_df.copy()

                            if "Timestamp_dt" in history_chart_df.columns:
                                history_chart_df = history_chart_df.sort_values(
                                    by="Timestamp_dt",
                                    ascending=True
                                )

                            fig_history = px.bar(
                                history_chart_df.tail(12),
                                x="Run ID",
                                y="Score global du run",
                                color="Statut global",
                                title="Score global des runs récents"
                            )

                            fig_history.update_layout(
                                xaxis_title="Run",
                                yaxis_title="Score global"
                            )

                            st.plotly_chart(fig_history, use_container_width=True, key="history_scores_chart")

                        if (
                            "Run ID" in run_history_df.columns
                            and "Score global du run" in run_history_df.columns
                            and "Statut global" in run_history_df.columns
                        ):
                            history_chart_df = run_history_df.copy()
                        st.markdown("**Récurrences sur runs survivants**")

                        if "Run survivant" in run_history_df.columns:
                            survivor_history_df = run_history_df[
                                run_history_df["Run survivant"].astype(str) == "Oui"
                            ].copy()
                        else:
                            survivor_history_df = pd.DataFrame()

                        if survivor_history_df.empty:
                            st.info(
                                "Aucune lecture spécifique des runs survivants n'est disponible pour le moment."
                            )
                        else:
                            survivor_recurrence_rows = []

                            def add_survivor_recurrence_row(source_df, column_name, label_name):
                                if column_name not in source_df.columns:
                                    return "N/A", 0

                                series = (
                                    source_df[column_name]
                                    .dropna()
                                    .astype(str)
                                    .str.strip()
                                )
                                series = series[series != ""]

                                if series.empty:
                                    return "N/A", 0

                                counts = series.value_counts()
                                top_value = counts.index[0]
                                top_count = int(counts.iloc[0])

                                survivor_recurrence_rows.append({
                                    "Lecture": label_name,
                                    "Élément dominant": top_value,
                                    "Occurrences": top_count
                                })

                                return top_value, top_count

                            top_survivor_dominance, top_survivor_dominance_count = add_survivor_recurrence_row(
                                survivor_history_df, "Dominance", "Dominance survivante"
                            )
                            top_survivor_context, top_survivor_context_count = add_survivor_recurrence_row(
                                survivor_history_df, "Best Context", "Contexte survivant"
                            )
                            top_survivor_session, top_survivor_session_count = add_survivor_recurrence_row(
                                survivor_history_df, "Best Session", "Session survivante"
                            )

                            survivor_signature_column = (
                                "Signature courte"
                                if "Signature courte" in survivor_history_df.columns
                                else "Signature run"
                            )

                            top_survivor_signature, top_survivor_signature_count = add_survivor_recurrence_row(
                                survivor_history_df, survivor_signature_column, "Signature survivante"
                            )

                            surv_col1, surv_col2, surv_col3, surv_col4 = st.columns(4)

                            surv_col1.metric(
                                "Dominance survivante",
                                top_survivor_dominance,
                                delta=f"{top_survivor_dominance_count} run(s)" if top_survivor_dominance_count > 0 else None
                            )
                            surv_col2.metric(
                                "Contexte survivant",
                                top_survivor_context,
                                delta=f"{top_survivor_context_count} run(s)" if top_survivor_context_count > 0 else None
                            )
                            surv_col3.metric(
                                "Session survivante",
                                top_survivor_session,
                                delta=f"{top_survivor_session_count} run(s)" if top_survivor_session_count > 0 else None
                            )
                            surv_col4.metric(
                                "Signature survivante",
                                top_survivor_signature,
                                delta=f"{top_survivor_signature_count} run(s)" if top_survivor_signature_count > 0 else None
                            )

                            if survivor_recurrence_rows:
                                survivor_recurrence_df = pd.DataFrame(survivor_recurrence_rows)
                                st.dataframe(survivor_recurrence_df, use_container_width=True)

                                if len(survivor_history_df) == 1:
                                    st.info(
                                        "Lecture survivants : un seul run survivant est enregistré pour l'instant. "
                                        "Cette vue deviendra plus parlante quand plusieurs survivants auront été accumulés."
                                    )
                                else:
                                    st.info(
                                        f"Lecture survivants : parmi les runs survivants, on retrouve surtout une dominance "
                                        f"**{top_survivor_dominance}**, un contexte **{top_survivor_context}**, "
                                        f"une session **{top_survivor_session}** et une signature récurrente "
                                        f"**{top_survivor_signature}**."
                                    )
                        st.markdown("**Palmarès des signatures testées**")
                        st.markdown("**Récurrences inter-runs**")

                        recurrence_rows = []

                        def add_recurrence_row(source_df, column_name, label_name):
                            if column_name not in source_df.columns:
                                return "N/A", 0

                            series = (
                                source_df[column_name]
                                .dropna()
                                .astype(str)
                                .str.strip()
                            )
                            series = series[series != ""]

                            if series.empty:
                                return "N/A", 0

                            counts = series.value_counts()
                            top_value = counts.index[0]
                            top_count = int(counts.iloc[0])

                            recurrence_rows.append({
                                "Lecture": label_name,
                                "Élément le plus fréquent": top_value,
                                "Occurrences": top_count
                            })

                            return top_value, top_count

                        top_status_value, top_status_count = add_recurrence_row(
                            run_history_df, "Statut global", "Statut global"
                        )
                        top_dominance_value, top_dominance_count = add_recurrence_row(
                            run_history_df, "Dominance", "Dominance"
                        )
                        top_context_value, top_context_count = add_recurrence_row(
                            run_history_df, "Best Context", "Contexte dominant"
                        )
                        top_session_value, top_session_count = add_recurrence_row(
                            run_history_df, "Best Session", "Session dominante"
                        )

                        rec_col1, rec_col2, rec_col3, rec_col4 = st.columns(4)

                        rec_col1.metric(
                            "Statut le plus fréquent",
                            top_status_value,
                            delta=f"{top_status_count} run(s)" if top_status_count > 0 else None
                        )
                        rec_col2.metric(
                            "Dominance la plus fréquente",
                            top_dominance_value,
                            delta=f"{top_dominance_count} run(s)" if top_dominance_count > 0 else None
                        )
                        rec_col3.metric(
                            "Contexte le plus fréquent",
                            top_context_value,
                            delta=f"{top_context_count} run(s)" if top_context_count > 0 else None
                        )
                        rec_col4.metric(
                            "Session la plus fréquente",
                            top_session_value,
                            delta=f"{top_session_count} run(s)" if top_session_count > 0 else None
                        )

                        if recurrence_rows:
                            recurrence_summary_df = pd.DataFrame(recurrence_rows)
                            st.dataframe(recurrence_summary_df, use_container_width=True)

                            if total_runs == 1:
                                st.info(
                                    "Lecture récurrences : avec un seul run enregistré, cette vue sert surtout de point de départ. "
                                    "Elle deviendra beaucoup plus utile quand plusieurs familles de runs auront été testées."
                                )
                            else:
                                st.info(
                                    f"Lecture récurrences : pour l'instant, les runs reviennent surtout avec un statut "
                                    f"**{top_status_value}**, une dominance **{top_dominance_value}**, "
                                    f"un contexte récurrent **{top_context_value}** et une session récurrente "
                                    f"**{top_session_value}**."
                                )

                        if (
                            "Signature run" in run_history_df.columns
                            and "Score global du run" in run_history_df.columns
                            and "Statut global" in run_history_df.columns
                        ):
                            signature_summary_df = (
                                run_history_df.groupby("Signature run", dropna=False)
                                .agg(
                                    Occurrences=("Signature run", "size"),
                                    Meilleur_score=("Score global du run", "max"),
                                    Dernière_apparition=("Timestamp", "first"),
                                    Dernier_statut=("Statut global", "first")
                                )
                                .reset_index()
                            )

                            signature_summary_df["Signature courte"] = (
                                signature_summary_df["Signature run"]
                                .astype(str)
                                .str.replace(" | Sess=", " | ", regex=False)
                                .str.replace(" | TF=", " | ", regex=False)
                                .str.replace(" | VOL=", " | ", regex=False)
                                .str.replace(" | REG=", " | ", regex=False)
                            )

                            signature_summary_df = signature_summary_df.rename(columns={
                                "Meilleur_score": "Meilleur score",
                                "Dernière_apparition": "Dernière apparition",
                                "Dernier_statut": "Dernier statut"
                            })

                            signature_summary_df = signature_summary_df.sort_values(
                                by=["Meilleur score", "Occurrences"],
                                ascending=[False, False]
                            ).reset_index(drop=True)

                            signature_summary_display_df = signature_summary_df[
                                [
                                    "Signature courte",
                                    "Occurrences",
                                    "Meilleur score",
                                    "Dernière apparition",
                                    "Dernier statut"
                                ]
                            ].rename(columns={
                                "Signature courte": "Signature"
                            })

                            st.dataframe(
                                signature_summary_display_df.head(8),
                                use_container_width=True
                            )

                            top_signature_row = signature_summary_df.iloc[0]
                            top_signature_name = top_signature_row["Signature courte"]
                            top_signature_occurrences = int(top_signature_row["Occurrences"])
                            top_signature_score = round(float(top_signature_row["Meilleur score"]), 2)

                            if len(signature_summary_df) == 1:
                                st.info(
                                    f"Lecture signatures : pour l'instant, une seule signature domine l'historique "
                                    f"(**{top_signature_name}**, score max = {top_signature_score}). "
                                    f"C'est normal si tu explores encore un seul couloir."
                                )
                            elif top_signature_occurrences >= 3:
                                st.info(
                                    f"Lecture signatures : la signature la plus travaillée actuellement est "
                                    f"**{top_signature_name}** avec **{top_signature_occurrences} occurrences** "
                                    f"et un meilleur score de **{top_signature_score}**."
                                )
                            else:
                                st.info(
                                    f"Lecture signatures : tu commences à diversifier les tests. "
                                    f"La meilleure signature actuelle est **{top_signature_name}** "
                                    f"(score max = {top_signature_score})."
                                )

                        if (
                            "Run ID" in run_history_df.columns
                            and "Score global du run" in run_history_df.columns
                            and "Statut global" in run_history_df.columns
                        ):
                            history_chart_df = run_history_df.copy()

                            if "Timestamp_dt" in history_chart_df.columns:
                                history_chart_df = history_chart_df.sort_values(
                                    by="Timestamp_dt",
                                    ascending=True
                                )

                            fig_history = px.bar(
                                history_chart_df.tail(12),
                                x="Run ID",
                                y="Score global du run",
                                color="Statut global",
                                title="Score global des runs récents"
                            )

                            fig_history.update_layout(
                                xaxis_title="Run",
                                yaxis_title="Score global"
                            )

                            st.plotly_chart(fig_history, use_container_width=True)

                        history_display_columns = [
                            "Run ID",
                            "Timestamp",
                            "Statut global",
                            "Score global du run",
                            "Signature courte",
                            "Dominance",
                            "Robustesse multi-splits",
                            "Splits survécus"
                        ]

                        available_history_columns = [
                            col for col in history_display_columns if col in run_history_df.columns
                        ]

                        run_history_display_df = run_history_df[available_history_columns].copy()

                        run_history_display_df = run_history_display_df.rename(columns={
                            "Signature courte": "Signature"
                        })

                        st.dataframe(run_history_display_df.head(10), use_container_width=True)
                        st.caption(
                            "Ce tableau affiche les 10 runs les plus récents avec leur signature compacte, "
                            "pour repérer immédiatement les répétitions et les vrais nouveaux tests."
                        )

                        st.markdown("**Gestion de l'historique**")
                        hist_action_col1, hist_action_col2 = st.columns(2)

                        with hist_action_col1:
                            if st.button("Réinitialiser l'historique en mémoire", key="reset_history_memory_button"):
                                st.session_state.run_history = []
                                st.success("Historique en mémoire réinitialisé.")
                                st.rerun()

                        with hist_action_col2:
                            if st.button("Supprimer l'historique + le CSV", key="reset_history_csv_button"):
                                st.session_state.run_history = []
                                if os.path.exists(RUN_HISTORY_FILE):
                                    os.remove(RUN_HISTORY_FILE)
                                st.success("Historique en mémoire et fichier CSV supprimés.")
                                st.rerun()

                    else:
                        st.info("Aucun run enregistré pour le moment.")

                        st.markdown("**Gestion de l'historique**")
                        empty_hist_col1, empty_hist_col2 = st.columns(2)

                        with empty_hist_col1:
                            if st.button("Réinitialiser l'historique vide", key="reset_empty_history_button"):
                                st.session_state.run_history = []
                                st.success("Historique vide confirmé.")
                                st.rerun()

                        with empty_hist_col2:
                            if st.button("Supprimer le CSV historique", key="delete_empty_history_csv_button"):
                                if os.path.exists(RUN_HISTORY_FILE):
                                    os.remove(RUN_HISTORY_FILE)
                                    st.success("Fichier CSV historique supprimé.")
                                else:
                                    st.info("Aucun fichier CSV historique à supprimer.")
                                st.rerun()

                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Nombre de trades", metrics["number_of_trades"])
                    col2.metric("Trades gagnants", metrics["winning_trades"])
                    col3.metric("Trades perdants", metrics["losing_trades"])
                    col4.metric("Breakeven", metrics["breakeven_trades"])

                    col5, col6, col7 = st.columns(3)
                    col5.metric("Win Rate %", metrics["win_rate"])
                    col6.metric("Total R", metrics["total_pnl"])
                    col7.metric("R moyen / trade", metrics["average_return"])

                    col8, col9, col10, col11 = st.columns(4)
                    col8.metric("Gain moyen (R)", metrics["average_gain"])
                    col9.metric("Perte moyenne (R)", metrics["average_loss"])
                    col10.metric("Expectancy (R)", metrics["expectancy"])
                    col11.metric("Max Drawdown (R)", metrics["max_drawdown"])

                    col12, col13, col14 = st.columns(3)
                    col12.metric("Profit Factor", metrics["profit_factor"])
                    col13.metric("Max Winning Streak", metrics["max_winning_streak"])
                    col14.metric("Max Losing Streak", metrics["max_losing_streak"])

                    st.subheader("Equity Curve")

                    fig = px.line(
                        equity_df,
                        x="Step",
                        y="Equity",
                        markers=True,
                        title="Évolution du capital"
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    st.subheader("Données de l'equity curve")
                    st.dataframe(equity_df)
else:
    st.info("Aucun fichier chargé pour le moment.")