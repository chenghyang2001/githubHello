# Session 1 — githubHello: PR-Agent-Pipeline 建置與泛化部署

**日期**：2026-05-08
**主機**：NB00547
**Repo**：`chenghyang2001/githubHello`（私有）+ `chenghyang2001/langchain_v1.2`（私有）

---

## 完成事項

### 1. 建立 githubHello 專案（spec-driven AI codegen demo）
- 從零建立私有 repo `chenghyang2001/githubHello`
- 設計 `spec.md` 驅動 GitHub Actions 呼叫 Claude Haiku API 自動生成 `githubHello.py`
- workflow `implement-from-spec.yml`：push spec.md 到 main → AI 重新生成腳本 → bot 自動 commit
- 配套 workflow `test-githubhello.yml`：githubHello.py 變動時驗證輸出含問候訊息與 GMT+8 時間格式

### 2. 建立 PR-Agent-Pipeline（3 段 agent 自動化）
**Commit `67e57eb` on main**：當 PR 開啟或同步時自動跑：
- **classify** (Haiku 4.5, ~$0.0004) → 分類 WRITER / DEBUGGER
- **resolver** (Sonnet 4.6, ~$0.024) → 讀 PR 意圖、修改 spec.md / githubHello.py、AST 安全掃描後 commit 推回 PR 分支
- **qa** (Sonnet 4.6, ~$0.018) → 自動產 2 個 pytest 測試案例（happy + edge）並執行，PR 留言貼結果

**安全機制**：
- 同 repo 守衛（`head.repo.full_name == github.repository`）
- AST 掃描（封禁 eval / exec / os.system / subprocess / ctypes / socket / urllib.request / requests / http.client）
- bot-loop guard（跳過 `github-actions[bot]` 為 last committer）
- 不可信輸入分隔（PR title/body/diff 用 `<PR_TITLE>` / `<PR_BODY>` / `<PR_DIFF>` XML tags 包覆 + 警示前置）
- SDK 版本釘選（`anthropic==0.40.*` / `pytest==8.*`）

**3-agent 鐵律執行**：writer 4 檔 (workflow + 3 Python) → QA PASS w/ 7 NICE_TO_HAVE → reviewer **CHANGES_REQUESTED**（2 MUST_FIX）→ writer 補丁 3 檔 → QA PASS → reviewer **APPROVED**

### 3. 端對端驗證（PR #4 multiply 測試）
- 開測試 PR：spec.md 加「功能 5：乘法函式 mul(6, 7)」
- pipeline 全 3 job PASS（classify 12s / resolver 22s / qa 17s，總 ~51s，~$0.04）
- resolver 正確新增 `mul(a, b)` 函式 + `mul(6, 7)` 呼叫並推回 PR 分支
- QA 產 2 測試（test_normal_hello_output / test_edge_datetime_format）全 PASS

### 4. Phase 1：泛化 pipeline 為 config-driven 架構
**Commit `7772aed` on main**：
- 新增 `pipeline.config.json`（5 keys: spec_file / implementation_target / test_target / language / run_command）
- 重構 `scripts/resolver_agent.py`（310 行）+ `scripts/qa_agent.py`（222 行）讀 CONFIG，缺檔 fallback 到 githubHello legacy 預設值
- Sonnet JSON 回應 key 從 `spec_md` / `github_hello_py` 改為通用 `spec` / `code`
- 修兩個邊界 bug：pytest path 改用 `relative_to(REPO_ROOT)` 支援子目錄；`run_cmd_repr` 加防禦分支

### 5. Phase 2：泛化 pipeline 移植至 langchain_v1.2
**PR #1 on `chenghyang2001/langchain_v1.2`**（待你 merge）：https://github.com/chenghyang2001/langchain_v1.2/pull/1
- 7 個檔案：workflow + 3 scripts + `pipeline.config.json` + `pipeline-demo/spec.md` + `pipeline-demo/example.py` + `.github/workflows/`
- `ANTHROPIC_API_KEY` secret 程式化新增（從 `~/Downloads/langchain_v1.2/.env` 讀取後 `gh secret set`）
- **self-bootstrap 測試**：pipeline 在自己被加入的 PR 上跑成功
- 結果：classify 15s / resolver 19s（正確 no-op，spec 與 code 已一致）/ qa 25s（2/2 PASS）
- 總 ~59s，~$0.04
- **`relative_to(REPO_ROOT)` 修正驗證生效**：pytest 跑 `pipeline-demo/test_example.py::test_normal_hello_message` + `test_edge_python_version_line` 全 PASS

### 6. 5 repos 評估 + visibility 調整
評估 `mermaid-viewer / kindle-reader / arvesta / mermaid / langchain_v1.2`：
- 把 mermaid-viewer + kindle-reader 從 PUBLIC 改為 PRIVATE（`gh repo edit --visibility private --accept-visibility-change-consequences`）
- 5 repos 全為 PRIVATE
- 評估後決定**只移植到 langchain_v1.2**（其他 4 repo 不適用：mermaid-viewer 無 Python target、arvesta 純文件、mermaid 主領域是 .mmd 圖表、kindle-reader 工具腳本無 spec→code loop）

