# task.md — Blueprint-to-Code Framework 開發任務追蹤

---

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
- [x] **T-24** 初始化 `vscode-extension/`：TypeScript 插件專案
- [x] **T-25** 設定 `package.json`：commands, activationEvents (`onLanguage:cpp`)
- [x] **T-26** 實作 `extension.ts`：註冊 `showDiagram` 指令，開啟空白 `WebviewPanel`
- [x] **T-27** 建立 `webview/index.html`：顯示 Hello World 節點

### Sprint 2.2 — 圖表渲染（Week 6）
- [x] **T-28** 實作 extension → WebView `postMessage`：傳入 `blueprint_index.json` 資料
- [x] **T-29** 實作節點生成：每個 `ClassEntry` → 一個節點
- [x] **T-30** 實作自動佈局
- [x] **T-31** 實作邊 (edge) 依 dependency type 區分顏色與線型
- [x] **T-32** 實作小地圖與無限畫布縮放

### Sprint 2.3 — 互動聯動（Week 7）
- [x] **T-33** 節點雙擊 → `vscode.window.showTextDocument`
- [x] **T-34** 游標所在類別 → WebView 高亮對應節點
- [x] **T-35** 右鍵選單：`highlightUpstream` / `highlightDownstream`
- [x] **T-36** `togglePrivate` 開關
- [x] **T-37** `vscode.workspace.createFileSystemWatcher` 監聽 `blueprint_index.json` → 自動重繪

### Sprint 2.4 — 插件整合測試（Week 8）
- [x] **T-38** 撰寫 VS Code Extension Test
- [x] **T-39** 效能驗收：插件啟動時間 ≤ 2 秒
- [x] **T-40** 可用性驗收

---

## Phase 3：AI 與動態整合 The Soul（第 9–12 週）

### Sprint 3.1 — AI 索引（Week 9）
- [x] **T-41** 實作 `ai_api/indexer.py`：TF-IDF 向量化
- [x] **T-42** 實作 `query(text, top_k)` → cosine similarity 排序
- [x] **T-43** 實作索引 pickle 序列化 / 反序列化
- [x] **T-44** 撰寫 `tests/test_indexer.py`

### Sprint 3.2 — FastAPI 查詢服務（Week 10）
- [x] **T-45** 實作 `ai_api/server.py`：`POST /query`, `POST /rebuild-index`, `GET /health`
- [x] **T-46** 加入請求驗證與錯誤處理
- [x] **T-47** 撰寫 `tests/test_server.py`

### Sprint 3.3 — Call Stack 轉換（Week 11）
- [x] **T-48** 實作 GDB Backtrace 文字解析器
- [x] **T-49** 實作 trace → Mermaid `sequenceDiagram` 轉換
- [x] **T-50** 實作 FSM 掃描器

### Sprint 3.4 — RAG 驗證與收尾（Week 12）
- [x] **T-51** 建立 20 組人工標註 query-groundtruth 對
- [x] **T-52** 時序圖準確度驗收
- [x] **T-53** 撰寫 `CLAUDE.md`
- [x] **T-54** 整合測試

---

## 跨 Phase 任務

- [x] **T-X1** 建立 `requirements.txt` 並鎖定版本
- [x] **T-X2** 設定 `pyproject.toml`
- [x] **T-X3** 撰寫範例 C++ 專案（`examples/storage_engine/`）
- [x] **T-X4** 建立 GitHub Actions CI

---

## Phase 4：WebView UI 互動升級

- [x] **UI-01** 節點可拖拉
- [x] **UI-02** 拖拉後記住位置
- [x] **UI-03** 節點預設折疊
- [x] **UI-04** 點擊展開顯示 attributes
- [x] **UI-05** 點擊展開顯示 interfaces
- [x] **UI-06** 折疊/展開按鈕，展開狀態自動調整節點高度
- [x] **UI-07** hover 方法名稱顯示 tooltip
- [x] **UI-08** 點擊方法名稱 → 跳轉原始碼行號
- [x] **UI-09** hover edge 顯示 tooltip
- [x] **UI-10** 點擊 edge 高亮兩端節點
- [x] **UI-11** 搜尋結果顯示 match count
- [x] **UI-12** 支援 namespace 過濾
- [x] **UI-13** 右鍵選單「只顯示此類別的 neighborhood」
- [x] **UI-14** 節點顏色依 namespace 區分
- [x] **UI-15** 匯出圖表為 SVG 或複製 Mermaid 語法

---

## Phase 5：深度探索 Deep Dive

- [x] **P5-01** `interfaceMeta` 新增 `usedTypes[]`
- [x] **P5-02** 方法行右側顯示 class badge
- [x] **P5-03** 點擊 badge → 展開對應節點
- [x] **P5-04** hover badge 顯示 tooltip
- [x] **P5-05** 節點 header 顯示「+N」badge
- [x] **P5-06** 點擊「+N」→ 載入 1-hop 鄰居
- [x] **P5-07** 新節點 fade-in 動畫
- [x] **P5-08** 支援連續多次展開
- [x] **P5-09** 「收合最後一次展開」按鈕
- [x] **P5-10** 探索歷史棧
- [x] **P5-11** `Ctrl+Z` Undo
- [x] **P5-12** 右鍵「從這裡開始探索」
- [x] **P5-13** 更新 `ai_api/indexer.py` 納入 interfaceMeta
- [x] **P5-14** CamelCase 展開
- [x] **P5-15** 更新 `POST /query` 加入 `matchedMethods[]`
- [x] **P5-16** 撰寫 `tests/test_indexer_v2.py`

---

## Phase 6：掃描控制 — Exclude Paths

- [x] **P6-01** `scanner/main.py`：`--exclude` 選項
- [x] **P6-02** `scan_directory()` 支援 `exclude_patterns`
- [x] **P6-03** `incremental_scan()` 支援 `exclude_patterns`
- [x] **P6-04** 支援 `.blueprintignore` 設定檔
- [x] **P6-05** VS Code 插件 `clangBlueprint.excludePaths` 設定
- [x] **P6-06** 撰寫 `tests/test_exclude.py`

---

## Phase 7：節點可調整大小

- [x] **P7-01** 節點右下角 resize handle
- [x] **P7-02** 拖拉動態更新節點寬度
- [x] **P7-03** 調整大小後記住寬度
- [x] **P7-04** 調整大小後即時重繪 edges

---

## Phase 8：解析精準度與互動修正

- [x] **P8-01** 點擊節點自動展開鄰居
- [x] **P8-02** `ast_parser.py` 掃描 `TYPEDEF_DECL` / `TYPE_ALIAS_DECL`
- [x] **P8-03** field 型別展開 alias
- [x] **P8-04** `BlueprintEntry` 新增 `typeAliases[]`
- [x] **P8-05** 處理 `FUNCTION_DECL`（自由函數）
- [x] **P8-06** 自由函數合成 `BlueprintEntry`
- [x] **P8-07** 自由函數 dependency 產生

---

## Phase 9：Method Trace Mode

- [x] **P9-01** Webview：method 行末加入 `↗` icon
- [x] **P9-02** `ast_parser.py`：`_scan_method_accesses()` 記錄 `callSequence[]`
- [x] **P9-03** Webview：Trace Mode — dim 無關節點、數字 badge、Escape 退出

---

## Phase 10：節點四區塊分層顯示

- [x] **P10-01** `BlueprintEntry` 新增 `privateMethods[]`
- [x] **P10-02** Webview：4 個可獨立折疊的區塊

---

## Phase 11：Trace Mode 完整 Call Stack 面板

- [x] **P11-01** `_scan_method_accesses()` 偵測 read / write（`isWrite: bool`）
- [x] **P11-02** Webview：右側 Trace Panel，完整 call sequence 清單
- [x] **P11-03** numbered badge 依存取類型上色（call=藍、read=綠、write=橘）

---

## Phase 12：Layout、Edge 方向與折疊修正

