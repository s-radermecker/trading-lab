from core.macro_pillar import build_macro_thesis
from core.thesis_objects import (
    MarketInfoObject,
    PillarName,
    SourceTier,
    SourceType,
    EventType,
    TimeHorizon,
    DirectionHint,
)


def main() -> None:
    infos = [
        MarketInfoObject(
            info_id="US_CPI_1",
            pillar_target=PillarName.MACRO,
            source_name="BLS",
            source_type=SourceType.OFFICIAL,
            source_tier=SourceTier.A,
            title="US CPI above consensus",
            raw_text="US CPI stronger than expected",
            normalized_summary="Inflation surprise positive for USD.",
            asset_scope=["EURUSD", "GBPUSD", "USDJPY"],
            country_scope=["US"],
            time_horizon=TimeHorizon.MACRO,
            event_type=EventType.DATA_RELEASE,
            importance_score=90,
            confidence_score=95,
            novelty_score=90,
            market_relevance_score=95,
            direction_hint=DirectionHint.BULLISH,
            tags=["hawkish", "inflation_upside", "usd_supportive"],
        ),
        MarketInfoObject(
            info_id="FED_1",
            pillar_target=PillarName.MACRO,
            source_name="FOMC",
            source_type=SourceType.OFFICIAL,
            source_tier=SourceTier.A,
            title="Fed remains restrictive",
            raw_text="Fed signals higher for longer",
            normalized_summary="Fed remains restrictive and supports USD.",
            asset_scope=["EURUSD", "GBPUSD", "USDJPY"],
            country_scope=["US"],
            time_horizon=TimeHorizon.MACRO,
            event_type=EventType.CENTRAL_BANK,
            importance_score=95,
            confidence_score=98,
            novelty_score=85,
            market_relevance_score=95,
            direction_hint=DirectionHint.BULLISH,
            tags=["hawkish", "higher_rates", "usd_supportive"],
        ),
    ]

    thesis = build_macro_thesis(
        info_objects=infos,
        asset_scope=["EURUSD", "GBPUSD", "USDJPY"],
        thesis_id="macro_test_001",
    )

    print(thesis.to_dict())


if __name__ == "__main__":
    main()