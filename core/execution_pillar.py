from __future__ import annotations

from core.thesis_objects import (
    GlobalThesisObject,
    PillarName,
    PillarThesisObject,
    PriorityLevel,
    RecommendedAction,
    StrategyStyle,
    TriggerState,
)


def build_execution_thesis(
    global_thesis: GlobalThesisObject,
    risk_thesis: PillarThesisObject,
    process_thesis: PillarThesisObject,
    thesis_id: str = "execution_thesis_v1",
) -> PillarThesisObject:
    broker_constraint_flags = []
    cancel_conditions = []
    execution_warnings = []

    # Hypothèses simplifiées v1
    spread_penalty_score = 10
    slippage_risk_score = 10
    session_validity = "valid"
    event_risk_flag = False
    order_type = "none"

    if process_thesis.state_label == "ready_to_plan_execution":
        if global_thesis.preferred_style == StrategyStyle.CONTINUATION:
            order_type = "place_limit_order"
        elif global_thesis.preferred_style == StrategyStyle.BREAKOUT:
            order_type = "place_stop_order"
        elif global_thesis.preferred_style == StrategyStyle.RANGE_FADE:
            order_type = "place_limit_order"
        elif global_thesis.preferred_style == StrategyStyle.REVERSAL:
            order_type = "wait_no_order"
        else:
            order_type = "wait_no_order"
    else:
        order_type = "wait_no_order"

    if global_thesis.trigger_state == TriggerState.ABSENT:
        execution_warnings.append("trigger_absent")
        cancel_conditions.append("do_not_execute_without_trigger")
    elif global_thesis.trigger_state == TriggerState.WATCHING:
        execution_warnings.append("trigger_only_watching")
        cancel_conditions.append("do_not_execute_while_trigger_is_only_watching")

    if risk_thesis.state_label in {"flat_protection_mode", "trigger_absent_blocked"}:
        broker_constraint_flags.append("risk_layer_blocks_execution")

    if not process_thesis.tradable:
        broker_constraint_flags.append("process_layer_not_ready")

    if global_thesis.hard_veto:
        broker_constraint_flags.append("hard_veto_active")

    hard_block = bool(broker_constraint_flags)

    if hard_block:
        execution_state_label = "execution_cancelled"
        execution_permission = False
        recommended_action = RecommendedAction.NO_TRADE
        execution_quality_score = 0
        entry_price_reference = "none"
        stop_loss_reference = "none"
        take_profit_reference = "none"
        size_factor_applied = 0.0
    else:
        if process_thesis.state_label == "ready_to_plan_execution":
            execution_state_label = "execution_ready"
            execution_permission = True
            recommended_action = process_thesis.recommended_action
            execution_quality_score = max(
                0,
                round(
                    (
                        process_thesis.conviction_score
                        + risk_thesis.conviction_score
                        + global_thesis.global_conviction
                    )
                    / 3
                )
                - round((spread_penalty_score + slippage_risk_score) / 4),
            )
            entry_price_reference = "market_context_dependent_entry"
            stop_loss_reference = "structure_invalidation_level"
            take_profit_reference = "strategy_module_target"
            if risk_thesis.state_label == "normal_risk_mode":
                size_factor_applied = 1.0
            elif risk_thesis.state_label == "reduced_risk_mode":
                size_factor_applied = 0.5
            elif risk_thesis.state_label == "defensive_mode":
                size_factor_applied = 0.25
            else:
                size_factor_applied = 0.0
        elif process_thesis.state_label in {"waiting_for_trigger", "waiting_for_structure"}:
            execution_state_label = "execution_waiting_price_location"
            execution_permission = False
            recommended_action = RecommendedAction.WAIT
            execution_quality_score = max(10, process_thesis.trigger_readiness_score)
            entry_price_reference = "watch_only"
            stop_loss_reference = "not_active"
            take_profit_reference = "not_active"
            size_factor_applied = 0.0
            cancel_conditions.append("setup_expires_if_context_degrades")
        else:
            execution_state_label = "execution_logged_only"
            execution_permission = False
            recommended_action = RecommendedAction.WATCHLIST
            execution_quality_score = 5
            entry_price_reference = "none"
            stop_loss_reference = "none"
            take_profit_reference = "none"
            size_factor_applied = 0.0

    if not cancel_conditions:
        cancel_conditions = ["cancel_if_global_context_changes_materially"]

    thesis_summary_short = (
        f"Execution state = {execution_state_label}, order_type = {order_type}, "
        f"permission = {'yes' if execution_permission else 'no'}."
    )

    thesis_summary_long = (
        f"The execution pillar evaluated the global, risk and process layers and produced "
        f"execution state {execution_state_label} with order type {order_type}, "
        f"execution quality {execution_quality_score}/100 and size factor {size_factor_applied}."
    )

    main_risks = []
    main_risks.extend(broker_constraint_flags)
    main_risks.extend(execution_warnings)

    if not main_risks:
        main_risks = ["no_major_execution_constraint_detected"]

    return PillarThesisObject(
        thesis_id=thesis_id,
        pillar_name=PillarName.EXECUTION,
        asset_scope=global_thesis.asset_scope,
        directional_bias=global_thesis.global_bias,
        conviction_score=execution_quality_score,
        uncertainty_score=max(0, 100 - execution_quality_score),
        tradable=execution_permission,
        state_label=execution_state_label,
        time_horizon=global_thesis.time_horizon,
        preferred_styles=process_thesis.preferred_styles,
        forbidden_styles=process_thesis.forbidden_styles,
        priority_level=PriorityLevel.HIGH,
        thesis_summary_short=thesis_summary_short,
        thesis_summary_long=thesis_summary_long,
        key_drivers=[
            f"order_type_{order_type}",
            f"process_state_{process_thesis.state_label}",
            f"risk_state_{risk_thesis.state_label}",
        ],
        supporting_info_ids=[
            global_thesis.global_thesis_id,
            risk_thesis.thesis_id,
            process_thesis.thesis_id,
        ],
        counter_arguments=main_risks,
        main_risks=main_risks,
        invalidation_conditions=cancel_conditions,
        data_quality_score=execution_quality_score,
        recommended_action=recommended_action,
        mispricing_score=global_thesis.global_mispricing_score,
        trigger_needed=global_thesis.trigger_required,
        trigger_type_preferred=global_thesis.preferred_trigger_type,
        trigger_watchlist=[global_thesis.trigger_summary],
        trigger_confirmed=global_thesis.trigger_state == TriggerState.CONFIRMED,
        trigger_readiness_score=process_thesis.trigger_readiness_score,
    )