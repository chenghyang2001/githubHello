# Session 3 — webHello：PR-Agent-Pipeline HTML 版部署與端對端驗證

**日期**：2026-05-08
**主機**：NB00547
**Repo**：`chenghyang2001/webHello`（私有）

---

## 完成事項

### 1. webHello Pipeline 架構規劃（HTML repo 與 Python repo 的差異分析）
- 分析 `index.html`（單頁 HTML/JS，無 Python），確認需調整 3 個元件
- 確定可直接複製：`pr-agent-pipeline.yml`（144 行）、`classify_pr.py`（96 行）
- 確定需改寫：`resolver_agent.py`（AST scan → HTML/JS regex）、`qa_agent.py`（HTML test 策略）
- 確定需新建：`spec.md`、`pipeline.config.json`、`test_index.py` 佔位

### 2. 三 Agent 鐵律部署（Writer → QA → Reviewer，兩輪）

**Round 1（5 個新檔）**：
- Writer 產出 5 個程式碼檔，QA **24/24 PASS**
- Reviewer **CHANGES_REQUESTED**，3 個 MUST_FIX：
  1. `resolver_agent.py`：HTML/JS regex scan 只有 4 個模式，漏 6 個攻擊向量
  2. `qa_agent.py`：`run_cmd_repr` 在 HTML 分支不用到卻仍計算（邏輯不乾淨）
  3. `qa_agent.py`：HTML test_strategy prompt 會讓 LLM 硬編碼當前內容（造成假陽性迴圈）

**Round 2（修補 2 個檔）**：
- Writer 修補：resolver scan 擴充至 10 個模式，qa prompt 改要求「assert HTML 結構而非硬編碼內容」，run_cmd_repr 移至 else 分支
- QA **6/6 PASS**，所有 MUST_FIX 確認修復

### 3. 部署與端對端驗證
- `ANTHROPIC_API_KEY` secret 設定（從 `~/Downloads/langchain_v1.2/.env` 讀取）
- 7 個檔案 push 到 webHello master（commit `20c570a`）
- 開測試 PR #1（`feat/test-pipeline-hello-message`，spec 加「功能 3：頁面副標題」）
- Pipeline 全 3 job PASS（classify WRITER → resolver 修改 index.html → qa PASS 2/2，總 ~72s）
- QA 產出的測試名稱：`test_normal_required_structural_elements` + `test_edge_structural_attributes_and_nesting`（確認結構性 assert 生效）
- PR #1 squash merge（commit `2f69ac9`）

---

## 關鍵技術筆記

### HTML repo 與 Python repo 的 Pipeline 差異

| 元件 | Python（githubHello） | HTML（webHello） |
|---|---|---|
| 安全掃描 | Python `ast.parse()`（8 項）| HTML/JS regex（**10 項**）|
| 掃描項目 | eval/exec/os.system/subprocess 等 | eval/document.write/innerHTML/new Function/setTimeout-string/setInterval-string/on\* attr/javascript: URI/data: URI/外部 script src |
| QA 測試策略 | `subprocess.run` + assert stdout | `pathlib` 讀 HTML + assert **結構**（非硬編碼內容）|
| `run_cmd_repr` 計算 | 無條件計算 | 只在 `else`（非 html）分支計算 |
| test 函式 assert 方向 | 比對 stdout 輸出值 | 比對 HTML 標籤存在性、id/class 屬性 |

### HTML test 假陽性問題（MUST_FIX #3 的根因）
- 若 test_strategy prompt 說「assert HTML 內容」，LLM 會把 `楊政憲` 等當前文字值寫死進 assertion
- resolver 修改 HTML 後，QA 測試就因「舊內容消失」而誤報假陽性紅燈
- 解法：prompt 明確要求「assert HTML STRUCTURE，NOT on hardcoded text content that may change」
- 驗證：Pipeline 跑出 `test_normal_required_structural_elements`，不含任何硬編碼文字

### webHello 特殊注意
- webHello 的預設分支是 **`master`**（不是 `main`），PR base branch 要用 `master`
- `pipeline.config.json` 的 `language: "html"` 是整個條件邏輯的驅動鍵

---

## 產出檔案

### `chenghyang2001/webHello`（master branch，commit `20c570a`）

| 檔案 | 行數 | 用途 |
|---|---|---|
| `.github/workflows/pr-agent-pipeline.yml` | 144 | 直接複製自 githubHello（語言無關）|
| `scripts/classify_pr.py` | 96 | 直接複製自 githubHello（語言無關）|
| `scripts/resolver_agent.py` | 289 | HTML/JS regex scan（10 個模式）|
| `scripts/qa_agent.py` | 241 | language 條件分支：html → 結構斷言 |
| `test_index.py` | 18 | QA Agent 佔位（每次 PR 自動覆蓋）|
| `spec.md` | 31 | index.html 功能規格 |
| `pipeline.config.json` | 7 | 路徑設定（language: html）|

### 測試 PR
- PR #1 `feat/test-pipeline-hello-message`：classify `WRITER` / resolver 修改 index.html / qa `PASS 2/2`
- Squash merge commit：`2f69ac9`

---

## HANDOFF（下次 session 優先處理）

### 立即行動
- [ ] Merge `chenghyang2001/langchain_v1.2` PR #1（feat/add-pr-agent-pipeline，self-bootstrap 已驗證，等使用者 merge）
- [ ] Merge `chenghyang2001/githubHello` PR #3（feat/add-goodbye-message）和 PR #4（test/pipeline-add-multiply）

### 進行中（需接續）
- webHello pipeline 已 100% 部署驗證，無待辦
- githubHello PR #3 / PR #4 仍 open，等使用者 merge
- langchain_v1.2 PR #1 仍 open，等使用者 merge

### 注意事項
- **webHello 預設分支是 `master` 不是 `main`**（開 PR 要指定 `--base master`）
- **HTML test 假陽性風險**：若使用者直接改 qa_agent.py 的 prompt，要確保 `NOT on hardcoded text content` 的說明還在，否則 LLM 會寫死內容值
- **AST scan 仍是 regex**（不是真正的 JS parser），混淆技術（字串分割、Unicode 轉義）可繞過 — 屬「善意防禦」而非「絕對封鎖」，已在 docstring 說明
- **三個 repo 的 Pipeline 成本**：每 PR 約 $0.04（Haiku $0.0004 + Sonnet $0.024 + Sonnet $0.018）
