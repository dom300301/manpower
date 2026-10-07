#!/bin/bash
# 雙擊執行：input/ 內的 Word → output/index.html（含語意相近題目）
cd "$(dirname "$0")"
PY=".venv/bin/python"; [ -x "$PY" ] || PY="python3"
"$PY" build.py && open output
echo; read -n 1 -s -r -p "按任意鍵關閉視窗"
