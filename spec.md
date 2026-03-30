# spec.md — Blueprint-to-Code Framework (C++14) 技術規格書

## 1. 專案願景

打造「圖碼同步」開發導航系統。透過 libclang 深度解析 C++14 原始碼，將複雜的類別關係、動態呼叫鏈與隱式狀態機轉化為可拖拉、可縮放的互動式圖表，並產出 AI 友善的輕量化索引，實現「以最少代碼閱讀量完成需求開發」的目標。

---

## 2. 使用者故事

| ID | 角色 | 情境 | 驗收條件 |
|----|------|------|----------|
| US-01 | 新進開發者 | 一鍵生成 Class Diagram，理清 NVMe Controller 與 Buffer Manager 的 1:N 關聯 | 60 秒內完成 10 萬行掃描，圖表可拖拉縮放 |
| US-02 | 資深開發者 | 新增 RAID 6 支援，AI 直接指出需修改的 3 個檔案 | `/query` API 回傳 top-k 結果，relevance score > 0.8 |
| US-03 | 除錯人員 | 從 Call Stack 還原 Sequence Diagram，點擊訊息定位到原始碼行號 | 時序圖與 GDB Backtrace 一致性 ≥ 95% |

---

## 3. 功能規範

### 3.1 靜態結構解析 (Static Engine)

#### C++14 深度辨識
- `auto` 返回值解析（透過 AST `CursorKind.CXX_METHOD` + 型別推導）
- Lambda 捕獲列表識別（`[=]`, `[&]`, 具名捕獲）
- Template 實例化追蹤（`ClassTemplate` + `TemplateRef`）

#### 智慧關聯推斷

| 關係類型 | C++ 語法模式 | Mermaid 符號 |
|----------|-------------|-------------|
| Composition | `T member_` / `std::unique_ptr<T>` | `*--` |
| Aggregation | `std::shared_ptr<T>` / `std::weak_ptr<T>` / raw ptr `T*` | `o--` |
| Inheritance | `: public Base` | `<\|--` |
| Association | 方法參數 / 回傳值 | `-->` |
| Dependency | 函式內區域變數 | `..>` |
| Cardinality 1..* | `std::vector<T>` / `std::map<K,T>` / `std::unordered_map<K,T>` | `"1" --> "*"` |

#### 職責標籤自動分類

| 命名慣例 | 自動職責標籤 |
|----------|------------|
| `*Manager` | Resource Lifecycle |
| `*Handler` | Event Processing |
| `*Provider` | Data Supply |
| `*Factory` | Object Creation |
| `*Controller` | Orchestration |
| `*Driver` | Hardware Abstraction |
| `*Scheduler` | Task Ordering |

若無法匹配命名慣例，則從 `public` 介面方法名稱以 NLP 分詞推斷。

---

### 3.2 動態行為解析 (Dynamic Engine)

#### Trace-to-Diagram (時序圖還原)
- 輸入格式：GDB Backtrace / 自定義執行日誌（JSON Lines）
- 過濾規則：移除 `std::`, `__cxx`, `boost::` 前綴的標準庫呼叫
- 輸出：Mermaid `sequenceDiagram`，每個訊息標註原始碼 `file:line`

**日誌輸入格式（JSON Lines）：**
```jsonc
{"ts": 1234567890, "caller": "NVMeController::submit", "callee": "DmaEngine::transfer", "file": "nvme_ctrl.cpp", "line": 142}
```

#### FSM 抽象化
掃描條件：
1. `switch(state_var)` 且 `state_var` 型別為 `enum` 或 `enum class`
2. State Design Pattern：基類有 `virtual void handle()` + 多個具體狀態子類

輸出：Mermaid `stateDiagram-v2`，標註 transition event 與 guard condition。

---

### 3.3 VS Code 插件規格

#### 指令清單

| Command ID | 觸發方式 | 行為 |
|------------|---------|------|
| `clangBlueprint.showDiagram` | Command Palette / 側邊欄按鈕 | 開啟 WebviewPanel 顯示 Class Diagram |
| `clangBlueprint.showSequence` | Command Palette | 開啟 Sequence Diagram（需先選取 trace 檔） |
| `clangBlueprint.jumpToDefinition` | 圖表節點雙擊 | `vscode.window.showTextDocument` 跳至 `fileLocation:lineNumber` |
| `clangBlueprint.rebuildIndex` | Command Palette | 觸發全量掃描並重建 `blueprint_index.json` |
| `clangBlueprint.highlightUpstream` | 節點右鍵選單 | 高亮所有上游呼叫者（橘色） |
| `clangBlueprint.highlightDownstream` | 節點右鍵選單 | 高亮所有下游依賴者（藍色） |
| `clangBlueprint.togglePrivate` | 工具列開關 | 切換隱藏/顯示 private 成員 |

