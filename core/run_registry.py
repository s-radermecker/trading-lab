from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


def register_pipeline_run(
    pipeline_result: Dict[str, Any],
    run_file_path: str,
    registry_path: str = "lab_runs/run_registry.json",
) -> str:
    registry_file = Path(registry_path)
    registry_file.parent.mkdir(parents=True, exist_ok=True)

    if registry_file.exists():
        with registry_file.open("r", encoding="utf-8") as f:
            registry_data = json.load(f)
    else:
        registry_data = []

    global_block = pipeline_result.get("global", {})

    entry = {
        "registered_at": datetime.now().isoformat(),
        "pipeline_id": pipeline_result.get("pipeline_id", ""),
        "asset_scope": pipeline_result.get("asset_scope", []),
        "run_file_path": run_file_path,
        "global_state_label": global_block.get("state_label", ""),
        "global_bias": global_block.get("global_bias", ""),
        "trade_permission": global_block.get("trade_permission", ""),
        "preferred_style": global_block.get("preferred_style", ""),
        "trigger_state": global_block.get("trigger_state", ""),
        "risk_posture": global_block.get("risk_posture", ""),
    }

    registry_data.append(entry)

    with registry_file.open("w", encoding="utf-8") as f:
        json.dump(registry_data, f, ensure_ascii=False, indent=2)

    return str(registry_file)


def load_run_registry(
    registry_path: str = "lab_runs/run_registry.json",
) -> List[Dict[str, Any]]:
    registry_file = Path(registry_path)

    if not registry_file.exists():
        return []

    with registry_file.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        return []

    return data