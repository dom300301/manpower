# 數位課程影片製作（每章一支 MP4）

## 資料夾
| 位置 | 內容 | 進版控？ |
|---|---|---|
| `input/slides/` | 簡報檔（檔名開頭為章節數字，如 `01_xxx.pptx`） | 否（教材不進版控） |
| `input/source/` | 重點摘要、掃描教材（撰寫講稿參考） | 否 |
| `scripts/chNN.txt` | 各章講稿（`# 章名`、`## 頁碼` + 旁白） | 是 |
| `course.json` | 課程名稱、講師稱謂、語音與語速 | 是 |
| `work/` | 中間檔（簡報頁圖、配音、分頁影片） | 否 |
| `output/chNN.mp4` | 成品 | 否 |

## 執行
```bash
pip install edge-tts python-pptx pillow numpy      # 首次
python3 build_course.py all 01                     # 第 1 章：轉簡報 → 配音 → 合成
python3 build_course.py all                        # 全部章節
python3 build_course.py all 01 --fake-audio        # 無網路時以模擬音訊測版面
```
需要：LibreOffice（PPTX→PDF）、poppler `pdftoppm`（PDF→PNG）、ffmpeg（含 libass）。
配音使用微軟 Edge 語音服務 `speech.platform.bing.com`（zh-TW 曉臻），需可連外網。

## 版面
1920×1080：上方標題列（課程名／章名）、左側簡報、右下 Q 版講師（`avatar.py` 向量繪製，依音量同步口型、自動眨眼）、下方字幕（由語音字界事件自動對齊）。
