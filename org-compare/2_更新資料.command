#!/bin/bash
# 雙擊：依 pending_updates.json（有異動的既有機關）與 new_agencies.json（要新增的機關）重新下載解析，寫出新總表
cd "$(dirname "$0")"
export LANG=zh_TW.UTF-8
MASTER=$(ls -t data/組織法編制表_總表*.xlsx 2>/dev/null | head -1)
[ -z "$MASTER" ] && { echo "找不到總表"; read -p "按 Enter 結束"; exit 1; }
STAMP=$(date +%Y%m%d)
OUT="data/組織法編制表_總表_$STAMP.xlsx"
echo "使用總表：$MASTER → 產出 $OUT"
if [ -s pending_updates.json ]; then
  python3 add_agencies.py --master "$MASTER" --config pending_updates.json --cache moj_cache --pdf-dir moj_cache/pdfs --out "$OUT" --offline --replace || exit 1
  MASTER="$OUT"
fi
if [ -s new_agencies.json ]; then
  python3 add_agencies.py --master "$MASTER" --config new_agencies.json --cache moj_cache --pdf-dir moj_cache/pdfs --out "$OUT" --offline || exit 1
fi
echo; echo "完成：$OUT。請打開檢查「檢核_待人工確認」工作表；需要補登的列請寫進 manual_fixes.json，然後雙擊 3_建檔.command"
read -p "按 Enter 結束"
