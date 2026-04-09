from __future__ import annotations

from core.thesis_objects import (
    GlobalThesisObject,
    PillarName,
    PillarThesisObject,
    PriorityLevel,
    RecommendedAction,
    RiskPosture,
    StrategyStyle,
    TradePermission,
    TriggerState,
)


def build_process_strategy_thesis(
    global_thesis: GlobalThesisObject,
    risk_thesis: PillarThesisObject,
    thesis_id: str = "process_strategy_thesis_v1",
) -> PillarThesisObject:
    allowed_modules = []
    forbidden_modules = []
    entry_conditions = []
    no_trade_conditions = []
    invalidation_conditions = []
    discipline_flags = []

    primary_style = global_thesis.preferred_style

    if primary_style == StrategyStyle.CONTINUATION:
        allowed_modules = ["impulse_continuation_v1"]
        forbidden_modules = ["range_edge_v1", "blind_reversal_v1"]
        entry_conditions = [
            "trigger confirmé ou en développement avancé",
            "pullback propre ou reprise directionnelle nette",
            "pas de chase après extension excessive",
            "structure toujours alignée avec le biais global",
        ]
        no_trade_conditions = [
            "prix trop étendu",
            "structure se dégrade",
            "spread ou conditions marché défavorables",
        ]
    elif primary_style == StrategyStyle.BREAKOUT:
        allowed_modules = ["breakout_confirmation_v1"]
        forbidden_modules = ["range_edge_v1"]
        entry_conditions = [
            "cassure confirmée",
            "compression préalable crédible",
            "pas de faux breakout évident",
            "trigger compatible avec le contexte",
        ]
        no_trade_conditions = [
            "cassure déjà trop loin",
            "retour immédiat dans la zone",
            "absence de follow-through",
        ]
    elif primary_style == StrategyStyle.RANGE_FADE:
        allowed_modules = ["range_edge_v1"]
        forbidden_modules = ["impulse_continuation_v1", "breakout_confirmation_v1"]
        entry_conditions = [
            "range propre",
            "prix proche d’une borne",
            "pas de signal de transition",
            "conditions de fade encore valides",
        ]
        no_trade_conditions = [
            "prix au milieu du range",
            "compression pré-breakout détectée",
            "régime plus assez propre",
        ]
    elif primary_style == StrategyStyle.REVERSAL:
        allowed_modules = ["reversal_exhaustion_v1"]
        forbidden_modules = ["breakout_confirmation_v1"]
        entry_conditions = [
            "excès identifié",
            "signal de fatigue crédible",
            "contexte compatible avec un renversement",
            "pas de simple continuation déguisée",
        ]
        no_trade_conditions = [
            "pas de confirmation de fatigue",
            "momentum encore trop fort contre le trade",
            "crowding sans signal de cassure",
        ]
    else:
        allowed_modules = []
        forbidden_modules = [
            "impulse_continuation_v1",
            "breakout_confirmation_v1",
            "range_edge_v1",
            "reversal_exhaustion_v1",
        ]
        entry_conditions = []
        no_trade_conditions = [
            "aucun style de stratégie cohérent n’est autorisé",
        ]

    if global_thesis.trade_permission == TradePermission.NO:
        discipline_flags.append("global_permission_no")
    elif global_thesis.trade_permission == TradePermission.WAIT:
        discipline_flags.append("wait_before_any_execution")
    elif global_thesis.trade_permission == TradePermission.CONDITIONAL:
        discipline_flags.append("execution_only_if_conditions_improve")

    if risk_thesis.state_label in {"flat_protection_mode", "trigger_absent_blocked"}:
        discipline_flags.append("risk_layer_blocks_execution")

    if global_thesis.trigger_state == TriggerState.ABSENT:
        discipline_flags.append("no_trigger_no_execution")
        no_trade_conditions.append("trigger absent")
    elif global_thesis.trigger_state == TriggerState.WATCHING:
        discipline_flags.append("watch_trigger_only")
        no_trade_conditions.append("trigger still only in watch mode")
    elif global_thesis.trigger_state == TriggerState.DEVELOPING:
        discipline_flags.append("conditional_execution_only")
        entry_conditions.append("trigger development must continue")
    elif global_thesis.trigger_state == TriggerState.CONFIRMED:
        entry_conditions.append("trigger confirmed")

    if global_thesis.risk_posture in {RiskPosture.DEFENSIVE, RiskPosture.FLAT}:
        discipline_flags.append(f"risk_posture_{global_thesis.risk_posture.value}")

    if global_thesis.hard_veto:
        process_state_label = "no_trade_clean_decision"
        action_state = "stand_down"
        allowed_modules = []
        recommended_action = RecommendedAction.NO_TRADE
    elif global_thesis.trade_permission == TradePermission.YES and risk_thesis.tradable:
        process_state_label = "ready_to_plan_execution"
        action_state = "execute_if_confirmed"
        recommended_action = (
            RecommendedAction.LONG_BIAS
            if global_thesis.global_bias.value == "bullish"
            else RecommendedAction.SHORT_BIAS
            if global_thesis.global_bias.value == "bearish"
            else RecommendedAction.WAIT
        )
    elif global_thesis.trade_permission in {TradePermission.WAIT, TradePermission.CONDITIONAL}:
        if global_thesis.trigger_state in {TriggerState.WATCHING, TriggerState.DEVELOPING}:
            process_state_label = "waiting_for_trigger"
            action_state = "watch_trigger_only"
        else:
            process_state_label = "waiting_for_structure"
            action_state = "watch_only"
        recommended_action = RecommendedAction.WAIT
    else:
        process_state_label = "no_trade_clean_decision"
        action_state = "stand_down"
        recommended_action = RecommendedAction.NO_TRADE

    if not entry_conditions:
        entry_conditions = ["no_entry_condition_active"]

    if not no_trade_conditions:
        no_trade_conditions = ["no_major_no_trade_condition_detected"]

    invalidation_conditions = [
        "global thesis changes materially",
        "risk thesis reduces permission",
        "style no longer authorized",
        "trigger fails or degrades",
    ]

    setup_quality_score = max(
        0,
        round(
            (
                global_thesis.global_conviction
                + risk_thesis.conviction_score
                + (100 - global_thesis.global_uncertainty)
            )
            / 3
        )
    )

    execution_readiness_score = 0
    if process_state_label == "ready_to_plan_execution":
        execution_readiness_score = min(90, setup_quality_score)
    elif process_state_label == "waiting_for_trigger":
        execution_readiness_score = min(65, setup_quality_score)
    elif process_state_label == "waiting_for_structure":
        execution_readiness_score = min(50, setup_quality_score)
    else:
        execution_readiness_score = 10

    thesis_summary_short = (
        f"Process state = {process_state_label}, action = {action_state}, "
        f"primary style = {primary_style.value}."
    )

    thesis_summary_long = (
        f"The process/strategy pillar converted the global thesis state "
        f"{global_thesis.state_label.value} and risk state {risk_thesis.state_label} "
        f"into action state {action_state}, with setup quality {setup_quality_score}/100 "
        f"and execution readiness {execution_readiness_score}/100."
    )

    return PillarThesisObject(
        thesis_id=thesis_id,
        pillar_name=PillarName.PROCESS,
        asset_scope=global_thesis.asset_scope,
        directional_bias=global_thesis.global_bias,
        conviction_score=setup_quality_score,
        uncertainty_score=max(0, 100 - execution_readiness_score),
        tradable=process_state_label == "ready_to_plan_execution",
        state_label=process_state_label,
        time_horizon=global_thesis.time_horizon,
        preferred_styles=[primary_style] if primary_style != StrategyStyle.NO_TRADE else [],
        forbidden_styles=list(global_thesis.forbidden_styles),
        priority_level=PriorityLevel.HIGH,
        thesis_summary_short=thesis_summary_short,
        thesis_summary_long=thesis_summary_long,
        key_drivers=[
            f"action_state_{action_state}",
            f"primary_style_{primary_style.value}",
            f"risk_state_{risk_thesis.state_label}",
        ],
        supporting_info_ids=[
            global_thesis.global_thesis_id,
            risk_thesis.thesis_id,
        ],
        counter_arguments=no_trade_conditions,
        main_risks=discipline_flags if discipline_flags else ["no_major_process_risk_detected"],
        invalidation_conditions=invalidation_conditions,
        data_quality_score=setup_quality_score,
        recommended_action=recommended_action,
        mispricing_score=global_thesis.global_mispricing_score,
        trigger_needed=global_thesis.trigger_required,
        trigger_type_preferred=global_thesis.preferred_trigger_type,
        trigger_watchlist=[global_thesis.trigger_summary],
        trigger_confirmed=global_thesis.trigger_state == TriggerState.CONFIRMED,
        trigger_readiness_score=execution_readiness_score,
    )