- [x] **P12-01** `ast_parser.py`：移除 `PARSE_SKIP_FUNCTION_BODIES`
- [x] **P12-02** Webview：所有 section 預設折疊
- [x] **P12-03** Webview：Kahn's BFS 拓撲排序樹狀佈局
- [x] **P12-04** Webview：Edge 改用曲線 path + 明確方向箭頭（explicit polygon arrowheads）

---

## Phase 13：產品架構重設計 — Foundation Layer

> 目標：建立清晰的分層架構，讓三個 Mode（Explore / Trace / Chat）可以在同一個 shell 下獨立運作，互不干擾，變動可預測。
>
> 架構分層：Data → Analysis → AI → View → Mode Controllers → Shell

- [x] **P13-01** 建立 `shared/types.ts`，定義所有跨層資料契約（`ClassEntry`、`Dependency`、`CallStep`、`MethodMeta`、`ImpactResult`、`AnalysisSummary`）
- [x] **P13-02** 定義 `IAnalysisProvider` interface（`summarize` / `findRelevant` / `explainChain` / `locateAnchor` / `chat`），支援 `local` 與 `claude` 兩種實作插拔
- [x] **P13-03** 重新規劃 extension 目錄結構：`src/shell/`、`src/modes/`、`src/ai/`、`src/view/components/`
- [x] **P13-04** 定義 Extension Host ↔ Webview 雙向訊息協議（`ModeChanged`、`IndexLoaded`、`QueryResult`、`TraceResult`、`ChatResponse`），全部有 TypeScript 型別，不用 `any`

---

## Phase 14：Data Layer 精煉

> 目標：Scanner 只管 AST → 結構化資料，修正依賴過度引入問題，輸出語義分析結果供上層使用。

- [x] **P14-01** 修正依賴過度引入 bug：dependency 只記錄「在 method body / field declaration 中實際出現的 MEMBER_REF_EXPR / CALL_EXPR target」，不記錄 `#include` 傳遞進來的所有符號
- [x] **P14-02** Scanner 輸出 `blueprint_graph.json`：`reverseDeps` map（誰依賴誰的反向索引），自動在 scan 後產生；`impact_set` 在 TraceController 用 BFS on-demand 計算
- [x] **P14-03** Local intent heuristic 實作於 `LocalAnalysisProvider.summarize()`：method 名稱前綴 → role pattern；context 中的反向依賴 → usedBy；heuristic 是 ClassEntry → AnalysisSummary 純函數，scanner 不動

---

## Phase 15：AI Layer

> 目標：實作可插拔的 `IAnalysisProvider`，讓 Local 和 Claude 實作都符合同一個 interface。未設定 API key 時自動 fallback 到 local。

- [x] **P15-01** 實作 `LocalAnalysisProvider`（stub，heuristic 基礎版）
- [x] **P15-02** 實作 `ClaudeAnalysisProvider`（stub，P15-02 完整版待補）
- [x] **P15-03** 實作 `ContextBuilder`：`src/analysis/context.ts` 純函數模組（`buildExploreContext` / `buildTraceContext` / `buildChatContext` / `computeImpact`）；TraceController 改用 `buildTraceContext` + `computeImpact`
- [x] **P15-04** Provider 工廠 + VS Code 設定：`clang-blueprint.analysisProvider`（`"local"` | `"claude"`）、`clang-blueprint.claudeApiKey`，未設定 API key 自動 fallback

---

## Phase 16：Shell Layer 重構

> 目標：Extension Host 只負責命令註冊、WebviewPanel lifecycle、訊息路由。每個 Mode 有自己的 Controller，互不知道。

- [x] **P16-01** 重構 `extension.ts` → `AppShell`：只管命令、lifecycle、路由訊息到 active ModeController；ModeController 介面定義（`activate` / `deactivate` / `handleMessage`）
- [x] **P16-02** 實作 `ExploreController`（stub + requestSummary / featureQuery routing）
- [x] **P16-03** 實作 `TraceController`（setFocal / requestImpact / locateAnchor + BFS n-hop + reverse dep）
- [x] **P16-04** 實作 `ChatController`（streaming chat + context update）

---

## Phase 17：View Layer 重構

> 目標：Webview 拆成明確的元件邊界。Canvas / NodeCard / EdgeRenderer 是純 UI 元件，只接收資料，不含業務邏輯。Mode 層傳不同資料給同一個元件。

- [x] **P17-01** 重構 `index.html`：用 JS module pattern 建立清楚的 section 邊界（`AppShell`、`Canvas`、`LeftPanel`、`RightPanel`），每個 section 有明確的 input/output interface，維持 single file 但有架構
- [x] **P17-02** 抽出 `Canvas` 元件：接收 `{nodes[], edges[], options}`，負責 pan/zoom、minimap、rubber-band select、節點拖拉；不知道自己在哪個 mode
- [x] **P17-03** 抽出 `NodeCard` 元件：接收 `{entry, displayOptions}`，`displayOptions` 控制顯示哪些區塊、badge 類型等；三個 mode 傳不同的 displayOptions
- [x] **P17-04** 實作 Mode Bar UI + AppShell layout：Explore / Trace / Chat 切換按鈕在 toolbar 左側；左 Panel（240px）+ 右 Panel（290px）固定 sidebar；canvas 自動調整左右 margin；切換 mode 通知 Extension Host via `modeSwitch`；處理 `modeChanged` 和 `indexLoaded` 訊息

---

## Phase 18：Explore Mode

> 目標：讓用戶從不熟悉的 codebase 出發，透過 namespace 層次樹和 AI summary，10 分鐘內理解系統架構。

- [x] **P18-01** 左 Panel：Namespace 樹，可展開到 class 層；點擊 namespace → canvas 顯示該 namespace cluster；點擊 class → canvas 聚焦 + 觸發 AI summary
- [x] **P18-02** Canvas：Module Cluster View，預設每個 namespace 是一個大方塊（含 class 數量 badge），點擊展開顯示內部 class nodes；解決「一次看到 200 個 node」的認知負擔
- [x] **P18-03** 右 Panel：AI Summary，顯示當前選中 namespace/class 的 intent、key responsibilities、主要被哪些 class 使用、主要依賴哪些 class；lazy load（點選時才觸發）
- [x] **P18-04** Feature Keyword 入口：頂部搜尋框輸入 feature 描述 → `findRelevant()` 找出相關 class 子集 → Canvas 只顯示這些 class + 它們的關係；解決「不知道從哪裡定位 feature」

---

## Phase 19：Trace Mode

> 目標：讓老手從已知的 anchor point（class / method / error log）出發，快速定位 bug 影響範圍或理解執行路徑。

- [x] **P19-01** 左 Panel：Focal Point 搜尋 + N-hop 深度 slider（1/2/3 hop）；Canvas 只顯示 focal node + 相關節點，不相關的 class 完全不出現
- [x] **P19-02** 右 Panel：Call Chain 清單，從 focal method 出發的完整 call chain（用 `blueprint_graph.json` 資料）；步驟可點擊 → canvas 聚焦；顯示每一步的 read/write field 存取
- [x] **P19-03** 右 Panel：Impact Analysis，選定 class/method → 顯示「改這裡會影響哪些 class」；分級：直接影響 / 間接影響；可點擊跳到受影響的 class
- [x] **P19-04** 左 Panel：Error Log 貼上輸入框 → `locateAnchor()` 解析找出相關 class/method → 自動設為 focal point；解決「有 bug report 但不知從哪開始」

---

## Phase 20：Chat Mode

> 目標：讓用戶把 codebase 上下文注入給 AI，進行任務導向的對話（debug / 加新功能 / code review），AI 回應可直接跳到原始碼。

- [x] **P20-01** 右 Panel：Chat UI，訊息列表 + 輸入框 + 串流回應顯示；AI 回應中的 class name / method name 自動變成可點擊連結（→ canvas 聚焦）；支援 Markdown 渲染
- [x] **P20-02** 左 Panel：Context Builder，顯示目前 chat context 裡的 class 清單（checkbox 可移除）；canvas 上的 class 可點擊加入 context；AI 回應時 auto-suggest 應加入哪些 class（canvas 高亮，用戶確認）
- [x] **P20-03** Code Suggestion 顯示 + Jump to Source：AI 回應包含 code suggestion 時以 diff 格式顯示（file path + line + before/after）；「Jump to Source」按鈕直接跳到 VS Code editor 對應行

