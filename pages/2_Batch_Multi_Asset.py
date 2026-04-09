from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Batch Multi-Asset", layout="wide")

BASE_DIR = Path.home() / "Desktop" / "Trading Lab"
BATCH_RESULTS_DIR = BASE_DIR / "batch_results"
MASTER_SUMMARY_FILE = BATCH_RESULTS_DIR / "master_batch_summary.csv"

st.title("Batch Multi-Asset")
st.caption("Lecture centralisée des campagnes batch multi-actifs du lab.")

if not MASTER_SUMMARY_FILE.exists():
    st.warning("Aucun master_batch_summary.csv trouvé pour le moment.")
    st.stop()

master_df = pd.read_csv(MASTER_SUMMARY_FILE)

if master_df.empty:
    st.warning("Le master_batch_summary.csv est vide.")
    st.stop()

st.subheader("Filtres de lecture")

working_df = master_df.copy()

preset_options = ["Tous"] + sorted([str(x) for x in working_df["preset"].dropna().unique()]) if "preset" in working_df.columns else ["Tous"]
selected_preset = st.selectbox("Preset", preset_options, index=0)

asset_options = ["Tous"] + sorted([str(x) for x in working_df["asset"].dropna().unique()]) if "asset" in working_df.columns else ["Tous"]
selected_asset = st.selectbox("Actif", asset_options, index=0)

latest_only = st.checkbox("Afficher seulement la dernière campagne par preset", value=True)

if selected_preset != "Tous" and "preset" in working_df.columns:
    working_df = working_df[working_df["preset"] == selected_preset].copy()

if selected_asset != "Tous" and "asset" in working_df.columns:
    working_df = working_df[working_df["asset"] == selected_asset].copy()

if latest_only and "timestamp" in working_df.columns and "preset" in working_df.columns:
    working_df["timestamp"] = pd.to_datetime(working_df["timestamp"], errors="coerce")
    working_df = (
        working_df.sort_values("timestamp", ascending=False)
        .groupby(["preset", "asset"], as_index=False)
        .head(1)
        .reset_index(drop=True)
    )

if "asset" in working_df.columns:
    def classify_asset_group(asset_name):
        asset_name = str(asset_name).upper()
        if "JPY" in asset_name:
            return "JPY"
        if asset_name == "XAUUSD":
            return "XAUUSD"
        return "Non-JPY FX"

    working_df["asset_group"] = working_df["asset"].apply(classify_asset_group)

if "profitable_combo_count" in working_df.columns and "combo_count" in working_df.columns:
    working_df["profitable_ratio"] = (
        pd.to_numeric(working_df["profitable_combo_count"], errors="coerce")
        / pd.to_numeric(working_df["combo_count"], errors="coerce")
    ).round(4)

if "best_expectancy" in working_df.columns and "top5_avg_expectancy" in working_df.columns:
    working_df["top_gap_expectancy"] = (
        pd.to_numeric(working_df["best_expectancy"], errors="coerce")
        - pd.to_numeric(working_df["top5_avg_expectancy"], errors="coerce")
    ).round(4)

if all(col in working_df.columns for col in ["best_expectancy", "top5_avg_expectancy", "profitable_ratio", "best_max_dd"]):
    working_df["quality_score"] = (
        pd.to_numeric(working_df["best_expectancy"], errors="coerce") * 100
        + pd.to_numeric(working_df["top5_avg_expectancy"], errors="coerce") * 80
        + pd.to_numeric(working_df["profitable_ratio"], errors="coerce") * 40
        - abs(pd.to_numeric(working_df["best_max_dd"], errors="coerce")) * 2
        - abs(pd.to_numeric(working_df.get("top_gap_expectancy", 0), errors="coerce")) * 50
    ).round(2)

st.subheader("Vue filtrée du batch summary")

export_preset_label = selected_preset.replace(" ", "_") if selected_preset else "Tous"
export_asset_label = selected_asset.replace(" ", "_") if selected_asset else "Tous"

filtered_csv_data = working_df.to_csv(index=False)

filtered_json_data = working_df.to_json(
    orient="records",
    force_ascii=False,
    indent=2
)

col_export_1, col_export_2 = st.columns(2)

