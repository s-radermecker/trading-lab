from core.global_synthesis import build_global_thesis
from core.macro_pillar import build_macro_thesis
from core.regime_pillar import build_regime_thesis
from core.risk_pillar import build_risk_thesis
from core.sentiment_pillar import build_sentiment_thesis
from core.thesis_objects import (
    DirectionHint,
    EventType,
    MarketInfoObject,
    PillarName,
    SourceTier,
    SourceType,
    TimeHorizon,
)


def main() -> None:
    infos = [
        MarketInfoObject(
            info_id="MACRO_RISK_1",
            pillar_target=PillarName.MACRO,
            source_name="BLS",
            source_type=SourceType.OFFICIAL,
            source_tier=SourceTier.A,
            title="US CPI above consensus",
            raw_text="Inflation stronger than expected",
            normalized_summary="USD macro support after upside inflation surprise.",
            asset_scope=["EURUSD"],
            country_scope=["US"],
            time_horizon=TimeHorizon.MACRO,
            event_type=EventType.DATA_RELEASE,
            importance_score=90,
            confidence_score=95,
            novelty_score=88,
            market_relevance_score=94,
            direction_hint=DirectionHint.BULLISH,
            tags=["hawkish", "inflation_upside", "usd_supportive"],
        ),
        MarketInfoObject(
            info_id="REGIME_RISK_1",
            pillar_target=PillarName.PRICE_ACTION,
            source_name="internal_price_engine",
            source_type=SourceType.INTERNAL_MODEL,
            source_tier=SourceTier.B,
            title="EURUSD bearish structure intact",
            raw_text="Lower highs and lower lows remain intact",
            normalized_summary="Clean downtrend structure on EURUSD.",
            asset_scope=["EURUSD"],
            country_scope=[],
            time_horizon=TimeHorizon.INTRADAY,
            event_type=EventType.MARKET_MOVE,
            importance_score=82,
            confidence_score=86,
            novelty_score=70,
            market_relevance_score=84,
            direction_hint=DirectionHint.BEARISH,
            tags=["trend_down", "bearish_structure", "lower_highs", "lower_lows", "clean_downtrend"],
        ),
        MarketInfoObject(
            info_id="SENT_RISK_1",
            pillar_target=PillarName.SENTIMENT,
            source_name="internal_sentiment_engine",
            source_type=SourceType.INTERNAL_MODEL,
            source_tier=SourceTier.B,
            title="Risk-off tone supports defensive USD demand",
            raw_text="Risk assets soft, demand for defensives rising.",
            normalized_summary="Risk-off environment supportive of USD continuation.",
            asset_scope=["EURUSD"],
            country_scope=[],
            time_horizon=TimeHorizon.INTRADAY,
            event_type=EventType.MARKET_MOVE,
            importance_score=76,
            confidence_score=80,
            novelty_score=68,
            market_relevance_score=79,
            direction_hint=DirectionHint.BEARISH,
            tags=["risk_off", "fear", "equities_weak"],
        ),
    ]

    macro_thesis = build_macro_thesis(
        info_objects=infos,
        asset_scope=["EURUSD"],
        thesis_id="macro_risk_test_001",
    )

    regime_thesis = build_regime_thesis(
        info_objects=infos,
        asset_scope=["EURUSD"],
        thesis_id="regime_risk_test_001",
    )

    sentiment_thesis = build_sentiment_thesis(
        info_objects=infos,
        asset_scope=["EURUSD"],
        thesis_id="sentiment_risk_test_001",
    )

    global_thesis = build_global_thesis(
        macro_thesis=macro_thesis,
        regime_thesis=regime_thesis,
        sentiment_thesis=sentiment_thesis,
        global_thesis_id="global_risk_test_001",
        asset_scope=["EURUSD"],
    )

    risk_thesis = build_risk_thesis(
        global_thesis=global_thesis,
        thesis_id="risk_test_001",
    )

    print("=== GLOBAL ===")
    print(global_thesis.to_dict())
    print()
    print("=== RISK ===")
    print(risk_thesis.to_dict())


if __name__ == "__main__":
    main()