---

## ⚡ Phase 21：Module Abstraction Layer — 模塊抽象層（Scanner 端）

> **問題**：目前 scanner 輸出是扁平的 ClassEntry[]，所有類別處於同一層級。沒有 System → Module → Class 的抽象層級，導致 webview 一開就是數百個 node 攤在畫布上，認知負擔巨大。
>
> **目標**：Scanner 輸出新增 module 層，自動聚類，偵測 entry point，為上層 UI 提供分層資料。
>
> **成果**：`blueprint_index.json` 新增 `modules[]` 頂層欄位；每個 module 有 name、classes、inter-module edges、auto-generated summary seed。

### M21-01 — Module 聚類演算法（scanner/module_grouper.py）✅
- 輸入：`ClassEntry[]` + project root
- 聚類策略（優先順序）：
  1. 顯式 namespace → 直接成為 module（`core::*` → module "core"）
  2. 無 namespace 的 class → 依目錄路徑第一層分組（`src/storage/*.cpp` → module "storage"）
  3. 孤立 class（不屬於任何群組）→ 放入 `_ungrouped` module
- 輸出：`ModuleEntry[]`，每個含 `{ name, namespace, directory, classNames[], internalEdgeCount, externalDeps[] }`
- **可獨立開發**：純函數，只依賴 ClassEntry schema
- **驗收**：用 `examples/storage_engine/` 驗證至少 3 個合理 module 分組

### M21-02 — Inter-module 依賴計算（scanner/module_grouper.py）✅
- 從 ClassEntry.dependencies 聚合出 module 間的邊
- 輸出：`ModuleEdge[]`，每個含 `{ source: moduleName, target: moduleName, weight: number, depTypes: string[] }`
- weight = 該方向的 class-level dependency 數量
- **可獨立開發**：依賴 M21-01 的 ModuleEntry 型別定義，但實作可同步進行
- **驗收**：module graph 可轉為 Mermaid graph 驗證

### M21-03 — Entry Point 偵測（scanner/entry_detector.py）✅
- 掃描 ClassEntry[] 找出以下模式：
  - `main()` 或 `int main(` 所在的 class / free function
  - 名稱含 `Server`、`App`、`Handler`、`Controller`、`Main`、`Entry` 的 class
  - 入度 = 0（沒有其他 class 依賴它）但出度 > 0 的 class（graph root）
  - 被最多 class 依賴的 top-5（hub class）
- 輸出：`EntryPoint[]`，每個含 `{ className, kind: 'main'|'server'|'root'|'hub', reason: string }`
- **可獨立開發**：純函數，只需 ClassEntry[] + reverseDeps
- **驗收**：在 storage_engine example 中正確找到 main 和至少 2 個 hub class

### M21-04 — Scanner 輸出 schema 擴展（scanner/main.py + ast_parser.py）✅
- `blueprint_index.json` 新增頂層結構：
  ```json
  {
    "version": 2,
    "generatedAt": "...",
    "projectName": "...",
    "modules": [ ModuleEntry ],
    "moduleEdges": [ ModuleEdge ],
    "entryPoints": [ EntryPoint ],
    "classes": [ ClassEntry ]  // 原有的，位置不變
  }
  ```
- 向下相容：如果 `"version"` 不存在或 = 1，extension 視為舊格式（只有 ClassEntry[]）
- **依賴**：M21-01, M21-02, M21-03 的型別定義
- **驗收**：`python -m scanner.main scan` 輸出新格式；舊版 extension 不 crash

### M21-05 — Module-level Summary Seed（scanner/module_grouper.py）✅
- 對每個 module 生成一段 heuristic summary seed（不需 AI）：
  - 「Module "storage" contains 12 classes, primarily responsible for {top-3 responsibility labels}. Key hub: DiskManager (used by 8 classes). Entry via BufferPool.」
- 用 ClassEntry.responsibility 聚合 + entry point + hub 資訊拼接
- 這段 seed 後續會被 AI provider 精煉成更好的 summary
- **依賴**：M21-01, M21-03
- **驗收**：每個 module 有 ≥1 句非空 summary

### M21-06 — 測試（tests/test_module_grouper.py）✅
- namespace-based 分組 correctness
- directory-based fallback correctness
- inter-module edge 計算 correctness
- entry point 偵測 precision（手動標註 5 個 case）
- **可獨立開發**：只依賴型別定義
- **驗收**：`pytest tests/test_module_grouper.py -v` all pass

---

## ⚡ Phase 22：Hierarchical Overview UI — 分層總覽視圖

> **問題**：Webview 一打開就是 class-level nodes，沒有 System → Module 的 drill-down 層級。DeepWiki 式的 landing page 完全缺失。
>
> **目標**：新增 Overview 視圖作為 Explore Mode 的預設入口。用戶先看到 module-level 方塊圖，點擊 drill down 到 class level。
>
> **成果**：打開 extension 時先看到 5-15 個 module 方塊 + 連線，點擊任一 module 展開其 class nodes。

### M22-01 — TypeScript 型別定義擴展（shared/types.ts）✅
- 新增：
  ```typescript
  interface ModuleEntry {
    name: string;
    namespace?: string;
    directory?: string;
    classNames: string[];
    summarySeed: string;
    internalEdgeCount: number;
    externalDeps: { target: string; weight: number; depTypes: string[] }[];
  }
  interface EntryPoint {
    className: string;
    kind: 'main' | 'server' | 'root' | 'hub';
    reason: string;
  }
  interface BlueprintIndex {
    version: number;
    projectName?: string;
    modules: ModuleEntry[];
    moduleEdges: { source: string; target: string; weight: number }[];
    entryPoints: EntryPoint[];
    classes: ClassEntry[];
  }
  ```
- **可獨立開發**：純型別，不影響現有功能
- **驗收**：`npm run compile` 無型別錯誤

### M22-02 — AppShell 解析 v2 index + 向下相容（shell/AppShell.ts）✅
- 讀取 `blueprint_index.json` 時：
  - 如果是 array → v1 格式，包進 `{ version: 1, modules: [], classes: array }`
  - 如果是 object with `version: 2` → 直接使用
- `allEntries` 不變（仍是 ClassEntry[]），新增 `allModules: ModuleEntry[]`、`entryPoints: EntryPoint[]`
- postMessage 給 webview 時增加 `modules` 和 `entryPoints` payload
- **依賴**：M22-01 型別
- **驗收**：v1 格式 JSON 載入不 break；v2 格式 modules 正確傳到 webview

### M22-03 — Webview: Module Overview 渲染器（index.html）✅
- 新增 `renderModuleOverview(modules, moduleEdges, entryPoints)` 函數
- 每個 module 渲染為一個大方塊（寬 200px+）：
  - 標題 = module name
  - 副標題 = class 數量 badge（「12 classes」）
  - entry point 標記（⚡ icon）
  - summarySeed 前 80 字元
- module 之間依 moduleEdges 畫線（weight 越大線越粗）
- 佈局：force-directed 或 grid，module 數量少（5-15），不需複雜佈局
- **依賴**：M22-01 型別；不依賴 M22-02（可用 mock 資料開發）
- **驗收**：傳入 mock modules 資料，畫面顯示正確方塊 + 連線

### M22-04 — Webview: Module Drill-down 互動（index.html）✅
- 點擊 module 方塊 → 展開該 module 的 class nodes（現有 renderAll 邏輯）
  - 只顯示該 module 內的 classes + 它們的 1-hop 外部依賴
  - 頂部顯示 breadcrumb：`Overview > storage`
- breadcrumb 點擊 `Overview` → 返回 module 視圖
- 左 Panel namespace 樹同步高亮當前 drill-down 的 module
- **依賴**：M22-03
- **驗收**：可在 module view ↔ class view 間自由切換；breadcrumb 正確

