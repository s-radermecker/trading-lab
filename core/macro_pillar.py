from __future__ import annotations

from typing import List

from core.thesis_objects import (
    DirectionalBias,
    MarketInfoObject,
    PillarName,
    PillarThesisObject,
    PriorityLevel,
    RecommendedAction,
    StrategyStyle,
    TimeHorizon,
    TriggerType,
)


USD_POSITIVE_TAGS = {
    "hawkish",
    "inflation_upside",
    "strong_jobs",
    "usd_supportive",
    "higher_rates",
    "growth_positive",
    "surprise_positive",
    "not_priced_in",
}

USD_NEGATIVE_TAGS = {
    "dovish",
    "inflation_downside",
    "weak_jobs",
    "usd_negative",
    "lower_rates",
    "growth_negative",
    "surprise_negative",
}

EUR_POSITIVE_TAGS = {
    "eur_positive",
    "euro_positive",
    "ecb_hawkish",
    "eurozone_growth_positive",
}

EUR_NEGATIVE_TAGS = {
    "eur_negative",
    "euro_negative",
    "ecb_dovish",
    "eurozone_growth_negative",
    "inflation_downside",
    "lower_rates",
    "dovish",
}

GBP_POSITIVE_TAGS = {"gbp_positive", "boe_hawkish"}
GBP_NEGATIVE_TAGS = {"gbp_negative", "boe_dovish"}

JPY_POSITIVE_TAGS = {"jpy_positive", "boj_hawkish"}
JPY_NEGATIVE_TAGS = {"jpy_negative", "boj_dovish"}

AUD_POSITIVE_TAGS = {"aud_positive", "rba_hawkish"}
AUD_NEGATIVE_TAGS = {"aud_negative", "rba_dovish"}

CAD_POSITIVE_TAGS = {"cad_positive", "boc_hawkish"}
CAD_NEGATIVE_TAGS = {"cad_negative", "boc_dovish"}

CURRENCY_POSITIVE_MAP = {
    "USD": USD_POSITIVE_TAGS,
    "EUR": EUR_POSITIVE_TAGS,
    "GBP": GBP_POSITIVE_TAGS,
    "JPY": JPY_POSITIVE_TAGS,
    "AUD": AUD_POSITIVE_TAGS,
    "CAD": CAD_POSITIVE_TAGS,
}

CURRENCY_NEGATIVE_MAP = {
    "USD": USD_NEGATIVE_TAGS,
    "EUR": EUR_NEGATIVE_TAGS,
    "GBP": GBP_NEGATIVE_TAGS,
    "JPY": JPY_NEGATIVE_TAGS,
    "AUD": AUD_NEGATIVE_TAGS,
    "CAD": CAD_NEGATIVE_TAGS,
}


def _score_pair(tag_set: set, asset: str) -> int:
    parts = []
    if len(asset) == 6:
        parts = [asset[:3], asset[3:]]
    elif len(asset) == 7 and asset[3] == "/":
        parts = [asset[:3], asset[4:]]
    else:
        parts = ["USD"]

    base = parts[0].upper()
    quote = parts[1].upper() if len(parts) > 1 else "USD"

    score = 0
    score += len(tag_set.intersection(CURRENCY_POSITIVE_MAP.get(base, set())))
    score -= len(tag_set.intersection(CURRENCY_NEGATIVE_MAP.get(base, set())))
    score -= len(tag_set.intersection(CURRENCY_POSITIVE_MAP.get(quote, set())))
    score += len(tag_set.intersection(CURRENCY_NEGATIVE_MAP.get(quote, set())))
    return score


