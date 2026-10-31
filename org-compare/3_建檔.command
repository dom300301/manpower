#!/bin/bash
# 雙擊：以最新總表產生查詢網頁 output/index.html
cd "$(dirname "$0")"
export LANG=zh_TW.UTF-8
MASTER=$(ls -t data/組織法編制表_總表*.xlsx 2>/dev/null | head -1)
[ -z "$MASTER" ] && { echo "找不到總表"; read -p "按 Enter 結束"; exit 1; }
echo "使用總表：$MASTER"
python3 build_org_search.py --master "$MASTER" --fixes manual_fixes.json --out output/index.html && open output/index.html
read -p "按 Enter 結束"
