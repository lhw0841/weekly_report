#!/usr/bin/env python3
"""
weekly_report_snippets.py / weekly_report_web.py 공용 git 로직
"""

import subprocess
import sys

_LANG_EXTS = {
    ".py": "python", ".js": "javascript", ".ts": "typescript", ".tsx": "tsx",
    ".jsx": "jsx", ".java": "java", ".kt": "kotlin", ".go": "go", ".rb": "ruby",
    ".c": "c", ".cpp": "cpp", ".cs": "csharp", ".sql": "sql", ".sh": "bash",
    ".yml": "yaml", ".yaml": "yaml", ".json": "json", ".html": "html", ".css": "css",
}


def run_git(repo: str, args: list[str]) -> str:
    result = subprocess.run(
        ["git", "-C", repo] + args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git 명령 실행 실패")
    return result.stdout


def get_commit_hashes(repo: str, since: str, until: str, author: str | None, max_commits: int) -> list[str]:
    args = ["log", f"--since={since}", f"--until={until}", "--pretty=format:%H"]
    if author:
        args += [f"--author={author}"]
    out = run_git(repo, args)
    return [h for h in out.splitlines() if h.strip()][:max_commits]


def get_commit_info(repo: str, commit_hash: str, repo_label: str | None = None) -> dict:
    meta = run_git(repo, ["show", "-s", "--format=%h|%an|%ad|%s", "--date=short", commit_hash]).strip()
    short_hash, author, date, subject = meta.split("|", 3)
    files = run_git(repo, ["show", "--stat", "--format=", commit_hash]).strip()
    file_lines = [l.strip() for l in files.splitlines() if l.strip()]
    diff = run_git(repo, ["show", "--format=", "--unified=1", commit_hash])
    info = {
        "hash": short_hash, "author": author, "date": date, "subject": subject,
        "files": file_lines, "diff": diff,
    }
    if repo_label is not None:
        info["repo"] = repo_label
    return info


def extract_snippet(diff: str, max_lines: int) -> str:
    """diff에서 실제 추가/수정된 코드 라인(+로 시작, 헤더 제외)만 추려서 스니펫으로 만든다."""
    lines = []
    for line in diff.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            lines.append(line[1:])
        if len(lines) >= max_lines:
            break
    return "\n".join(lines) if lines else "(변경 코드 없음 - 파일 삭제/이동 등)"


def guess_lang(files: list[str]) -> str:
    for f in files:
        for ext, lang in _LANG_EXTS.items():
            if ext in f:
                return lang
    return ""
