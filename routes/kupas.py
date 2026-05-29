"""KUPAS CAMP 评测平台适配接口。"""

from __future__ import annotations

import base64
import json
from flask import Blueprint, jsonify, request

from core.vision import analyze_image
from core.taxonomy import get_defects

bp = Blueprint("kupas", __name__)


@bp.post("/api/kupas")
def api_kupas():
    """KUPAS CAMP 统一入口。

    接收格式：
    {
        "input": "图片URL 或 base64 或 文本描述"
    }

    返回格式：
    {
        "output": "结构化 JSON 字符串"
    }
    """
    data = request.get_json(silent=True) or {}
    user_input = (data.get("input") or data.get("query") or "").strip()

    if not user_input:
        return jsonify({"output": json.dumps({"error": "缺少 input 参数"}, ensure_ascii=False)})

    try:
        image_bytes, mime_type = _resolve_image(user_input)
    except ValueError as e:
        return jsonify({"output": json.dumps({"error": str(e)}, ensure_ascii=False)})

    try:
        result = analyze_image(image_bytes, mime_type)
    except Exception as e:
        return jsonify({"output": json.dumps({"error": f"分析失败: {str(e)}"}, ensure_ascii=False)})

    # 包装成 KUPAS 期望的简洁输出
    output = _format_output(result)
    return jsonify({"output": json.dumps(output, ensure_ascii=False)})


@bp.post("/api/kupas/health")
def api_kupas_health():
    return jsonify({"status": "ok", "agent": "pipe-cctv-defect-detector"})


def _resolve_image(user_input: str) -> tuple[bytes, str]:
    """解析输入为图片 bytes 和 mime type。"""
    import requests as req

    # 1. base64
    if user_input.startswith("data:image/"):
        header, b64data = user_input.split(",", 1)
        mime = header.split(":")[1].split(";")[0]
        return base64.b64decode(b64data), mime

    if _looks_like_base64(user_input):
        return base64.b64decode(user_input), "image/png"

    # 2. URL
    if user_input.startswith(("http://", "https://")):
        resp = req.get(user_input, timeout=30)
        resp.raise_for_status()
        ct = resp.headers.get("Content-Type", "image/png")
        mime = ct.split(";")[0].strip()
        return resp.content, mime

    raise ValueError("无法识别输入格式，请提供图片 URL 或 base64 编码")


def _looks_like_base64(s: str) -> bool:
    if len(s) < 100:
        return False
    try:
        base64.b64decode(s)
        return True
    except Exception:
        return False


def _format_output(result: dict) -> dict:
    """把检测结果格式化为 KUPAS 评测友好的结构。"""
    defects = result.get("defects", [])
    primary = defects[0] if defects else {}

    return {
        "defect_code": primary.get("code", "UNKNOWN"),
        "defect_name": primary.get("name", "无法判断"),
        "grade": primary.get("grade"),
        "confidence": primary.get("confidence", 0),
        "bbox": primary.get("bbox"),
        "defect_ratio": primary.get("defect_ratio"),
        "position_detail": primary.get("position_detail", ""),
        "visible_features": primary.get("visible_features", []),
        "recommendation": primary.get("recommendation", ""),
        "all_defects": [
            {
                "code": d.get("code"),
                "name": d.get("name"),
                "grade": d.get("grade"),
                "confidence": d.get("confidence"),
            }
            for d in defects
        ],
        "observation": result.get("observation", {}),
        "overall_risk": result.get("overall_risk", ""),
        "needs_human_review": result.get("needs_human_review", True),
        "report_text": result.get("report_text", ""),
        "review_stage": result.get("review_stage", "first_pass"),
    }
