# Clang Blueprint

Interactive C++ class diagram, AI-powered wiki knowledge base, and deterministic change report for VS Code — powered by libclang.

---

## 功能概覽

| 方向 | 功能 | 說明 |
|------|------|------|
| **掃描** | `blueprint scan` | libclang AST 解析，產生 `blueprint_index.json` |
| **語意豐富** | `blueprint enrich` | 啟發式 + LLM 寫入 intent / tradeoffs / risk / pattern |
| **變更報告** | `blueprint diff` | 純 AST diff + git metadata，零 LLM，寫入 `blueprint_changes.json` |
| **Wiki** | Blueprint Wiki panel | DeepWiki 風格可瀏覽知識庫（VS Code Webview） |
| **圖表** | Blueprint Diagram panel | 互動式 class 圖、namespace cluster、Explore / Trace / Chat |

---

## 快速開始

### 1. 安裝 Python 依賴

```bash
pip install -r requirements.txt
```

確認 libclang 版本與系統 clang 一致。若 `import clang.cindex` 失敗：

```bash
# macOS
export DYLD_LIBRARY_PATH=$(brew --prefix llvm)/lib

# Linux
export LD_LIBRARY_PATH=/usr/lib/llvm-14/lib
```

### 2. 掃描你的 C++ 專案

```bash
# 全量掃描，輸出 blueprint_index.json 與 blueprint_graph.json
python -m scanner.main scan --project-root /path/to/your/project --output blueprint_index.json

# 有 compile_commands.json（推薦，解析更準確）
python -m scanner.main scan \
  --project-root /path/to/your/project \
  --compile-commands /path/to/build/compile_commands.json \
  --output blueprint_index.json

# 增量掃描（只重新解析有變動的檔案，速度快 10 倍以上）
python -m scanner.main scan --project-root /path/to/your/project --incremental

# 排除目錄（支援 glob）
python -m scanner.main scan \
  --project-root . \
  --exclude "third_party/**" "build/**" "*.pb.cc"
```

> 掃描完成後會在同目錄自動產生 `blueprint_graph.json`（反向依賴索引，Trace Mode 需要）。

### 3. 語意豐富（可選）

```bash
# 啟發式豐富（免 API Key，掃描時已自動執行）
python -m scanner.main enrich --input blueprint_index.json

# LLM 豐富（需要 ANTHROPIC_API_KEY 或 GEMINI_API_KEY）
# 為每個 class 產生 intent / tradeoffs / changeRisk / designPattern
# 也為每個 module 與整個專案產生摘要段落
# 結果寫回 blueprint_index.json 並 commit — 全團隊共享，查看 Wiki 不消耗 token
python -m scanner.main enrich --input blueprint_index.json --llm
```

`.blueprint_semantic_cache.json`（本機，不 commit）會快取 LLM 結果，相同 structural hash 不重複呼叫。

### 4. 變更報告

```bash
# 比較 working tree 與 HEAD（最常用）
python -m scanner.main diff

# 比較兩個 git ref
python -m scanner.main diff --from HEAD~1 --to HEAD

# 指定輸出路徑
python -m scanner.main diff --from v1.0 --output blueprint_changes.json
```

`blueprint_changes.json` 可 commit 進 git — 讓整個團隊（與 AI agent）能看到架構演進歷史。

**安裝 git hook（自動化）：**

```bash
bash scripts/install-hooks.sh
```

每次 commit 後自動執行 `blueprint diff HEAD~1 HEAD`，保持 `blueprint_changes.json` 同步。

### 5. 安裝 VS Code 插件

```bash
cd vscode-extension
npm install
npm run compile
npm run build:wiki   # 建置 Wiki webview bundle
```

在 VS Code 中按 `F5` 啟動 Extension Development Host，或打包安裝：

```bash
npm run package   # 產生 .vsix 檔
```

### 6. 開啟 Wiki / 圖表

在 VS Code 開啟包含 `blueprint_index.json` 的資料夾，然後：

- **Blueprint Wiki**（知識庫）：命令面板 → `Blueprint: Show Wiki`，或點擊活動列 `$(book)` 圖示
- **Blueprint Diagram**（互動圖表）：命令面板 → `Blueprint: Show Class Diagram`

---

## Blueprint Wiki

Wiki panel 是 DeepWiki 風格的可瀏覽知識庫，完全由 `blueprint_index.json` 驅動。

### 頁面結構

