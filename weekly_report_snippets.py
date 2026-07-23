#!/usr/bin/env python3
"""
주간 업무보고용 코드 스니펫 자동 생성기

로컬 git 저장소에서 지정한 기간의 커밋을 훑어서,
커밋 메시지 + 실제 변경된 코드(주요 추가/수정 라인)를
업무보고에 바로 붙여넣을 수 있는 Markdown으로 정리한다.

사용법:
    python weekly_report_snippets.py --repo /path/to/repo
    python weekly_report_snippets.py --repo /path/to/repo --since "1 week ago" --until "now"
    python weekly_report_snippets.py --repo /path/to/repo --author "hyunwoo" --out report.md
    python weekly_report_snippets.py --repo /path/to/repo --max-lines 15

옵션:
    --repo        git 저장소 경로 (기본값: 현재 디렉토리)
    --since       조회 시작 시점 (기본값: "1 week ago". git date 포맷 아무거나 가능, 예: 2026-07-17)
    --until       조회 종료 시점 (기본값: "now")
    --author      특정 작성자 커밋만 필터 (기본값: 전체)
    --out         결과를 저장할 파일 경로 (기본값: 없음 = 콘솔 출력만)
    --max-lines   커밋당 스니펫에 포함할 최대 라인 수 (기본값: 20)
    --max-commits 처리할 최대 커밋 수 (기본값: 30)
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_git(repo: str, args: list[str]) -> str:
    result = subprocess.run(
        ["git", "-C", repo] + args,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"[git 오류] {' '.join(args)}\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result.stdout


def get_commit_hashes(repo: str, since: str, until: str, author: str | None, max_commits: int) -> list[str]:
    args = ["log", f"--since={since}", f"--until={until}", "--pretty=format:%H"]
    if author:
        args += [f"--author={author}"]
    out = run_git(repo, args)
    hashes = [h for h in out.splitlines() if h.strip()]
    return hashes[:max_commits]


def get_commit_info(repo: str, commit_hash: str) -> dict:
    meta = run_git(
        repo,
        ["show", "-s", "--format=%h|%an|%ad|%s", "--date=short", commit_hash],
    ).strip()
    short_hash, author, date, subject = meta.split("|", 3)

    files = run_git(repo, ["show", "--stat", "--format=", commit_hash]).strip()
    file_lines = [l.strip() for l in files.splitlines() if l.strip()]

    diff = run_git(repo, ["show", "--format=", "--unified=1", commit_hash])

    return {
        "hash": short_hash,
        "author": author,
        "date": date,
        "subject": subject,
        "files": file_lines,
        "diff": diff,
    }


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
    exts = {
        ".py": "python", ".js": "javascript", ".ts": "typescript", ".tsx": "tsx",
        ".jsx": "jsx", ".java": "java", ".kt": "kotlin", ".go": "go", ".rb": "ruby",
        ".c": "c", ".cpp": "cpp", ".cs": "csharp", ".sql": "sql", ".sh": "bash",
        ".yml": "yaml", ".yaml": "yaml", ".json": "json", ".html": "html", ".css": "css",
    }
    for f in files:
        for ext, lang in exts.items():
            if ext in f:
                return lang
    return ""


def build_markdown(commits: list[dict], max_lines: int) -> str:
    if not commits:
        return "해당 기간에 커밋이 없습니다. --since/--until/--author 값을 확인해주세요.\n"

    out = [f"# 주간 업무보고 - 코드 스니펫 ({commits[-1]['date']} ~ {commits[0]['date']})\n"]
    for i, c in enumerate(commits, 1):
        snippet = extract_snippet(c["diff"], max_lines)
        lang = guess_lang(c["files"])
        out.append(f"## {i}. {c['subject']}")
        out.append(f"- 커밋: `{c['hash']}` / 작성자: {c['author']} / 날짜: {c['date']}")
        if c["files"]:
            out.append(f"- 변경 파일: {len(c['files'])}개")
        out.append(f"```{lang}")
        out.append(snippet)
        out.append("```")
        out.append("")
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description="주간 업무보고용 코드 스니펫 생성기")
    parser.add_argument("--repo", default=".", help="git 저장소 경로")
    parser.add_argument("--since", default="1 week ago", help="조회 시작 시점")
    parser.add_argument("--until", default="now", help="조회 종료 시점")
    parser.add_argument("--author", default=None, help="작성자 필터")
    parser.add_argument("--out", default=None, help="결과 저장 파일 경로")
    parser.add_argument("--max-lines", type=int, default=20, help="커밋당 최대 스니펫 라인 수")
    parser.add_argument("--max-commits", type=int, default=30, help="최대 처리 커밋 수")
    args = parser.parse_args()

    repo = str(Path(args.repo).expanduser().resolve())
    hashes = get_commit_hashes(repo, args.since, args.until, args.author, args.max_commits)
    commits = [get_commit_info(repo, h) for h in hashes]

    md = build_markdown(commits, args.max_lines)

    if args.out:
        Path(args.out).write_text(md, encoding="utf-8")
        print(f"저장 완료: {args.out}")
    else:
        print(md)


if __name__ == "__main__":
    main()
