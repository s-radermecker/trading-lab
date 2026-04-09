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


TREND_UP_TAGS = {
    "trend_up",
    "bullish_structure",
    "higher_highs",
    "higher_lows",
    "clean_trend",
    "breakout_up",
}

TREND_DOWN_TAGS = {
    "trend_down",
    "bearish_structure",
    "lower_highs",
    "lower_lows",
    "clean_downtrend",
    "breakout_down",
}

RANGE_TAGS = {
    "range",
    "mean_reversion",
    "range_clean",
    "range_edges",
}

COMPRESSION_TAGS = {
    "compression",
    "coil",
    "pre_breakout",
    "tight_range",
}

CHAOTIC_TAGS = {
    "chaotic",
    "messy",
    "unstable",
    "whipsaw",
    "low_clarity",
}


def build_regime_thesis(
    info_objects: List[MarketInfoObject],
    asset_scope: List[str],
    thesis_id: str = "regime_thesis_v1",
) -> PillarThesisObject:
    regime_infos = [
        info
        for info in info_objects
        if info.pillar_target == PillarName.PRICE_ACTION
    ]

    if not regime_infos:
        return PillarThesisObject(
            thesis_id=thesis_id,
            pillar_name=PillarName.PRICE_ACTION,
            asset_scope=asset_scope,
            directional_bias=DirectionalBias.NEUTRAL,
            conviction_score=10,
            uncertainty_score=85,
            tradable=False,
            state_label="no_regime_information",
            time_horizon=TimeHorizon.INTRADAY,
            preferred_styles=[],
            forbidden_styles=[],
            priority_level=PriorityLevel.LOW,
            thesis_summary_short="No regime information available.",
            thesis_summary_long="The regime pillar has no usable information to classify market state.",
            key_drivers=[],
            supporting_info_ids=[],
            counter_arguments=["missing_price_action_inputs"],
            main_risks=["low_structure_visibility"],
            invalidation_conditions=[],
            data_quality_score=10,
            recommended_action=RecommendedAction.WATCHLIST,
            mispricing_score=0,
            trigger_needed=True,
            trigger_type_preferred=TriggerType.TECHNICAL,
            trigger_watchlist=[],
            trigger_confirmed=False,
            trigger_readiness_score=0,
        )

    trend_up_score = 0
    trend_down_score = 0
    range_score = 0
    compression_score = 0
    chaotic_score = 0

    supporting_ids: List[str] = []
    key_drivers: List[str] = []
    counter_arguments: List[str] = []
    trigger_watchlist: List[str] = []
    total_confidence = 0
    total_importance = 0

    for info in regime_infos:
        supporting_ids.append(info.info_id)
        total_confidence += info.confidence_score
        total_importance += info.importance_score

        tag_set = set(info.tags)

        trend_up_score += len(tag_set.intersection(TREND_UP_TAGS))
        trend_down_score += len(tag_set.intersection(TREND_DOWN_TAGS))
        range_score += len(tag_set.intersection(RANGE_TAGS))
        compression_score += len(tag_set.intersection(COMPRESSION_TAGS))
        chaotic_score += len(tag_set.intersection(CHAOTIC_TAGS))

        if tag_set.intersection(TREND_UP_TAGS | TREND_DOWN_TAGS | RANGE_TAGS | COMPRESSION_TAGS):
            key_drivers.append(info.title)

        if tag_set.intersection(CHAOTIC_TAGS):
            counter_arguments.append(info.title)

        if "breakout_up" in tag_set or "breakout_down" in tag_set or "pre_breakout" in tag_set:
            trigger_watchlist.append(info.title)

    avg_confidence = round(total_confidence / len(regime_infos))
    avg_importance = round(total_importance / len(regime_infos))
    data_quality_score = round((avg_confidence + avg_importance) / 2)

    dominant_state = "mixed"
    dominant_score = max(
        trend_up_score,
        trend_down_score,
        range_score,
        compression_score,
        chaotic_score,
    )

    if dominant_score == chaotic_score and chaotic_score > 0:
        dominant_state = "chaotic"
    elif dominant_score == trend_up_score and trend_up_score > 0:
        dominant_state = "trend_up"
    elif dominant_score == trend_down_score and trend_down_score > 0:
        dominant_state = "trend_down"
    elif dominant_score == range_score and range_score > 0:
        dominant_state = "range"
    elif dominant_score == compression_score and compression_score > 0:
        dominant_state = "compression"

    if dominant_state == "trend_up":
        directional_bias = DirectionalBias.BULLISH
        state_label = "trend_up_clean"
        conviction_score = min(85, 45 + trend_up_score * 8)
        uncertainty_score = max(15, 70 - trend_up_score * 8)
        tradable = True
        preferred_styles = [StrategyStyle.CONTINUATION, StrategyStyle.BREAKOUT]
        forbidden_styles = [StrategyStyle.RANGE_FADE]
        recommended_action = RecommendedAction.LONG_BIAS
    elif dominant_state == "trend_down":
        directional_bias = DirectionalBias.BEARISH
        state_label = "trend_down_clean"
        conviction_score = min(85, 45 + trend_down_score * 8)
        uncertainty_score = max(15, 70 - trend_down_score * 8)
        tradable = True
        preferred_styles = [StrategyStyle.CONTINUATION, StrategyStyle.BREAKOUT]
        forbidden_styles = [StrategyStyle.RANGE_FADE]
        recommended_action = RecommendedAction.SHORT_BIAS
    elif dominant_state == "range":
        directional_bias = DirectionalBias.NEUTRAL
        state_label = "range_clean"
        conviction_score = min(75, 40 + range_score * 8)
        uncertainty_score = max(20, 75 - range_score * 8)
        tradable = True
        preferred_styles = [StrategyStyle.RANGE_FADE]
        forbidden_styles = [StrategyStyle.CONTINUATION, StrategyStyle.BREAKOUT]
        recommended_action = RecommendedAction.WATCHLIST
    elif dominant_state == "compression":
        directional_bias = DirectionalBias.MIXED
        state_label = "compression_pre_breakout"
        conviction_score = min(70, 35 + compression_score * 8)
        uncertainty_score = max(25, 80 - compression_score * 8)
        tradable = False
        preferred_styles = [StrategyStyle.BREAKOUT]
        forbidden_styles = [StrategyStyle.RANGE_FADE]
        recommended_action = RecommendedAction.WAIT
    elif dominant_state == "chaotic":
        directional_bias = DirectionalBias.MIXED
        state_label = "market_chaotic"
        conviction_score = 20
        uncertainty_score = 80
        tradable = False
        preferred_styles = []
        forbidden_styles = [
            StrategyStyle.CONTINUATION,
            StrategyStyle.BREAKOUT,
            StrategyStyle.RANGE_FADE,
            StrategyStyle.REVERSAL,
        ]
        recommended_action = RecommendedAction.NO_TRADE
    else:
        directional_bias = DirectionalBias.MIXED
        state_label = "regime_mixed_no_clear_edge"
        conviction_score = 30
        uncertainty_score = 70
        tradable = False
        preferred_styles = []
        forbidden_styles = []
        recommended_action = RecommendedAction.WATCHLIST

    if not key_drivers:
        key_drivers = ["no_clear_regime_driver_detected"]

    if not counter_arguments:
        counter_arguments = ["no_major_regime_counter_argument_detected"]

    mispricing_score = 20 if state_label in {"market_chaotic", "regime_mixed_no_clear_edge"} else conviction_score
    trigger_readiness_score = min(80, 20 + len(trigger_watchlist) * 10)

    return PillarThesisObject(
        thesis_id=thesis_id,
        pillar_name=PillarName.PRICE_ACTION,
        asset_scope=asset_scope,
        directional_bias=directional_bias,
        conviction_score=conviction_score,
        uncertainty_score=uncertainty_score,
        tradable=tradable,
        state_label=state_label,
        time_horizon=TimeHorizon.INTRADAY,
        preferred_styles=preferred_styles,
        forbidden_styles=forbidden_styles,
        priority_level=PriorityLevel.HIGH if tradable else PriorityLevel.MEDIUM,
        thesis_summary_short=(
            f"Regime state = {state_label}, based on {len(regime_infos)} price-action inputs."
        ),
        thesis_summary_long=(
            f"The regime pillar processed {len(regime_infos)} information objects and classified "
            f"the market as {state_label} with conviction {conviction_score}/100 and uncertainty "
            f"{uncertainty_score}/100."
        ),
        key_drivers=key_drivers,
        supporting_info_ids=supporting_ids,
        counter_arguments=counter_arguments,
        main_risks=[
            "state classification may be unstable",
            "technical trigger may fail",
        ],
        invalidation_conditions=[
            "market structure changes materially",
            "breakout fails or range invalidates",
        ],
        data_quality_score=data_quality_score,
        recommended_action=recommended_action,
        mispricing_score=mispricing_score,
        trigger_needed=True,
        trigger_type_preferred=TriggerType.TECHNICAL,
        trigger_watchlist=trigger_watchlist,
        trigger_confirmed=False,
        trigger_readiness_score=trigger_readiness_score,
    )