with col_export_1:
    st.download_button(
        label="Télécharger la vue filtrée en CSV",
        data=filtered_csv_data,
        file_name=f"batch_filtre_{export_preset_label}_{export_asset_label}.csv",
        mime="text/csv"
    )

with col_export_2:
    st.download_button(
        label="Télécharger la vue filtrée en JSON",
        data=filtered_json_data,
        file_name=f"batch_filtre_{export_preset_label}_{export_asset_label}.json",
        mime="application/json"
    )

st.dataframe(working_df, use_container_width=True)
if "asset_group" in working_df.columns:
    st.subheader("Synthèse par groupe d’actifs")

    group_cols = []
    for col in [
        "best_expectancy",
        "top5_avg_expectancy",
        "oos_expectancy",
        "quality_score",
        "profitable_combo_count",
        "profitable_ratio",
        "multi_split_ratio",
    ]:
        if col in working_df.columns:
            group_cols.append(col)

    if group_cols:
        group_summary_df = (
            working_df.groupby("asset_group")[group_cols]
            .mean(numeric_only=True)
            .round(4)
            .reset_index()
        )
        st.dataframe(group_summary_df, use_container_width=True)

if "best_expectancy" in working_df.columns:
    st.subheader("Classement par best expectancy")
    expectancy_df = working_df.sort_values(by="best_expectancy", ascending=False).reset_index(drop=True)
    st.dataframe(expectancy_df, use_container_width=True)

if "best_total_r" in working_df.columns:
    st.subheader("Classement par best total R")
    total_r_df = working_df.sort_values(by="best_total_r", ascending=False).reset_index(drop=True)
    st.dataframe(total_r_df, use_container_width=True)

if "best_max_dd" in working_df.columns:
    st.subheader("Classement par best max drawdown")
    dd_df = working_df.sort_values(by="best_max_dd", ascending=False).reset_index(drop=True)
    st.dataframe(dd_df, use_container_width=True)

if "quality_score" in working_df.columns:
    st.subheader("Classement par quality score")
    quality_df = working_df.sort_values(by="quality_score", ascending=False).reset_index(drop=True)
    st.dataframe(quality_df, use_container_width=True)
if "oos_expectancy" in working_df.columns and not working_df["oos_expectancy"].isna().all():
    st.subheader("Classement par OOS expectancy")
    oos_expectancy_df = working_df.sort_values(by="oos_expectancy", ascending=False).reset_index(drop=True)
    st.dataframe(oos_expectancy_df, use_container_width=True)

if "oos_total_r" in working_df.columns and not working_df["oos_total_r"].isna().all():
    st.subheader("Classement par OOS total R")
    oos_total_r_df = working_df.sort_values(by="oos_total_r", ascending=False).reset_index(drop=True)
    st.dataframe(oos_total_r_df, use_container_width=True)

if "delta_is_oos_expectancy" in working_df.columns and not working_df["delta_is_oos_expectancy"].isna().all():
    st.subheader("Classement par stabilité IS vs OOS expectancy")
    oos_stability_df = working_df.sort_values(by="delta_is_oos_expectancy", ascending=True).reset_index(drop=True)
    st.dataframe(oos_stability_df, use_container_width=True)

if "multi_split_ratio" in working_df.columns and not working_df["multi_split_ratio"].isna().all():
    st.subheader("Classement par multi-split ratio")
    multi_split_df = working_df.sort_values(by="multi_split_ratio", ascending=False).reset_index(drop=True)
    st.dataframe(multi_split_df, use_container_width=True)

if "multi_split_status" in working_df.columns and not working_df["multi_split_status"].isna().all():
    st.subheader("Vue multi-split status")
    multi_split_status_df = working_df.sort_values(
        by=["multi_split_ratio", "best_expectancy"],
        ascending=[False, False]
    ).reset_index(drop=True)
    st.dataframe(multi_split_status_df, use_container_width=True)
if "cost_expectancy" in working_df.columns and not working_df["cost_expectancy"].isna().all():
    st.subheader("Classement par cost expectancy")
    cost_expectancy_df = working_df.sort_values(by="cost_expectancy", ascending=False).reset_index(drop=True)
    st.dataframe(cost_expectancy_df, use_container_width=True)

