"""缺陷分类体系。优先从激活的标准数据读取，fallback 到内置字典。"""

from __future__ import annotations

import json
from typing import Any

from config import STANDARDS_DIR

STANDARD_CODES = [
    "PL", "BX", "FS", "CW", "QF", "TJ", "JK", "AJ", "QR", "SL",
    "CJ", "JG", "ZA", "SG", "FZ",
]

BUILTIN_DEFECTS: dict[str, dict[str, Any]] = {
    "PL": {"name": "破裂", "category": "结构性缺陷", "definition": "管道的外部压力超过自身的承受力致使管子发生破裂。", "evidence_cues": "管壁可见裂痕、裂口、破碎、脱落或坍塌。", "recommendation": "局部现场固化法修复或开挖处理", "grades": {1: "裂痕：管壁上可见细裂痕。", 2: "裂口：破裂处已形成明显间隙，管道形状未受影响。", 3: "破碎：管壁破裂处环向覆盖范围小于弧长60°。", 4: "坍塌：裂痕或破碎处环向覆盖范围大于弧长60°。"}},
    "BX": {"name": "变形", "category": "结构性缺陷", "definition": "管道受外力挤压造成形状变异。", "evidence_cues": "管体截面失圆、扁化、局部内凹、管壁轮廓连续变形。", "recommendation": "局部现场固化法修复或开挖处理", "grades": {1: "变形小于管道直径的5%。", 2: "变形为管道直径的5%-15%。", 3: "变形为管道直径的15%-25%。", 4: "变形大于管道直径的25%。"}},
    "FS": {"name": "腐蚀", "category": "结构性缺陷", "definition": "管道内壁受侵蚀而流失或剥落。", "evidence_cues": "管道内壁麻面、剥落、显露粗骨料或钢筋。", "recommendation": "局部修复或专项复核", "grades": {1: "轻度腐蚀：表面剥落显露粗骨料。", 2: "中度腐蚀：表面剥落显露粗骨料或钢筋。", 3: "重度腐蚀：粗骨料或钢筋完全显露。"}},
    "CW": {"name": "错位", "category": "结构性缺陷", "definition": "同一接口的两个管口产生横向偏离。", "evidence_cues": "接口处横向偏离、错台、中心线不连续。", "recommendation": "局部现场固化法修复或开挖处理", "grades": {1: "轻度错位：错位距离少于管壁厚度1/2。", 2: "中度错位：错位距离在管壁厚度1/2及1倍之间。", 3: "重度错位：错位距离为管壁厚度1至2倍。", 4: "严重错位：错位距离为管壁厚度2倍以上。"}},
    "QF": {"name": "蛇形起伏", "category": "结构性缺陷", "definition": "管道竖向或横向发生明显蛇形变化。", "evidence_cues": "管道走向蛇形变化，低处形成洼水。", "recommendation": "暂不处理或专项复核", "grades": {1: "水深/管径≤20%。", 2: "20%<水位高/管径≤40%。", 3: "40%<水位高/管径≤60%。", 4: "水位高/管径>60%。"}},
    "TJ": {"name": "脱节", "category": "结构性缺陷", "definition": "两根管道端部未充分接合或接口脱离。", "evidence_cues": "管道端部脱开、接口间隙或泥土挤入。", "recommendation": "局部现场固化法修复或开挖处理", "grades": {1: "轻度脱节：管道端部有少量泥土挤入。", 2: "中度脱节：脱节距离为管壁厚度1/2-1倍。", 3: "重度脱节：脱节距离处于管壁厚度1-2倍。", 4: "严重脱节：脱节距离为管壁厚度2倍以上。"}},
    "JK": {"name": "接口材料脱落", "category": "结构性缺陷", "definition": "橡胶圈、沥青、水泥等接口材料进入管道。", "evidence_cues": "接口材料进入管内，可见橡胶圈、沥青、水泥。", "recommendation": "局部修复或清理处理", "grades": {1: "接口材料在管道水平中心线上方可见。", 2: "接口材料在管道水平中心线下方可见。"}},
    "AJ": {"name": "支管暗接", "category": "结构性缺陷", "definition": "支管未通过检查井直接侧向接入主管。", "evidence_cues": "支管直接侧向接入主管，未通过检查井。", "recommendation": "开挖处理或专项复核", "grades": {1: "支管进入主管内长度小于主管直径10%。", 2: "支管进入主管内长度在10%-20%。", 3: "支管进入主管内长度大于20%。", 4: "支管未接入到主管。"}},
    "QR": {"name": "异物侵入", "category": "结构性缺陷", "definition": "非管道系统附属设施的物体穿透管壁进入管内。", "evidence_cues": "外部异物穿透管壁进入管道内部。", "recommendation": "局部现场固化法修复或开挖处理", "grades": {1: "异物在中心线上方，占用过水断面<10%。", 2: "异物在中心线上方占用10%-20%，或下方<10%。", 3: "异物在中心线上方>20%，或下方10%-20%。", 4: "异物在中心线下方，占用过水断面>20%。"}},
    "SL": {"name": "渗漏", "category": "结构性缺陷", "definition": "管道外的水流入管道或管内水漏出管外。", "evidence_cues": "缺陷点有滴漏、线漏、涌漏或喷出水流。", "recommendation": "局部现场固化法修复或开挖处理", "grades": {1: "滴漏：水持续从缺陷点滴出。", 2: "线漏：水持续从缺陷点流出并脱离管壁。", 3: "涌漏：水涌出，涌漏面积<管道断面1/3。", 4: "涌漏：水涌出，涌漏面积>管道断面1/3。"}},
    "CJ": {"name": "沉积", "category": "功能性缺陷", "definition": "杂质在管道底部沉淀淤积。", "evidence_cues": "管底连续、低位、平缓的泥沙/淤泥沉积层。", "recommendation": "疏通处理", "grades": {1: "沉积物厚度<管径5%。", 2: "沉积物厚度在管径5%-20%。", 3: "沉积物厚度在管径20%-40%。", 4: "沉积物厚度>管径40%。"}},
    "JG": {"name": "结垢", "category": "功能性缺陷", "definition": "管道内壁上的附着物。", "evidence_cues": "管道内壁硬质或软质附着物造成过水断面损失。", "recommendation": "清洗或疏通处理", "grades": {1: "硬质结垢断面损失<15%；软质15%-25%。", 2: "硬质15%-25%；软质25%-50%。", 3: "硬质25%-50%；软质50%-70%。", 4: "硬质>50%；软质>70%。"}},
    "ZA": {"name": "障碍物", "category": "功能性缺陷", "definition": "管道内影响过流的阻挡物。", "evidence_cues": "管内独立外来物、硬块、砖石、油块、施工残留。", "recommendation": "特殊疏通处理", "grades": {1: "断面损失<5%。", 2: "断面损失5%-15%。", 3: "断面损失15%-30%。", 4: "断面损失>30%。"}},
    "SG": {"name": "树根", "category": "功能性缺陷", "definition": "树根群自然生长进入管道。", "evidence_cues": "细长、分叉、须状、纤维状或团簇状根系。", "recommendation": "切割处理或疏通处理", "grades": {1: "过水断面损失<5%。", 2: "过水断面损失5%-15%。", 3: "过水断面损失15%-30%。", 4: "过水断面损失>30%。"}},
    "FZ": {"name": "浮渣", "category": "功能性缺陷", "definition": "管道内水面上的漂浮物（不参与计算）。", "evidence_cues": "管道内水面漂浮物。", "recommendation": "清理或人工复核", "grades": {}},
    "TG": {"name": "套管", "category": "样本扩展缺陷", "definition": "管道内出现管径或材质不同的套管。", "evidence_cues": "管道内管径材质不同的套管、内衬或管中管。", "recommendation": "专项复核后处理", "grades": {4: "管道内管径材质不同。"}},
    "NONE": {"name": "无明显缺陷", "category": "无", "definition": "图像清楚且未见明显缺陷。", "recommendation": "暂不处理，保留人工复核", "grades": {}},
    "UNKNOWN": {"name": "无法判断", "category": "待复核", "definition": "图像质量不足或证据不足以判断。", "recommendation": "人工复核", "grades": {}},
}