def build_macro_thesis(
    info_objects: List[MarketInfoObject],
    asset_scope: List[str],
    thesis_id: str = "macro_thesis_v1",
) -> PillarThesisObject:
    macro_infos = [
        info
        for info in info_objects
        if info.pillar_target == PillarName.MACRO
    ]

    if not macro_infos:
        return PillarThesisObject(
            thesis_id=thesis_id,
            pillar_name=PillarName.MACRO,
            asset_scope=asset_scope,
            directional_bias=DirectionalBias.NEUTRAL,
            conviction_score=10,
            uncertainty_score=85,
            tradable=False,
            state_label="no_macro_information",
            time_horizon=TimeHorizon.SWING,
            preferred_styles=[],
            forbidden_styles=[],
            priority_level=PriorityLevel.LOW,
            thesis_summary_short="No macro information available.",
            thesis_summary_long="The macro pillar has no usable information to build a thesis.",
            key_drivers=[],
            supporting_info_ids=[],
            counter_arguments=["missing_macro_inputs"],
            main_risks=["low_information_quality"],
            invalidation_conditions=[],
            data_quality_score=10,
            recommended_action=RecommendedAction.WATCHLIST,
            mispricing_score=0,
            trigger_needed=True,
            trigger_type_preferred=TriggerType.UNKNOWN,
            trigger_watchlist=[],
            trigger_confirmed=False,
            trigger_readiness_score=0,
        )

    usd_score = 0
    supporting_ids: List[str] = []
    key_drivers: List[str] = []
    counter_arguments: List[str] = []
    trigger_watchlist: List[str] = []
    total_confidence = 0
    total_importance = 0

    for info in macro_infos:
        supporting_ids.append(info.info_id)
        total_confidence += info.confidence_score
        total_importance += info.importance_score

        tag_set = set(info.tags)

        pair_score = 0
        if asset_scope:
            for asset in asset_scope:
                pair_score += _score_pair(tag_set, asset)
        else:
            positive_hits = len(tag_set.intersection(USD_POSITIVE_TAGS))
            negative_hits = len(tag_set.intersection(USD_NEGATIVE_TAGS))
            pair_score += positive_hits - negative_hits

        usd_score += pair_score

        if pair_score != 0:
            key_drivers.append(info.title)

        if info.event_type.value in {"data_release", "central_bank"}:
            trigger_watchlist.append(info.title)

    avg_confidence = round(total_confidence / len(macro_infos))
    avg_importance = round(total_importance / len(macro_infos))
    primary_asset = asset_scope[0] if asset_scope else "UNKNOWN"

    if usd_score >= 2:
        directional_bias = DirectionalBias.BULLISH
        state_label = f"macro_bullish_{primary_asset.lower()}"
        conviction_score = min(85, 45 + usd_score * 10)
        uncertainty_score = max(15, 70 - usd_score * 10)
        tradable = True
        recommended_action = RecommendedAction.LONG_BIAS
    elif usd_score <= -2:
        directional_bias = DirectionalBias.BEARISH
        state_label = f"macro_bearish_{primary_asset.lower()}"
        conviction_score = min(85, 45 + abs(usd_score) * 10)
        uncertainty_score = max(15, 70 - abs(usd_score) * 10)
        tradable = True
        recommended_action = RecommendedAction.SHORT_BIAS
    else:
        directional_bias = DirectionalBias.MIXED
        state_label = "macro_mixed_no_clear_edge"
        conviction_score = 35
        uncertainty_score = 65
        tradable = False
        recommended_action = RecommendedAction.WATCHLIST

    data_quality_score = round((avg_confidence + avg_importance) / 2)
    mispricing_score = conviction_score if directional_bias != DirectionalBias.MIXED else 25
    trigger_readiness_score = min(80, 20 + len(trigger_watchlist) * 10)
    preferred_styles = [StrategyStyle.CONTINUATION, StrategyStyle.BREAKOUT] if tradable else []
    forbidden_styles = [StrategyStyle.RANGE_FADE] if tradable else []

    thesis_summary_short = (
        f"Macro bias = {directional_bias.value}, based on {len(macro_infos)} macro inputs."
    )

    thesis_summary_long = (
        f"The macro pillar processed {len(macro_infos)} information objects and produced a "
        f"{directional_bias.value} bias with conviction {conviction_score}/100 and uncertainty "
        f"{uncertainty_score}/100."
    )

    if not key_drivers:
        key_drivers = ["no_strong_positive_macro_driver_detected"]

    if not counter_arguments:
        counter_arguments = ["no_major_macro_counter_argument_detected"]

    return PillarThesisObject(
        thesis_id=thesis_id,
        pillar_name=PillarName.MACRO,
        asset_scope=asset_scope,
        directional_bias=directional_bias,
        conviction_score=conviction_score,
        uncertainty_score=uncertainty_score,
        tradable=tradable,
        state_label=state_label,
        time_horizon=TimeHorizon.SWING,
        preferred_styles=preferred_styles,
        forbidden_styles=forbidden_styles,
        priority_level=PriorityLevel.HIGH if tradable else PriorityLevel.MEDIUM,
        thesis_summary_short=thesis_summary_short,
        thesis_summary_long=thesis_summary_long,
        key_drivers=key_drivers,
        supporting_info_ids=supporting_ids,
        counter_arguments=counter_arguments,
        main_risks=[
            "macro narrative may already be priced in",
            "follow-through may fail",
        ],
        invalidation_conditions=[
            "new major macro release contradicts current bias",
            "central bank communication shifts materially",
        ],
        data_quality_score=data_quality_score,
        recommended_action=recommended_action,
        mispricing_score=mispricing_score,
        trigger_needed=True,
        trigger_type_preferred=TriggerType.FUNDAMENTAL,
        trigger_watchlist=trigger_watchlist,
        trigger_confirmed=False,
        trigger_readiness_score=trigger_readiness_score,
    )