if "delta_cost_expectancy" in working_df.columns and not working_df["delta_cost_expectancy"].isna().all():
    st.subheader("Classement par résistance aux coûts")
    cost_resistance_df = working_df.sort_values(by="delta_cost_expectancy", ascending=True).reset_index(drop=True)
    st.dataframe(cost_resistance_df, use_container_width=True)
if "best_trades_per_year" in working_df.columns and not working_df["best_trades_per_year"].isna().all():
    st.subheader("Classement par best trades par an")
    best_trades_year_df = working_df.sort_values(by="best_trades_per_year", ascending=False).reset_index(drop=True)
    st.dataframe(best_trades_year_df, use_container_width=True)

if "oos_trades_per_year" in working_df.columns and not working_df["oos_trades_per_year"].isna().all():
    st.subheader("Classement par OOS trades par an")
    oos_trades_year_df = working_df.sort_values(by="oos_trades_per_year", ascending=False).reset_index(drop=True)
    st.dataframe(oos_trades_year_df, use_container_width=True)

if "cost_trades_per_year" in working_df.columns and not working_df["cost_trades_per_year"].isna().all():
    st.subheader("Classement par cost trades par an")
    cost_trades_year_df = working_df.sort_values(by="cost_trades_per_year", ascending=False).reset_index(drop=True)
    st.dataframe(cost_trades_year_df, use_container_width=True)

if "cost_expectancy" in working_df.columns and not working_df["cost_expectancy"].isna().all():
    cost_row = working_df.sort_values("cost_expectancy", ascending=False).iloc[0]
    st.info(
        f"Actif le plus résistant aux coûts : {cost_row['asset']} "
        f"(cost expectancy = {cost_row['cost_expectancy']})"
    )

if "delta_cost_expectancy" in working_df.columns and not working_df["delta_cost_expectancy"].isna().all():
    low_cost_penalty_row = working_df.sort_values("delta_cost_expectancy", ascending=True).iloc[0]
    st.info(
        f"Actif le moins pénalisé par les coûts : {low_cost_penalty_row['asset']} "
        f"(delta cost expectancy = {low_cost_penalty_row['delta_cost_expectancy']})"
    )

if "best_trades_per_year" in working_df.columns and not working_df["best_trades_per_year"].isna().all():
    trades_year_row = working_df.sort_values("best_trades_per_year", ascending=False).iloc[0]
    st.info(
        f"Actif le plus exploitable en fréquence : {trades_year_row['asset']} "
        f"({trades_year_row['best_trades_per_year']} trades/an sur le meilleur set)"
    )

    



st.subheader("Lecture automatique simple")

best_expectancy_asset = None
best_total_r_asset = None
best_dd_asset = None
best_trades_asset = None

if "best_expectancy" in working_df.columns and not working_df["best_expectancy"].isna().all():
    best_expectancy_row = working_df.sort_values(by="best_expectancy", ascending=False).iloc[0]
    best_expectancy_asset = best_expectancy_row["asset"]

if "best_total_r" in working_df.columns and not working_df["best_total_r"].isna().all():
    best_total_r_row = working_df.sort_values(by="best_total_r", ascending=False).iloc[0]
    best_total_r_asset = best_total_r_row["asset"]

if "best_max_dd" in working_df.columns and not working_df["best_max_dd"].isna().all():
    best_dd_row = working_df.sort_values(by="best_max_dd", ascending=False).iloc[0]
    best_dd_asset = best_dd_row["asset"]

if "best_trades" in working_df.columns and not working_df["best_trades"].isna().all():
    best_trades_row = working_df.sort_values(by="best_trades", ascending=False).iloc[0]
    best_trades_asset = best_trades_row["asset"]

if best_expectancy_asset is not None:
    st.info(f"Actif le moins mauvais en best expectancy : {best_expectancy_asset}")

if best_total_r_asset is not None:
    st.info(f"Actif le moins mauvais en best total R : {best_total_r_asset}")

if best_dd_asset is not None:
    st.info(f"Actif le plus défensif en best max drawdown : {best_dd_asset}")

