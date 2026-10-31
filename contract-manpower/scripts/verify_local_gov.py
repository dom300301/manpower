#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""檢查 contract-manpower/data/local_gov.json：
  1. 22 個直轄市、縣（市）是否齊全（名稱完全比對）
  2. 每縣市至少一個來源（sources 非空）且至少一筆 regulations
  3. 必要欄位齊全、type 與縣市名稱一致
  4. 統計：正式規定（regulations 中非純新聞者）／僅新聞或簡章／隨首長進退條款狀態／可取得性

用法：python3 -I contract-manpower/scripts/verify_local_gov.py [json路徑] [--md]
  --md 以 Markdown 片段輸出（供貼入 research/04 末尾）
"""
import json
import sys
from pathlib import Path

EXPECTED = [
    ("臺北市", "直轄市"), ("新北市", "直轄市"), ("桃園市", "直轄市"), ("臺中市", "直轄市"), ("臺南市", "直轄市"), ("高雄市", "直轄市"),
    ("基隆市", "市"), ("新竹市", "市"), ("嘉義市", "市"),
    ("新竹縣", "縣"), ("苗栗縣", "縣"), ("彰化縣", "縣"), ("南投縣", "縣"), ("雲林縣", "縣"), ("嘉義縣", "縣"), ("屏東縣", "縣"),
    ("宜蘭縣", "縣"), ("花蓮縣", "縣"), ("臺東縣", "縣"), ("澎湖縣", "縣"), ("金門縣", "縣"), ("連江縣", "縣"),
]
REQUIRED = ["name", "type", "regulations", "contract_types", "political_appointee_clause", "salary_scheme",
            "labor_standards_act", "caps_or_limits", "core_noncore_rule", "headcount", "notable_practices", "sources"]
NEWS_HINTS = ("新聞", "自由時報", "報導", "1111", "udn", "ltn", "chinatimes", "thenewslens", "pts.org")


def is_formal(regulation: dict) -> bool:
    """『正式規定』＝要點／規則／辦法／對照表／契約書／標準表／一覽表／計畫；排除純新聞與甄選公告。"""
    t = regulation.get("title", "")
    if any(h in t for h in NEWS_HINTS):
        return False
    if any(k in t for k in ("公告", "簡章", "甄選", "甄試", "資料集")) and not any(k in t for k in ("要點", "規則", "辦法")):
        return False
    return any(k in t for k in ("要點", "規則", "辦法", "原則", "對照表", "契約書", "標準表", "一覽表", "注意事項", "規定", "準則", "計畫", "上限數表", "差異表"))


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    md = "--md" in sys.argv
    path = Path(args[0]) if args else Path(__file__).resolve().parents[1] / "data" / "local_gov.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    rows = doc["local_governments"] if isinstance(doc, dict) else doc
    byname = {r.get("name"): r for r in rows}
    errors, warnings = [], []

    # 1. 齊全
    missing = [n for n, _ in EXPECTED if n not in byname]
    extra = [n for n in byname if n not in {e[0] for e in EXPECTED}]
    if missing:
        errors.append(f"缺少縣市：{missing}")
    if extra:
        errors.append(f"多出未預期名稱：{extra}")
    if len(rows) != 22:
        errors.append(f"筆數 {len(rows)} ≠ 22")

    # 2-3. 欄位與來源
    stats = {"formal": [], "news_only": [], "clause": {}, "lsa": {}, "access": {"yes": 0, "blocked": 0, "listing": 0}}
    for name, typ in EXPECTED:
        r = byname.get(name)
        if not r:
            continue
        for k in REQUIRED:
            if k not in r:
                errors.append(f"{name}: 缺欄位 {k}")
        if r.get("type") != typ:
            errors.append(f"{name}: type 應為 {typ}，實為 {r.get('type')}")
        if not r.get("sources"):
            errors.append(f"{name}: sources 為空")
        if not r.get("regulations"):
            errors.append(f"{name}: regulations 為空")
        for reg in r.get("regulations", []):
            for k in ("title", "year", "url", "accessible", "summary"):
                if k not in reg:
                    errors.append(f"{name}: regulation 缺 {k}: {reg.get('title')}")
            acc = reg.get("accessible")
            if acc in stats["access"]:
                stats["access"][acc] += 1
            else:
                warnings.append(f"{name}: accessible 值不明 {acc}")
        if any(is_formal(x) for x in r.get("regulations", [])):
            stats["formal"].append(name)
        else:
            stats["news_only"].append(name)
        st = (r.get("political_appointee_clause") or {}).get("status", "不明")
        stats["clause"].setdefault(st, []).append(name)
        lsa = r.get("labor_standards_act", "不明")
        stats["lsa"].setdefault(lsa, []).append(name)
        if not r.get("headcount"):
            warnings.append(f"{name}: 無人數資料")

    ok = not errors
    lines = []
    if md:
        lines.append("## 附錄：verify_local_gov.py 檢查結果")
        lines.append("")
        lines.append(f"- 檢查檔案：`{path.as_posix().split('/manpower/')[-1] if '/manpower/' in path.as_posix() else path.name}`")
        lines.append(f"- 縣市筆數：{len(rows)}／22，缺少：{missing or '無'}，多出：{extra or '無'}")
        lines.append(f"- 每縣市至少一個來源：{'通過' if not any('sources 為空' in e for e in errors) else '未通過'}")
        lines.append(f"- 法規條目可取得性：直接可讀 {stats['access']['yes']}、被擋（僅摘要）{stats['access']['blocked']}、僅目錄名稱 {stats['access']['listing']}")
        lines.append(f"- 找到正式規定（要點／規則／對照表等）者（{len(stats['formal'])}）：{'、'.join(stats['formal'])}")
        lines.append(f"- 僅有新聞摘要或甄選公告者（{len(stats['news_only'])}）：{'、'.join(stats['news_only']) or '無'}")
        for st, names in stats["clause"].items():
            lines.append(f"- 隨首長進退條款「{st}」（{len(names)}）：{'、'.join(names)}")
        for st, names in stats["lsa"].items():
            lines.append(f"- 適用勞基法「{st}」（{len(names)}）：{'、'.join(names)}")
        if warnings:
            lines.append(f"- 警告（{len(warnings)}）：" + "；".join(warnings))
        lines.append(f"- 錯誤（{len(errors)}）：" + ("；".join(errors) if errors else "無"))
        lines.append(f"- 結果：**{'通過' if ok else '未通過'}**")
    else:
        lines.append(f"[{'OK' if ok else 'FAIL'}] {path}")
        lines.append(f"縣市數 {len(rows)}/22；缺少 {missing}；多出 {extra}")
        lines.append(f"可取得性 {stats['access']}")
        lines.append(f"正式規定({len(stats['formal'])}): {stats['formal']}")
        lines.append(f"僅新聞/公告({len(stats['news_only'])}): {stats['news_only']}")
        lines.append(f"隨首長進退條款: { {k: len(v) for k, v in stats['clause'].items()} }")
        lines.append(f"勞基法: { {k: len(v) for k, v in stats['lsa'].items()} }")
        for w in warnings:
            lines.append("WARN " + w)
        for e in errors:
            lines.append("ERROR " + e)
    print("\n".join(lines))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
