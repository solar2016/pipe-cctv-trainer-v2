"""样本路由。"""

from flask import Blueprint, jsonify, request, send_file

from services.sample_service import load_samples, get_sample, get_sample_image_path, get_sample_text, load_predictions

bp = Blueprint("samples", __name__)


@bp.get("/api/samples")
def api_samples():
    samples = load_samples()
    predictions = load_predictions()
    for s in samples:
        pred = predictions.get(s["id"])
        if pred:
            s["ai_prediction"] = pred
            s["status"] = "predicted"
            defects = pred.get("defects") or []
            first = defects[0] if defects else {}
            s["ai_code"] = first.get("code", "")
            s["ai_grade"] = first.get("grade", "")
            s["ai_confidence"] = first.get("confidence", 0)
            if s.get("correction"):
                s["status"] = "corrected"
    return jsonify({"samples": samples})


@bp.get("/api/samples/<sample_id>")
def api_sample(sample_id: str):
    sample = get_sample(sample_id)
    if not sample:
        return jsonify({"error": "样本不存在"}), 404
    predictions = load_predictions()
    pred = predictions.get(sample["id"])
    if pred:
        sample["ai_prediction"] = pred
    return jsonify({"sample": sample, "answer_text": get_sample_text(sample)})


@bp.get("/sample-images/<sample_id>.png")
def sample_image(sample_id: str):
    sample = get_sample(sample_id)
    if not sample:
        return "not found", 404
    path = get_sample_image_path(sample)
    if not path or not path.exists():
        return "not found", 404
    return send_file(path, mimetype="image/png")
