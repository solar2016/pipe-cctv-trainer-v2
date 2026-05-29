"""AI 检测引擎。方法论对齐版：7步观察 + 6条扫描策略 + bbox输出。"""

from __future__ import annotations

import base64
import json
from typing import Any

import requests

from config import get_api_base, get_api_key, get_model, SAMPLES_DIR
from core.taxonomy import defect_options_text, enrich_defect

TEMPERATURE = 0.1
FEWSHOT_MAX = 8


def analyze_image(image_bytes: bytes, mime_type: str = "image/png", fewshot_anchors: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    from services.prompt_service import get_active_prompt_info
    prompt_info = get_active_prompt_info()
    prompt = _build_prompt()
    fewshot_images = _load_fewshot_images(fewshot_anchors)
    first = _call_model(image_bytes, mime_type, prompt, fewshot_images)
    first = _normalize(first)
    first["review_stage"] = "first_pass"
    if prompt_info:
        first["prompt_version"] = prompt_info["version"]
        first["prompt_reason"] = prompt_info.get("reason", "")
    if fewshot_anchors:
        first["fewshot_used"] = len(fewshot_images)

    code = _primary_code(first)
    if code in ("CJ", "SG", "ZA", "UNKNOWN"):
        try:
            second = _call_model(image_bytes, mime_type, _build_second_pass_prompt(first))
            second = _normalize(second)
            second["review_stage"] = "second_pass"
            second["first_pass_summary"] = {
                "code": _primary_code(first),
                "grade": _primary_grade(first),
                "confidence": _primary_confidence(first),
            }
            first = second
        except Exception:
            pass

    return _apply_unknown_route(image_bytes, mime_type, first)


def _load_fewshot_images(anchors: list[dict[str, Any]] | None) -> list[tuple[bytes, str, str]]:
    if not anchors:
        return []
    images = []
    type_order = {"positive": 0, "hard": 1, "boundary": 2, "negative": 3}
    sorted_anchors = sorted(anchors, key=lambda a: type_order.get(a.get("anchor_type", ""), 9))

    for anchor in sorted_anchors[:FEWSHOT_MAX]:
        sid = anchor.get("sample_id", "")
        img_path = SAMPLES_DIR / "images" / f"{sid}.png"
        if not img_path.exists():
            continue
        atype = anchor.get("anchor_type", "")
        code = anchor.get("target_code", "")
        note = anchor.get("note", "")
        reason = anchor.get("reason", "")

        desc = f"[{code}] "
        if atype == "positive":
            desc += f"正例：这是 {code} 的典型样本"
        elif atype == "hard":
            desc += f"困难例：这是 {code}，容易被误判"
        elif atype == "boundary":
            desc += f"边界例：这是 {code}，置信度较低"
        elif atype == "negative":
            desc += f"反例：这不是 {code}，注意区分"
        if reason:
            desc += f"。{reason}"
        elif note:
            desc += f"。{note}"
        images.append((img_path.read_bytes(), "image/png", desc))
    return images


def _call_model(image_bytes: bytes, mime_type: str, prompt: str, fewshot_images: list[tuple[bytes, str, str]] | None = None) -> dict[str, Any]:
    base_url = get_api_base()
    api_key = get_api_key()
    model = get_model()
    if not base_url or not api_key:
        raise RuntimeError("缺少 OPENAI_API_BASE_URL 或 OPENAI_API_KEY")

    url = base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"

    content: list[dict[str, Any]] = []
    if fewshot_images:
        content.append({"type": "text", "text": "以下是不同类型缺陷的参考样本图片，请先学习它们的视觉特征和区分要点，然后独立判断最后一张图片的缺陷类型。注意：参考样本的标签仅供参考学习，你需要根据图片内容独立判断。"})
        for img_bytes, img_mime, desc in fewshot_images:
            data_url = f"data:{img_mime};base64,{base64.b64encode(img_bytes).decode()}"
            content.append({"type": "text", "text": desc})
            content.append({"type": "image_url", "image_url": {"url": data_url}})
        content.append({"type": "text", "text": "---\n现在请独立判断以下这张图片，不要受参考样本标签的影响，根据图片可见证据做判断："})

    content.append({"type": "text", "text": prompt})
    target_url = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode()}"
    content.append({"type": "image_url", "image_url": {"url": target_url}})

    payload = {
        "model": model,
        "temperature": TEMPERATURE,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "你是城镇排水管道 CCTV 检测复核助手。只根据图片可见证据做初判。"},
            {"role": "user", "content": content},
        ],
    }
    resp = requests.post(url, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json=payload, timeout=120)
    resp.raise_for_status()
    resp_json = resp.json()
    content_text = resp_json["choices"][0]["message"]["content"]

    # 记录 token 使用量
    usage = resp_json.get("usage", {})
    if usage:
        import sys
        print(f"[Token] model={model}, prompt={usage.get('prompt_tokens', 0)}, completion={usage.get('completion_tokens', 0)}, total={usage.get('total_tokens', 0)}", file=sys.stderr)

    return _parse_json(content_text)


