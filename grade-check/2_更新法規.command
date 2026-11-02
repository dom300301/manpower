#!/bin/bash
# 雙擊：從考試院開放資料更新法規全文與院會紀錄索引（需網路）
cd "$(dirname "$0")"
export LANG=zh_TW.UTF-8
python3 fetch_exam_laws.py
python3 fetch_exam_council.py
read -p "完成，按 Enter 結束"
