from __future__ import annotations

import json
import os
import uuid
from typing import List

from dotenv import load_dotenv
from groq import Groq

from core.thesis_objects import (
    DirectionHint,
    EventType,
    MarketInfoObject,
    PillarName,
    SourceTier,
    SourceType,
    TimeHorizon,
)

load_dotenv()

_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM_PROMPT = """
Tu es un analyste spécialisé dans le sentiment de marché et le positionnement forex.
On te donne un texte brut (article, news, opinion) sur les marchés financiers.
Tu dois retourner UNIQUEMENT un objet JSON valide, sans texte avant ni après, avec exactement ces champs :

{
  "title": "titre court résumant le sentiment (max 10 mots)",
  "normalized_summary": "résumé neutre du sentiment de marché en 1-2 phrases",
  "direction_hint": "bullish" ou "bearish" ou "neutral" ou "mixed",
  "risk_regime": "risk_on" ou "risk_off" ou "neutral",
  "asset_scope": ["paires forex concernées ex: EURUSD, USDJPY, AUDUSD"],
  "country_scope": [],
  "importance_score": nombre entier entre 0 et 100,
  "confidence_score": nombre entier entre 0 et 100,
  "novelty_score": nombre entier entre 0 et 100,
  "market_relevance_score": nombre entier entre 0 et 100,
  "event_type": "market_move" ou "positioning_update" ou "headline" ou "other",
  "time_horizon": "intraday" ou "swing",
  "tags": ["liste", "de", "tags", "pertinents"]
}

Tags disponibles pour sentiment :
risk_on, risk_off, fear, optimism, equities_strong, equities_weak,
vol_compression, panic, crowded_long, crowded_short, consensus_long,
consensus_short, euphoric, capitulation, overbought_sentiment,
oversold_sentiment, retail_short, retail_long, retail_fading_uptrend,
retail_fading_downtrend, carry_supportive, flight_to_safety,
squeeze_risk, positioning_extreme, excess, geopolitical_risk,
us_iran, trade_war, recession_fear, soft_landing, hard_landing

Réponds UNIQUEMENT avec le JSON. Aucun texte avant ou après.
"""


def analyze_sentiment_from_text(
    raw_text: str,
    source_name: str = "groq_sentiment_agent",
    source_tier: SourceTier = SourceTier.B,
    info_id: str | None = None,
) -> MarketInfoObject:
    if info_id is None:
        info_id = f"SENT_AGENT_{uuid.uuid4().hex[:8].upper()}"

    response = _client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": raw_text},
        ],
        temperature=0.2,
    )

    raw_response = response.choices[0].message.content.strip()
    parsed = json.loads(raw_response)

    direction_map = {
        "bullish": DirectionHint.BULLISH,
        "bearish": DirectionHint.BEARISH,
        "neutral": DirectionHint.NEUTRAL,
        "mixed": DirectionHint.MIXED,
    }

    event_map = {
        "market_move": EventType.MARKET_MOVE,
        "positioning_update": EventType.POSITIONING_UPDATE,
        "headline": EventType.HEADLINE,
        "other": EventType.OTHER,
    }

    horizon_map = {
        "intraday": TimeHorizon.INTRADAY,
        "swing": TimeHorizon.SWING,
    }

    risk_regime = parsed.get("risk_regime", "neutral")
    tags = parsed.get("tags", [])

    if risk_regime == "risk_on" and "risk_on" not in tags:
        tags.append("risk_on")
    elif risk_regime == "risk_off" and "risk_off" not in tags:
        tags.append("risk_off")

    return MarketInfoObject(
        info_id=info_id,
        pillar_target=PillarName.SENTIMENT,
        source_name=source_name,
        source_type=SourceType.NEWSWIRE,
        source_tier=source_tier,
        title=parsed.get("title", "no_title"),
        raw_text=raw_text,
        normalized_summary=parsed.get("normalized_summary", ""),
        asset_scope=parsed.get("asset_scope", []),
        country_scope=parsed.get("country_scope", []),
        time_horizon=horizon_map.get(parsed.get("time_horizon", "intraday"), TimeHorizon.INTRADAY),
        event_type=event_map.get(parsed.get("event_type", "other"), EventType.OTHER),
        importance_score=int(parsed.get("importance_score", 50)),
        confidence_score=int(parsed.get("confidence_score", 50)),
        novelty_score=int(parsed.get("novelty_score", 50)),
        market_relevance_score=int(parsed.get("market_relevance_score", 50)),
        direction_hint=direction_map.get(parsed.get("direction_hint", "neutral"), DirectionHint.NEUTRAL),
        tags=tags,
    )


def analyze_sentiments_from_texts(
    texts: List[str],
    source_name: str = "groq_sentiment_agent",
    source_tier: SourceTier = SourceTier.B,
) -> List[MarketInfoObject]:
    results = []
    for text in texts:
        info = analyze_sentiment_from_text(
            raw_text=text,
            source_name=source_name,
            source_tier=source_tier,
        )
        results.append(info)
    return results