from __future__ import annotations

from typing import Any, Dict, List

from core.execution_pillar import build_execution_thesis
from core.global_synthesis import build_global_thesis
from core.macro_pillar import build_macro_thesis
from core.process_strategy_pillar import build_process_strategy_thesis
from core.regime_pillar import build_regime_thesis
from core.risk_pillar import build_risk_thesis
from core.sentiment_pillar import build_sentiment_thesis
from core.thesis_objects import MarketInfoObject


def run_pipeline_v1(
    info_objects: List[MarketInfoObject],
    asset_scope: List[str],
    pipeline_id: str = "pipeline_v1_run",
) -> Dict[str, Any]:
    macro_thesis = build_macro_thesis(
        info_objects=info_objects,
        asset_scope=asset_scope,
        thesis_id=f"{pipeline_id}_macro",
    )

    regime_thesis = build_regime_thesis(
        info_objects=info_objects,
        asset_scope=asset_scope,
        thesis_id=f"{pipeline_id}_regime",
    )

    sentiment_thesis = build_sentiment_thesis(
        info_objects=info_objects,
        asset_scope=asset_scope,
        thesis_id=f"{pipeline_id}_sentiment",
    )

    global_thesis = build_global_thesis(
        macro_thesis=macro_thesis,
        regime_thesis=regime_thesis,
        sentiment_thesis=sentiment_thesis,
        global_thesis_id=f"{pipeline_id}_global",
        asset_scope=asset_scope,
    )

    risk_thesis = build_risk_thesis(
        global_thesis=global_thesis,
        thesis_id=f"{pipeline_id}_risk",
    )

    process_thesis = build_process_strategy_thesis(
        global_thesis=global_thesis,
        risk_thesis=risk_thesis,
        thesis_id=f"{pipeline_id}_process",
    )

    execution_thesis = build_execution_thesis(
        global_thesis=global_thesis,
        risk_thesis=risk_thesis,
        process_thesis=process_thesis,
        thesis_id=f"{pipeline_id}_execution",
    )

    return {
        "pipeline_id": pipeline_id,
        "asset_scope": asset_scope,
        "macro": macro_thesis.to_dict(),
        "regime": regime_thesis.to_dict(),
        "sentiment": sentiment_thesis.to_dict(),
        "global": global_thesis.to_dict(),
        "risk": risk_thesis.to_dict(),
        "process": process_thesis.to_dict(),
        "execution": execution_thesis.to_dict(),
    }