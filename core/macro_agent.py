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
Tu es un analyste macro forex senior.
On te donne un texte brut (article, news, opinion) sur un marché ou une devise.
Tu dois retourner UNIQUEMENT un objet JSON valide, sans texte avant ni après, avec exactement ces champs :

{
  "title": "titre court résumant l'information (max 10 mots)",
  "normalized_summary": "résumé neutre de l'information macro en 1-2 phrases",
  "direction_hint": "bullish" ou "bearish" ou "neutral" ou "mixed",
  "currency_main": "devise principale concernée (ex: USD, EUR, GBP, JPY, AUD, CAD, CHF, NZD)",
  "currency_secondary": "devise secondaire si applicable, sinon null",
  "asset_scope": ["paire(s) forex concernée(s) ex: EURUSD, GBPUSD"],
  "country_scope": ["pays concerné(s) ex: US, EU, UK, JP"],
  "importance_score": nombre entier entre 0 et 100,
  "confidence_score": nombre entier entre 0 et 100,
  "novelty_score": nombre entier entre 0 et 100,
  "market_relevance_score": nombre entier entre 0 et 100,
  "event_type": "data_release" ou "central_bank" ou "headline" ou "market_move" ou "other",
  "time_horizon": "intraday" ou "swing" ou "weekly" ou "macro",
  "tags": ["liste", "de", "tags", "pertinents"]
}

Tags disponibles pour macro :
hawkish, dovish, inflation_upside, inflation_downside, strong_jobs, weak_jobs,
usd_supportive, usd_negative, higher_rates, lower_rates, growth_positive,
growth_negative, risk_on, risk_off, eur_positive, eur_negative, gbp_positive,
gbp_negative, jpy_positive, jpy_negative, aud_positive, aud_negative,
cad_positive, cad_negative, geopolitical_risk, central_bank, data_release,
surprise_positive, surprise_negative, priced_in, not_priced_in

Réponds UNIQUEMENT avec le JSON. Aucun texte avant ou après.
"""


def analyze_text_to_market_info(
    raw_text: str,
    source_name: str = "groq_macro_agent",
    source_tier: SourceTier = SourceTier.B,
    info_id: str | None = None,
) -> MarketInfoObject:
    if info_id is None:
        info_id = f"MACRO_AGENT_{uuid.uuid4().hex[:8].upper()}"

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
        "data_release": EventType.DATA_RELEASE,
        "central_bank": EventType.CENTRAL_BANK,
        "headline": EventType.HEADLINE,
        "market_move": EventType.MARKET_MOVE,
        "other": EventType.OTHER,
    }

    horizon_map = {
        "intraday": TimeHorizon.INTRADAY,
        "swing": TimeHorizon.SWING,
        "weekly": TimeHorizon.WEEKLY,
        "macro": TimeHorizon.MACRO,
    }

    return MarketInfoObject(
        info_id=info_id,
        pillar_target=PillarName.MACRO,
        source_name=source_name,
        source_type=SourceType.NEWSWIRE,
        source_tier=source_tier,
        title=parsed.get("title", "no_title"),
        raw_text=raw_text,
        normalized_summary=parsed.get("normalized_summary", ""),
        asset_scope=parsed.get("asset_scope", []),
        country_scope=parsed.get("country_scope", []),
        time_horizon=horizon_map.get(parsed.get("time_horizon", "swing"), TimeHorizon.SWING),
        event_type=event_map.get(parsed.get("event_type", "other"), EventType.OTHER),
        importance_score=int(parsed.get("importance_score", 50)),
        confidence_score=int(parsed.get("confidence_score", 50)),
        novelty_score=int(parsed.get("novelty_score", 50)),
        market_relevance_score=int(parsed.get("market_relevance_score", 50)),
        direction_hint=direction_map.get(parsed.get("direction_hint", "neutral"), DirectionHint.NEUTRAL),
        tags=parsed.get("tags", []),
    )


def analyze_texts_to_market_infos(
    texts: List[str],
    source_name: str = "groq_macro_agent",
    source_tier: SourceTier = SourceTier.B,
) -> List[MarketInfoObject]:
    results = []
    for text in texts:
        info = analyze_text_to_market_info(
            raw_text=text,
            source_name=source_name,
            source_tier=source_tier,
        )
        results.append(info)
    return results