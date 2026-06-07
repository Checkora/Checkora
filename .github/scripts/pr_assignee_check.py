#!/usr/bin/env python3
"""
Verify a PR author is assigned to every linked issue.

Used by GitHub Actions (ci.yml) and optionally Vercel ignoreCommand.
Exit codes for vercel mode: 0 = skip build, 1 = proceed with build.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request

CLOSING_RE = re.compile(
    r"(?i)\b(?:fix(?:e)?s?|close[sd]?|resolve[sd]?)\s+(?:[^\n#]*)?#(\d+)"
)
FIXES_RE = re.compile(r"(?i)fixes\s+#(\d+)")
RELATED_RE = re.compile(r"(?i)related issue[^\n]*#(\d+)")


def github_get(url: str, token: str):
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "checkora-pr-guardian",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    # GitHub REST only; URLs are built from repo metadata, not user input.
    with urllib.request.urlopen(request, timeout=30) as response:  # nosec B310
        return json.load(response)


def is_infra_only_pr(owner: str, repo: str, pr_number: int, token: str) -> bool:
    """Allow workflow-only PRs (e.g. PR Guardian itself) without a linked issue."""
    files = github_get(
        f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files?per_page=100",
        token,
    )
    if not isinstance(files, list) or not files:
        return False
    for entry in files:
        name = entry.get("filename", "")
        if not (name.startswith(".github/") or name == "vercel.json"):
            return False
    return True


def parse_issue_numbers(body: str, title: str = "") -> list[int]:
    text = f"{title}\n{body or ''}"
    numbers: set[int] = set()
    for pattern in (CLOSING_RE, FIXES_RE, RELATED_RE):
        for match in pattern.finditer(text):
            numbers.add(int(match.group(1)))
    return sorted(numbers)


def has_maintainer_bypass(owner: str, repo: str, author: str, token: str) -> bool:
    try:
        data = github_get(
            f"https://api.github.com/repos/{owner}/{repo}/collaborators/{author}/permission",
            token,
        )
        return data.get("permission") in ("admin", "maintain")
    except urllib.error.HTTPError:
        return False


def evaluate_pr(
    owner: str,
    repo: str,
    pr_number: int,
    token: str,
    pr_author: str | None = None,
) -> tuple[bool, str]:
    pr = github_get(
        f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}",
        token,
    )
    author = pr_author or pr["user"]["login"]
    body = pr.get("body") or ""
    title = pr.get("title") or ""

    if has_maintainer_bypass(owner, repo, author, token):
        return True, "maintainer_bypass"

    if is_infra_only_pr(owner, repo, pr_number, token):
        return True, "infra_only"

    if re.search(r"#\s*\(\s*issue\s+number\s*\)", body, re.IGNORECASE):
        return False, "template_not_filled"

    issue_numbers = parse_issue_numbers(body, title)
    if not issue_numbers:
        return False, "no_issue_linked"

    for number in issue_numbers:
        issue = github_get(
            f"https://api.github.com/repos/{owner}/{repo}/issues/{number}",
            token,
        )
        if issue.get("pull_request"):
            continue
        assignees = [user["login"] for user in issue.get("assignees", [])]
        if not assignees:
            return False, f"issue_{number}_unassigned"
        if author not in assignees:
            return False, f"issue_{number}_assignee_mismatch"

    return True, "ok"


def write_github_output(name: str, value: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as handle:
        handle.write(f"{name}={value}\n")


def run_ci() -> int:
    repository = os.environ["GITHUB_REPOSITORY"]
    owner, repo = repository.split("/", 1)
    pr_number = int(os.environ["PR_NUMBER"])
    pr_author = os.environ.get("PR_AUTHOR", "")
    token = os.environ["GITHUB_TOKEN"]

    allowed, reason = evaluate_pr(owner, repo, pr_number, token, pr_author or None)
    write_github_output("ci_allowed", "true" if allowed else "false")
    write_github_output("reason", reason)
    print(f"ci_allowed={'true' if allowed else 'false'} reason={reason}")
    return 0


def run_vercel() -> int:
    pr_id = os.environ.get("VERCEL_GIT_PULL_REQUEST_ID", "").strip()
    if not pr_id:
        print("Not a PR preview — building")
        return 1

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("GITHUB_TOKEN not set on Vercel — building (set token to skip mismatched PRs)")
        return 1

    owner = os.environ.get("VERCEL_GIT_REPO_OWNER") or ""
    repo = os.environ.get("VERCEL_GIT_REPO_SLUG") or ""
    if not owner or not repo:
        repository = os.environ.get("GITHUB_REPOSITORY", "")
        if "/" in repository:
            owner, repo = repository.split("/", 1)
        else:
            print("Missing repo owner/slug — building")
            return 1

    allowed, reason = evaluate_pr(owner, repo, int(pr_id), token)
    if allowed:
        print(f"Vercel build allowed: {reason}")
        return 1
    print(f"Vercel build skipped: {reason}")
    return 0


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "ci"
    if mode == "vercel":
        return run_vercel()
    if mode == "ci":
        return run_ci()
    print(f"Unknown mode: {mode}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
