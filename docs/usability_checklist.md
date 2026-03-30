# T-40: Usability Acceptance Checklist

> 驗收標準：使用者能在**不查閱任何手冊**的情況下，透過圖表找到特定邏輯的實作檔案。

## 情境一：新進開發者首次使用（對應 US-01）

| # | 步驟 | 預期結果 | 通過 |
|---|------|---------|------|
| 1 | 開啟包含 `blueprint_index.json` 的 workspace | 狀態列出現 `$(type-hierarchy) Blueprint` 圖示 | ☐ |
| 2 | 點擊狀態列圖示（或 Cmd+Shift+P → "Blueprint: Show Class Diagram"） | WebView 側欄出現，圖表在 3 秒內渲染完成 | ☐ |
| 3 | 在圖表上捲動滑鼠滾輪 | 畫布縮放，無卡頓 | ☐ |
| 4 | 拖曳畫布空白處 | 畫布平移 | ☐ |
| 5 | 不看說明，直覺找到 `DiskManager` 節點 | 可在 30 秒內找到 | ☐ |
| 6 | 雙擊 `DiskManager` 節點 | VS Code 編輯器跳轉至 `disk_mgr.h` 對應行號 | ☐ |

## 情境二：精準修改（對應 US-02）

| # | 步驟 | 預期結果 | 通過 |
|---|------|---------|------|
| 7 | 在搜尋框輸入 `Manager` | 圖表即時過濾，只顯示含 "Manager" 的節點 | ☐ |
| 8 | 右鍵點擊 `DiskManager` 節點 | 出現上下文選單：Jump / Upstream / Downstream / Clear | ☐ |
| 9 | 選擇「Highlight Upstream Callers」 | 上游節點變橘色，其餘節點變淡 | ☐ |
| 10 | 選擇「Highlight Downstream Dependencies」 | 下游節點變綠色，其餘節點變淡 | ☐ |
| 11 | 按 `Escape` 鍵 | 高亮清除 | ☐ |

## 情境三：選代碼跳圖（對應 T-34，US-03）

| # | 步驟 | 預期結果 | 通過 |
|---|------|---------|------|
| 12 | 在 C++ 編輯器中，將游標移到 `DiskManager` 類別定義內 | WebView 中 `DiskManager` 節點自動高亮（橘框） | ☐ |
| 13 | 將游標移到 `NVMeController` 類別定義內 | WebView 切換高亮至 `NVMeController` | ☐ |

## 情境四：重建索引（對應 US-02）

| # | 步驟 | 預期結果 | 通過 |
|---|------|---------|------|
| 14 | Cmd+Shift+P → "Blueprint: Rebuild Index" | Terminal 自動開啟並執行掃描指令 | ☐ |
| 15 | 掃描完成後，圖表自動刷新（`autoReloadOnChange: true`） | 無需手動操作，圖表更新 | ☐ |

## 情境五：AI 查詢（對應 US-02）

| # | 步驟 | 預期結果 | 通過 |
|---|------|---------|------|
| 16 | 確認 `uvicorn ai_api.server:app` 已啟動 | `GET /health` 回傳 `{"status":"ok","index_built":true}` | ☐ |
| 17 | `POST /query {"query":"負責磁碟讀寫","top_k":3}` | 回傳結果中 `DiskManager` 排名第一 | ☐ |

---

## 自動化驗收腳本

執行 `python scripts/usability_smoke.py` 可自動驗證情境四、五的機器可測部分。