if best_trades_asset is not None:
    st.info(f"Actif avec le plus de trades sur le meilleur set : {best_trades_asset}")
st.subheader("Fréquence des signatures")

if "best_params_signature" in working_df.columns and not working_df["best_params_signature"].isna().all():
    clean_signature_series = working_df["best_params_signature"].dropna()
    clean_signature_series = clean_signature_series[clean_signature_series.astype(str).str.lower() != "none"]

    if not clean_signature_series.empty:
        signature_freq_df = (
            clean_signature_series
            .value_counts(dropna=False)
            .reset_index()
        )
        signature_freq_df.columns = ["best_params_signature", "occurrences"]
        st.dataframe(signature_freq_df, use_container_width=True)

        top_signature = signature_freq_df.iloc[0]["best_params_signature"]
        top_signature_count = int(signature_freq_df.iloc[0]["occurrences"])
        st.info(f"Signature la plus fréquente : {top_signature} | occurrences = {top_signature_count}")
st.subheader("Fréquence des best trend impact values")

if "best_trend_impact_value" in working_df.columns and not working_df["best_trend_impact_value"].isna().all():
    clean_trend_series = working_df["best_trend_impact_value"].dropna()
    clean_trend_series = clean_trend_series[clean_trend_series.astype(str).str.lower() != "none"]

    if not clean_trend_series.empty:
        trend_freq_df = (
            clean_trend_series
            .value_counts(dropna=False)
            .reset_index()
        )
        trend_freq_df.columns = ["best_trend_impact_value", "occurrences"]
        st.dataframe(trend_freq_df, use_container_width=True)

        top_trend_value = trend_freq_df.iloc[0]["best_trend_impact_value"]
        top_trend_count = int(trend_freq_df.iloc[0]["occurrences"])
        st.info(f"Trend lookback d’impact le plus fréquent : {top_trend_value} | occurrences = {top_trend_count}")
st.subheader("Fréquence des best RR impact values")

if "best_rr_impact_value" in working_df.columns and not working_df["best_rr_impact_value"].isna().all():
    clean_rr_series = working_df["best_rr_impact_value"].dropna()
    clean_rr_series = clean_rr_series[clean_rr_series.astype(str).str.lower() != "none"]

    if not clean_rr_series.empty:
        rr_freq_df = (
            clean_rr_series
            .value_counts(dropna=False)
            .reset_index()
        )
        rr_freq_df.columns = ["best_rr_impact_value", "occurrences"]
        st.dataframe(rr_freq_df, use_container_width=True)

        top_rr_value = rr_freq_df.iloc[0]["best_rr_impact_value"]
        top_rr_count = int(rr_freq_df.iloc[0]["occurrences"])
        st.info(f"RR d’impact le plus fréquent : {top_rr_value} | occurrences = {top_rr_count}")

st.subheader("Fréquence des dominantes top 10")

top10_columns = [
    ("top10_dominant_tlb", "TLB dominant top 10"),
    ("top10_dominant_rr", "RR dominant top 10"),
    ("top10_dominant_conf", "CONF dominant top 10"),
    ("top10_dominant_pb", "PB dominant top 10"),
    ("top10_dominant_mta", "MTA dominant top 10"),
    ("top10_dominant_depth", "DEPTH dominant top 10"),
]

for col_name, label in top10_columns:
    if col_name in working_df.columns and not working_df[col_name].isna().all():
        clean_series = working_df[col_name].dropna()
        clean_series = clean_series[clean_series.astype(str).str.lower() != "none"]

        if not clean_series.empty:
            freq_df = clean_series.value_counts(dropna=False).reset_index()
            freq_df.columns = [col_name, "occurrences"]

            st.markdown(f"**{label}**")
            st.dataframe(freq_df, use_container_width=True)

            top_value = freq_df.iloc[0][col_name]
            top_count = int(freq_df.iloc[0]["occurrences"])
            st.info(f"{label} le plus fréquent : {top_value} | occurrences = {top_count}")

st.subheader("Lecture automatique avancée")

