#!/bin/bash
# 雙擊：以最新總表重建職稱列等對照表、逐機關檢核、查詢網頁 output/index.html
cd "$(dirname "$0")"
export LANG=zh_TW.UTF-8
MASTER=$(ls -t ../org-compare/data/組織法編制表_總表*.xlsx data/組織法編制表_總表*.xlsx 2>/dev/null | head -1)
[ -z "$MASTER" ] && { echo "找不到總表（請放在 ../org-compare/data/ 或本資料夾 data/）"; read -p "按 Enter 結束"; exit 1; }
echo "使用總表：$MASTER"
python3 build_grade_table.py --master "$MASTER" && \
python3 check_grades.py --master "$MASTER" && \
python3 build_grade_site.py && open output/index.html
read -p "按 Enter 結束"