### M22-05 — Webview: Entry Point 引導（index.html）✅
- Module Overview 上，entry point class 所在的 module 有特殊高亮（金色邊框）
- 首次載入時顯示一行引導文字：「Start exploring from {entryPointName} — it's the main entry to this codebase」
- 引導文字可點擊 → 直接 drill down 到該 module 並選中 entry point class
- **依賴**：M22-03, M21-03 的 EntryPoint 資料
- **驗收**：有 entry point 時顯示引導；點擊後正確 drill down

### M22-06 — ExploreController 適配（modes/ExploreController.ts）✅
- Explore Mode activate 時：
  - 如果有 modules 資料 → 預設顯示 Module Overview（M22-03）
  - 如果沒有（v1 index）→ fallback 到現有行為
- 處理 `moduleDrillDown` / `moduleOverview` webview message
- **依賴**：M22-01, M22-02
- **驗收**：v2 index → 顯示 module overview；v1 index → 現有行為不變

---

## ⚡ Phase 23：AI Narrative Layer — 敘事層

> **問題**：目前只有結構資料（what depends on what），缺少自然語言敘事回答 why 和 how。用戶看到 dependency edge 但不知道設計意圖。
>
> **目標**：每個層級（system / module / class）都有 AI 生成的自然語言摘要。摘要是 lazy-load 的，不增加初始載入時間。
>
> **成果**：選中 module 或 class 時右 Panel 顯示 intent + responsibilities + 關鍵互動說明。

### M23-01 — IAnalysisProvider 擴展：summarizeModule()（shared/types.ts + providers）✅
- 新增方法：
  ```typescript
  summarizeModule(
    module: ModuleEntry,
    classes: ClassEntry[],
    neighborModules: ModuleEntry[],
  ): Promise<ModuleSummary>;
  ```
- `ModuleSummary` 型別：
  ```typescript
  interface ModuleSummary {
    intent: string;          // 一句話：這個 module 做什麼
    keyClasses: string[];    // 最重要的 3-5 個 class
    interactions: string[];  // 與其他 module 的關鍵互動（2-4 句）
    entryPath?: string;      // 建議的探索入口 class
    notes?: string;
  }
  ```
- **可獨立開發**：純型別 + interface 擴展
- **驗收**：compile 通過

### M23-02 — LocalAnalysisProvider.summarizeModule()（ai/LocalAnalysisProvider.ts）✅
- Heuristic 實作（不需 AI）：
  - intent = 聚合 module 內 class 的 responsibility labels（取最高頻）
  - keyClasses = 依 dependency 入度排序取 top-5
  - interactions = 從 externalDeps 生成 「depends on module X for {depType}」
  - entryPath = module 內的 entry point（如有）或 hub class
- **可獨立開發**：純函數
- **驗收**：對 mock data 返回合理結構

### M23-03 — ClaudeAnalysisProvider.summarizeModule()（ai/ClaudeAnalysisProvider.ts）✅
- Prompt 設計：
  - 提供 module 內所有 class 的 _classDigest + 相鄰 module 的名稱/class 清單
  - 要求回傳 ModuleSummary JSON
  - 使用 HAIKU model（低延遲，module summary 是單次調用）
- 錯誤回退 → LocalAnalysisProvider.summarizeModule()
- **可獨立開發**：只依賴 M23-01 型別
- **驗收**：Claude API 返回合法 ModuleSummary；network error 時 fallback 正確

### M23-04 — GeminiAnalysisProvider.summarizeModule()（ai/GeminiAnalysisProvider.ts）✅
- 與 M23-03 同構，使用 Gemini flash model
- **可與 M23-03 並行開發**
- **驗收**：同 M23-03

### M23-05 — Webview: Module Summary Panel（index.html 右 Panel）✅
- Module Overview 模式下，點擊 module 方塊時：
  - 右 Panel 顯示 module summary（intent、keyClasses、interactions）
  - keyClasses 可點擊 → drill down 到 class level 並選中
  - Loading state：顯示 summarySeed（M21-05 的 heuristic），AI summary 回來後替換
- Drill-down 到 class level 後：右 Panel 切回現有的 class AnalysisSummary
- **依賴**：M22-03（module 渲染）、M23-01（ModuleSummary 型別）
- **驗收**：點擊 module → 右 Panel 顯示 loading → 顯示 summary；keyClasses 可點擊

### M23-06 — System-level 一句話摘要（AI provider + Webview）✅
- IAnalysisProvider 新增 `summarizeProject(modules, entryPoints): Promise<string>`
  - 輸入所有 module name + class count + entry points
  - 輸出 1-3 句話描述整個專案做什麼
- Webview Module Overview 頂部顯示這段摘要
- Local provider：拼接「Project with N modules, entry via {main class}, focused on {top responsibility}」
- Claude/Gemini：一次 API call，限 150 tokens
- **依賴**：M21-04（modules 資料）、M23-01
- **驗收**：Module Overview 頂部有 project 摘要文字

---

## ⚡ Phase 24：Guided Exploration — 引導式探索

> **問題**：目前 Explore mode 是 BFS on graph without guide — 用戶點卡片展開鄰居，但不知道「接下來看什麼最有價值」。對比 autoresearch 的 explore → synthesize → prioritize → drill deeper 循環，我們缺少 synthesize 和 prioritize。
>
> **目標**：每次展開後，AI 建議下一步；提供預設探索路徑；支援 query-driven 探索。
>
> **成果**：Explore Mode 有「Suggested Next」提示；可從自然語言描述開始定位相關 module。

### M24-01 — Exploration Suggestion Engine（analysis/explore_advisor.ts）✅
- 純函數，輸入：
  - `currentlyVisible: ClassEntry[]`（畫布上的 nodes）
  - `allEntries: ClassEntry[]`
  - `exploreHistory: {triggerClass, addedClasses}[]`
  - `moduleContext: ModuleEntry[]`
- 輸出：`ExplorationSuggestion[]`（最多 3 個）：
  ```typescript
  interface ExplorationSuggestion {
    targetClass: string;
    reason: string;      // 「DiskManager is the hub of this module with 8 dependents」
    priority: 'high' | 'medium';
    kind: 'hub' | 'boundary' | 'unexplored' | 'flow-next';
  }
  ```
- 策略：
  1. **hub**：目前可見 class 中 dependency 入度最高但尚未展開的
  2. **boundary**：連接到另一個 module 的 class（跨界探索）
  3. **unexplored**：與當前 context 強相關但還沒出現在畫布上的
  4. **flow-next**：如果用戶剛看完 A 的 call chain，建議 chain 的下一站
- **可獨立開發**：純函數，不需 AI
- **驗收**：單元測試覆蓋四種策略

### M24-02 — Webview: Suggestion Chip Bar（index.html）✅
- Canvas 底部（info bar 上方）顯示 1-3 個 suggestion chip：
  - `💡 Explore DiskManager — hub of storage module`
  - `🔗 Cross to network::SocketPool — boundary class`
- 點擊 chip → 等同於 selectNode(targetClass)，展開該 class 的鄰居
- 每次 selectNode / undo / toggle-collapse 後重新計算 suggestions
- 可 dismiss（X 按鈕），dismiss 後該 suggestion 不再出現
- **依賴**：M24-01 的 ExplorationSuggestion 型別
- **驗收**：展開 class 後底部出現 chip；點擊 chip 觸發正確展開

### M24-03 — Query-driven Module Filter（ExploreController + Webview）✅
- Explore Mode 搜尋框增強：
  - 輸入自然語言（如 「how does the read path work」）
  - 先 `findRelevant()` 找出相關 class
  - 從相關 class 反推所屬 module
  - Module Overview 中只高亮相關 module（其他 dim）；或直接 drill down 到最相關 module
- 搜尋結果面板顯示：「Found in modules: storage (4 classes), io (2 classes)」
- **依賴**：M22-03（module view）、現有 findRelevant()
- **驗收**：輸入 feature 描述 → 正確高亮 module → drill down 顯示相關 class