NAME_TO_CODE = {
    "破裂": "PL", "变形": "BX", "腐蚀": "FS", "错位": "CW",
    "蛇形起伏": "QF", "脱节": "TJ", "接口材料脱落": "JK", "支管暗接": "AJ",
    "异物侵入": "QR", "渗漏": "SL", "沉积": "CJ", "结垢": "JG",
    "障碍物": "ZA", "树根": "SG", "浮渣": "FZ", "套管": "TG",
}


def get_defects() -> dict[str, dict[str, Any]]:
    """获取缺陷字典。优先从激活的标准读取。"""
    from config import STANDARDS_DIR
    active_path = STANDARDS_DIR / "active.json"
    if active_path.exists():
        try:
            active = json.loads(active_path.read_text(encoding="utf-8"))
            std_path = STANDARDS_DIR / f"{active['standard_id']}.json"
            if std_path.exists():
                std = json.loads(std_path.read_text(encoding="utf-8"))
                defects_from_std = {}
                for d in std.get("defects", []):
                    code = d.get("code", "").upper()
                    if code:
                        grades = {}
                        for g in d.get("grades", {}):
                            g_info = d["grades"][g]
                            grades[int(g)] = g_info.get("description", str(g_info))
                        defects_from_std[code] = {
                            "name": d.get("name", code),
                            "category": d.get("category", ""),
                            "definition": d.get("definition", ""),
                            "evidence_cues": d.get("evidence_cues", ""),
                            "recommendation": d.get("recommendation", ""),
                            "grades": grades,
                        }
                if defects_from_std:
                    merged = dict(BUILTIN_DEFECTS)
                    merged.update(defects_from_std)
                    return merged
        except Exception:
            pass
    return dict(BUILTIN_DEFECTS)


