from core.thesis_objects import (
    MarketInfoObject,
    PillarThesisObject,
    GlobalThesisObject,
    PillarName,
    SourceType,
    SourceTier,
    TimeHorizon,
    EventType,
    DirectionHint,
    DirectionalBias,
    PriorityLevel,
    RecommendedAction,
    StrategyStyle,
    GlobalStateLabel,
    TradePermission,
    RiskPosture,
    TriggerType,
    TriggerState,
    ExecutionPermissionState,
)


def main() -> None:
    info = MarketInfoObject(
        info_id="US_CPI_2026_04_10_1230",
        pillar_target=PillarName.MACRO,
        source_name="BLS",
        source_type=SourceType.OFFICIAL,
        source_tier=SourceTier.A,
        title="US CPI above consensus",
        raw_text="US CPI YoY 3.4% vs 3.2% expected",
        normalized_summary="Inflation US above consensus, hawkish repricing risk for USD.",
        asset_scope=["EURUSD", "GBPUSD", "USDJPY"],
        country_scope=["US"],
        time_horizon=TimeHorizon.MACRO,
        event_type=EventType.DATA_RELEASE,
        numeric_payload={
            "actual": 3.4,
            "consensus": 3.2,
            "previous": 3.1,
            "surprise": 0.2,
        },
        importance_score=92,
        confidence_score=98,
        novelty_score=95,
        market_relevance_score=94,
        direction_hint=DirectionHint.BULLISH,
        tags=["usd", "inflation", "cpi", "hawkish"],
    )

    macro_thesis = PillarThesisObject(
        thesis_id="macro_usd_2026_04_10_pm",
        pillar_name=PillarName.MACRO,
        asset_scope=["EURUSD", "GBPUSD", "USDJPY"],
        directional_bias=DirectionalBias.BULLISH,
        conviction_score=74,
        uncertainty_score=28,
        tradable=True,
        state_label="hawkish_usd_repricing",
        time_horizon=TimeHorizon.SWING,
        preferred_styles=[StrategyStyle.CONTINUATION, StrategyStyle.BREAKOUT],
        forbidden_styles=[StrategyStyle.RANGE_FADE],
        priority_level=PriorityLevel.HIGH,
        thesis_summary_short="USD favored after upside inflation surprise.",
        thesis_summary_long=(
            "Higher-than-expected CPI increases probability of restrictive Fed path persistence, "
            "supporting USD unless follow-through fails."
        ),
        key_drivers=[
            "inflation_surprise_positive",
            "hawkish_rate_repricing",
            "usd_relative_macro_support",
        ],
        supporting_info_ids=[info.info_id],
        counter_arguments=[
            "market may have partially priced hawkish surprise",
            "follow-through in yields required",
        ],
        main_risks=[
            "risk-on squeeze against USD",
            "rapid reversal in rate expectations",
        ],
        invalidation_conditions=[
            "yields fail to confirm",
            "subsequent dovish Fed communication",
        ],
        data_quality_score=95,
        recommended_action=RecommendedAction.LONG_BIAS,
        mispricing_score=66,
        trigger_needed=True,
        trigger_type_preferred=TriggerType.FUNDAMENTAL,
        trigger_watchlist=["FOMC", "US yields continuation", "NFP"],
        trigger_confirmed=False,
        trigger_readiness_score=58,
    )

    global_thesis = GlobalThesisObject(
        global_thesis_id="global_eurusd_2026_04_10_01",
        asset_scope=["EURUSD"],
        state_label=GlobalStateLabel.ALIGNED_BUT_WAITING_EXECUTION,
        global_bias=DirectionalBias.BEARISH,
        global_conviction=68,
        global_uncertainty=31,
        trade_permission=TradePermission.WAIT,
        preferred_style=StrategyStyle.CONTINUATION,
        time_horizon=TimeHorizon.SWING,
        forbidden_styles=[StrategyStyle.RANGE_FADE, StrategyStyle.REVERSAL],
        priority_market="EURUSD",
        watchlist_markets=["GBPUSD", "USDJPY"],
        macro_thesis_id=macro_thesis.thesis_id,
        regime_thesis_id="regime_eurusd_2026_04_10_01",
        sentiment_thesis_id="sentiment_usd_2026_04_10_01",
        hard_veto=False,
        soft_warnings=["trigger_not_confirmed", "wait_for_structure"],
        key_alignment_points=[
            "macro favors USD",
            "continuation style preferred",
        ],
        main_conflicts=[
            "technical trigger not yet confirmed",
        ],
        summary_short="USD bias valid, but EURUSD execution should wait for trigger.",
        summary_long=(
            "Macro context supports USD, but execution should remain patient until price structure "
            "and trigger state improve."
        ),
        risk_posture=RiskPosture.REDUCED,
        next_step="wait_for_pullback",
        global_mispricing_score=63,
        trigger_required=True,
        trigger_state=TriggerState.WATCHING,
        preferred_trigger_type=TriggerType.EITHER,
        trigger_summary="Watching for either macro follow-through or technical confirmation.",
        execution_permission_state=ExecutionPermissionState.WATCH_TRIGGER,
    )

    print("=== MarketInfoObject ===")
    print(info.to_dict())
    print()
    print("=== PillarThesisObject ===")
    print(macro_thesis.to_dict())
    print()
    print("=== GlobalThesisObject ===")
    print(global_thesis.to_dict())


if __name__ == "__main__":
    main()