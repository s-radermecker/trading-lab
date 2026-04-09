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


RISK_ON_TAGS = {
    "risk_on",
    "equities_strong",
    "carry_supportive",
    "vol_compression",
    "optimism",
}

RISK_OFF_TAGS = {
    "risk_off",
    "fear",
    "equities_weak",
    "flight_to_safety",
    "panic",
}

CROWDED_LONG_TAGS = {
    "crowded_long",
    "consensus_long",
    "euphoric",
    "overbought_sentiment",
}

CROWDED_SHORT_TAGS = {
    "crowded_short",
    "consensus_short",
    "capitulation",
    "oversold_sentiment",
}

RETAIL_CONTRARIAN_BULLISH_TAGS = {
    "retail_short",
    "retail_fading_uptrend",
}

RETAIL_CONTRARIAN_BEARISH_TAGS = {
    "retail_long",
    "retail_fading_downtrend",
}

EXCESS_TAGS = {
    "excess",
    "panic",
    "euphoric",
    "squeeze_risk",
    "positioning_extreme",
}


def build_sentiment_thesis(
    info_objects: List[MarketInfoObject],
    asset_scope: List[str],
    thesis_id: str = "sentiment_thesis_v1",
) -> PillarThesisObject:
    sentiment_infos = [
        info
        for info in info_objects
        if info.pillar_target == PillarName.SENTIMENT
    ]

    if not sentiment_infos:
        return PillarThesisObject(
            thesis_id=thesis_id,
            pillar_name=PillarName.SENTIMENT,
            asset_scope=asset_scope,
            directional_bias=DirectionalBias.NEUTRAL,
            conviction_score=10,
            uncertainty_score=85,
            tradable=False,
            state_label="no_sentiment_information",
            time_horizon=TimeHorizon.INTRADAY,
            preferred_styles=[],
            forbidden_styles=[],
            priority_level=PriorityLevel.LOW,
            thesis_summary_short="No sentiment information available.",
            thesis_summary_long="The sentiment pillar has no usable information to build a thesis.",
            key_drivers=[],
            supporting_info_ids=[],
            counter_arguments=["missing_sentiment_inputs"],
            main_risks=["low_sentiment_visibility"],
            invalidation_conditions=[],
            data_quality_score=10,
            recommended_action=RecommendedAction.WATCHLIST,
            mispricing_score=0,
            trigger_needed=True,
            trigger_type_preferred=TriggerType.EITHER,
            trigger_watchlist=[],
            trigger_confirmed=False,
            trigger_readiness_score=0,
        )

    bullish_score = 0
    bearish_score = 0
    excess_score = 0
    crowded_long_score = 0
    crowded_short_score = 0

    supporting_ids: List[str] = []
    key_drivers: List[str] = []
    counter_arguments: List[str] = []
    trigger_watchlist: List[str] = []
    total_confidence = 0
    total_importance = 0

    for info in sentiment_infos:
        supporting_ids.append(info.info_id)
        total_confidence += info.confidence_score
        total_importance += info.importance_score

        tag_set = set(info.tags)

        bullish_score += len(tag_set.intersection(RISK_ON_TAGS))
        bullish_score += len(tag_set.intersection(RETAIL_CONTRARIAN_BULLISH_TAGS))

        bearish_score += len(tag_set.intersection(RISK_OFF_TAGS))
        bearish_score += len(tag_set.intersection(RETAIL_CONTRARIAN_BEARISH_TAGS))

        crowded_long_score += len(tag_set.intersection(CROWDED_LONG_TAGS))
        crowded_short_score += len(tag_set.intersection(CROWDED_SHORT_TAGS))
        excess_score += len(tag_set.intersection(EXCESS_TAGS))

        if bullish_score > bearish_score and tag_set.intersection(
            RISK_ON_TAGS | RETAIL_CONTRARIAN_BULLISH_TAGS
        ):
            key_drivers.append(info.title)
        elif bearish_score > bullish_score and tag_set.intersection(
            RISK_OFF_TAGS | RETAIL_CONTRARIAN_BEARISH_TAGS
        ):
            key_drivers.append(info.title)

        if tag_set.intersection(CROWDED_LONG_TAGS | CROWDED_SHORT_TAGS | EXCESS_TAGS):
            counter_arguments.append(info.title)
            trigger_watchlist.append(info.title)

    avg_confidence = round(total_confidence / len(sentiment_infos))
    avg_importance = round(total_importance / len(sentiment_infos))
    data_quality_score = round((avg_confidence + avg_importance) / 2)

    if bullish_score >= bearish_score + 2:
        directional_bias = DirectionalBias.BULLISH
        base_state_label = "risk_on_supportive"
        conviction_score = min(80, 40 + bullish_score * 8)
        uncertainty_score = max(20, 75 - bullish_score * 8)
        tradable = True
        recommended_action = RecommendedAction.LONG_BIAS
        preferred_styles = [StrategyStyle.CONTINUATION, StrategyStyle.BREAKOUT]
        forbidden_styles = []
    elif bearish_score >= bullish_score + 2:
        directional_bias = DirectionalBias.BEARISH
        base_state_label = "risk_off_supportive"
        conviction_score = min(80, 40 + bearish_score * 8)
        uncertainty_score = max(20, 75 - bearish_score * 8)
        tradable = True
        recommended_action = RecommendedAction.SHORT_BIAS
        preferred_styles = [StrategyStyle.CONTINUATION, StrategyStyle.BREAKOUT]
        forbidden_styles = []
    else:
        directional_bias = DirectionalBias.MIXED
        base_state_label = "positioning_mixed"
        conviction_score = 35
        uncertainty_score = 65
        tradable = False
        recommended_action = RecommendedAction.WATCHLIST
        preferred_styles = []
        forbidden_styles = []

    state_label = base_state_label

    if crowded_long_score >= 2 and directional_bias == DirectionalBias.BULLISH:
        state_label = "crowded_long_risk"
        tradable = False
        recommended_action = RecommendedAction.WAIT
        preferred_styles = [StrategyStyle.REVERSAL]
        forbidden_styles = [StrategyStyle.BREAKOUT]
        uncertainty_score = min(90, uncertainty_score + 15)

    if crowded_short_score >= 2 and directional_bias == DirectionalBias.BEARISH:
        state_label = "crowded_short_risk"
        tradable = False
        recommended_action = RecommendedAction.WAIT
        preferred_styles = [StrategyStyle.REVERSAL]
        forbidden_styles = [StrategyStyle.BREAKOUT]
        uncertainty_score = min(90, uncertainty_score + 15)

    if excess_score >= 2 and state_label not in {"crowded_long_risk", "crowded_short_risk"}:
        state_label = "sentiment_excess_watch"
        tradable = False
        recommended_action = RecommendedAction.WAIT
        preferred_styles = [StrategyStyle.REVERSAL]
        forbidden_styles = [StrategyStyle.BREAKOUT]
        uncertainty_score = min(90, uncertainty_score + 10)

    if not key_drivers:
        key_drivers = ["no_clear_sentiment_driver_detected"]

    if not counter_arguments:
        counter_arguments = ["no_major_sentiment_counter_argument_detected"]

    mispricing_score = max(20, conviction_score - 10) if tradable else 25
    trigger_readiness_score = min(80, 20 + len(trigger_watchlist) * 10)

    return PillarThesisObject(
        thesis_id=thesis_id,
        pillar_name=PillarName.SENTIMENT,
        asset_scope=asset_scope,
        directional_bias=directional_bias,
        conviction_score=conviction_score,
        uncertainty_score=uncertainty_score,
        tradable=tradable,
        state_label=state_label,
        time_horizon=TimeHorizon.INTRADAY,
        preferred_styles=preferred_styles,
        forbidden_styles=forbidden_styles,
        priority_level=PriorityLevel.MEDIUM if tradable else PriorityLevel.HIGH,
        thesis_summary_short=(
            f"Sentiment state = {state_label}, based on {len(sentiment_infos)} sentiment inputs."
        ),
        thesis_summary_long=(
            f"The sentiment pillar processed {len(sentiment_infos)} information objects and produced "
            f"a {directional_bias.value} / {state_label} reading with conviction {conviction_score}/100 "
            f"and uncertainty {uncertainty_score}/100."
        ),
        key_drivers=key_drivers,
        supporting_info_ids=supporting_ids,
        counter_arguments=counter_arguments,
        main_risks=[
            "sentiment can stay extreme longer than expected",
            "crowding may not reverse immediately",
        ],
        invalidation_conditions=[
            "risk regime changes materially",
            "positioning proxy reverses sharply",
        ],
        data_quality_score=data_quality_score,
        recommended_action=recommended_action,
        mispricing_score=mispricing_score,
        trigger_needed=True,
        trigger_type_preferred=TriggerType.EITHER,
        trigger_watchlist=trigger_watchlist,
        trigger_confirmed=False,
        trigger_readiness_score=trigger_readiness_score,
    )