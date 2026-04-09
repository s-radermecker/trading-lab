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
            info_id="SENT_1",
            pillar_target=PillarName.SENTIMENT,
            source_name="internal_sentiment_engine",
            source_type=SourceType.INTERNAL_MODEL,
            source_tier=SourceTier.B,
            title="Risk-on tone across markets",
            raw_text="Equities strong and volatility compressed.",
            normalized_summary="Broad risk-on tone supportive of continuation.",
            asset_scope=["EURUSD", "GBPUSD", "AUDUSD"],
            country_scope=[],
            time_horizon=TimeHorizon.INTRADAY,
            event_type=EventType.MARKET_MOVE,
            importance_score=78,
            confidence_score=82,
            novelty_score=70,
            market_relevance_score=80,
            direction_hint=DirectionHint.BULLISH,
            tags=["risk_on", "equities_strong", "vol_compression"],
        ),
        MarketInfoObject(
            info_id="SENT_2",
            pillar_target=PillarName.SENTIMENT,
            source_name="retail_positioning_feed",
            source_type=SourceType.POSITIONING,
            source_tier=SourceTier.B,
            title="Retail remains short into strength",
            raw_text="Retail traders continue fading the move.",
            normalized_summary="Retail short positioning acts as a contrarian bullish support.",
            asset_scope=["EURUSD"],
            country_scope=[],
            time_horizon=TimeHorizon.INTRADAY,
            event_type=EventType.POSITIONING_UPDATE,
            importance_score=72,
            confidence_score=79,
            novelty_score=66,
            market_relevance_score=74,
            direction_hint=DirectionHint.BULLISH,
            tags=["retail_short", "retail_fading_uptrend"],
        ),
    ]

    thesis = build_sentiment_thesis(
        info_objects=infos,
        asset_scope=["EURUSD"],
        thesis_id="sentiment_test_001",
    )

    print(thesis.to_dict())


if __name__ == "__main__":
    main()