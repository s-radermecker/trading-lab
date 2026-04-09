from __future__ import annotations

from core.thesis_objects import (
    DirectionalBias,
    GlobalStateLabel,
    GlobalThesisObject,
    PillarName,
    PillarThesisObject,
    PriorityLevel,
    RecommendedAction,
    RiskPosture,
    StrategyStyle,
    TimeHorizon,
    TradePermission,
    TriggerState,
    TriggerType,
)


def build_risk_thesis(
    global_thesis: GlobalThesisObject,
    thesis_id: str = "risk_thesis_v1",
) -> PillarThesisObject:
    hard_constraints = []
    soft_constraints = []

    correlation_penalty_score = 0
    drawdown_penalty_score = 0
    execution_penalty_score = 0
    trigger_penalty_score = 0

    if global_thesis.hard_veto:
        hard_constraints.append(global_thesis.hard_veto_reason or "hard_veto_active")

    if global_thesis.trade_permission == TradePermission.NO:
        hard_constraints.append("global_trade_permission_no")

    if global_thesis.trigger_state == TriggerState.ABSENT:
        trigger_penalty_score = 80
        soft_constraints.append("trigger_absent")
    elif global_thesis.trigger_state == TriggerState.WATCHING:
        trigger_penalty_score = 45
        soft_constraints.append("trigger_watching")
    elif global_thesis.trigger_state == TriggerState.DEVELOPING:
        trigger_penalty_score = 20
        soft_constraints.append("trigger_developing")
    else:
        trigger_penalty_score = 0

    if global_thesis.state_label == GlobalStateLabel.MIXED_CONTEXT_REDUCE_AGGRESSION:
        drawdown_penalty_score = 20
        soft_constraints.append("mixed_context_reduce_aggression")

    if global_thesis.state_label == GlobalStateLabel.CONTRADICTORY_NO_TRADE:
        drawdown_penalty_score = 35
        hard_constraints.append("contradictory_context")

    if global_thesis.state_label == GlobalStateLabel.EXTREME_RISK_NO_TRADE:
        drawdown_penalty_score = 60
        execution_penalty_score = 40
        hard_constraints.append("extreme_risk_no_trade")

    if global_thesis.risk_posture == RiskPosture.FLAT:
        hard_constraints.append("flat_risk_posture")
    elif global_thesis.risk_posture == RiskPosture.DEFENSIVE:
        drawdown_penalty_score += 10
    elif global_thesis.risk_posture == RiskPosture.REDUCED:
        drawdown_penalty_score += 5

    if global_thesis.soft_warnings:
        correlation_penalty_score = min(35, len(global_thesis.soft_warnings) * 5)
        soft_constraints.extend(global_thesis.soft_warnings)

    total_penalty = min(
        100,
        correlation_penalty_score
        + drawdown_penalty_score
        + execution_penalty_score
        + trigger_penalty_score,
    )

    context_quality_score = max(
        0,
        round(
            (
                global_thesis.global_conviction
                + (100 - global_thesis.global_uncertainty)
                + global_thesis.global_mispricing_score
            )
            / 3
        )
        - round(total_penalty * 0.4),
    )

    if hard_constraints:
        risk_state_label = "flat_protection_mode"
        risk_permission = TradePermission.NO
        risk_posture = RiskPosture.FLAT
        recommended_size_factor = 0.0
        max_risk_per_trade = 0.0
        max_risk_total = 0.0
        kill_switch_active = True
        recommended_action = RecommendedAction.NO_TRADE
    elif global_thesis.trigger_state == TriggerState.ABSENT:
        risk_state_label = "trigger_absent_blocked"
        risk_permission = TradePermission.CONDITIONAL
        risk_posture = RiskPosture.DEFENSIVE
        recommended_size_factor = 0.0
        max_risk_per_trade = 0.0
        max_risk_total = 0.0
        kill_switch_active = False
        recommended_action = RecommendedAction.WAIT
    elif global_thesis.trigger_state == TriggerState.WATCHING:
        risk_state_label = "defensive_mode"
        risk_permission = TradePermission.WAIT
        risk_posture = RiskPosture.DEFENSIVE
        recommended_size_factor = 0.25
        max_risk_per_trade = 0.25
        max_risk_total = 0.5
        kill_switch_active = False
        recommended_action = RecommendedAction.WAIT
    elif global_thesis.trigger_state == TriggerState.DEVELOPING:
        risk_state_label = "reduced_risk_mode"
        risk_permission = TradePermission.CONDITIONAL
        risk_posture = RiskPosture.REDUCED
        recommended_size_factor = 0.5
        max_risk_per_trade = 0.5
        max_risk_total = 1.0
        kill_switch_active = False
        recommended_action = (
            RecommendedAction.LONG_BIAS
            if global_thesis.global_bias == DirectionalBias.BULLISH
            else RecommendedAction.SHORT_BIAS
            if global_thesis.global_bias == DirectionalBias.BEARISH
            else RecommendedAction.WAIT
        )
    else:
        risk_state_label = "normal_risk_mode"
        risk_permission = TradePermission.YES
        risk_posture = (
            RiskPosture.NORMAL
            if global_thesis.risk_posture in {RiskPosture.NORMAL, RiskPosture.REDUCED}
            else global_thesis.risk_posture
        )
        recommended_size_factor = 1.0 if context_quality_score >= 60 else 0.75
        max_risk_per_trade = recommended_size_factor
        max_risk_total = round(recommended_size_factor * 2, 2)
        kill_switch_active = False
        recommended_action = (
            RecommendedAction.LONG_BIAS
            if global_thesis.global_bias == DirectionalBias.BULLISH
            else RecommendedAction.SHORT_BIAS
            if global_thesis.global_bias == DirectionalBias.BEARISH
            else RecommendedAction.WATCHLIST
        )

    preferred_styles = (
        [global_thesis.preferred_style]
        if global_thesis.preferred_style != StrategyStyle.NO_TRADE
        else []
    )

    forbidden_styles = list(global_thesis.forbidden_styles)

    thesis_summary_short = (
        f"Risk state = {risk_state_label}, permission = {risk_permission.value}, "
        f"size_factor = {recommended_size_factor}."
    )

    thesis_summary_long = (
        f"The risk pillar evaluated the global thesis with context quality "
        f"{context_quality_score}/100 and total penalty {total_penalty}/100. "
        f"Trigger state = {global_thesis.trigger_state.value}, hard constraints = "
        f"{len(hard_constraints)}, soft constraints = {len(soft_constraints)}."
    )

    main_risks = list(hard_constraints) + list(soft_constraints)
    if not main_risks:
        main_risks = ["no_major_risk_constraint_detected"]

    invalidation_conditions = []
    if global_thesis.trigger_state != TriggerState.CONFIRMED:
        invalidation_conditions.append("trigger_fails_to_confirm")
    invalidation_conditions.append("global_context_deteriorates")
    invalidation_conditions.append("risk_posture_reduced_by_new_constraint")

    return PillarThesisObject(
        thesis_id=thesis_id,
        pillar_name=PillarName.RISK,
        asset_scope=global_thesis.asset_scope,
        directional_bias=global_thesis.global_bias,
        conviction_score=context_quality_score,
        uncertainty_score=min(100, total_penalty),
        tradable=risk_permission == TradePermission.YES,
        state_label=risk_state_label,
        time_horizon=global_thesis.time_horizon,
        preferred_styles=preferred_styles,
        forbidden_styles=forbidden_styles,
        priority_level=PriorityLevel.HIGH,
        thesis_summary_short=thesis_summary_short,
        thesis_summary_long=thesis_summary_long,
        key_drivers=[
            f"risk_permission_{risk_permission.value}",
            f"risk_posture_{risk_posture.value}",
            f"trigger_state_{global_thesis.trigger_state.value}",
        ],
        supporting_info_ids=[
            global_thesis.global_thesis_id,
            global_thesis.macro_thesis_id,
            global_thesis.regime_thesis_id,
            global_thesis.sentiment_thesis_id,
        ],
        counter_arguments=main_risks,
        main_risks=main_risks,
        invalidation_conditions=invalidation_conditions,
        data_quality_score=context_quality_score,
        recommended_action=recommended_action,
        mispricing_score=global_thesis.global_mispricing_score,
        trigger_needed=global_thesis.trigger_required,
        trigger_type_preferred=global_thesis.preferred_trigger_type,
        trigger_watchlist=[global_thesis.trigger_summary],
        trigger_confirmed=global_thesis.trigger_state == TriggerState.CONFIRMED,
        trigger_readiness_score=max(0, 100 - trigger_penalty_score),
    )