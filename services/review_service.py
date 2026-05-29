"""预测 + 纠正服务。"""

from __future__ import annotations

from typing import Any

from core.vision import analyze_image
from services.sample_service import (
    get_sample, get_sample_image_path, update_sample_prediction, save_correction,
    get_fewshot_anchors_for_code, get_dynamic_fewshot_anchors,
)


def predict_sample(sample_id: str, use_fewshot: bool = False) -> dict[str, Any]:
    sample = get_sample(sample_id)
    if not sample:
        return {"error": "样本不存在"}

    img_path = get_sample_image_path(sample)
    if not img_path:
        return {"error": "样本图片不存在"}

    image_bytes = img_path.read_bytes()

    fewshot_anchors = None
    if use_fewshot:
        fewshot_anchors = get_dynamic_fewshot_anchors()
        if not fewshot_anchors:
            expected_code = sample.get("defect_code", "")
            if expected_code:
                fewshot_anchors = get_fewshot_anchors_for_code(expected_code)

    result = analyze_image(image_bytes, "image/png", fewshot_anchors=fewshot_anchors)

    update_sample_prediction(sample_id, result)

    sample["ai_prediction"] = result
    sample["status"] = "predicted"

    return {
        "result": result,
        "sample": sample,
        "comparison": _compare(result, sample),
    }


def correct_sample(sample_id: str, correct_code: str, correct_grade: str, reason: str = "") -> dict[str, Any]:
    sample = get_sample(sample_id)
    if not sample:
        return {"error": "样本不存在"}

    correction = save_correction(sample_id, correct_code, correct_grade, reason)
    return {"ok": True, "correction": correction}


def _compare(result: dict[str, Any], sample: dict[str, Any]) -> dict[str, Any]:
    defects = result.get("defects") or []
    first = defects[0] if defects else {}
    predicted_code = str(first.get("code") or "").upper()
    predicted_grade = "" if first.get("grade") is None else str(first.get("grade"))

    expected_code = sample.get("defect_code", "").upper()
    expected_grade = sample.get("grade", "")

    return {
        "expected_code": expected_code,
        "predicted_code": predicted_code,
        "code_match": predicted_code == expected_code,
        "expected_grade": expected_grade,
        "predicted_grade": predicted_grade,
        "grade_match": predicted_grade == expected_grade,
    }