| 頁面 | 說明 |
|------|------|
| **Overview** | 專案統計、Entry Points、Module 依賴圖 |
| **Module** | 模組摘要、內外部依賴、class 列表、內部 class diagram |
| **Class** | intent、依賴圖、interfaces、base classes、dependencies、used by、attributes |
| **Change Report** | 架構變更歷史，每次 commit 一張卡片，顯示 added/removed/modified class 與 impact 分析 |

### 側欄

- 搜尋框（即時過濾 module / class 名稱）
- Overview / Change Report（僅在 `blueprint_changes.json` 存在時顯示）
- Module 樹（可展開到 class 層）

### 自動重載

`blueprint_index.json` 或 `blueprint_changes.json` 有變動時，Wiki 會自動重載，不需要手動重新整理。

---

## Change Report

`blueprint_changes.json` 格式：

```json
{
  "version": 1,
  "records": [
    {
      "commit": "a1b2c3d4...",
      "author": "Alice",
      "date": "2026-04-09T10:00:00+00:00",
      "message": "refactor: split DiskManager",
      "added":   [{ "className": "NvmeDiskManager", "fileLocation": "src/...", "changeRisk": "high" }],
      "removed": [{ "className": "LegacyDiskManager" }],
      "modified": [
        {
          "className": "BlockCache",
          "depChanges": [{ "target": "NvmeDiskManager", "change": "added", "type": "composition" }]
        }
      ],
      "impact": {
        "direct":   ["StorageController", "WriteBuffer"],
        "indirect": ["MetadataManager"]
      }
    }
  ]
}
```

每個 `ChangeRecord` 完全由 AST diff + git metadata 產生，**不涉及 LLM**，確保準確性。

---

## 三個 Mode（Diagram Panel）

切換按鈕在圖表頂部工具列左側（**Explore / Trace / Chat**）。

### Explore Mode — 理解架構

| 功能 | 操作 |
|------|------|
| **Namespace 樹** | 左 Panel，可展開到 class 層；點擊 namespace → canvas 顯示該 namespace；點擊 class → 聚焦 + 觸發 AI Summary |
| **AI Summary** | 右 Panel，自動顯示選中 class 的 intent、key responsibilities、被哪些 class 使用、依賴哪些 class |
| **Feature Keyword 搜尋** | 左 Panel 頂部輸入框，輸入功能描述 → 自動找出相關 class |
| **⬡ Cluster View** | 工具列按鈕，每個 namespace 顯示為一個大方塊，點擊展開看裡面的 class |

### Trace Mode — 追蹤執行路徑與影響範圍

| 功能 | 操作 |
|------|------|
| **Focal Point** | 左 Panel 輸入 class 名稱，選擇 method，設定 N-hop 深度（1/2/3），按 Trace |
| **Call Chain** | 右 Panel 顯示從 focal method 出發的完整呼叫鏈 |
| **Impact Analysis** | 右 Panel 自動顯示「改這個 class 會影響哪些地方」，分直接 / 間接兩層 |
| **Error Log Anchor** | 左 Panel 貼上 crash log → 自動定位相關 class |

### Chat Mode — AI 問答

| 功能 | 操作 |
|------|------|
| **Context Builder** | 左 Panel，將 canvas 上的 class 加入 AI context |
| **對話** | 右 Panel 輸入問題，支援 Shift+Enter 換行，Enter 送出 |
| **Code Suggestion** | AI 回應中的程式碼區塊自動渲染，含 Copy 按鈕與 Jump 按鈕 |

> **預設使用本地 heuristic（不需要 API Key）**。若要啟用 Claude AI 分析：
> VS Code 設定 → `clangBlueprint.analysisProvider: "claude"` + `clangBlueprint.claudeApiKey: "sk-ant-..."`

---

## Canvas 操作

| 操作 | 說明 |
|------|------|
| 滾輪 | 縮放 |
| 拖拉空白處 | 平移 |
| 拖拉節點標題列 | 移動節點 |
| 單擊節點 | 選取，高亮上下游 |
| 雙擊節點 | 跳到原始碼 |
| `F` | Fit all（全部縮到畫面內） |
| `S` | 切換框選模式 |
| `Ctrl+Z` | 撤回上一次展開鄰居 |
| `Escape` | 清除篩選與選取 |

---

## VS Code 設定

