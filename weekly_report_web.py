#!/usr/bin/env python3
"""
주간 업무보고 코드 스니펫 생성기 - 웹 버전

로컬에서 실행하는 간단한 웹앱입니다.
브라우저에서 저장소 경로/기간을 입력하고 "생성" 버튼을 누르면
git 커밋 내역에서 코드 스니펫을 뽑아 화면에 보여주고,
Markdown 파일로 다운로드할 수 있습니다.

실행:
    pip install flask
    python weekly_report_web.py

그 다음 브라우저에서 http://127.0.0.1:5050 접속
"""

# Vercel 재배포 트리거용 빈 커밋

from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, request, Response, send_file

from weekly_report_core import get_commit_hashes, get_commit_info
from weekly_report_github import (
    get_authenticated_username,
    get_github_commits,
    github_commit_to_info,
    normalize_github_repo,
    search_user_commits,
)

app = Flask(__name__)
HTML_FILE = Path(__file__).parent / "weekly_report.html"
EXTRA_HTML_FILE = Path(__file__).parent / "battle.html"


def fmt_md(date_str: str) -> str:
    """'2026-07-22' -> '7.22'"""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{dt.month}.{dt.day}"


def build_markdown(commits, name):
    if not commits:
        return "해당 기간에 커밋이 없습니다. 저장소 경로/기간/작성자 값을 확인해주세요.\n"

    # commits는 최신순으로 들어오므로 날짜 오름차순으로 정렬
    ordered = sorted(commits, key=lambda c: c["date"])
    start_date = ordered[0]["date"]
    end_date = ordered[-1]["date"]

    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    next_start_dt = end_dt + timedelta(days=1)
    next_end_dt = end_dt + timedelta(days=5)

    out = []

    # 1) 참고용: 이번 주 커밋 내역 (근거 자료)
    out.append("## 이번 주 커밋 내역 (참고)\n")
    for c in ordered:
        prefix = f"[{c['repo']}] " if c.get("repo") else ""
        out.append(f"- {prefix}`{c['hash']}` {c['date']} - {c['subject']} (작성자: {c['author']})")
    out.append("")
    out.append("---")
    out.append("")

    # 2) 그룹웨어 양식
    display_name = name or ordered[-1]["author"]
    out.append(f"# 주간보고 _ {display_name} (참고)\n")
    out.append(f"**금주 업무 내용 : {fmt_md(start_date)}~{fmt_md(end_date)}**\n")
    for i, c in enumerate(ordered, 1):
        prefix = f"[{c['repo']}] " if c.get("repo") else ""
        out.append(f"{i}. {prefix}{c['subject']}")
    out.append("")
    out.append(f"**차주 업무 내용 : {fmt_md(next_start_dt.strftime('%Y-%m-%d'))}~{fmt_md(next_end_dt.strftime('%Y-%m-%d'))}**\n")
    out.append("1. ")
    out.append("2. ")

    return "\n".join(out)


# ---------- 웹 페이지 ----------
# 실제 화면은 weekly_report.html 파일에서 서빙한다 (같은 폴더에 있어야 함).

@app.route("/")
def index():
    return send_file(HTML_FILE)


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(silent=True) or {}

    # 여러 저장소 (신규) + 기존 단일 repo 필드 둘 다 지원
    repos = data.get("repos") or []
    single = data.get("repo", "").strip()
    if single:
        repos = [single] + list(repos)
    repos = [r.strip() for r in repos if r and r.strip()]

    since = data.get("since", "1 week ago").strip() or "1 week ago"
    until = data.get("until", "now").strip() or "now"
    author = data.get("author", "").strip() or None
    name = data.get("name", "").strip() or None
    github_token = data.get("github_token") or None
    mode = data.get("mode") or None

    if mode == "github_auto":
        if not github_token:
            return {"error": "GitHub 로그인이 필요합니다."}
        try:
            username = get_authenticated_username(github_token)
            commits_json = search_user_commits(username, since, until, github_token, 50)
        except Exception as e:
            return {"error": str(e)}
        md = build_markdown(commits_json, name or username)
        return {"markdown": md}

    if not repos:
        return {"error": "저장소 경로를 하나 이상 입력해주세요."}

    all_commits = []
    for repo in repos:
        owner_repo = normalize_github_repo(repo)
        if owner_repo:
            try:
                commits_json = get_github_commits(owner_repo, since, until, author, github_token, 30)
            except Exception as e:
                return {"error": f"[{repo}] {e}"}
            label = owner_repo.split("/")[-1]
            all_commits += [github_commit_to_info(c, label) for c in commits_json]
            continue

        repo_path = Path(repo).expanduser()
        if repo_path.name == ".git":
            repo_path = repo_path.parent
        if not repo_path.exists():
            return {"error": f"경로를 찾을 수 없습니다: {repo}"}

        try:
            resolved = str(repo_path.resolve())
            label = repo_path.name
            hashes = get_commit_hashes(resolved, since, until, author, 30)
            all_commits += [get_commit_info(resolved, h, repo_label=label) for h in hashes]
        except Exception as e:
            return {"error": f"[{repo}] {e}"}

    md = build_markdown(all_commits, name)
    return {"markdown": md}


@app.route("/battle")
def battle():
    return send_file(EXTRA_HTML_FILE)


@app.route("/battle_data", methods=["POST"])
def battle_data():
    """로그인한 사용자의 기간 내 커밋을 저장소별로 묶어 병력 규모로 변환해 돌려준다."""
    data = request.get_json(silent=True) or {}
    since = data.get("since", "1 week ago").strip() or "1 week ago"
    until = data.get("until", "now").strip() or "now"
    github_token = data.get("github_token") or None

    if not github_token:
        return {"error": "GitHub 로그인이 필요합니다."}

    try:
        username = get_authenticated_username(github_token)
        commits_json = search_user_commits(username, since, until, github_token, 100)
    except Exception as e:
        return {"error": str(e)}

    counts = Counter(c["repo"] for c in commits_json)
    empires = [{"name": name, "soldiers": count} for name, count in counts.items()]

    if len(empires) < 2:
        return {"error": "해당 기간 동안 2개 이상의 저장소에서 활동한 기록이 있어야 전쟁이 가능합니다."}

    return {"empires": empires}


if __name__ == "__main__":
    print("브라우저에서 http://127.0.0.1:5050 로 접속하세요.")
    app.run(host="127.0.0.1", port=5050, debug=False)