### M24-04 — AI-powered 「Why This Architecture」 解釋（IAnalysisProvider）✅
- IAnalysisProvider 新增：
  ```typescript
  explainArchitecture(
    modules: ModuleEntry[],
    moduleEdges: ModuleEdge[],
    focusModule?: string,
  ): Promise<string>;
  ```
- 用戶在 Module Overview 右鍵 → 「Explain architecture」：
  - AI 輸出 2-4 段，解釋為什麼系統分成這些 module、module 間的關鍵互動、設計 tradeoff
- Local provider：基於 module 依賴拓撲生成模板化說明
- Claude/Gemini：完整 prompt，限 500 tokens
- **可獨立開發**：interface 擴展 + provider 實作
- **驗收**：右鍵選單出現選項；AI 返回可讀的架構解釋

### M24-05 — Suggested Exploration Path（預設路徑）✅
- 載入 v2 index 時，自動生成一條建議探索路徑：
  - 從 entry point 出發 → 沿最重 dependency edge 走 → 經過 3-5 個 module
  - 輸出 `ExplorationPath: { steps: { moduleName, className, reason }[] }`
- Module Overview 上以虛線 + 數字標記這條路徑（1 → 2 → 3 → ...）
- 左 Panel 顯示路徑清單，可點擊跳到對應 module
- **依賴**：M21-03（entry points）、M21-02（module edges）
- **驗收**：有 entry point 的 index → 自動生成 ≥3 步路徑

---

## ⚡ Phase 25：Flow-first Navigation — 資料流視角

> **問題**：目前只有結構視角（class 有哪些 dependency），缺少行為視角（一個 request 怎麼流過系統）。call chain 資料存在但沒有被提升為一等公民。
>
> **目標**：支援「show me the read path」式的 flow query；在 module overview 層級也能看到跨 module 資料流。
>
> **成果**：Trace Mode 新增 Flow View，選定一條 flow → 高亮整條路徑涉及的 module 和 class。

### M25-01 — Flow 擷取：跨 class call chain 拼接（analysis/flow_builder.ts）✅
- 輸入：起點 class + method，`blueprint_graph.json` 的 call chain 資料
- 遞迴拼接：A::foo() → B::bar() → C::baz()，直到 chain 終止或深度 > 10
- 輸出：`Flow[]`：
  ```typescript
  interface Flow {
    name: string;           // auto-generated: 「A::foo → C::baz」
    steps: FlowStep[];
    crossedModules: string[];  // 經過了哪些 module
  }
  interface FlowStep {
    className: string;
    method: string;
    module: string;
    action: 'call' | 'read' | 'write';
  }
  ```
- **可獨立開發**：純函數
- **驗收**：從 entry point method 出發，生成 ≥1 條跨 class flow

### M25-02 — Flow Discovery：自動找出 key flows（analysis/flow_builder.ts）✅
- 不需要用戶指定起點；自動從 entry points 的 public methods 出發
- 過濾掉太短（< 3 步）或純 self-reference 的 flow
- 依 flow 長度和跨 module 數排序，取 top-10 作為 「Key Flows」
- **依賴**：M25-01, M21-03
- **驗收**：自動產出 ≥3 條有意義的 flow

### M25-03 — Webview: Flow Overlay on Module Overview（index.html）✅
- Module Overview 模式下，左 Panel 新增 「Key Flows」section
- 每條 flow 一行：`Read Path: DiskManager → BufferPool → PageCache（3 modules）`
- hover flow → module overview 上高亮該 flow 經過的 module（彩色邊框 + 方向箭頭）
- 點擊 flow → drill down 到一個專門的 flow view：只顯示該 flow 涉及的 class，按順序排列
- **依賴**：M25-02, M22-03
- **驗收**：hover 高亮正確 module；點擊顯示 flow 涉及的 class

### M25-04 — Trace Mode: Flow Query（modes/TraceController.ts + Webview）✅
- Trace Mode 新增 flow 搜尋：
  - 輸入自然語言（「how does a write request flow through the system」）
  - AI `findRelevant` 找相關 class → 從這些 class 的 method 出發拼 flow → 返回最匹配的 flow
  - Canvas 顯示 flow view（同 M25-03 的 drill-down 結果）
- **依賴**：M25-01, 現有 findRelevant
- **驗收**：輸入 flow 描述 → 顯示相關 flow path

---

## ⚡ Phase 26：Prose + Diagram Integration — 圖文整合

> **問題**：圖（canvas）和文字（summary / chat）是分離的兩個區域。無法在看圖的同時看到 module 說明，也無法從 AI 回答直接操作圖。
>
> **目標**：AI 回應中的 class/module 名稱可點擊操作畫布；畫布上的 hover 顯示 inline summary。
>
> **成果**：圖和文字雙向互動，形成 DeepWiki 式的圖文並茂體驗。

### M26-01 — Webview: Node Hover Tooltip 增強（index.html）✅
- 現有 hover tooltip 只顯示 class name
- 增強為 rich tooltip（300px 寬）：
  - intent（一句話）— 來自 AnalysisSummary.intent（如有，否則 responsibility）
  - dependency 數量 + base class
  - 「Click to explore, double-click to jump to source」
- Module 方塊 hover：顯示 summarySeed / ModuleSummary.intent
- **可獨立開發**：純 UI 改動
- **驗收**：hover 顯示 rich tooltip；無 summary 時 fallback 到 responsibility

### M26-02 — Chat 回應中的可點擊連結（index.html Chat Panel）✅
- Chat Mode AI 回應中出現的 class name / module name：
  - 用 regex 匹配已知的 className 和 moduleName
  - 包裝為 `<span class="clickable-ref">ClassName</span>`
  - 點擊 → 如果在 Explore mode，selectNode(className)；如果在 Chat mode，postMessage 要求切到 Explore + selectNode
- method 名稱（`ClassName::methodName`）→ 點擊跳到源碼
- **依賴**：現有 chat rendering
- **驗收**：AI 回應中 class name 出現藍色連結；點擊觸發正確動作

### M26-03 — Canvas ↔ Chat 雙向同步 ✅
- 在 Canvas 上選中 class → Chat 左 Panel 的 context builder 自動加入該 class
- 在 Chat 回答中點擊 class → Canvas 同步聚焦（如果 canvas 有該 node）
- Chat 中 AI 建議 「you should also look at X」 → X 自動出現在 suggestion chip（M24-02）
- **依賴**：M24-02, M26-02
- **驗收**：選 canvas node → chat context 更新；chat 點擊 → canvas 聚焦

---

## 並行開發地圖

```
                         ┌──────────────────┐
                         │  M21-01 ~ M21-06 │  Phase 21: Scanner Module Layer
                         │  (Python, 獨立)   │
                         └────────┬─────────┘
                                  │ produces v2 index
          ┌───────────────────────┼──────────────────────┐
          ▼                       ▼                      ▼
┌─────────────────┐   ┌─────────────────┐   ┌───────────────────┐
│  M22-01 ~ M22-06│   │  M23-01 ~ M23-06│   │  M25-01 ~ M25-04  │
│  Phase 22: UI   │   │  Phase 23: AI   │   │  Phase 25: Flow   │
│  (TypeScript)   │   │  Narrative      │   │  (TypeScript)     │
│  (Webview)      │   │  (Providers)    │   │  (analysis/)      │
└────────┬────────┘   └────────┬────────┘   └─────────┬─────────┘
         │                     │                      │
         └─────────┬───────────┘                      │
                   ▼                                  │
         ┌─────────────────┐                          │
         │  M24-01 ~ M24-05│◄─────────────────────────┘
         │  Phase 24:      │
         │  Guided Explore │
         └────────┬────────┘
                  ▼
         ┌─────────────────┐
         │  M26-01 ~ M26-03│
         │  Phase 26:      │
         │  Integration    │
         └─────────────────┘
```

**可完全並行的工作流：**
- 🟢 Phase 21（全部）：Python 端，不動 TypeScript
- 🟢 M22-01 + M22-03：TypeScript 型別 + Webview mock 渲染，不需 scanner 產出
- 🟢 M23-01 + M23-02：型別 + local provider，不需 UI
- 🟢 M25-01 + M25-02：flow builder 純函數，不需 UI
- 🟢 M24-01：suggestion engine 純函數，不需 UI
- 🟢 M26-01：hover tooltip，不依賴新 phase

