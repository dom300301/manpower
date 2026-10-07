#!/bin/bash
# 雙擊執行：把 output/index-手機加密版.html 發布到 Firebase Hosting
# （請先執行 3_手機加密版.command 產出加密檔；第一次使用前請依部署說明完成 Firebase 設定）
cd "$(dirname "$0")"
SRC="output/index-手機加密版.html"
pause(){ echo; read -n 1 -s -r -p "按任意鍵關閉視窗"; }

if [ ! -f "$SRC" ]; then
  echo "找不到 ${SRC}，請先雙擊 3_手機加密版.command 產出加密檔。"; pause; exit 1
fi
if grep -q "請改成您的Firebase專案ID" .firebaserc 2>/dev/null; then
  echo ".firebaserc 尚未填入 Firebase 專案 ID，請依部署說明第二節設定。"; pause; exit 1
fi
# 安全檢查：只允許發布「加密版」（含密碼外殼），避免誤傳未加密的原文
if ! grep -q 'id="enc"' "$SRC"; then
  echo "【停止】${SRC} 不是加密版檔案，為避免資料外流，不予發布。"; pause; exit 1
fi
if command -v firebase >/dev/null 2>&1; then FB="firebase"
elif [ -x "$HOME/.local/bin/firebase" ]; then FB="$HOME/.local/bin/firebase"
else echo "找不到 firebase 指令，請依部署說明安裝 Firebase CLI。"; pause; exit 1; fi

rm -rf public && mkdir public && cp "$SRC" public/index.html
echo "即將發布：$(du -h public/index.html | cut -f1)  建檔時間 $(date -r "$SRC" '+%Y-%m-%d %H:%M')"
"$FB" deploy --only hosting --message "手機加密版 $(date '+%Y-%m-%d %H:%M')"
rm -rf public
pause