if not working_df.empty:
    local_df = working_df.copy()

    if "best_expectancy" in local_df.columns:
        promising_row = local_df.sort_values("best_expectancy", ascending=False).iloc[0]
        st.info(
            f"Actif le plus prometteur en best expectancy : {promising_row['asset']} "
            f"({promising_row['best_expectancy']})"
        )

    if "quality_score" in local_df.columns:
        quality_row = local_df.sort_values("quality_score", ascending=False).iloc[0]
        st.info(
            f"Actif le plus solide en quality score : {quality_row['asset']} "
            f"({quality_row['quality_score']})"
        )

    if "oos_expectancy" in local_df.columns and not local_df["oos_expectancy"].isna().all():
        robust_row = local_df.sort_values("oos_expectancy", ascending=False).iloc[0]
        st.info(
            f"Actif le plus robuste en OOS expectancy : {robust_row['asset']} "
            f"({robust_row['oos_expectancy']})"
        )

    if "delta_is_oos_expectancy" in local_df.columns and not local_df["delta_is_oos_expectancy"].isna().all():
        stable_row = local_df.sort_values("delta_is_oos_expectancy", ascending=True).iloc[0]
        st.info(
            f"Actif le plus stable entre IS et OOS : {stable_row['asset']} "
            f"(delta expectancy = {stable_row['delta_is_oos_expectancy']})"
        )

    if "multi_split_ratio" in local_df.columns and not local_df["multi_split_ratio"].isna().all():
        multisplit_row = local_df.sort_values("multi_split_ratio", ascending=False).iloc[0]
        st.info(
            f"Actif le plus solide en multi-splits : {multisplit_row['asset']} "
            f"({multisplit_row['multi_split_surviving_count']}/{multisplit_row['multi_split_total_count']}, "
            f"ratio = {multisplit_row['multi_split_ratio']}, statut = {multisplit_row['multi_split_status']})"
        )

    if "best_max_dd" in local_df.columns:
        defensive_row = local_df.sort_values("best_max_dd", ascending=False).iloc[0]
        st.info(
            f"Actif le plus défensif : {defensive_row['asset']} "
            f"({defensive_row['best_max_dd']})"
        )

    if "profitable_combo_count" in local_df.columns:
        combo_row = local_df.sort_values("profitable_combo_count", ascending=False).iloc[0]
        st.info(
            f"Actif avec le plus de combinaisons profitables : {combo_row['asset']} "
            f"({combo_row['profitable_combo_count']})"
        )

st.subheader("Alertes simples")
st.subheader("Lecture synthétique des familles top 10")

family_messages = []

family_map = [
    ("top10_dominant_tlb", "TLB"),
    ("top10_dominant_rr", "RR"),
    ("top10_dominant_conf", "CONF"),
    ("top10_dominant_pb", "PB"),
    ("top10_dominant_mta", "MTA"),
    ("top10_dominant_depth", "DEPTH"),
]

for col_name, short_name in family_map:
    if col_name in working_df.columns and not working_df[col_name].isna().all():
        clean_series = working_df[col_name].dropna()
        clean_series = clean_series[clean_series.astype(str).str.lower() != "none"]

        if not clean_series.empty:
            dominant_value = clean_series.mode().iloc[0]
            dominant_count = int((clean_series == dominant_value).sum())
            family_messages.append(f"{short_name} dominant top 10 = {dominant_value} ({dominant_count} occurrences)")

if family_messages:
    for msg in family_messages:
        st.info(msg)
st.subheader("Lecture par groupes d’actifs")

if "asset_group" in working_df.columns and not working_df.empty:
    group_read_df = working_df.copy()

    if "best_expectancy" in group_read_df.columns:
        best_group_expectancy = (
            group_read_df.groupby("asset_group")["best_expectancy"]
            .mean()
            .sort_values(ascending=False)
        )
        if not best_group_expectancy.empty:
            st.info(
                f"Groupe le moins mauvais en best expectancy : "
                f"{best_group_expectancy.index[0]} ({round(best_group_expectancy.iloc[0], 4)})"
            )

    if "quality_score" in group_read_df.columns:
        best_group_quality = (
            group_read_df.groupby("asset_group")["quality_score"]
            .mean()
            .sort_values(ascending=False)
        )
        if not best_group_quality.empty:
            st.info(
                f"Groupe le plus solide en quality score : "
                f"{best_group_quality.index[0]} ({round(best_group_quality.iloc[0], 2)})"
            )

    if "profitable_combo_count" in group_read_df.columns:
        best_group_profitable = (
            group_read_df.groupby("asset_group")["profitable_combo_count"]
            .mean()
            .sort_values(ascending=False)
        )
        if not best_group_profitable.empty:
            st.info(
                f"Groupe avec le plus de combinaisons profitables : "
                f"{best_group_profitable.index[0]} ({round(best_group_profitable.iloc[0], 2)})"
            )

