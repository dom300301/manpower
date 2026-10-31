#!/bin/bash
# 雙擊：下載全國法規資料庫開放資料，比對總表，產生「更新偵測報告.md」與 pending_updates.json
cd "$(dirname "$0")"
export LANG=zh_TW.UTF-8
MASTER=$(ls -t data/組織法編制表_總表*.xlsx 2>/dev/null | head -1)
[ -z "$MASTER" ] && { echo "找不到 data/組織法編制表_總表*.xlsx，請先把總表放進 data 資料夾"; read -p "按 Enter 結束"; exit 1; }
echo "使用總表：$MASTER"
python3 check_updates.py --master "$MASTER" --cache moj_cache --out 更新偵測報告.md
echo; echo "完成。請打開 更新偵測報告.md 查看；有異動時接著雙擊 2_更新資料.command"
read -p "按 Enter 結束"