**關鍵串接點：**
- M21-04 完成 → M22-02 可接（v2 index 解析）
- M22-03 完成 → M22-04, M22-05, M25-03 可接（module 渲染基礎）
- M23-01 完成 → M23-03, M23-04 可並行（provider 實作）
- M24-01 完成 → M24-02 可接（chip UI）

---

## 優先順序

> Phase 1–20 全部完成。

**Phase 21–26 建議執行順序：**

1. **P21**（Module Layer）→ 所有新功能的資料基礎，必須先完成
2. **P22 + P23 + P25**（可並行）→ UI 分層 + AI 敘事 + Flow，三條線獨立推進
3. **P24**（Guided Explore）→ 依賴 P22 的 module view + P25 的 flow data
4. **P26**（Integration）→ 最後整合，依賴 P22–P25 都就緒

**里程碑：**
- **M1**：P21 完成 → 用 CLI 驗證 `blueprint_index.json` v2 結構正確
- **M2**：P22 完成 → 打開 extension 看到 module overview，可 drill down
- **M3**：P23 + P25 完成 → module 有 AI summary，有 key flows
- **M4**：P24 + P26 完成 → 引導式探索 + 圖文整合，產品體驗閉環

---

## ⚡ Phase 27：Deep Call Tree — 方法呼叫樹完整化

> **問題診斷**（2026-04-03 實測發現）：
>
> 點擊 method 後期望看到遞迴呼叫樹（如 `main → AppService::PrepareManagers → DeviceManager → loadConfig`），
> 但實際什麼都沒顯示。根本原因是三層斷點疊加：
>
> | 層 | 現況 | 缺口 |
> |---|---|---|
> | Scanner `_scan_method_accesses` | 只抓 `MEMBER_REF_EXPR` | 漏掉 `CALL_EXPR`（函式呼叫）、constructor（`Baz b(42)`）、static call（`Baz::helper()`） |
> | Scanner 去重 | `seen` set 按 `(targetClass, member)` 去重 | 同一 target 被呼叫多次只記一次，破壞順序完整性 |
> | Scanner 深度 | 只掃當前 method body 的直接引用 | 不遞迴展開被呼叫方法的 body → 只有一層 |
> | Webview | `callSequence` 空 → `if (sequence.length === 0) return;` 靜默退出 | 用戶點了沒反應，無 fallback |
> | Webview | 有資料時顯示平坦 step list | 不是樹狀結構，無法表達縮排層級 |
>
> **實測數據**（3486 class，36994 method）：
> - 72% 的 public method callSequence 為空（20683 / 28372）
> - 有資料的 step 中：54% self field、39% ext call、6% ext field → 沒有 constructor、free function、static call
> - 所有 `main()` 的 callSequence 長度 = 0
> - 最富 callSequence 的 method 只有 55 步（且只有一層深度）
>
> **目標**：點擊任何 method → 展開可折疊的呼叫樹，顯示完整的
> `A::foo → B::bar → C::baz` 調用路徑（遞迴到深度 10），涵蓋所有呼叫類型。
>
> **成果指標**：
> - `main()` 的 callSequence 非空
> - callSequence 非空比例從 28% → ≥ 70%
> - 點擊 method 永遠有反饋（有資料 → 樹；無資料 → 提示訊息）
> - 樹狀展開可遞迴顯示至少 5 層深

---

### 第一段：Scanner — 擴展 callSequence 抓取範圍

> **意圖**：讓 `_scan_method_accesses` 從 "只看成員引用" 變成 "看所有呼叫行為"，
> 使每個 method 的 callSequence 完整反映 body 裡的調用順序。
>
> **不做的事**：這一段不做遞迴展開，只確保單層（當前 method body）的資料完整。
> 遞迴拼接在第二段由 TypeScript 端負責。

#### M27-01 ✅ — 新增 `CALL_EXPR` 擷取（free function + static method）

**檔案**：`scanner/ast_parser.py` → `_scan_method_accesses` 的 `_walk()` 函數

**現況**：`_walk` 只檢查 `c.kind == CursorKind.MEMBER_REF_EXPR`

**改法**：在 `_walk` 中新增一個 `elif c.kind == CursorKind.CALL_EXPR` 分支：

```
libclang AST 結構（實測確認）：
  f.bar()          → CALL_EXPR(spelling="bar")   > MEMBER_REF_EXPR > DECL_REF_EXPR
  freeFunc()       → CALL_EXPR(spelling="freeFunc") > UNEXPOSED_EXPR > DECL_REF_EXPR
  Baz::helper()    → CALL_EXPR(spelling="helper")  > UNEXPOSED_EXPR > DECL_REF_EXPR > TYPE_REF(class Baz)
```

邏輯：
1. 對每個 `CALL_EXPR`，取 `c.referenced`
2. 如果 `referenced` 存在且是 `CursorKind.FUNCTION_DECL`（free function）：
   - `targetClass` = 合成 class 名（從 referenced.semantic_parent 取 namespace，或用檔名）
   - `member` = function name
   - `kind` = "call"
3. 如果 `referenced` 是 `CursorKind.CXX_METHOD`（static method）：
   - `targetClass` = `referenced.semantic_parent.spelling`（class name）
   - `member` = method name
   - `kind` = "call"
4. **跳過已經被 MEMBER_REF_EXPR 捕獲的**：如果這個 CALL_EXPR 的子節點包含 MEMBER_REF_EXPR，
   那個 member call 已被現有邏輯抓到，不要重複記錄。
   判斷方式：檢查 CALL_EXPR 的 first child 是否是 MEMBER_REF_EXPR。

**去重策略改動**：不改這個 task，在 M27-03 統一處理。

**驗收**：
- 寫測試 `tests/test_call_tree.py::test_free_function_captured`：free function 出現在 callSequence
- 寫測試 `tests/test_call_tree.py::test_static_method_captured`：static method 出現，targetClass 正確
- 用真實 index 驗證：所有 `main()` 的 callSequence 非空

**可獨立開發**：是。純 Python scanner 改動。

---

#### M27-02 ✅ — 新增 constructor 呼叫擷取

**檔案**：`scanner/ast_parser.py` → `_scan_method_accesses` 的 `_walk()` 函數

**現況**：`Baz b(42)` 在 AST 中表現為：
```
VAR_DECL(spelling="b")
  TYPE_REF(spelling="class Baz")
  CALL_EXPR(spelling="Baz")     ← 這就是 constructor call
    INTEGER_LITERAL
```

但現有 `_walk` 不處理這個 pattern。CALL_EXPR spelling = class name 時，表示 constructor。

**改法**：在 M27-01 新增的 `CALL_EXPR` 分支中加一條邏輯：
- 如果 `c.referenced` 是 `CursorKind.CONSTRUCTOR`：
  - `targetClass` = `referenced.semantic_parent.spelling`
  - `member` = constructor 的 class name（即 `targetClass` 本身，或帶參數簽名）
  - `kind` = "call"
  - 新增欄位 `isConstructor: true`（給 webview 用來顯示不同 icon）

**驗收**：
- 測試 `tests/test_call_tree.py::test_constructor_captured`：`Baz b(42)` 出現在 callSequence
- 測試 `tests/test_call_tree.py::test_new_expr_captured`：`new Baz(42)` 也被抓到
- 真實 index：含多個 constructor 呼叫的 Initialize 類方法中，所有 constructor 均被捕獲

**可獨立開發**：否，依賴 M27-01 的 CALL_EXPR 分支。但可合併到 M27-01 一起做。

---

#### M27-03 ✅ — 移除 callSequence 去重，改為保留完整有序列表

**檔案**：`scanner/ast_parser.py` → `_scan_method_accesses`

**現況**：
```python
seen: list[tuple[str, str]] = []
# ...
key = (cls_name, member)
if key not in seen:
    seen.append(key)
    result.append({...})
```
同一 target.member 只記錄第一次出現。例如 `syscall(handle, CMD1)` 和 `syscall(handle, CMD2)` 只記一次。

