#!/bin/bash
# 雙擊：安裝需要的 Python 套件（只需做一次）
cd "$(dirname "$0")"
python3 -m pip install --user -r requirements.txt
read -p "完成，按 Enter 結束"
