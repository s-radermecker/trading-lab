from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.connectors.investinglive import fetch_latest_articles
from core.macro_agent import analyze_texts_to_market_infos as analyze_macro
from core.sentiment_agent import analyze_sentiments_from_texts as analyze_sentiment
from core.pipeline_v1 import run_pipeline_v1
from core.thesis_objects import MarketInfoObject


def run_pipeline_v2(
    asset_scope: List[str],
    pipeline_id: str = "pipeline_v2_run",
    news_section: str = "forex",
    max_articles: int = 5,
    extra_info_objects: Optional[List[MarketInfoObject]] = None,
) -> Dict[str, Any]:
    print(f"[pipeline_v2] Fetching live articles from investinglive ({news_section})...")
    articles = fetch_latest_articles(
        section=news_section,
        max_articles=max_articles,
        fetch_full_text=True,
        delay_between_requests=1.0,
    )

    if not articles:
        print("[pipeline_v2] No articles fetched. Running pipeline with empty info objects.")
        texts = []
    else:
        texts = [f"{a.title}\n\n{a.summary}" for a in articles]
        print(f"[pipeline_v2] {len(texts)} articles fetched.")

    macro_infos = []
    sentiment_infos = []

    if texts:
        print("[pipeline_v2] Running macro agent...")
        macro_infos = analyze_macro(
            texts=texts,
            source_name="investinglive",
        )

        print("[pipeline_v2] Running sentiment agent...")
        sentiment_infos = analyze_sentiment(
            texts=texts,
            source_name="investinglive",
        )

    all_infos = macro_infos + sentiment_infos

    if extra_info_objects:
        all_infos += extra_info_objects

    print(f"[pipeline_v2] Running 7-pillar pipeline with {len(all_infos)} info objects...")
    result = run_pipeline_v1(
        info_objects=all_infos,
        asset_scope=asset_scope,
        pipeline_id=pipeline_id,
    )

    result["sources"] = [a.url for a in articles]
    result["articles_analyzed"] = len(articles)

    return result