**改法**：
1. 移除 `seen` 集合和 `if key not in seen` 檢查
2. 每次 encounter 都 append 到 result（保留完整順序）
3. `order` 欄位改為從 1 遞增的全局序號
4. 新增 `lineNumber` 欄位到每個 step（取 `c.location.line`），用於：
   - webview 點擊 step 可以 jump to source
   - 排序驗證（line number 應該遞增）

**風險**：step 數量會增加。加上限：單個 method body 最多 200 steps，超過截斷並附 `truncated: true` 標記。

**驗收**：
- 測試：同一個 target 被呼叫 3 次 → callSequence 有 3 條記錄
- 測試：每個 step 都有 lineNumber 且遞增
- 真實 index：最富 callSequence 的 method step 數應 ≥ 55（現為 55，去重移除後應更多）

**可獨立開發**：是。不影響 M27-01/02 的邏輯。

---

#### M27-04 ✅ — 新增 `ioctl` / 系統呼叫語意標記

**檔案**：`scanner/ast_parser.py` → `_scan_method_accesses`

**意圖**：系統程式中 `ioctl(handle, DEVICE_GET_VERSION)` 等呼叫是關鍵語意。
ioctl 是 free function call（M27-01 會捕獲），但第二個參數（command constant）承載了語意。

**改法**：
1. 在 CALL_EXPR 處理中，如果 function name 是 `ioctl`/`fcntl`/`prctl` 等 syscall-like function：
   - 嘗試讀取第二個參數的 spelling（通常是 macro constant 如 `DEVICE_GET_VERSION`）
   - 附加到 step 的新欄位 `annotation`：`"ioctl @ DEVICE_GET_VERSION"`
2. 不修改 callSequence schema 的必填欄位，`annotation` 是 optional string

**驗收**：
- 測試：`ioctl(fd, MY_CMD)` → step 的 annotation = `"ioctl @ MY_CMD"`
- 真實 index：main 裡的多個 ioctl 各自有不同 annotation

**可獨立開發**：是。只在 M27-01 的 CALL_EXPR 分支上加 annotation 邏輯。

---

#### M27-05 ✅ — 更新 `CallStep` TypeScript 型別 + JSON schema

**檔案**：`vscode-extension/src/shared/types.ts`

**改法**：
```typescript
export interface CallStep {
  targetClass: string;
  member: string;
  kind: 'call' | 'field';
  isWrite?: boolean;
  isConstructor?: boolean;   // 新增 (M27-02)
  lineNumber?: number;       // 改為必有 (M27-03)
  annotation?: string;       // 新增 (M27-04)
}
```

同步更新 CLAUDE.md 的 schema 文檔。

**驗收**：`npx tsc --noEmit` 無錯誤

**可獨立開發**：是。純型別改動，不影響 runtime。

---

### 第二段：遞迴呼叫樹建構

> **意圖**：利用第一段產出的完整單層 callSequence，在 TypeScript 端遞迴拼接成多層樹。
> Scanner 不需要遞迴 — 樹的建構在 runtime 完成，按需展開（lazy）。

#### M27-06 ✅ — 建立 `CallTreeNode` 資料結構 + 建構函數

**檔案**：新建 `vscode-extension/src/analysis/callTree.ts`

**資料結構**：
```typescript
export interface CallTreeNode {
  className: string;
  method: string;
  kind: 'call' | 'field';
  isWrite?: boolean;
  isConstructor?: boolean;
  lineNumber?: number;
  annotation?: string;
  depth: number;
  children: CallTreeNode[];   // 遞迴展開的下一層
  childrenLoaded: boolean;    // false = 尚未展開（lazy）
  fileLocation?: string;      // 來自 ClassEntry，用於 jump to source
}
```

**建構函數**：
```typescript
export function buildCallTree(
  rootClass: string,
  rootMethod: string,
  entries: ClassEntry[],
  maxDepth: number = 10,
): CallTreeNode
```

邏輯：
1. 建立 `Map<className, ClassEntry>` lookup
2. 從 rootClass 找到對應 ClassEntry
3. 從 interfaceMeta / privateMethods 找到 rootMethod 的 callSequence
4. 對每個 step：
   - 建立 CallTreeNode
   - 如果 step.kind === 'call' 且 depth < maxDepth：
     - 遞迴查找 step.targetClass 的 step.member 的 callSequence
     - 如果找到 → 遞迴建樹（`children`）
     - 如果找不到 → `childrenLoaded = true, children = []`
   - 如果 step.kind === 'field' → leaf node（不遞迴）
5. 循環偵測：維護 `visited: Set<string>`（key = `class::method`），避免無限遞迴

**驗收**：
- 單元測試：3 個 class 的 mock callSequence → 建出 3 層樹
- 單元測試：循環引用（A→B→A）不會無限遞迴
- 單元測試：depth limit 生效

**可獨立開發**：是。純函數，不依賴 scanner 改動（但資料品質依賴第一段）。

---

#### M27-07 ✅ — Extension Host 新增 `requestCallTree` 訊息處理

**檔案**：
- `vscode-extension/src/shared/messages.ts` — 新增訊息型別
- `vscode-extension/src/modes/ExploreController.ts` — 處理請求
- `vscode-extension/src/modes/TraceController.ts` — 處理請求

**新增訊息**：
```typescript
// Webview → Extension
export interface WvRequestCallTree {
  type: 'requestCallTree';
  className: string;
  methodSignature: string;
  maxDepth?: number;
}

// Extension → Webview
export interface MsgCallTreeResult {
  type: 'callTreeResult';
  className: string;
  methodSignature: string;
  tree: CallTreeNode;
}
```

Controller 邏輯：
1. 收到 `requestCallTree`
2. 呼叫 `buildCallTree(className, methodName, this.allEntries)`
3. postMessage `callTreeResult` 回 webview

**驗收**：TypeScript 編譯通過；手動測試 postMessage round-trip

**可獨立開發**：否，依賴 M27-06。

---

### 第三段：Webview — 呼叫樹 UI

> **意圖**：把現有的平坦 step list 替換為可折疊的樹狀視圖。
> 點擊 method → 展開呼叫樹 → 點擊樹節點可跳到源碼或展開下一層。

#### M27-08 ✅ — 呼叫樹 CSS + HTML 骨架

**檔案**：`vscode-extension/webview/index.html` → `<style>` 區塊

**新增 CSS class**：
```css
.call-tree { font-size: 11px; }
.call-tree-node { 
  padding: 2px 0 2px calc(var(--depth) * 16px);  /* 依深度縮排 */
  cursor: pointer; 
}
.call-tree-node:hover { background: rgba(255,255,255,0.04); }
.call-tree-toggle { display: inline-block; width: 14px; cursor: pointer; }
.call-tree-toggle.expanded::before { content: '▾'; }
.call-tree-toggle.collapsed::before { content: '▸'; }
.call-tree-toggle.leaf::before { content: '·'; color: #555; }
.call-tree-icon { margin-right: 4px; }
.call-tree-icon.call { color: #4fc3f7; }
.call-tree-icon.read { color: #7ee787; }
.call-tree-icon.write { color: #f78166; }
.call-tree-icon.construct { color: #d4a0ff; }
.call-tree-annotation { color: #888; font-size: 10px; margin-left: 6px; }
.call-tree-line { color: #555; font-size: 9px; margin-left: 4px; }
```

**驗收**：加入 CSS 後頁面無 layout 破壞

**可獨立開發**：是。純 CSS。

---

#### M27-09 ✅ — `renderCallTree()` 函數：遞迴渲染樹 DOM

**檔案**：`vscode-extension/webview/index.html` → `<script>` 區塊

**新增函數**：
```javascript
function renderCallTree(tree, container) {
  // 遞迴渲染 CallTreeNode → DOM
  // 每個 node 一行：[toggle] [icon] ClassName::method [annotation] [:line]
  // toggle 可展開/折疊 children
  // 點擊 node → jump to source（postMessage methodClick）
  // 點擊 class name → selectNode（canvas 聚焦）
}
```