st.subheader("Synthèse finale de campagne")

if not working_df.empty:
    final_df = working_df.copy()

    if "quality_score" in final_df.columns and not final_df["quality_score"].isna().all():
        final_best_row = final_df.sort_values("quality_score", ascending=False).iloc[0]
        st.success(
            f"Meilleur actif global actuel : {final_best_row['asset']} "
            f"| quality score = {final_best_row['quality_score']} "
            f"| best expectancy = {final_best_row.get('best_expectancy', 'N/A')} "
            f"| best total R = {final_best_row.get('best_total_r', 'N/A')}"
        )

    if "oos_expectancy" in final_df.columns and not final_df["oos_expectancy"].isna().all():
        final_oos_row = final_df.sort_values("oos_expectancy", ascending=False).iloc[0]
        st.info(
            f"Meilleur actif OOS : {final_oos_row['asset']} "
            f"| oos expectancy = {final_oos_row['oos_expectancy']} "
            f"| delta IS/OOS = {final_oos_row.get('delta_is_oos_expectancy', 'N/A')}"
        )

    if "multi_split_ratio" in final_df.columns and not final_df["multi_split_ratio"].isna().all():
        final_ms_row = final_df.sort_values("multi_split_ratio", ascending=False).iloc[0]
        st.info(
            f"Meilleur actif multi-split : {final_ms_row['asset']} "
            f"| ratio = {final_ms_row['multi_split_ratio']} "
            f"| statut = {final_ms_row.get('multi_split_status', 'N/A')}"
        )

    if "cost_expectancy" in final_df.columns and not final_df["cost_expectancy"].isna().all():
        final_cost_row = final_df.sort_values("cost_expectancy", ascending=False).iloc[0]
        st.info(
            f"Meilleur actif sous coûts : {final_cost_row['asset']} "
            f"| cost expectancy = {final_cost_row['cost_expectancy']} "
            f"| delta coût = {final_cost_row.get('delta_cost_expectancy', 'N/A')}"
        )

    if "asset_group" in final_df.columns and "quality_score" in final_df.columns:
        final_group_df = (
            final_df.groupby("asset_group")["quality_score"]
            .mean()
            .sort_values(ascending=False)
        )
        if not final_group_df.empty:
            st.info(
                f"Groupe dominant actuel : {final_group_df.index[0]} "
                f"| quality score moyen = {round(final_group_df.iloc[0], 2)}"
            )

    family_summary = []

    for col_name, label in [
        ("top10_dominant_tlb", "TLB"),
        ("top10_dominant_rr", "RR"),
        ("top10_dominant_conf", "CONF"),
        ("top10_dominant_pb", "PB"),
        ("top10_dominant_mta", "MTA"),
        ("top10_dominant_depth", "DEPTH"),
    ]:
        if col_name in final_df.columns and not final_df[col_name].isna().all():
            clean_series = final_df[col_name].dropna()
            clean_series = clean_series[clean_series.astype(str).str.lower() != "none"]
            if not clean_series.empty:
                dominant_value = clean_series.mode().iloc[0]
                family_summary.append(f"{label}={dominant_value}")

    if family_summary:
        st.success("Familles dominantes finales : " + " | ".join(family_summary))

    fragile_messages = []

    for _, row in final_df.iterrows():
        asset = row["asset"] if "asset" in row else "N/A"

        try:
            best_exp = float(row["best_expectancy"]) if "best_expectancy" in row and pd.notna(row["best_expectancy"]) else None
            oos_exp = float(row["oos_expectancy"]) if "oos_expectancy" in row and pd.notna(row["oos_expectancy"]) else None
            ms_ratio = float(row["multi_split_ratio"]) if "multi_split_ratio" in row and pd.notna(row["multi_split_ratio"]) else None
            cost_delta = float(row["delta_cost_expectancy"]) if "delta_cost_expectancy" in row and pd.notna(row["delta_cost_expectancy"]) else None
        except Exception:
            continue

        local_flags = []

        if best_exp is not None and oos_exp is not None and best_exp > 0 and oos_exp < 0:
            local_flags.append("OOS négatif")

        if ms_ratio is not None and ms_ratio < 0.5:
            local_flags.append("multi-split faible")

        if cost_delta is not None and cost_delta > 0.08:
            local_flags.append("très sensible aux coûts")

        if local_flags:
            fragile_messages.append(f"{asset} : {', '.join(local_flags)}")

    if fragile_messages:
        for msg in fragile_messages:
            st.warning(msg)
    else:
        st.success("Aucun actif n’apparaît particulièrement fragile selon les filtres actuels.")


