# 組織法規與編制表查詢系統

行政院所屬機關的組織法規、處務規程、編制表彙整與同層級比對工具。資料來源：全國法規資料庫。

| 檔案 | 用途 |
|---|---|
| `output/index.html` | **查詢網頁**（離線單檔；上傳主機即線上版） |
| `data/組織法編制表_總表_日期.xlsx` | 總表（原始資料，585 機關） |
| `操作手冊.md` | 使用與更新說明（請先讀這份） |
| `0_首次安裝.command`～`3_建檔.command` | Mac 雙擊：安裝、檢查更新、更新資料、建檔 |
| `check_updates.py` / `add_agencies.py` / `reparse_pdfs.py` | 更新偵測、下載解析、PDF 解析 |
| `build_dataset.py` / `build_org_search.py` / `org_template.html` | 資料整備、建檔、網頁樣板 |
| `new_agencies.json` / `manual_fixes.json` | 要新增的機關、人工補登 |
| `verify_tables_online.py`、`verification/` | 驗證程式與結果 |
| `01_資料驗證報告.md`、`03_第二階段驗證報告.md` | 驗證報告 |
| `02_系統規劃與待決事項.md` | 規劃與決策紀錄 |
| `poc/` | 早期概念驗證 |

雲端硬碟原始資料夾：https://drive.google.com/drive/folders/1blFuKALjYpYwQ4XPonoYTA7dgdekmxlv
