"""预测路由。"""

from flask import Blueprint, jsonify, request

from services.review_service import predict_sample, correct_sample

bp = Blueprint("predict", __name__)


@bp.post("/api/predict/<sample_id>")
def api_predict(sample_id: str):
    data = request.get_json(silent=True) or {}
    use_fewshot = bool(data.get("use_fewshot"))
    result = predict_sample(sample_id, use_fewshot=use_fewshot)
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)


@bp.post("/api/correct/<sample_id>")
def api_correct(sample_id: str):
    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip().upper()
    grade = str(data.get("grade", "")).strip()
    reason = (data.get("reason") or "").strip()
    if not code:
        return jsonify({"error": "请填写正确的缺陷代码"}), 400
    result = correct_sample(sample_id, code, grade, reason)
    return jsonify(result)