def _parse_json(content: str) -> dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            return json.loads(content[start:end + 1])
        raise RuntimeError("模型没有返回合法 JSON")


def _normalize(result: dict[str, Any]) -> dict[str, Any]:
    defects = result.get("defects")
    if not isinstance(defects, list):
        if isinstance(result.get("defect"), dict):
            defects = [result["defect"]]
        elif isinstance(result.get("code"), str):
            defects = [result]
        else:
            defects = []
    normalized = []
    for item in defects[:5]:
        if isinstance(item, dict):
            normalized.append(enrich_defect(item))
    if not normalized:
        normalized.append(enrich_defect({"code": "UNKNOWN", "confidence": 0, "visible_features": ["模型未返回缺陷列表"]}))
    out = {
        "defects": normalized,
        "overall_risk": result.get("overall_risk") or "无法判断",
        "report_text": result.get("report_text") or "",
        "needs_human_review": True,
    }
    obs = result.get("observation")
    if isinstance(obs, dict):
        out["observation"] = obs
    scan = result.get("scan_findings")
    if isinstance(scan, list):
        out["scan_findings"] = scan
    secondary = result.get("secondary_observations")
    if isinstance(secondary, list):
        out["secondary_observations"] = [str(s).strip() for s in secondary if str(s).strip()]
    if isinstance(result.get("unknown_route"), dict):
        out["unknown_route"] = result["unknown_route"]
    return out


def _primary_code(result: dict) -> str:
    defects = result.get("defects") or []
    return str((defects[0] if defects else {}).get("code") or "UNKNOWN").upper()


def _primary_grade(result: dict) -> int | None:
    defects = result.get("defects") or []
    g = (defects[0] if defects else {}).get("grade")
    try:
        return int(g) if g is not None else None
    except (TypeError, ValueError):
        return None


def _primary_confidence(result: dict) -> float:
    defects = result.get("defects") or []
    c = (defects[0] if defects else {}).get("confidence")
    try:
        return float(c)
    except (TypeError, ValueError):
        return 0.0


