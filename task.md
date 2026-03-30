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

## 優先順序（MVP 最小可行產品）

> 完成以下項目即可示範核心價值：

1. **T-06 ~ T-12**：AST 解析出 `blueprint_index.json`
2. **T-19**：Mermaid Class Diagram 輸出
3. **T-26 ~ T-31**：VS Code 插件顯示圖表
4. **T-33**：節點雙擊跳轉原始碼
5. **T-41 ~ T-45**：`/query` API 回傳相關類別