具體邏輯：
1. 建立 `<div class="call-tree-node">` 並設 `style="--depth: N"`
2. toggle 按鈕：有 children → `collapsed`/`expanded`；無 children → `leaf`
3. icon：根據 kind + isConstructor 選擇（call=◆, read=◇, write=◆, construct=★）
4. class name：包裝為 `<span class="call-tree-class" data-class="X">`，點擊 → selectNode
5. member name：純文字
6. annotation（如 `ioctl @ CMD`）：灰色小字
7. line number：灰色小字，點擊 → postMessage `methodClick`
8. children container：初始 `display: none`，toggle 切換
9. 遞迴 children

**驗收**：
- mock 一棵 3 層樹 → 渲染出正確的縮排結構
- 點擊 toggle → children 顯示/隱藏
- 點擊 class name → selectNode 被呼叫
- 點擊 line number → postMessage 發送

**可獨立開發**：否，依賴 M27-08 的 CSS。可合併開發。

---

#### M27-10 ✅ — 改造 `enterTraceMode`：空 callSequence 不再靜默退出

**檔案**：`vscode-extension/webview/index.html` → `enterTraceMode()` 函數

**現況**（第 3736 行）：
```javascript
if (sequence.length === 0) return;  // ← 靜默退出，用戶看不到任何反饋
```

**改法**：
```javascript
if (sequence.length === 0) {
  // 仍然進入 trace mode，但顯示提示
  traceMode = {className: entry.className, sig, rowEl};
  if (rowEl) rowEl.classList.add('trace-method-active');
  tracePanelTitle.textContent = `${entry.className}::${trimSignature(sig)}`;
  tracePanelList.innerHTML = '<div class="trace-empty-msg">' +
    'No call data available for this method.<br>' +
    '<span style="color:#888;font-size:10px;">' +
    'Possible reasons: method body not in parsed files, ' +
    'or only a declaration without definition.</span></div>';
  tracePanel.classList.add('visible');
  return;
}
```

並且向 extension 請求 call tree：
```javascript
vscode.postMessage({ type: 'requestCallTree', className: entry.className, methodSignature: sig });
```

**驗收**：
- 點擊任何 method → 永遠有反饋（樹或提示訊息）
- 空 callSequence → 顯示灰色說明文字 + trace panel 可見

**可獨立開發**：是。不依賴 tree 渲染（先修 silent fail）。

---

#### M27-11 ✅ — Trace Panel 整合呼叫樹

**檔案**：`vscode-extension/webview/index.html`

**改法**：
1. `enterTraceMode` 在顯示完 flat step list 後，向 extension 發送 `requestCallTree`
2. 收到 `callTreeResult` 後：
   - 在 Trace Panel 的 step list 下方新增一個分隔線 + 「Call Tree」section
   - 呼叫 `renderCallTree(msg.tree, container)`
   - 首層展開，子層折疊（用戶點擊展開）
3. 如果 flat list 已經有足夠資訊（< 5 步），不額外顯示 tree（避免資訊重複）

**驗收**：
- 點擊有豐富 callSequence 的 method → 看到可折疊樹
- 展開到第 3 層 → 顯示正確的遞迴呼叫
- 點擊樹節點的 class name → canvas 聚焦到對應 node

**依賴**：M27-07（訊息）, M27-09（渲染）, M27-10（不靜默退出）

---

#### M27-12 ✅ — AI 呼叫路徑解釋

**檔案**：
- `vscode-extension/src/shared/messages.ts`
- `vscode-extension/src/modes/TraceController.ts`
- `vscode-extension/webview/index.html`

**改法**：
1. Call Tree panel 下方加一個 「Explain this path」按鈕
2. 點擊 → 取 tree 的 root-to-leaf 最長路徑（或用戶正在看的展開路徑）
3. 轉為 CallStep[] → 呼叫 `provider.explainChain(steps, context)`
4. 結果顯示在 tree 下方

**驗收**：
- 點擊 Explain → AI 返回 1-2 句自然語言解釋
- 解釋內容與呼叫路徑相符

**依賴**：M27-11

---

### 並行開發地圖

```
第一段（Python Scanner）                第二段（TypeScript）           第三段（Webview）
┌──────────────┐                        ┌──────────────┐
│  M27-01      │                        │  M27-05      │          ┌──────────────┐
│  CALL_EXPR   │                        │  型別更新     │          │  M27-08      │
│  + M27-02    │                        └──────┬───────┘          │  CSS 骨架     │
│  constructor │                               │                  └──────┬───────┘
└──────┬───────┘                               │                         │
       │                                ┌──────▼───────┐          ┌──────▼───────┐
┌──────▼───────┐                        │  M27-06      │          │  M27-09      │
│  M27-03      │                        │  buildCallTree│         │  renderTree  │
│  去重移除     │                        └──────┬───────┘          └──────┬───────┘
└──────┬───────┘                               │                         │
       │                                ┌──────▼───────┐          ┌──────▼───────┐
┌──────▼───────┐                        │  M27-07      │          │  M27-10      │◄── 可最先做
│  M27-04      │                        │  訊息處理     │          │  空值處理     │
│  ioctl 標記  │                        └──────┬───────┘          └──────┬───────┘
└──────────────┘                               │                         │
                                               └────────────┬───────────┘
                                                     ┌──────▼───────┐
                                                     │  M27-11      │
                                                     │  Panel 整合   │
                                                     └──────┬───────┘
                                                     ┌──────▼───────┐
                                                     │  M27-12      │
                                                     │  AI 解釋      │
                                                     └──────────────┘
```

**可完全並行的工作流：**
- 🟢 M27-01 + M27-02（scanner CALL_EXPR + constructor）：Python，不動 TypeScript
- 🟢 M27-05（型別更新）：TypeScript types.ts，不動 Python
- 🟢 M27-08（CSS）：webview，不動 Python 或 TypeScript
- 🟢 M27-10（空值處理）：webview，不依賴任何其他 task，**建議最先做**

**串接點：**
- M27-01 + M27-02 + M27-03 完成 → **重新 scan** → 驗證 callSequence 覆蓋率
- M27-06 完成 → M27-07 可接
- M27-07 + M27-09 + M27-10 完成 → M27-11 可接
- M27-11 完成 → M27-12 可接

**驗收里程碑：**
- **MS-A**：第一段完成 + 重新 scan → callSequence 非空比例 ≥ 70%，main() 非空
- **MS-B**：M27-10 完成 → 點擊任何 method 都有視覺反饋
- **MS-C**：M27-11 完成 → 點擊 method 展示可折疊呼叫樹，可遞迴展開 ≥ 5 層
- **MS-D**：M27-12 完成 → 呼叫路徑有 AI 自然語言解釋

## 架構總覽

```
Shell Layer      (VS Code Extension)   命令、lifecycle、訊息路由
Mode Controllers                       Explore / Trace / Chat 各自邏輯，互不知道
View Layer       (Webview)             Canvas + Panels，純 UI，不含業務邏輯
  └─ NEW: Module Overview              System → Module drill-down 視圖
  └─ NEW: Flow View                    資料流路徑視圖
  └─ NEW: Suggestion Chips             引導式探索提示
Analysis Layer                         call graph、impact、dependency 精煉
  └─ NEW: module_grouper               namespace/directory 聚類 → module
  └─ NEW: entry_detector               entry point 偵測
  └─ NEW: flow_builder                 跨 class call chain 拼接
  └─ NEW: explore_advisor              探索建議引擎
AI Layer                               IAnalysisProvider（local / claude / gemini 插拔）
  └─ NEW: summarizeModule()            module 級 AI 摘要
  └─ NEW: summarizeProject()           system 級 AI 摘要
  └─ NEW: explainArchitecture()        架構設計意圖解釋
Data Layer       (Scanner)             AST → 結構化資料，不知道 UI 存在
  └─ NEW: blueprint_index.json v2      modules[] + moduleEdges[] + entryPoints[]
```
