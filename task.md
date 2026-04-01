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

## 架構總覽

```
Shell Layer      (VS Code Extension)   命令、lifecycle、訊息路由
Mode Controllers                       Explore / Trace / Chat 各自邏輯，互不知道
View Layer       (Webview)             Canvas + Panels，純 UI，不含業務邏輯
Analysis Layer                         call graph、impact、dependency 精煉
AI Layer                               IAnalysisProvider（local / claude 插拔）
Data Layer       (Scanner)             AST → 結構化資料，不知道 UI 存在
```

## IAnalysisProvider Interface

```typescript
interface IAnalysisProvider {
  readonly providerId: 'local' | 'claude';
  isAvailable(): Promise<boolean>;
  summarize(entry: ClassEntry): Promise<string>;
  findRelevant(query: string, all: ClassEntry[]): Promise<ClassEntry[]>;
  explainChain(steps: CallStep[], context: ClassEntry[]): Promise<string>;
  locateAnchor(errorLog: string, all: ClassEntry[]): Promise<ClassEntry[]>;
  chat(messages: ChatMessage[], context: ClassEntry[], onChunk: (chunk: string) => void): Promise<void>;
}
```

---

## 優先順序

> Phase 1–12 全部完成。

**進行中 / 待開始（Phase 13–20）建議執行順序：**

1. **P13**（Foundation）→ 先建立 interface 契約，後續所有層都依賴它
2. **P14**（Data Layer）→ 修正 scanner 的根本問題，後續 analysis 需要乾淨的資料
3. **P15**（AI Layer）→ 建立可插拔 provider，Chat Mode 需要它
4. **P16 + P17**（Shell + View，可並行）→ 重構架構骨架
5. **P18**（Explore Mode）→ 第一個完整 mode，新人入口
6. **P19**（Trace Mode）→ 承接現有 trace 功能，老手入口
7. **P20**（Chat Mode）→ 需要 AI Layer + Context Builder 就緒後才開始
