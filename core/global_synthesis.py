from __future__ import annotations

from typing import List

from core.thesis_objects import (
    DirectionalBias,
    GlobalStateLabel,
    GlobalThesisObject,
    PillarThesisObject,
    RiskPosture,
    StrategyStyle,
    TimeHorizon,
    TradePermission,
    TriggerState,
    TriggerType,
    ExecutionPermissionState,
)


def build_global_thesis(
    macro_thesis: PillarThesisObject,
    regime_thesis: PillarThesisObject,
    sentiment_thesis: PillarThesisObject,
    global_thesis_id: str = "global_thesis_v1",
    asset_scope: List[str] | None = None,
) -> GlobalThesisObject:
    if asset_scope is None:
        asset_scope = _merge_asset_scopes(
            macro_thesis.asset_scope,
            regime_thesis.asset_scope,
            sentiment_thesis.asset_scope,
        )

    key_alignment_points: List[str] = []
    main_conflicts: List[str] = []
    soft_warnings: List[str] = []

    macro_bias = macro_thesis.directional_bias
    regime_bias = regime_thesis.directional_bias
    sentiment_bias = sentiment_thesis.directional_bias

    macro_conviction = macro_thesis.conviction_score
    regime_conviction = regime_thesis.conviction_score
    sentiment_conviction = sentiment_thesis.conviction_score

    if macro_bias in {DirectionalBias.BULLISH, DirectionalBias.BEARISH}:
        key_alignment_points.append(f"macro_bias_{macro_bias.value}")
    else:
        soft_warnings.append("macro_bias_not_clear")

    if regime_thesis.state_label in {
        "trend_up_clean",
        "trend_down_clean",
        "range_clean",
        "compression_pre_breakout",
    }:
        key_alignment_points.append(f"regime_state_{regime_thesis.state_label}")
    else:
        soft_warnings.append("regime_not_clean")

    if sentiment_thesis.state_label not in {
        "positioning_mixed",
        "no_sentiment_information",
    }:
        key_alignment_points.append(f"sentiment_state_{sentiment_thesis.state_label}")
    else:
        soft_warnings.append("sentiment_not_clear")

    aligned_direction = False

    if (
        macro_bias == DirectionalBias.BULLISH
        and regime_bias == DirectionalBias.BULLISH
        and sentiment_bias in {DirectionalBias.BULLISH, DirectionalBias.MIXED}
    ):
        aligned_direction = True
        global_bias = DirectionalBias.BULLISH
    elif (
        macro_bias == DirectionalBias.BEARISH
        and regime_bias == DirectionalBias.BEARISH
        and sentiment_bias in {DirectionalBias.BEARISH, DirectionalBias.MIXED}
    ):
        aligned_direction = True
        global_bias = DirectionalBias.BEARISH
    elif (
        macro_bias in {DirectionalBias.BULLISH, DirectionalBias.BEARISH}
        and regime_bias == macro_bias
        and sentiment_bias == DirectionalBias.NEUTRAL
    ):
        aligned_direction = True
        global_bias = macro_bias
    else:
        global_bias = DirectionalBias.MIXED

    if global_bias == DirectionalBias.MIXED:
        main_conflicts.append(
            f"bias_conflict_macro_{macro_bias.value}_regime_{regime_bias.value}_sentiment_{sentiment_bias.value}"
        )

    common_styles = _intersect_styles(
        macro_thesis.preferred_styles,
        regime_thesis.preferred_styles,
        sentiment_thesis.preferred_styles,
    )

    forbidden_styles = _merge_forbidden_styles(
        macro_thesis.forbidden_styles,
        regime_thesis.forbidden_styles,
        sentiment_thesis.forbidden_styles,
    )

    preferred_style = _pick_preferred_style(common_styles)

    avg_conviction = round(
        (macro_conviction + regime_conviction + sentiment_conviction) / 3
    )
    avg_uncertainty = round(
        (
            macro_thesis.uncertainty_score
            + regime_thesis.uncertainty_score
            + sentiment_thesis.uncertainty_score
        )
        / 3
    )

    global_mispricing_score = round(
        (
            macro_thesis.mispricing_score
            + regime_thesis.mispricing_score
            + sentiment_thesis.mispricing_score
        )
        / 3
    )

    trigger_confirmed = (
        macro_thesis.trigger_confirmed
        or regime_thesis.trigger_confirmed
        or sentiment_thesis.trigger_confirmed
    )

    trigger_readiness_score = max(
        macro_thesis.trigger_readiness_score,
        regime_thesis.trigger_readiness_score,
        sentiment_thesis.trigger_readiness_score,
    )

    preferred_trigger_type = _pick_trigger_type(
        macro_thesis.trigger_type_preferred,
        regime_thesis.trigger_type_preferred,
        sentiment_thesis.trigger_type_preferred,
    )

    if trigger_confirmed:
        trigger_state = TriggerState.CONFIRMED
        execution_permission_state = ExecutionPermissionState.TRIGGER_CONFIRMED
        trigger_summary = "At least one pillar reports a confirmed trigger."
    elif trigger_readiness_score >= 60:
        trigger_state = TriggerState.DEVELOPING
        execution_permission_state = ExecutionPermissionState.CONDITIONAL_ON_TRIGGER
        trigger_summary = "Trigger appears to be developing but is not yet confirmed."
    elif trigger_readiness_score >= 30:
        trigger_state = TriggerState.WATCHING
        execution_permission_state = ExecutionPermissionState.WATCH_TRIGGER
        trigger_summary = "Trigger should be watched but is not yet active."
    else:
        trigger_state = TriggerState.ABSENT
        execution_permission_state = ExecutionPermissionState.BLOCKED_NO_TRIGGER
        trigger_summary = "No credible trigger is currently active."

    hard_veto = False
    hard_veto_reason = ""

    if regime_thesis.state_label in {"market_chaotic", "regime_mixed_no_clear_edge"}:
        hard_veto = True
        hard_veto_reason = "regime_not_tradable"

    if preferred_style == StrategyStyle.NO_TRADE:
        soft_warnings.append("no_common_strategy_style")

    if aligned_direction and preferred_style != StrategyStyle.NO_TRADE and trigger_state == TriggerState.CONFIRMED and not hard_veto:
        state_label = GlobalStateLabel.ALIGNED_TRADE_READY
        trade_permission = TradePermission.YES
        risk_posture = RiskPosture.NORMAL
        next_step = "execute_if_triggered"
    elif aligned_direction and preferred_style != StrategyStyle.NO_TRADE and trigger_state in {TriggerState.WATCHING, TriggerState.DEVELOPING} and not hard_veto:
        state_label = GlobalStateLabel.ALIGNED_BUT_WAITING_EXECUTION
        trade_permission = TradePermission.WAIT
        risk_posture = RiskPosture.REDUCED
        next_step = "wait_for_trigger"
    elif not hard_veto and preferred_style != StrategyStyle.NO_TRADE:
        state_label = GlobalStateLabel.MIXED_CONTEXT_REDUCE_AGGRESSION
        trade_permission = TradePermission.CONDITIONAL
        risk_posture = RiskPosture.DEFENSIVE
        next_step = "wait_for_better_alignment"
    elif hard_veto:
        state_label = GlobalStateLabel.EXTREME_RISK_NO_TRADE
        trade_permission = TradePermission.NO
        risk_posture = RiskPosture.FLAT
        next_step = "no_trade"
    else:
        state_label = GlobalStateLabel.CONTRADICTORY_NO_TRADE
        trade_permission = TradePermission.NO
        risk_posture = RiskPosture.FLAT
        next_step = "no_trade"

    if hard_veto:
        main_conflicts.append(hard_veto_reason)

    priority_market = asset_scope[0] if asset_scope else ""
    watchlist_markets = asset_scope[1:] if len(asset_scope) > 1 else []

    summary_short = (
        f"Global state = {state_label.value}, bias = {global_bias.value}, "
        f"style = {preferred_style.value}, trigger = {trigger_state.value}."
    )

    summary_long = (
        f"Macro ({macro_thesis.state_label}), regime ({regime_thesis.state_label}) and sentiment "
        f"({sentiment_thesis.state_label}) were synthesized into a {state_label.value} state with "
        f"bias {global_bias.value}, conviction {avg_conviction}/100 and uncertainty "
        f"{avg_uncertainty}/100."
    )

    return GlobalThesisObject(
        global_thesis_id=global_thesis_id,
        asset_scope=asset_scope,
        state_label=state_label,
        global_bias=global_bias,
        global_conviction=avg_conviction,
        global_uncertainty=avg_uncertainty,
        trade_permission=trade_permission,
        preferred_style=preferred_style,
        time_horizon=_pick_time_horizon(
            macro_thesis.time_horizon,
            regime_thesis.time_horizon,
            sentiment_thesis.time_horizon,
        ),
        forbidden_styles=forbidden_styles,
        priority_market=priority_market,
        watchlist_markets=watchlist_markets,
        macro_thesis_id=macro_thesis.thesis_id,
        regime_thesis_id=regime_thesis.thesis_id,
        sentiment_thesis_id=sentiment_thesis.thesis_id,
        hard_veto=hard_veto,
        hard_veto_reason=hard_veto_reason,
        soft_warnings=soft_warnings,
        key_alignment_points=key_alignment_points,
        main_conflicts=main_conflicts,
        summary_short=summary_short,
        summary_long=summary_long,
        risk_posture=risk_posture,
        next_step=next_step,
        global_mispricing_score=global_mispricing_score,
        trigger_required=True,
        trigger_state=trigger_state,
        preferred_trigger_type=preferred_trigger_type,
        trigger_summary=trigger_summary,
        execution_permission_state=execution_permission_state,
    )


