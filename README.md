# Clang Blueprint

Interactive C++ class diagram and AI-powered code navigation for VS Code, powered by libclang.

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

### 3. 安裝 VS Code 插件

```bash
cd vscode-extension
npm install
npm run compile
```

在 VS Code 中按 `F5` 啟動 Extension Development Host，或打包安裝：

```bash
npm run package   # 產生 .vsix 檔
```

### 4. 開啟圖表

在 VS Code 開啟包含 `blueprint_index.json` 的資料夾，然後：

- **命令面板** (`Cmd+Shift+P`) → `Blueprint: Show Class Diagram`
- 或點擊任意 `.cpp`/`.h` 檔案右上角的 `$(type-hierarchy)` 圖示

---

## 三個 Mode

切換按鈕在圖表頂部工具列左側（**Explore / Trace / Chat**）。

### Explore Mode — 理解架構

適合第一次進入陌生 codebase。

| 功能 | 操作 |
|------|------|
| **Namespace 樹** | 左 Panel，可展開到 class 層；點擊 namespace → canvas 顯示該 namespace；點擊 class → 聚焦 + 觸發 AI Summary |
| **AI Summary** | 右 Panel，自動顯示選中 class 的 intent、key responsibilities、被哪些 class 使用、依賴哪些 class |
| **Feature Keyword 搜尋** | 左 Panel 頂部輸入框，輸入功能描述（如 `disk scheduling`）→ 自動找出相關 class |
| **⬡ Cluster View** | 工具列按鈕，每個 namespace 顯示為一個大方塊，點擊展開看裡面的 class |

### Trace Mode — 追蹤執行路徑與影響範圍

適合老手找 bug 或評估改動影響。

| 功能 | 操作 |
|------|------|
| **Focal Point** | 左 Panel 輸入 class 名稱，選擇 method，設定 N-hop 深度（1/2/3），按 Trace → canvas 只顯示相關節點 |
| **Call Chain** | 右 Panel 顯示從 focal method 出發的完整呼叫鏈，每步可點擊跳到 canvas |
| **Impact Analysis** | 右 Panel 自動顯示「改這個 class 會影響哪些地方」，分直接 / 間接兩層 |
| **Error Log Anchor** | 左 Panel 貼上 crash log / error message → 自動定位相關 class，設為 focal point |

### Chat Mode — AI 問答

適合 debug、加功能、code review。

| 功能 | 操作 |
|------|------|
| **Context Builder** | 左 Panel，將 canvas 上的 class 加入 AI context（點選 class 後按 "+ Add selected class"） |
| **對話** | 右 Panel 輸入問題，支援 Shift+Enter 換行，Enter 送出 |
| **Code Suggestion** | AI 回應中的程式碼區塊自動渲染，含 Copy 按鈕；若包含 `// file: path.cpp:42` 則出現 ⤢ Jump 按鈕直接跳到原始碼 |
| **Class 連結** | AI 回應中出現的 class 名稱自動變成可點擊連結，點擊聚焦 canvas |

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
| 單擊方法名稱 | 跳到該方法定義 |
| `F` | Fit all（全部縮到畫面內） |
| `S` | 切換框選模式（拖拉框選後按 Delete 隱藏） |
| `Ctrl+Z` | 撤回上一次展開鄰居 |
| `Escape` | 清除篩選與選取 |
| hover 連線 | 顯示依賴類型（composition / aggregation / association …） |
| hover `+N` badge | 顯示有多少鄰居尚未在畫面上 |
| 點擊 `+N` badge | 展開那些鄰居節點 |

---

## VS Code 設定

| 設定 | 預設 | 說明 |
|------|------|------|
| `clangBlueprint.blueprintIndexPath` | `blueprint_index.json` | index 檔路徑（相對 workspace root） |
| `clangBlueprint.analysisProvider` | `"local"` | `"local"` 或 `"claude"` |
| `clangBlueprint.claudeApiKey` | `""` | Claude API key（provider 為 claude 時需要） |
| `clangBlueprint.autoReloadOnChange` | `true` | 偵測到 index 檔變更時自動重繪 |
| `clangBlueprint.maxClassesInDiagram` | `100` | 超過 5000 個 class 時限制顯示數量 |
| `clangBlueprint.layoutDirection` | `"TB"` | `TB` / `LR` / `BT` / `RL` |
| `clangBlueprint.excludePaths` | `[]` | 掃描時排除的 glob 路徑 |

---

## 命令列工具

```bash
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

## blueprint_index.json Schema

每個 entry 對應一個 class/struct：

```json
{
  "className": "DiskManager",
  "responsibility": "Resource Lifecycle",
  "namespace": "core",
  "baseClasses": ["IoBase"],
  "templateParams": [],
  "dependencies": [
    { "target": "NVMeDriver", "type": "composition" },
    { "target": "BlockCache", "type": "aggregation" }
  ],
  "interfaces": ["void readBlock(int lba, char* buf)", "void writeBlock(int lba)"],
  "attributes": ["+NVMeDriver* driver", "-int capacity"],
  "fileLocation": "src/core/disk_mgr.cpp",
  "lineNumber": 42
}
```

依賴類型：`composition`（unique_ptr / 直接成員）、`aggregation`（shared_ptr / raw ptr）、`inheritance`、`association`（方法參數/回傳）、`dependency`（局部變數）。

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

**Trace Mode 沒有 call chain 資料**
- 確認 `blueprint_graph.json` 存在於 `blueprint_index.json` 同目錄（掃描時自動產生）

**AI Summary 顯示「Local analysis mode is active」**
- 這是正常行為（local provider）。要啟用 AI chat 需設定 `clangBlueprint.analysisProvider: "claude"` 與 API key
