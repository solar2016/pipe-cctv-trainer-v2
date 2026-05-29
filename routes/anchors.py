"""锚点路由。"""

from flask import Blueprint, jsonify, request

from services.sample_service import (
    save_fewshot_anchor, remove_fewshot_anchor, load_fewshot_anchors,
)
from services.anchor_service import auto_recommend_anchors, apply_recommendations, find_confusion_probes

bp = Blueprint("anchors", __name__)


@bp.get("/api/fewshot")
def api_list_fewshot():
    anchors = load_fewshot_anchors()
    summary = {}
    for code, items in anchors.items():
        summary[code] = {"total": len(items), "by_type": {}}
        for item in items:
            t = item.get("anchor_type", "")
            summary[code]["by_type"][t] = summary[code]["by_type"].get(t, 0) + 1
    return jsonify({"anchors": anchors, "summary": summary})


@bp.post("/api/fewshot/<sample_id>")
def api_save_fewshot(sample_id: str):
    data = request.get_json(silent=True) or {}
    anchor_type = (data.get("anchor_type") or "").strip()
    target_code = (data.get("target_code") or "").strip().upper()
    note = (data.get("note") or "").strip()
    if not anchor_type or not target_code:
        return jsonify({"error": "请填写锚点类型和目标缺陷代码"}), 400
    if anchor_type not in ("positive", "hard", "boundary", "negative"):
        return jsonify({"error": "锚点类型必须是 positive/hard/boundary/negative"}), 400

    # 防重复检查
    from services.sample_service import load_fewshot_anchors
    existing = load_fewshot_anchors()
    for code, anchors in existing.items():
        for a in anchors:
            if a.get("sample_id") == sample_id and a.get("anchor_type") == anchor_type and a.get("target_code") == target_code:
                return jsonify({"ok": False, "error": f"该样本已存在相同的锚点（{anchor_type} {target_code}）"}), 409

    record = save_fewshot_anchor(sample_id, anchor_type, target_code, note)
    return jsonify({"ok": True, "anchor": record})


@bp.delete("/api/fewshot/<sample_id>")
def api_remove_fewshot(sample_id: str):
    anchor_type = request.args.get("type", "")
    target_code = request.args.get("code", "")
    removed = remove_fewshot_anchor(sample_id, anchor_type, target_code)
    return jsonify({"ok": True, "removed": removed})


@bp.post("/api/anchors/recommend")
def api_recommend_anchors():
    result = auto_recommend_anchors()
    return jsonify(result)


@bp.post("/api/anchors/confirm")
def api_confirm_anchors():
    data = request.get_json(silent=True) or {}
    confirmations = data.get("confirmations", [])
    result = apply_recommendations(confirmations)
    return jsonify(result)


@bp.get("/api/confusion-probes")
def api_confusion_probes():
    probes = find_confusion_probes()
    return jsonify({"probes": probes, "total": len(probes)})


@bp.get("/api/anchor-candidates/<code>")
def api_anchor_candidates(code: str):
    """按缺陷代码推荐候选样本（用于定向优化后的锚点创建）。"""
    from services.sample_service import load_samples, load_predictions, load_fewshot_anchors
    code = code.upper()

    samples = load_samples()
    predictions = load_predictions()
    existing = load_fewshot_anchors()
    existing_ids = set()
    for code_anchors in existing.values():
        for a in code_anchors:
            existing_ids.add(a.get("sample_id", ""))

    candidates = {"positive": [], "hard": [], "negative": []}

    for sample in samples:
        sid = sample.get("id", "")
        true_code = sample.get("defect_code", "").upper()
        pred = predictions.get(sid, {})
        defects = pred.get("defects", [])
        first = defects[0] if defects else {}
        pred_code = str(first.get("code", "")).upper()
        conf = float(first.get("confidence", 0) or 0)

        if sid in existing_ids:
            continue

        # 正例：真实标签匹配且已预测对
        if true_code == code and pred_code == code and len(candidates["positive"]) < 5:
            candidates["positive"].append({
                "sample_id": sid,
                "confidence": conf,
                "reason": f"真实为{code}，AI也判对",
            })

        # 困难例：真实标签匹配但置信度低
        if true_code == code and pred_code == code and 0.4 <= conf < 0.75 and len(candidates["hard"]) < 5:
            candidates["hard"].append({
                "sample_id": sid,
                "confidence": conf,
                "reason": f"判对但置信度仅{conf:.0%}",
            })

        # 反例：被误判为该代码
        if pred_code == code and true_code != code and true_code not in ("NONE", "UNKNOWN") and len(candidates["negative"]) < 5:
            candidates["negative"].append({
                "sample_id": sid,
                "true_code": true_code,
                "confidence": conf,
                "reason": f"实际为{true_code}，被误判为{code}",
            })

    return jsonify({"code": code, "candidates": candidates})