---

## 關鍵技術筆記

### Pipeline 設計選擇
- **同 repo 限制**（`if: github.event.pull_request.head.repo.full_name == github.repository`）必須加在每個 job 的 `if:`，與既有 skip-guard 用 `&&` 組合
- **AST scan 必須讀「磁碟最新內容」而非 in-memory 變數**（防 AI 寫入時故意不一致）
- **`re.search(...., DOTALL | IGNORECASE)`** 找 markdown fence 比 `startswith` 穩，模型常先寫導言再 fence
- **`needs.classify.outputs.skip` 只能在直接 `needs:` 鏈中引用** — qa job 必須 `needs: [classify, resolver]` 才能讀 classify 的 outputs

### config-driven 泛化心得
- `load_pipeline_config()` 內建 fallback 到 githubHello defaults → 重構期間舊行為不破
- `TEST_PATH.name` 不夠 — 子目錄 test_target 須用 `str(TEST_PATH.relative_to(REPO_ROOT)).replace("\\", "/")`
- `run_cmd_repr` 在 1-element run_command 時要走 `[sys.executable]` 分支，不留 trailing comma

### GitHub Actions 細節
- 第一次 PR 加入 workflow 同時 workflow 也會在這 PR 上跑（self-bootstrap），但僅限同 repo
- `gh secret set` 用 stdin pipe 避免 shell escape：`echo "$VAL" | gh secret set NAME -R repo`
- `gh repo edit --visibility private` 需要 `--accept-visibility-change-consequences` flag

---

## 產出檔案

### `chenghyang2001/githubHello`（main branch）
| 檔案 | 行數 | 用途 |
|---|---|---|
| `.github/workflows/pr-agent-pipeline.yml` | 144 | 3 段 agent 工作流（classify/resolver/qa）|
| `scripts/classify_pr.py` | 96 | Haiku 4.5 分類 WRITER/DEBUGGER |
| `scripts/resolver_agent.py` | 310 | Sonnet 4.6 解析 + AST 守衛（config-driven）|
| `scripts/qa_agent.py` | 222 | Sonnet 4.6 自動產 2 測試 + pytest（config-driven）|
| `pipeline.config.json` | 7 | 路徑集中設定（5 keys）|

### `chenghyang2001/langchain_v1.2`（PR #1, feat/add-pr-agent-pipeline branch）
| 檔案 | 用途 |
|---|---|
| `.github/workflows/pr-agent-pipeline.yml` | 移植自 githubHello |
| `scripts/{classify_pr,resolver_agent,qa_agent}.py` | 移植自 githubHello |
| `pipeline.config.json` | 路徑指向 `pipeline-demo/` 子目錄 |
| `pipeline-demo/spec.md` | 示範 spec |
| `pipeline-demo/example.py` | 示範實作 |

### Commits
- `67e57eb`：githubHello — 新增 PR-triggered 三段 agent pipeline
- `7772aed`：githubHello — 重構為 config-driven 架構
- `be1c9dd`：langchain_v1.2 — 新增 PR-Agent-Pipeline + pipeline-demo

---

## HANDOFF（下次 session 優先處理）

### 立即行動
- [ ] Merge `chenghyang2001/langchain_v1.2` PR #1（self-bootstrap 已驗證 pipeline 可運作）
- [ ] 在 langchain_v1.2 開後續測試 PR：改 `pipeline-demo/spec.md` 新增「輸出 3：當前時間」看 resolver 自動實作（驗證 spec→code 完整迴圈）
- [ ] Merge `chenghyang2001/githubHello` PR #3（feat/add-goodbye-message）和 PR #4（feat/test/pipeline-add-multiply）— 都已通過 pipeline 驗證

### 進行中（需接續）
- githubHello PR #3 / PR #4 仍 open，等使用者 merge
- langchain_v1.2 PR #1 仍 open，等使用者 merge
- 4 個未採用 repo（mermaid-viewer / arvesta / mermaid / kindle-reader）已記錄不適用原因；若未來重新評估需參考本次決策依據

### 注意事項
- **`ANTHROPIC_API_KEY` 不可放全域環境變數**（cost-rules.md）— 已 ✅ 只放在 GitHub Secret 與獨立 .env 檔
- **AST scan 已知漏洞**：未防 `pickle.loads / marshal.loads / getattr 動態 dispatch / importlib`（reviewer 標記 NICE_TO_HAVE，未來若 pipeline 平台化要補）
- **`scripts/load_pipeline_config()` 在兩個 .py 重複**（DRY 違規）— 未來抽取為 `scripts/pipeline_utils.py`
- **Node.js 20 actions 將於 2026-09-16 移除**（GitHub annotation 警告）— actions/checkout@v4 + actions/setup-python@v5 需要在 2026-06-02 前升級
- **每 PR 成本約 $0.04**（Haiku 0.0004 + Sonnet 0.024 + Sonnet 0.018）— 未來若 PR 數量爆增需設成本上限
