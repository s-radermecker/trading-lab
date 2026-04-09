from core.journal_logger import save_pipeline_run
from core.pipeline_v1 import run_pipeline_v1
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
            info_id="JOURNAL_MACRO_1",
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
            info_id="JOURNAL_REGIME_1",
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
            info_id="JOURNAL_SENT_1",
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

    result = run_pipeline_v1(
        info_objects=infos,
        asset_scope=["EURUSD"],
        pipeline_id="journal_test_001",
    )

    saved_path = save_pipeline_run(
        pipeline_result=result,
        output_dir="lab_runs",
    )

    print(saved_path)


if __name__ == "__main__":
    main()