def _merge_asset_scopes(*scopes: List[str]) -> List[str]:
    merged: List[str] = []
    for scope in scopes:
        for asset in scope:
            if asset not in merged:
                merged.append(asset)
    return merged


def _intersect_styles(*style_lists: List[StrategyStyle]) -> List[StrategyStyle]:
    filtered_lists = [set(styles) for styles in style_lists if styles]
    if not filtered_lists:
        return []
    common = set.intersection(*filtered_lists)
    return list(common)


def _merge_forbidden_styles(*style_lists: List[StrategyStyle]) -> List[StrategyStyle]:
    merged: List[StrategyStyle] = []
    for styles in style_lists:
        for style in styles:
            if style not in merged:
                merged.append(style)
    return merged


def _pick_preferred_style(common_styles: List[StrategyStyle]) -> StrategyStyle:
    priority_order = [
        StrategyStyle.CONTINUATION,
        StrategyStyle.BREAKOUT,
        StrategyStyle.RANGE_FADE,
        StrategyStyle.REVERSAL,
    ]
    for style in priority_order:
        if style in common_styles:
            return style
    return StrategyStyle.NO_TRADE


def _pick_trigger_type(*trigger_types: TriggerType) -> TriggerType:
    if TriggerType.EITHER in trigger_types:
        return TriggerType.EITHER
    if TriggerType.FUNDAMENTAL in trigger_types and TriggerType.TECHNICAL in trigger_types:
        return TriggerType.EITHER
    if TriggerType.FUNDAMENTAL in trigger_types:
        return TriggerType.FUNDAMENTAL
    if TriggerType.TECHNICAL in trigger_types:
        return TriggerType.TECHNICAL
    return TriggerType.UNKNOWN


def _pick_time_horizon(*horizons: TimeHorizon) -> TimeHorizon:
    if TimeHorizon.MACRO in horizons:
        return TimeHorizon.MACRO
    if TimeHorizon.WEEKLY in horizons:
        return TimeHorizon.WEEKLY
    if TimeHorizon.SWING in horizons:
        return TimeHorizon.SWING
    return TimeHorizon.INTRADAY