#### WebView 互動規格
- 圖形引擎：React Flow（透過 CDN 載入，無需 bundler）
- 佈局演算法：`dagre` 自動分層佈局
- 節點點擊 → `postMessage({type: 'jumpTo', file, line})` → extension 處理跳轉
- extension 監聽 `blueprint_index.json` 變動（`vscode.workspace.createFileSystemWatcher`）→ 自動重繪

#### 雙向選取
- 選圖跳代碼：節點雙擊 → `showTextDocument`
- 選代碼跳圖：`onDidChangeTextEditorSelection` → 比對游標所在類別 → WebView `postMessage` 高亮對應節點

---

### 3.4 AI 索引層 (AI-Ready RAG)

#### blueprint_index.json 完整 Schema

```json
{
  "version": "1.0",
  "generatedAt": "<ISO8601>",
  "projectRoot": "<absolute path>",
  "classes": [
    {
      "className": "DiskManager",
      "responsibility": "Handles low-level disk I/O and partitioning",
      "dependencies": [
        {"target": "NVMeDriver", "type": "composition"},
        {"target": "BufferPool", "type": "aggregation"}
      ],
      "interfaces": ["readBlock(int lba, char* buf)", "writeBlock(int lba, const char* buf)"],
      "fileLocation": "src/core/disk_mgr.cpp",
      "lineNumber": 42,
      "namespace": "core",
      "baseClasses": ["IoBase"],
      "templateParams": [],
      "cardinality": {"BufferPool": "1..*"}
    }
  ]
}
```

#### 最小上下文推薦 API

**Endpoint:** `POST /query`

```json
// Request
{"query": "負責管理 NVMe 寫入佇列的元件", "top_k": 5}

// Response
{
  "results": [
    {
      "score": 0.923,
      "className": "NVMeController",
      "fileLocation": "src/nvme/controller.cpp",
      "responsibility": "Manages NVMe submission and completion queues",
      "interfaces": ["submitIO()", "pollCompletion()"]
    }
  ]
}
```

索引策略：TF-IDF over `className + responsibility + interfaces`，cosine similarity 排序。

---

## 4. 系統架構

```
clang-blueprint/
├── scanner/              # Phase 1: Python libclang 掃描器
│   ├── ast_parser.py     # C++14 AST 解析核心
│   ├── incremental.py    # 增量掃描（SHA256 快取）
│   ├── mermaid_generator.py  # Class / Sequence / FSM 圖輸出
│   └── main.py           # CLI 入口
├── ai_api/               # Phase 3: AI 查詢服務
│   ├── indexer.py        # TF-IDF 索引建立與查詢
│   └── server.py         # FastAPI 伺服器
├── vscode-extension/     # Phase 2: VS Code 插件
│   ├── src/extension.ts  # 插件主邏輯
│   ├── webview/index.html # React Flow 畫布
│   └── package.json
└── tests/
    ├── test_ast_parser.py
    ├── test_incremental.py
    └── fixtures/          # 測試用 C++ 原始碼片段
```

### 資料流

```
C++ Source Files
      │
      ▼ (libclang AST walk)
 ast_parser.py
      │
      ├──► blueprint_index.json  ──► ai_api/indexer.py ──► POST /query
      │
      └──► mermaid_generator.py  ──► .mmd files
                                        │
                              vscode-extension (WebviewPanel)
                                        │
                              React Flow (互動圖表)
                                        │
                              vscode.showTextDocument (跳轉)
```

---

## 5. 驗收標準 (Acceptance Criteria)

| 指標 | 目標 | 量測方式 |
|------|------|---------|
| 全量掃描效能 | ≤ 60 秒 / 10 萬行 | `time python -m scanner.main scan --project-root <dir>` |
| 增量掃描效能 | ≤ 5 秒（無變更） | 連續執行兩次，第二次計時 |
| 時序圖準確度 | ≥ 95% vs GDB Backtrace | 對比 frame 數 / 呼叫順序 |
| AI 查詢精確度 | top-1 hit rate ≥ 80% | 人工標註 20 組 query-groundtruth 對 |
| 插件啟動時間 | ≤ 2 秒 | VS Code Extension Host 計時 |
