#!/usr/bin/env python3
"""QA Agent（Sonnet 4.6）。

讀 resolver 改完的 githubHello.py，請 Sonnet 寫出恰好 2 個 pytest 測試（happy + edge），
跑 pytest 收集結果，把結果以摺疊區塊留言到 PR。
紅燈不阻擋 workflow（透過 workflow 的 || true 達成）。
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import anthropic


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "githubHello.py"
TEST_PATH = REPO_ROOT / "test_githubHello.py"


def read_target_script() -> str:
    """讀 resolver 改完後的 githubHello.py（QA job checkout 已是最新 PR head）。"""
    if not SCRIPT_PATH.exists():
        raise FileNotFoundError(f"githubHello.py not found at {SCRIPT_PATH}")
    return SCRIPT_PATH.read_text(encoding="utf-8")


def call_qa(code: str, model: str) -> str:
    """請 Sonnet 產出測試檔內容（純 Python，不要 markdown）。"""
    client = anthropic.Anthropic()
    prompt = (
        "Read this Python script and write a `test_githubHello.py` containing EXACTLY 2 "
        "pytest test cases: (1) a normal/happy-path case named test_normal_*, "
        "(2) an edge case named test_edge_*. "
        "Use `subprocess.run([sys.executable, 'githubHello.py'], capture_output=True, text=True)` "
        "and assert on stdout. Return ONLY the raw Python code, no markdown fences, no commentary.\n\n"
        f"=== githubHello.py ===\n{code}\n"
    )
    response = client.messages.create(
        model=model,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def strip_markdown_fences(text: str) -> str:
    """Extract Python code from possibly-fenced model output.

    Handles three cases:
    1. Plain code (no fences) — returned as-is
    2. Code wrapped in ```python ... ``` (any position in text)
    3. Code wrapped in ``` ... ``` (no language tag)

    If fences exist, returns content of the FIRST code block found.
    Falls back to original text if regex finds no block.

    優於舊版：舊版只認「整個輸出以 ``` 開頭」，模型若先寫一句中文導言再 fence
    就會整段被當成 Python 噴 SyntaxError。新版用 re.search 在任意位置找第一個 fence。
    """
    block = re.search(r"```(?:python|py)?\s*\n(.*?)\n```", text, re.DOTALL | re.IGNORECASE)
    if block:
        return block.group(1).strip() + "\n"
    return text.strip() + "\n"


def write_test_file(content: str) -> None:
    """寫入測試檔，確保結尾單一 newline。"""
    if not content.endswith("\n"):
        content += "\n"
    content = content.rstrip("\n") + "\n"
    TEST_PATH.write_text(content, encoding="utf-8")


def run_pytest() -> tuple[int, str]:
    """跑 pytest，回傳 (exit_code, combined_output)。stderr 合併進 stdout 方便讀。"""
    result = subprocess.run(
        ["pytest", str(TEST_PATH), "-v", "--tb=short"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(REPO_ROOT),
    )
    combined = (result.stdout or "") + (result.stderr or "")
    return result.returncode, combined


def parse_pass_fail(output: str, exit_code: int) -> tuple[int, int]:
    """從 pytest summary 解析過/失，總共固定 2 個。"""
    # pytest summary 格式範例："2 passed in 0.10s" / "1 failed, 1 passed in 0.20s"
    passed = 0
    failed = 0
    m_passed = re.search(r"(\d+)\s+passed", output)
    m_failed = re.search(r"(\d+)\s+failed", output)
    if m_passed:
        passed = int(m_passed.group(1))
    if m_failed:
        failed = int(m_failed.group(1))
    # 萬一 summary 解析不到（pytest crash），用 exit code 兜底
    if passed == 0 and failed == 0:
        if exit_code == 0:
            passed = 2
        else:
            failed = 2
    return passed, failed


def build_comment(passed: int, failed: int, output: str) -> str:
    """組 PR 留言內文（含摺疊區塊放 pytest 輸出）。"""
    # 限制 pytest 輸出長度避免 PR 留言爆掉（GitHub 上限 65536 字元）
    excerpt = output if len(output) <= 30000 else output[:30000] + "\n... (truncated)"
    return (
        "**QA Agent Result**\n\n"
        f"Generated 2 test cases. Result: PASS {passed}/2 | FAIL {failed}/2\n\n"
        "<details><summary>Test output</summary>\n\n"
        "```\n"
        f"{excerpt}\n"
        "```\n"
        "</details>\n"
    )


def post_pr_comment(pr_number: str, body: str) -> None:
    """用 gh CLI 留言（透過 --body-file 避免多行 shell escape）。"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(body)
        tmp_path = tmp.name
    try:
        proc = subprocess.run(
            ["gh", "pr", "comment", pr_number, "--body-file", tmp_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if proc.returncode != 0:
            print(f"PR comment failed: {proc.stderr}", file=sys.stderr)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def main() -> None:
    pr_number = os.environ["PR_NUMBER"]
    model = os.environ["QA_MODEL"]
    print(f"QA agent running on PR #{pr_number} (model={model})")

    code = read_target_script()
    print(f"Loaded githubHello.py ({len(code)} chars)")

    raw = call_qa(code, model)
    test_code = strip_markdown_fences(raw)
    write_test_file(test_code)
    print(f"Wrote {TEST_PATH.name} ({len(test_code)} chars)")

    exit_code, output = run_pytest()
    print(f"pytest exit code: {exit_code}")
    print("--- pytest output ---")
    print(output)

    passed, failed = parse_pass_fail(output, exit_code)
    comment = build_comment(passed, failed, output)
    post_pr_comment(pr_number, comment)
    print(f"Posted QA comment: {passed} passed, {failed} failed")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"qa_agent.py failed: {e}", file=sys.stderr)
        # 設計上 QA 永遠 exit 0，紅燈不擋 workflow（workflow 也有 || true 雙保險）
        sys.exit(0)