def _build_prompt() -> str:
    from services.prompt_service import get_active_prompt
    active = get_active_prompt()
    if active:
        return active
    return f"""
你是排水管道 CCTV 检测复核助手。请按以下流程分析这张图片。

---

## 第一步：扫描阶段（高召回，宁可多报不漏报）

目标：发现所有可疑区域。任何与周围管壁纹理、颜色、平滑度存在差异的区域，无论多么细微，都必须列入候选。即使只有 10% 的把握，也要作为低置信候选输出。此阶段不急着下判断。

### 观察顺序（按顺序扫，没有异常的简要带过，有异常的深入描述）

1. **材质和管径** — 管道是什么材质（混凝土/塑料/砖砌）、大致管径。不同材质的"正常状态"不同，先确定基准。
2. **光照和水位** — 光照条件（正常/偏暗/偏亮/局部阴影）、水位（无水/低水位/高水位/满水）。阴影区域特征容易被忽略或误判。
3. **整体轮廓** — 截面圆不圆、管壁平不平。判断 BX（变形）的关键。
4. **管底形态** — 有没有堆积、连续还是独立。判断 CJ（沉积）/ZA（障碍物）的关键。
5. **管壁表面** — 有没有附着物、裂痕、凹陷。判断 JG（结垢）/PL（破裂）/BX（变形）。
6. **接口位置** — 有没有错位、脱节、支管接入。判断 CW（错位）/TJ（脱节）/AJ（支管暗接）。
7. **具体异常区域细节** — 形态、颜色、边界、和管壁的关系。

### 扫描策略

- **分区域扫描**：从左到右、从上到下逐个区域寻找可疑区域，不要只看中间，边缘容易遗漏。
- **强制输出所有实例**：多个小缺陷即使紧邻，只要外观有差异或中间有正常管壁隔开，必须独立列出，不要合并。
- **特别关注易遗漏区域**：图像四周边缘、强反光旁、深阴影内、管壁曲率变化处、接口附近。
- **自问自答**：输出前再扫视一遍整幅图像——"有没有任何一个区域，哪怕只是颜色略深、纹理稍粗、有微弱阴影，被我忽略了？"如果有，补充进列表。

---

## 第二步：判断阶段（高精度，逐个确认或排除）

基于扫描结果，对每个候选区域进行确认或排除，给出缺陷判断。

允许的缺陷字典：
{defect_options_text()}

判断时遵循：
1. 从描述出发，不从预设结论出发
2. 如果特征单一明确，直接判断
3. 如果多种特征混合，分别判断主缺陷和次要特征
4. 如果证据不足，用 UNKNOWN
5. 如果无异常，用 NONE

核心区分规则：
- BX/变形：管体截面失圆、扁化、局部内凹——看管壁轮廓线是否连续变形
- CW/错位：接口处横向偏离——看是否在接口位置、是否有错台
- CJ/沉积：管底连续低位堆积——看是否在管底、是否连续、是否平缓
- ZA/障碍物：管内独立外来物——看是否与管壁有边界、是否为外来物
- JG/结垢：管壁附着物——看是否与管壁融为一体、是否环状覆盖
- SG/树根：细长分叉须状——看形态是否为纤维/根系
- AJ/支管暗接：侧向管道接入——看是否有支管口轮廓
- PL/破裂：管壁裂缝或破碎——看是否有线状裂痕或块状破碎
- TJ/脱节：接口处纵向分离——看接口是否张开

---

请只输出 JSON，格式：
{{
  "observation": {{
    "材质管径": "混凝土管，约 DN400",
    "光照水位": "正常光照，低水位",
    "整体轮廓": "截面基本圆形，管壁平整",
    "管底形态": "管底有连续堆积物",
    "管壁表面": "管壁左侧有附着物",
    "接口位置": "接口处未见明显异常",
    "异常细节": "管底堆积物呈泥沙色，质地松软，连续分布约占管底60%区域"
  }},
  "scan_findings": [
    {{
      "position": "管底",
      "description": "连续泥沙色堆积",
      "confidence_level": "high"
    }}
  ],
  "defects": [
    {{
      "code": "CJ",
      "name": "沉积",
      "grade": 2,
      "confidence": 0.78,
      "bbox": [0.18, 0.58, 0.58, 0.68],
      "bbox_format": "归一化坐标 [x1, y1, x2, y2]，值域 0-1，相对于图片宽高",
      "defect_ratio": 0.15,
      "defect_ratio_desc": "缺陷约占管底画面宽度的15%",
      "defect_continuity": "连续",
      "position_detail": "管底偏左",
      "visible_features": ["管底连续泥沙色堆积物，质地松软"],
      "recommendation": "高压水清洗"
    }}
  ],
  "overall_risk": "中",
  "secondary_observations": [],
  "report_text": "该管段图像显示...",
  "needs_human_review": true
}}

要求：
1. observation 按 7 步观察顺序如实填写，不带判断倾向。没有异常的步骤简要带过，有异常的步骤深入描述。
2. scan_findings 列出所有扫描阶段发现的可疑区域。
3. code 必须来自缺陷字典；证据不足用 UNKNOWN，无缺陷用 NONE。
4. grade 只能是 1/2/3/4 或 null。
5. confidence 0-1。
6. bbox 为缺陷区域的归一化坐标 [x1, y1, x2, y2]，值域 0-1，相对于图片宽高。x 为水平方向（左0→右1），y 为垂直方向（上0→下1）。
7. defect_ratio 为缺陷占画面可用区域的比例（0-1），用于估算缺陷实际尺寸。
8. defect_continuity：连续/孤立/间断。
9. 多特征图像输出主缺陷+次要特征，不要直接 UNKNOWN。
10. 多个缺陷独立输出，不要合并。
11. needs_human_review 必须为 true。
""".strip()


def _build_second_pass_prompt(first_pass: dict) -> str:
    summary = {
        "code": _primary_code(first_pass),
        "grade": _primary_grade(first_pass),
        "confidence": _primary_confidence(first_pass),
    }
    return f"""
请对同一张排水管道 CCTV 图像做二阶段复判。

第一阶段判断仅供参考，不要被它带偏。请独立重新观察图片。

---

## 重新扫描（按观察顺序，独立于第一阶段）

1. **材质和管径** — 什么材质、大致管径
2. **光照和水位** — 光照条件、水位情况
3. **整体轮廓** — 截面圆不圆、管壁平不平
4. **管底形态** — 有没有堆积、连续还是独立
5. **管壁表面** — 有没有附着物、裂痕、凹陷
6. **接口位置** — 有没有错位、脱节、支管接入
7. **具体异常区域细节** — 形态、颜色、边界、和管壁的关系

没有异常的步骤简要带过，有异常的步骤深入描述。

---

## 独立判断

基于你自己的扫描结果，独立判断缺陷类型。

允许的缺陷字典：
{defect_options_text()}

重点复核：
1. 第一阶段判断为 CJ/SG/ZA/JG 的，检查是否可能是 BX（管壁变形容易被其他特征掩盖）
2. 第一阶段判断为 UNKNOWN 的，检查是否有足够证据支持某个具体判断
3. 特征混合的，区分主缺陷和次要特征

核心区分：
- BX vs 其他：管壁轮廓线是否连续变形是关键——如果管壁截面形状改变，优先 BX
- CJ vs ZA：底部连续平缓→CJ，局部高突独立→ZA
- JG vs ZA：与管壁融合→JG，与管壁分离→ZA

第一阶段结果：{json.dumps(summary, ensure_ascii=False)}

请只输出 JSON，格式同第一阶段（含 observation、scan_findings、defects 等字段）。
""".strip()


