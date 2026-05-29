"""评测计算：准确率、混淆矩阵、per-code 统计。"""

from __future__ import annotations

from typing import Any


def evaluate_predictions(samples: list[dict[str, Any]], predictions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    total = 0
    code_hits = 0
    grade_hits = 0
    grade_within_one = 0
    unknowns = 0
    confusion: dict[str, dict[str, int]] = {}
    per_code: dict[str, dict[str, int]] = {}

    for sample in samples:
        sid = sample["id"]
        pred = predictions.get(sid)
        if not pred:
            continue

        total += 1
        defects = pred.get("defects") or []
        first = defects[0] if defects else {}
        predicted_code = str(first.get("code") or "UNKNOWN").upper()
        predicted_grade = first.get("grade")

        expected_code = sample.get("defect_code", "").upper()
        expected_grade = sample.get("grade", "")

        if predicted_code == "UNKNOWN":
            unknowns += 1

        if predicted_code == expected_code:
            code_hits += 1

        try:
            eg = int(expected_grade) if expected_grade else None
            pg = int(predicted_grade) if predicted_grade is not None else None
            if eg is not None and pg is not None:
                if pg == eg:
                    grade_hits += 1
                if abs(pg - eg) <= 1:
                    grade_within_one += 1
        except (TypeError, ValueError):
            pass

        confusion.setdefault(expected_code, {})
        confusion[expected_code][predicted_code] = confusion[expected_code].get(predicted_code, 0) + 1

        per_code.setdefault(expected_code, {"total": 0, "hits": 0, "unknowns": 0})
        per_code[expected_code]["total"] += 1
        if predicted_code == expected_code:
            per_code[expected_code]["hits"] += 1
        if predicted_code == "UNKNOWN":
            per_code[expected_code]["unknowns"] += 1

    code_accuracy = round(code_hits / total, 4) if total else 0
    grade_accuracy = round(grade_hits / total, 4) if total else 0
    grade_within_one_accuracy = round(grade_within_one / total, 4) if total else 0
    unknown_rate = round(unknowns / total, 4) if total else 0

    per_code_stats = {}
    for code, stats in per_code.items():
        t = stats["total"]
        per_code_stats[code] = {
            "total": t,
            "hits": stats["hits"],
            "accuracy": round(stats["hits"] / t, 4) if t else 0,
            "unknowns": stats["unknowns"],
        }

    return {
        "total": total,
        "code_hits": code_hits,
        "grade_hits": grade_hits,
        "unknowns": unknowns,
        "code_accuracy": code_accuracy,
        "grade_accuracy": grade_accuracy,
        "grade_within_one_accuracy": grade_within_one_accuracy,
        "unknown_rate": unknown_rate,
        "per_code": per_code_stats,
        "confusion": confusion,
    }
