#!/bin/bash
# 雙擊執行：列出 input/ 內每份 Word 的切題結果，存成 report.txt 並自動開啟（不產生網頁）
cd "$(dirname "$0")"
PY=".venv/bin/python"; [ -x "$PY" ] || PY="python3"
"$PY" build.py --report 2>&1 | tee report.txt
echo; echo "已存成 report.txt（標有 ⚠ 的題目請優先檢查）"
open report.txt
echo; read -n 1 -s -r -p "按任意鍵關閉視窗"
