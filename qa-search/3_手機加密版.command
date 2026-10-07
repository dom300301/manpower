#!/bin/bash
# 雙擊執行：input/ 內的 Word → output/index.html ＋ output/index-手機加密版.html（會詢問密碼）
cd "$(dirname "$0")"
PY=".venv/bin/python"; [ -x "$PY" ] || PY="python3"
"$PY" build.py --mobile --no-semantic-search && open output
echo; read -n 1 -s -r -p "按任意鍵關閉視窗"
