# 中央政府員額查詢

整合主計總處總預算、人事總處公教人力統計年報、銓敘部銓敘統計年報三個公開來源的中央政府員額數字，並對照《中央政府機關總員額法》各類員額上限。

## 檔案
| 檔案 | 用途 |
|---|---|
| `output/index.html` | 查詢網頁（單一檔案，資料已內嵌，可離線開啟；不需密碼） |

## 線上版
與其他三套系統同一個 GitHub Pages 網站，路徑為 `/staffing/`：
`https://dom300301.github.io/manpower/staffing/`
（由 `.github/workflows/pages.yml` 發布；分支合併到 `main` 後才會上線。）

## 資料更新方式
本頁原由本機的 `build_report.py` 產生（即原 Google Apps Script 專案的 `page.html`）。
更新資料時：重新執行 `build_report.py` → 把產出的 `page.html` 改名為 `index.html`，覆蓋 `staffing/output/index.html` → 提交並推送。

## 沿革
2026-11-19：由 Google Apps Script 網頁應用程式（限機關帳號＋密碼登入）改為免密碼的靜態網頁，併入本專案。原登入頁（`login.html`）與伺服器端驗證程式（`程式碼.gs`）不再使用。