if not working_df.empty:
    alerts = []

    for _, row in working_df.iterrows():
        asset = row["asset"] if "asset" in row else "N/A"

        try:
            best_exp = float(row["best_expectancy"]) if "best_expectancy" in row and pd.notna(row["best_expectancy"]) else None
            best_trades = float(row["best_trades"]) if "best_trades" in row and pd.notna(row["best_trades"]) else None
            profitable_count = float(row["profitable_combo_count"]) if "profitable_combo_count" in row and pd.notna(row["profitable_combo_count"]) else None
            combo_count = float(row["combo_count"]) if "combo_count" in row and pd.notna(row["combo_count"]) else None
            profitable_ratio = float(row["profitable_ratio"]) if "profitable_ratio" in row and pd.notna(row["profitable_ratio"]) else None
            top_gap = float(row["top_gap_expectancy"]) if "top_gap_expectancy" in row and pd.notna(row["top_gap_expectancy"]) else None
            oos_exp = float(row["oos_expectancy"]) if "oos_expectancy" in row and pd.notna(row["oos_expectancy"]) else None
        except Exception:
            continue

        if best_exp is not None and best_trades is not None:
            if best_exp > 0.15 and best_trades < 40:
                alerts.append(f"{asset} : bonne expectancy mais peu de trades.")

        if oos_exp is not None and best_exp is not None:
            if best_exp > 0 and oos_exp < 0:
                alerts.append(f"{asset} : IS positif mais OOS négatif.")
            elif best_exp > 0 and oos_exp >= 0 and (best_exp - oos_exp) > 0.10:
                alerts.append(f"{asset} : OOS positif mais nette dégradation vs IS.")

        if profitable_ratio is not None and top_gap is not None:
            if profitable_ratio < 0.15 and top_gap > 0.08:
                alerts.append(f"{asset} : top probablement fragile ou trop isolé.")

        if profitable_count is not None and combo_count is not None:
            if combo_count >= 20 and profitable_count <= 2:
                alerts.append(f"{asset} : très peu de combinaisons profitables.")

        if "multi_split_ratio" in row and pd.notna(row["multi_split_ratio"]):
            try:
                ms_ratio = float(row["multi_split_ratio"])
                ms_status = str(row["multi_split_status"]) if "multi_split_status" in row else ""
                if ms_ratio == 0:
                    alerts.append(f"{asset} : ne survit à aucun split OOS.")
                elif ms_ratio < 0.5:
                    alerts.append(f"{asset} : robustesse multi-split faible ({ms_status}).")
            except Exception:
                pass

        if "delta_cost_expectancy" in row and pd.notna(row["delta_cost_expectancy"]):
            try:
                if float(row["delta_cost_expectancy"]) > 0.08:
                    alerts.append(f"{asset} : fortement pénalisé par les coûts.")
            except Exception:
                pass

        if "best_trades_per_year" in row and pd.notna(row["best_trades_per_year"]):
            try:
                if float(row["best_trades_per_year"]) < 8:
                    alerts.append(f"{asset} : fréquence très faible en trades/an.")
            except Exception:
                pass


    if alerts:
        for alert in alerts:
            st.warning(alert)
    else:
        st.success("Aucune alerte simple détectée sur la vue filtrée.")


