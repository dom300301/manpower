# 質詢擬答離線查詢系統

## 檔案說明
| 檔案 | 用途 |
|---|---|
| `build.py` | 建檔程式：讀取 `input/` 內 Word（.docx／.doc）→ 產出 `output/` 查詢網頁 |
| `template.html` | 查詢網頁樣板（電腦版、手機版共用） |
| `mobile_shell.html` | 手機加密版的「輸入密碼」外殼 |
| `synonyms.txt` | 主題／同義詞字典（請持續增修） |
| `2_建檔.command` | 雙擊：產出電腦版（含語意版，需本機 `semantic.py`、`vendor/`） |
| `3_手機加密版.command` | 雙擊：產出電腦版＋手機密碼加密版（會詢問密碼） |
| `4_部署手機版.command` | 雙擊：把手機加密版發布到 Firebase Hosting（只允許發布加密檔） |
| `firebase.json`／`.firebaserc` | Firebase 發布設定（禁止搜尋引擎收錄、不快取）／專案 ID |

> 原本機的 `semantic.py`、`vendor/`、模型檔請保留在本機資料夾，本程式會沿用；沒有時自動改用輕量相關題目計算。

## 本版改善（相較原版）
1. 目錄頁自動略過，不再被當成一題（原本會干擾所有搜尋）。
2. Word 自動編號還原（「2-2.」「一、」「（一）」），可用題號搜尋。
3. 支援 .doc：自動轉成 .docx（需本機有 LibreOffice 或 Microsoft Word）。
4. 搜尋：多個關鍵字改為「全部符合優先、部分符合也列出」；BM25 排序避免長篇答復永遠排前面；同義詞只在完全相符時展開。
5. 手機加密版：AES-256-GCM 加密，伺服器上只有密文，輸入密碼後於手機本機解密。

## 首次使用（本機）
```bash
python3 -m pip install python-docx cryptography
```

## 手機版發布流程（Firebase Hosting）
第一次設定請參照「Firebase Hosting 部署步驟」說明文件。之後每次：
1. 雙擊 `3_手機加密版.command`，設定密碼（至少 12 字元）。
2. 雙擊 `4_部署手機版.command`，發布到 `https://專案ID.web.app`。
3. 網址與密碼分開傳送；每會期更新資料時更換密碼。
4. 會期結束下架：`firebase hosting:disable`
