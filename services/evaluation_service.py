"""评测服务。"""

from __future__ import annotations

import json
import time
from typing import Any

from config import EVALUATIONS_DIR
from core.evaluator import evaluate_predictions
from services.sample_service import load_samples, load_predictions


def run_evaluation(label: str = "eval") -> dict[str, Any]:
    samples = load_samples()
    predictions = load_predictions()
    result = evaluate_predictions(samples, predictions)

    stamp = time.strftime("%Y%m%d_%H%M%S")
    eval_record = {
        "id": f"{label}_{stamp}",
        "label": label,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "result": result,
    }

    path = EVALUATIONS_DIR / f"{eval_record['id']}.json"
    path.write_text(json.dumps(eval_record, ensure_ascii=False, indent=2), encoding="utf-8")

    return eval_record


def list_evaluations() -> list[dict[str, Any]]:
    if not EVALUATIONS_DIR.exists():
        return []
    evals = []
    for f in sorted(EVALUATIONS_DIR.glob("*.json"), reverse=True):
        if f.name.startswith("report_") or f.name.startswith("agent_") or f.name.startswith("priorities_") or f.name.startswith("optimization_"):
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
            evals.append({
                "id": data.get("id", f.stem),
                "label": data.get("label", ""),
                "timestamp": data.get("timestamp", ""),
                "code_accuracy": data["result"]["code_accuracy"],
                "grade_accuracy": data["result"]["grade_accuracy"],
                "unknown_rate": data["result"]["unknown_rate"],
                "total": data["result"]["total"],
            })
        except Exception:
            pass
    return evals


def get_evaluation(eval_id: str) -> dict[str, Any] | None:
    path = EVALUATIONS_DIR / f"{eval_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
