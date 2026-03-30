# task.md — Blueprint-to-Code Framework 開發任務追蹤

## Phase 1：解析核心 The Brain（第 1–4 週）

### Sprint 1.1 — 環境與骨架（Week 1）
- [x] **T-01** 建立 Python 虛擬環境，安裝 `libclang`、`pytest`
- [x] **T-02** 確認 `compile_commands.json` 可從 CMake (`-DCMAKE_EXPORT_COMPILE_COMMANDS=ON`) 正確產出
- [x] **T-03** 建立 `scanner/ast_parser.py` 骨架，驗證 `clang.cindex.Index.create()` 可解析單一 `.cpp`
- [x] **T-04** 定義 `ClassEntry` dataclass（對應 `blueprint_index.json` schema）
- [x] **T-05** 建立 `tests/fixtures/` 目錄，放入基礎測試 C++ 片段

### Sprint 1.2 — AST 解析核心（Week 2）
- [x] **T-06** 實作 class / struct 節點識別（`CursorKind.CLASS_DECL`, `STRUCT_DECL`）
- [x] **T-07** 實作 public 方法擷取 → `interfaces[]`
- [x] **T-08** 實作成員變數型別分析 → `composition` / `aggregation` 依 `unique_ptr` / `shared_ptr` / raw ptr 區分
- [x] **T-09** 實作繼承關係擷取 → `baseClasses[]` + `inheritance` dependency
- [x] **T-10** 實作 template 參數擷取 → `templateParams[]`
- [x] **T-11** 實作 cardinality 識別（`vector`, `map`, `unordered_map` → `1..*`）
- [x] **T-12** 實作職責標籤自動分類（命名慣例 regex mapping）
- [x] **T-13** 撰寫 `tests/test_ast_parser.py`，覆蓋 composition / inheritance / template 情境

### Sprint 1.3 — 增量掃描與輸出（Week 3）
- [x] **T-14** 實作 `scanner/incremental.py`：SHA256 檔案雜湊 + `.blueprint_cache.json`
- [x] **T-15** 實作快取合併邏輯：只重新解析有變更的檔案
- [x] **T-16** 使用 `tempfile` + `os.replace()` 實作 cache 原子寫入
- [x] **T-17** 輸出 `blueprint_index.json`（完整 schema，含 `version`, `generatedAt`）
- [x] **T-18** 撰寫 `tests/test_incremental.py`，驗證無變更時 parse 不被呼叫

### Sprint 1.4 — Mermaid 產生器與 CLI（Week 4）
- [x] **T-19** 實作 `scanner/mermaid_generator.py`：Class Diagram 輸出
- [x] **T-20** 實作 Sequence Diagram 輸出（從 JSON Lines trace 輸入）
- [x] **T-21** 實作 FSM 狀態圖輸出（掃描 `switch(enum)` 模式）
- [x] **T-22** 實作 `scanner/main.py` CLI：`scan` / `diagram` 子命令
- [x] **T-23** 效能驗收：在 10 萬行代碼下執行全量掃描，確認 ≤ 60 秒

---

## Phase 2：VS Code 插件 The Body（第 5–8 週）

### Sprint 2.1 — 插件骨架（Week 5）
- [x] **T-24** 初始化 `vscode-extension/`：`yo code` 或手動建立 TypeScript 插件專案
- [x] **T-25** 設定 `package.json`：commands, activationEvents (`onLanguage:cpp`)
- [x] **T-26** 實作 `extension.ts`：註冊 `showDiagram` 指令，開啟空白 `WebviewPanel`
- [x] **T-27** 建立 `webview/index.html`：引入 React Flow CDN，顯示 Hello World 節點

### Sprint 2.2 — 圖表渲染（Week 6）
- [x] **T-28** 實作 extension → WebView `postMessage`：傳入 `blueprint_index.json` 資料
- [x] **T-29** 實作 React Flow 節點生成：每個 `ClassEntry` → 一個節點
- [x] **T-30** 實作 dagre 自動佈局（引入 `dagre` CDN）
- [x] **T-31** 實作邊 (edge) 依 dependency type 區分顏色與線型
- [x] **T-32** 實作小地圖 (`<MiniMap>`) 與無限畫布縮放

### Sprint 2.3 — 互動聯動（Week 7）
- [x] **T-33** 實作節點雙擊 → `postMessage({type: 'jumpTo', file, line})` → `vscode.window.showTextDocument`
- [x] **T-34** 實作 `onDidChangeTextEditorSelection`：游標所在類別 → WebView 高亮對應節點
- [x] **T-35** 實作右鍵選單：`highlightUpstream` / `highlightDownstream`（BFS 遍歷 dependency graph）
- [x] **T-36** 實作 `togglePrivate` 開關：過濾 private 成員後重新渲染
- [x] **T-37** 實作 `vscode.workspace.createFileSystemWatcher` 監聽 `blueprint_index.json` → 自動重繪

