#!/usr/bin/env python3
"""
GitHub API 기반 커밋 조회 로직.

로컬 git 저장소 대신 GitHub 저장소(owner/repo)를 조회할 때 사용한다.
배포 환경(Vercel 등)에서는 로컬 파일시스템에 접근할 수 없기 때문에,
로그인한 사용자의 GitHub 토큰으로 GitHub REST API를 호출해 커밋을 가져온다.
"""

import re
from datetime import datetime

import requests

GITHUB_API = "https://api.github.com"
REPO_PATTERN = re.compile(r"^[\w.-]+/[\w.-]+$")


def is_github_repo(repo: str) -> bool:
    """'owner/repo' 형식이면 GitHub API 대상으로 간주한다 (로컬 경로와 구분)."""
    return bool(REPO_PATTERN.match(repo)) and "\\" not in repo


def _to_iso8601(date_str: str) -> str | None:
    """'YYYY-MM-DD' 또는 'YYYY-MM-DD HH:MM:SS' -> GitHub API가 요구하는 ISO 8601."""
    date_str = (date_str or "").strip()
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue
    return None


def get_github_commits(owner_repo: str, since: str, until: str, author: str | None,
                        token: str | None, max_commits: int) -> list[dict]:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    params = {"per_page": min(max_commits, 100)}
    since_iso = _to_iso8601(since)
    until_iso = _to_iso8601(until)
    if since_iso:
        params["since"] = since_iso
    if until_iso:
        params["until"] = until_iso
    if author:
        params["author"] = author

    resp = requests.get(f"{GITHUB_API}/repos/{owner_repo}/commits", headers=headers, params=params, timeout=15)
    if resp.status_code != 200:
        message = "알 수 없는 오류"
        try:
            message = resp.json().get("message", message)
        except ValueError:
            pass
        if resp.status_code == 404:
            message = "저장소를 찾을 수 없거나 접근 권한이 없습니다 (비공개 저장소는 GitHub 로그인이 필요합니다)."
        elif resp.status_code == 403:
            message = "GitHub API 요청 한도를 초과했습니다. 로그인 후 다시 시도해주세요."
        raise RuntimeError(message)

    return resp.json()[:max_commits]


def get_authenticated_username(token: str) -> str:
    """로그인한 사용자의 GitHub 로그인 아이디를 가져온다."""
    resp = requests.get(
        f"{GITHUB_API}/user",
        headers={"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}"},
        timeout=15,
    )
    if resp.status_code != 200:
        raise RuntimeError("GitHub 로그인 정보를 확인할 수 없습니다. 다시 로그인해주세요.")
    return resp.json()["login"]


def search_user_commits(username: str, since: str, until: str, token: str, max_commits: int) -> list[dict]:
    """로그인한 사용자가 접근 가능한 모든 저장소에서, 기간 내 본인 커밋을 검색한다."""
    since_iso = _to_iso8601(since)
    until_iso = _to_iso8601(until)
    date_range = f"{since_iso or '*'}..{until_iso or '*'}"

    headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}"}
    params = {
        "q": f"author:{username} author-date:{date_range}",
        "sort": "author-date",
        "order": "desc",
        "per_page": min(max_commits, 100),
    }
    resp = requests.get(f"{GITHUB_API}/search/commits", headers=headers, params=params, timeout=15)
    if resp.status_code != 200:
        message = "알 수 없는 오류"
        try:
            message = resp.json().get("message", message)
        except ValueError:
            pass
        raise RuntimeError(f"GitHub 커밋 검색 실패: {message}")

    items = resp.json().get("items", [])[:max_commits]
    results = []
    for item in items:
        repo_label = (item.get("repository") or {}).get("name", "?")
        info = github_commit_to_info(item, repo_label)
        results.append(info)
    return results


def github_commit_to_info(commit_json: dict, repo_label: str) -> dict:
    commit = commit_json.get("commit", {})
    author_info = commit.get("author") or {}
    subject = (commit.get("message") or "").splitlines()[0] if commit.get("message") else ""
    return {
        "hash": commit_json.get("sha", "")[:7],
        "author": author_info.get("name") or (commit_json.get("author") or {}).get("login") or "알 수 없음",
        "date": (author_info.get("date") or "")[:10],
        "subject": subject,
        "files": [],
        "diff": "",
        "repo": repo_label,
    }