| 設定 | 預設 | 說明 |
|------|------|------|
| `clangBlueprint.blueprintIndexPath` | `blueprint_index.json` | index 檔路徑（相對 workspace root） |
| `clangBlueprint.analysisProvider` | `"local"` | `"local"` 或 `"claude"` |
| `clangBlueprint.claudeApiKey` | `""` | Claude API key |
| `clangBlueprint.autoReloadOnChange` | `true` | 偵測到 index 檔變更時自動重繪 |
| `clangBlueprint.maxClassesInDiagram` | `100` | 超過 5000 個 class 時限制顯示數量 |
| `clangBlueprint.layoutDirection` | `"TB"` | `TB` / `LR` / `BT` / `RL` |
| `clangBlueprint.excludePaths` | `[]` | 掃描時排除的 glob 路徑 |

---

## 命令列工具

```bash
# 全量掃描
python -m scanner.main scan --project-root . --output blueprint_index.json

# 增量掃描
python -m scanner.main scan --project-root . --incremental

# 語意豐富（LLM，寫回 index）
python -m scanner.main enrich --input blueprint_index.json --llm

# 架構 diff（append 到 blueprint_changes.json）
python -m scanner.main diff --from HEAD~1 --to HEAD

# 產生 Mermaid class diagram
python -m scanner.main diagram --type class --input blueprint_index.json > diagram.mmd

# 從 GDB backtrace 產生 sequence diagram
python -m scanner.main diagram --type sequence --gdb-backtrace trace.txt > seq.mmd

# 啟動 AI query server（RAG 語意搜尋）
uvicorn ai_api.server:app --host 0.0.0.0 --port 8000 --reload

# 跑測試
pytest tests/ -v
```

---

## blueprint_index.json Schema（v4）

```json
{
  "version": 4,
  "projectName": "MyProject",
  "projectSummary": "A storage engine handling NVMe I/O with a layered architecture...",
  "modules": [
    {
      "name": "Storage",
      "classNames": ["DiskManager", "BlockCache"],
      "summary": "Manages physical I/O and caching...",
      "internalEdgeCount": 3,
      "externalDeps": [{ "target": "Network", "weight": 2, "depTypes": ["association"] }]
    }
  ],
  "moduleEdges": [{ "source": "Storage", "target": "Network", "weight": 2 }],
  "entryPoints": [{ "className": "Server", "kind": "server", "reason": "high in-degree hub" }],
  "classes": [
    {
      "className": "DiskManager",
      "responsibility": "Resource Lifecycle",
      "namespace": "core",
      "baseClasses": ["IoBase"],
      "dependencies": [
        { "target": "NVMeDriver", "type": "composition" },
        { "target": "BlockCache", "type": "aggregation" }
      ],
      "interfaces": ["void readBlock(int lba, char* buf)", "void writeBlock(int lba)"],
      "attributes": ["+NVMeDriver* driver", "-int capacity"],
      "fileLocation": "src/core/disk_mgr.cpp",
      "lineNumber": 42,
      "intent": "Orchestrates raw NVMe I/O with cache write-through to ensure durability.",
      "designPattern": "Facade",
      "changeRisk": "high",
      "tradeoffs": ["Tight coupling to NVMeDriver limits portability"]
    }
  ]
}
```

**版本演進：**
- v1：bare `ClassEntry[]`
- v2：加入 `modules` / `moduleEdges` / `entryPoints`
- v3：加入 class 語意欄位（`intent` / `tradeoffs` / `changeRisk` / `designPattern`）
- v4：加入 `module.summary` 與 `projectSummary`（LLM 產生，commit 後全團隊共享）

---

## 常見問題

**libclang 找不到**
```bash
pip install libclang
# macOS: export DYLD_LIBRARY_PATH=$(xcode-select -p)/Toolchains/XcodeDefault.xctoolchain/usr/lib
```

**掃描後 class 很少或沒有**
- 確認 `--project-root` 指向包含 `.cpp`/`.h` 的目錄
- 加上 `--compile-commands`，沒有的話先用 CMake 產生：`cmake -DCMAKE_EXPORT_COMPILE_COMMANDS=ON`

**`blueprint enrich --llm` 沒有效果**
- 確認 `ANTHROPIC_API_KEY` 或 `GEMINI_API_KEY` 環境變數已設定

**Trace Mode 沒有 call chain 資料**
- 確認 `blueprint_graph.json` 存在於 `blueprint_index.json` 同目錄（掃描時自動產生）

**AI Summary 顯示「Local analysis mode is active」**
- 這是正常行為（local provider）。要啟用 AI chat 需設定 `clangBlueprint.analysisProvider: "claude"` 與 API key

**Wiki 的 Change Report 沒有出現**
- `blueprint_changes.json` 不存在時 sidebar 項目會自動隱藏
- 執行 `blueprint diff` 或安裝 git hook 後會自動顯示