### Sprint 2.4 — 插件整合測試（Week 8）
- [x] **T-38** 撰寫 VS Code Extension Test（`@vscode/test-electron`）
- [x] **T-39** 效能驗收：插件啟動時間 ≤ 2 秒
- [x] **T-40** 可用性驗收：使用者無需查閱手冊即可找到特定邏輯的實作檔案

---

## Phase 3：AI 與動態整合 The Soul（第 9–12 週）

### Sprint 3.1 — AI 索引（Week 9）
- [x] **T-41** 實作 `ai_api/indexer.py`：TF-IDF 向量化 (`sklearn.TfidfVectorizer`)
- [x] **T-42** 實作 `query(text, top_k)` → cosine similarity 排序
- [x] **T-43** 實作索引 pickle 序列化 / 反序列化（`.blueprint_tfidf.pkl`）
- [x] **T-44** 撰寫 `tests/test_indexer.py`：驗證 top-1 回傳符合預期

### Sprint 3.2 — FastAPI 查詢服務（Week 10）
- [x] **T-45** 實作 `ai_api/server.py`：`POST /query`, `POST /rebuild-index`, `GET /health`
- [x] **T-46** 加入請求驗證（`pydantic` model）與錯誤處理（404 when index missing）
- [x] **T-47** 撰寫 `tests/test_server.py`（`httpx` + `pytest-asyncio`）

### Sprint 3.3 — Call Stack 轉換（Week 11）
- [x] **T-48** 實作 GDB Backtrace 文字解析器 → 標準化 JSON Lines trace 格式
- [x] **T-49** 實作 trace → Mermaid `sequenceDiagram` 轉換（過濾 std:: 呼叫）
- [x] **T-50** 實作 FSM 掃描器：`switch(enum_state)` pattern → `stateDiagram-v2`

### Sprint 3.4 — RAG 驗證與收尾（Week 12）
- [x] **T-51** 建立 20 組人工標註 query-groundtruth 對，量測 top-1 hit rate
- [x] **T-52** 時序圖準確度驗收：對比 GDB Backtrace frame，確認 ≥ 95% 一致性
- [x] **T-53** 撰寫 `CLAUDE.md`（開發環境設定、常用指令、架構說明）
- [x] **T-54** 整合測試：從 C++ 原始碼 → blueprint_index.json → `/query` API 端到端驗證

---

## 跨 Phase 任務

- [x] **T-X1** 建立 `requirements.txt` 並鎖定版本
- [x] **T-X2** 設定 `pyproject.toml` 或 `setup.cfg`（`python -m scanner.main` 入口點）
- [x] **T-X3** 撰寫範例 C++ 專案（`examples/storage_engine/`）供示範與測試用
- [x] **T-X4** 建立 GitHub Actions CI：`pytest` + `eslint` on push

---

## Phase 4：WebView UI 互動升級（Post-MVP）

### Sprint 4.1 — 節點可拖拉
- [x] **UI-01** 每個 class 節點可以用滑鼠拖拉到任意位置（目前只有整體畫布 pan）
- [x] **UI-02** 拖拉後記住位置，filter 清空時不重置

### Sprint 4.2 — 節點內容折疊/展開
- [x] **UI-03** 節點預設折疊（只顯示 className + responsibility）
- [x] **UI-04** 點擊節點標題列展開：顯示 attributes（成員變數）
- [x] **UI-05** 點擊展開：顯示 interfaces（方法），每個方法顯示完整 return type + 參數型別
- [x] **UI-06** 折疊/展開按鈕（▶/▼），展開狀態自動調整節點高度並重繪 edges

### Sprint 4.3 — 方法詳細資訊
- [x] **UI-07** hover 方法名稱顯示 tooltip：完整 signature（含 template params、const/virtual）
- [ ] **UI-08** 點擊方法名稱 → 跳轉到該方法的原始碼行號

### Sprint 4.4 — Edge 互動
- [x] **UI-09** hover edge 顯示 tooltip：dependency 類型 + cardinality
- [x] **UI-10** 點擊 edge 高亮兩端節點

### Sprint 4.5 — 搜尋與 UX 強化
- [x] **UI-11** 搜尋結果顯示 match count（例如「找到 3 個類別 + 12 個鄰居」）
- [x] **UI-12** 支援 namespace 過濾（例如 `ns:storage`）
- [x] **UI-13** 右鍵選單加入「只顯示此類別的 neighborhood」選項
- [x] **UI-14** 節點顏色依 namespace 區分
- [x] **UI-15** 匯出目前可見圖表為 SVG 或複製 Mermaid 語法

---

## 優先順序（MVP 最小可行產品）

> 完成以下項目即可示範核心價值：

1. **T-06 ~ T-12**：AST 解析出 `blueprint_index.json`
2. **T-19**：Mermaid Class Diagram 輸出
3. **T-26 ~ T-31**：VS Code 插件顯示圖表
4. **T-33**：節點雙擊跳轉原始碼
5. **T-41 ~ T-45**：`/query` API 回傳相關類別
