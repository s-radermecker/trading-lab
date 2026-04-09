from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


def save_pipeline_run(
    pipeline_result: Dict[str, Any],
    output_dir: str = "lab_runs",
) -> str:
    base_dir = Path(output_dir)
    base_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pipeline_id = pipeline_result.get("pipeline_id", "pipeline_run")
    safe_pipeline_id = str(pipeline_id).replace(" ", "_")

    file_path = base_dir / f"{timestamp}_{safe_pipeline_id}.json"

    with file_path.open("w", encoding="utf-8") as f:
        json.dump(pipeline_result, f, ensure_ascii=False, indent=2)

    return str(file_path)