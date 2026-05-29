"""Prompt 路由。"""

from flask import Blueprint, jsonify, request

from services.prompt_service import (
    list_prompts, list_prompts_with_details, list_change_logs,
    get_prompt, get_prompt_diff, set_active_prompt, get_active_prompt,
)
from services.prompt_optimize import analyze_confusion_and_suggest_prompt

bp = Blueprint("prompts", __name__)


@bp.get("/api/prompts")
def api_list_prompts():
    prompts = list_prompts()
    active = get_active_prompt()
    return jsonify({"prompts": prompts, "has_active": active is not None})


@bp.get("/api/prompts/details")
def api_list_prompts_details():
    """列出所有版本含详情（含 prompt 预览和变更记录）。"""
    prompts = list_prompts_with_details()
    logs = list_change_logs()
    return jsonify({"prompts": prompts, "change_logs": logs})


@bp.get("/api/prompts/<version>")
def api_get_prompt(version: str):
    p = get_prompt(version)
    if not p:
        return jsonify({"error": "版本不存在"}), 404
    return jsonify(p)


@bp.get("/api/prompts/diff")
def api_prompt_diff():
    """对比两个版本。"""
    a = request.args.get("a", "")
    b = request.args.get("b", "")
    if not a or not b:
        return jsonify({"error": "请提供 a 和 b 参数"}), 400
    diff = get_prompt_diff(a, b)
    if "error" in diff:
        return jsonify(diff), 404
    return jsonify(diff)


@bp.post("/api/prompts/<version>/activate")
def api_activate_prompt(version: str):
    ok = set_active_prompt(version)
    if not ok:
        return jsonify({"error": "版本不存在"}), 404
    return jsonify({"ok": True, "version": version})


@bp.delete("/api/prompts/<version>")
def api_delete_prompt(version: str):
    from services.prompt_service import delete_prompt
    ok = delete_prompt(version)
    if not ok:
        return jsonify({"error": "版本不存在"}), 404
    return jsonify({"ok": True})


@bp.post("/api/prompt/optimize")
def api_optimize_prompt():
    result = analyze_confusion_and_suggest_prompt()
    return jsonify(result)
