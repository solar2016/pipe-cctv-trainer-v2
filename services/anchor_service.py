"""锚点推荐服务。"""

from __future__ import annotations

from typing import Any

from services.sample_service import load_samples, load_predictions, load_fewshot_anchors


def auto_recommend_anchors() -> dict[str, Any]:
    samples = load_samples()
    predictions = load_predictions()
    existing = load_fewshot_anchors()
    existing_ids = set()
    for code_anchors in existing.values():
        for a in code_anchors:
            existing_ids.add(a.get("sample_id", ""))

    recommendations = []
    used_sample_ids: set[str] = set()

    for sample in samples:
        sid = sample["id"]
        if sid in existing_ids or sid in used_sample_ids:
            continue

        pred = predictions.get(sid)
        if not pred:
            continue

        defects = pred.get("defects") or []
        first = defects[0] if defects else {}
        predicted_code = str(first.get("code") or "UNKNOWN").upper()
        expected_code = sample.get("defect_code", "").upper()
        confidence = float(first.get("confidence", 0) or 0)

        if predicted_code == "UNKNOWN":
            continue

        if predicted_code != expected_code:
            # 误判 → 作为反例候选
            if expected_code not in ("NONE", "UNKNOWN"):
                recommendations.append({
                    "sample_id": sid,
                    "anchor_type": "negative",
                    "target_code": predicted_code,
                    "reason": f"AI 误判为 {predicted_code}，实际为 {expected_code}",
                })
                used_sample_ids.add(sid)
        elif confidence < 0.7:
            # 低置信度判断对了 → 困难例
            recommendations.append({
                "sample_id": sid,
                "anchor_type": "hard",
                "target_code": expected_code,
                "reason": f"置信度仅 {confidence:.2f}，模型不确定",
            })
            used_sample_ids.add(sid)

    return {"recommendations": recommendations[:20], "total": len(recommendations)}


def apply_recommendations(confirmations: list[dict[str, Any]]) -> dict[str, Any]:
    from services.sample_service import save_fewshot_anchor
    applied = 0
    for c in confirmations:
        if not c.get("confirmed"):
            continue
        try:
            save_fewshot_anchor(
                c["sample_id"], c["anchor_type"], c["target_code"], c.get("reason", "")
            )
            applied += 1
        except Exception:
            pass
    return {"ok": True, "applied": applied}


def find_confusion_probes() -> list[dict[str, Any]]:
    samples = load_samples()
    predictions = load_predictions()
    probes = []

    for sample in samples:
        sid = sample["id"]
        pred = predictions.get(sid)
        if not pred:
            continue

        defects = pred.get("defects") or []
        first = defects[0] if defects else {}
        confidence = float(first.get("confidence", 0) or 0)
        expected_code = sample.get("defect_code", "").upper()

        # 判对但犹豫
        if str(first.get("code") or "").upper() == expected_code and 0.5 <= confidence < 0.75:
            probes.append({
                "sample_id": sid,
                "code": expected_code,
                "confidence": confidence,
                "reason": "判对但置信度低，存在混淆风险",
                "observation": pred.get("observation", {}),
            })

    return probes