def defect_options_text() -> str:
    defects = get_defects()
    lines = []
    for code in STANDARD_CODES:
        item = defects.get(code, BUILTIN_DEFECTS.get(code, {}))
        if not item:
            continue
        line = f"{code}: {item['name']}，{item['category']}，定义：{item['definition']}，建议：{item['recommendation']}"
        if item.get("evidence_cues"):
            line += f"，证据：{item['evidence_cues']}"
        grades = item.get("grades") or {}
        if grades:
            grade_text = "；".join(f"{g}级={desc}" for g, desc in sorted(grades.items()))
            line += f"，等级：{grade_text}"
        lines.append(line)
    lines.append("NONE: 无明显缺陷，图像清楚且未见缺陷。")
    lines.append("UNKNOWN: 无法判断，图像质量不足或证据不足。")
    return "\n".join(lines)


def enrich_defect(defect: dict) -> dict:
    defects = get_defects()
    code = str(defect.get("code") or "UNKNOWN").upper()
    item = defects.get(code, BUILTIN_DEFECTS["UNKNOWN"])
    enriched = dict(defect)
    enriched["code"] = code if code in defects else "UNKNOWN"
    enriched.setdefault("name", item["name"])
    enriched.setdefault("category", item["category"])
    if not enriched.get("recommendation"):
        enriched["recommendation"] = item["recommendation"]
    return enriched


def all_codes() -> list[str]:
    return list(STANDARD_CODES) + ["NONE", "UNKNOWN"]


def get_category_map() -> dict[str, str]:
    defects = get_defects()
    cmap = {}
    for code, info in defects.items():
        cat = info.get("category", "")
        if "结构" in cat:
            cmap[code] = "struct"
        elif "功能" in cat:
            cmap[code] = "func"
        elif "无" in cat:
            cmap[code] = "none"
        else:
            cmap[code] = "other"
    return cmap