UNKNOWN_ROUTE_CODES = {"BX", "CJ", "SG", "ZA", "JG"}
UNKNOWN_ROUTE_THRESHOLDS = {"BX": 0.55, "CJ": 0.65, "SG": 0.65, "ZA": 0.65, "JG": 0.65}

BX_TERMS = ("BX", "变形", "管壁", "管体", "轮廓", "内凹", "失圆", "压扁")
ZA_TERMS = ("ZA", "障碍", "外来物", "异物", "块", "砖", "石", "油块", "堵塞")
CJ_TERMS = ("CJ", "沉积", "泥沙", "淤泥", "管底", "低位")
SG_TERMS = ("SG", "树根", "根须", "根系", "细长", "分叉", "须状")


def _apply_unknown_route(image_bytes: bytes, mime_type: str, result: dict) -> dict:
    code = _primary_code(result)
    if code not in UNKNOWN_ROUTE_CODES:
        return result
    conf = _primary_confidence(result)
    threshold = UNKNOWN_ROUTE_THRESHOLDS.get(code, 0.0)
    if conf > threshold and not _has_boundary_conflict(result):
        return result

    prompt = f"""
当前主判断：code={code}, confidence={conf}

你的任务是判断这个判断的证据是否充分。

## 先按观察顺序扫一遍

1. 材质和管径 — 什么材质、大致管径
2. 光照和水位 — 光照条件、水位情况
3. 整体轮廓 — 截面圆不圆、管壁平不平
4. 管底形态 — 有没有堆积、连续还是独立
5. 管壁表面 — 有没有附着物、裂痕、凹陷
6. 接口位置 — 有没有错位、脱节、支管接入
7. 具体异常区域细节 — 形态、颜色、边界、和管壁的关系

## 再判断证据是否充分

基于你的扫描结果，判断：
1. 扫描中是否有足够特征支持 code={code} 的判断？
2. 扫描中是否存在多种特征，导致可能的混淆？
3. 扫描结果是否模糊到无法支撑任何判断？

允许的缺陷字典：
{defect_options_text()}

路由规则：
- 路由 UNKNOWN：描述中完全看不到异常特征，或特征矛盾无法区分，或图像质量差到管壁轮廓都无法辨认
- 不路由 UNKNOWN：描述中能看到特征，只是不够完美或有轻微干扰——有特征就给判断

请只输出 JSON：
{{
  "observation": {{
    "材质管径": "...",
    "光照水位": "...",
    "整体轮廓": "...",
    "管底形态": "...",
    "管壁表面": "...",
    "接口位置": "...",
    "异常细节": "..."
  }},
  "evidence_adequate": true/false,
  "route_to_unknown": true/false,
  "reason": "基于扫描结果的判断理由",
  "candidate_codes": ["BX"]
}}
"""
    try:
        decision = _call_model(image_bytes, mime_type, prompt)
    except Exception:
        return result

    route = bool(decision.get("route_to_unknown"))
    reason = str(decision.get("reason") or "").strip() or "主缺陷证据不足"
    candidates = decision.get("candidate_codes") or []
    if isinstance(candidates, list):
        candidates = [str(c).upper().strip() for c in candidates][:3]

    result["unknown_route"] = {
        "routed": route,
        "from_code": code,
        "from_grade": _primary_grade(result),
        "from_confidence": conf,
        "candidate_codes": candidates if candidates else [code],
        "reason": reason,
    }
    if route:
        result["defects"] = [enrich_defect({
            "code": "UNKNOWN", "name": "无法判断", "grade": None,
            "confidence": 0.4, "visible_features": [reason], "recommendation": "人工复核",
        })] + list(result.get("defects", []))[1:]
        result["overall_risk"] = "无法判断"
        result["report_text"] = f"主缺陷证据冲突，已路由为 UNKNOWN。原因：{reason}"
    return result


def _has_boundary_conflict(result: dict) -> bool:
    first = result.get("defects", [{}])[0] if result.get("defects") else {}
    text = " ".join([
        str(first.get("code") or ""),
        str(first.get("name") or ""),
        "；".join(str(f) for f in (first.get("visible_features") or [])),
        str(result.get("report_text") or ""),
        "；".join(str(s) for s in (result.get("secondary_observations") or [])),
    ])
    families = 0
    for terms in (BX_TERMS, ZA_TERMS, CJ_TERMS, SG_TERMS):
        if any(t in text for t in terms):
            families += 1
    return families >= 2
