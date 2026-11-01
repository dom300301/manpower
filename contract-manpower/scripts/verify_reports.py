#!/usr/bin/env python3
"""檢查 data/reports.json：每筆 local_path 是否存在、必要欄位是否齊全、summary 長度。

用法：python3 scripts/verify_reports.py（於 contract-manpower 目錄下執行）
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS = os.path.join(ROOT, "data", "reports.json")
REQUIRED = ["id", "title", "org", "date", "url", "local_path", "summary",
            "key_findings", "numbers", "related_personnel_types"]
ORGS = {"法制局", "預算中心"}


def main() -> int:
    with open(REPORTS, encoding="utf-8") as f:
        reports = json.load(f)
    problems = []
    ids = set()
    for i, r in enumerate(reports):
        rid = r.get("id", f"#{i}")
        if rid in ids:
            problems.append(f"{rid}: id 重複")
        ids.add(rid)
        for k in REQUIRED:
            if k not in r or r[k] in (None, "", [], {}):
                problems.append(f"{rid}: 缺少欄位 {k}")
        if r.get("org") not in ORGS:
            problems.append(f"{rid}: org 應為 法制局/預算中心，實為 {r.get('org')}")
        if len(r.get("summary", "")) > 300:
            problems.append(f"{rid}: summary 超過 300 字（{len(r['summary'])}）")
        paths = r.get("local_path") or []
        if isinstance(paths, str):
            paths = [paths]
        for p in paths:
            full = os.path.join(ROOT, p)
            if not os.path.exists(full):
                problems.append(f"{rid}: local_path 不存在 {p}")
        for n in r.get("numbers", []):
            for k in ("item", "value", "year"):
                if k not in n:
                    problems.append(f"{rid}: numbers 缺少 {k}: {n}")
    print(f"reports.json：共 {len(reports)} 筆")
    if problems:
        print(f"發現 {len(problems)} 項問題：")
        for p in problems:
            print("  -", p)
        return 1
    print("所有 local_path 存在、必要欄位齊全。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
