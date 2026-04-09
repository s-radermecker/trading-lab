from core.regime_pillar import build_regime_thesis
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
            info_id="PA_1",
            pillar_target=PillarName.PRICE_ACTION,
            source_name="internal_price_engine",
            source_type=SourceType.INTERNAL_MODEL,
            source_tier=SourceTier.B,
            title="EURUSD bullish structure intact",
            raw_text="Higher highs and higher lows remain intact.",
            normalized_summary="Bullish structure with clean trend continuation behavior.",
            asset_scope=["EURUSD"],
            country_scope=[],
            time_horizon=TimeHorizon.INTRADAY,
            event_type=EventType.MARKET_MOVE,
            importance_score=80,
            confidence_score=85,
            novelty_score=70,
            market_relevance_score=82,
            direction_hint=DirectionHint.BULLISH,
            tags=["trend_up", "bullish_structure", "higher_highs", "higher_lows", "clean_trend"],
        ),
        MarketInfoObject(
            info_id="PA_2",
            pillar_target=PillarName.PRICE_ACTION,
            source_name="internal_price_engine",
            source_type=SourceType.INTERNAL_MODEL,
            source_tier=SourceTier.B,
            title="Compression under resistance",
            raw_text="Price is compressing below a local breakout zone.",
            normalized_summary="Compression could precede breakout continuation.",
            asset_scope=["EURUSD"],
            country_scope=[],
            time_horizon=TimeHorizon.INTRADAY,
            event_type=EventType.MARKET_MOVE,
            importance_score=78,
            confidence_score=82,
            novelty_score=68,
            market_relevance_score=80,
            direction_hint=DirectionHint.BULLISH,
            tags=["compression", "pre_breakout", "breakout_up"],
        ),
    ]

    thesis = build_regime_thesis(
        info_objects=infos,
        asset_scope=["EURUSD"],
        thesis_id="regime_test_001",
    )

    print(thesis.to_dict())


if __name__ == "__main__":
    main()