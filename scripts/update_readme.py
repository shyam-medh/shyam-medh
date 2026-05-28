"""
Fetch assigned issues and authored pull requests for GITHUB_USERNAME,
then rewrite the matching marker blocks in README.md.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from urllib.parse import quote

import requests

USERNAME = os.environ.get("GITHUB_USERNAME", "shyam-medh")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
README = "README.md"
PER_PAGE = int(os.environ.get("README_ITEMS_PER_SECTION", "10"))

HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"

STATE_EMOJI = {
    "open": "\U0001F7E2",
    "closed": "\U0001F534",
    "merged": "\U0001F7E3",
}

LABEL_COLORS = {
    "bug": "e11d48",
    "enhancement": "7c3aed",
    "documentation": "0ea5e9",
    "help wanted": "f59e0b",
    "question": "6366f1",
    "good first issue": "22c55e",
}


def github_get(url: str, *, params: dict | None = None, timeout: int = 15) -> dict:
    resp = requests.get(url, headers=HEADERS, params=params, timeout=timeout)
    try:
        resp.raise_for_status()
    except requests.HTTPError as exc:
        message = resp.text[:500]
        raise RuntimeError(f"GitHub API request failed: {resp.status_code} {message}") from exc
    return resp.json()


def gh_search(query: str) -> list[dict]:
    url = "https://api.github.com/search/issues"
    params = {"q": query, "per_page": PER_PAGE, "sort": "updated", "order": "desc"}
    return github_get(url, params=params).get("items", [])


def is_merged(pr: dict) -> bool:
    if pr.get("state") == "open":
        return False
    pr_url = pr.get("pull_request", {}).get("url")
    if not pr_url:
        return False
    try:
        return bool(github_get(pr_url, timeout=10).get("merged_at"))
    except RuntimeError as exc:
        print(f"Could not check merge status for {pr.get('html_url')}: {exc}")
        return False


def fmt_date(iso: str) -> str:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return dt.strftime("%b %d, %Y")


def markdown_cell(text: str) -> str:
    return str(text).replace("\r", " ").replace("\n", " ").replace("|", "\\|").strip()


def truncate(text: str, limit: int = 60) -> str:
    text = markdown_cell(text)
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def label_badges(labels: list[dict]) -> str:
    badges = []
    for label in labels[:3]:
        name = str(label.get("name", "label"))
        color = str(label.get("color") or LABEL_COLORS.get(name.lower(), "6b7280")).lstrip("#")
        safe_name = quote(name.replace("-", "--"), safe="")
        alt = markdown_cell(name).replace("]", "\\]")
        badges.append(
            f"![{alt}](https://img.shields.io/badge/{safe_name}-{color}?style=flat-square)"
        )
    return " ".join(badges)


def repo_from_url(url: str) -> str:
    return "/".join(url.split("/")[3:5])


def build_issues_section(items: list[dict]) -> str:
    if not items:
        return "_No assigned issues found._\n"

    rows = [
        "| # | Repository | Title | Labels | Status | Updated |",
        "|---|-----------|-------|--------|--------|---------|",
    ]
    for item in items:
        number = item["number"]
        url = item["html_url"]
        repo = repo_from_url(url)
        title = truncate(item["title"])
        state = STATE_EMOJI.get(item["state"], "\u26AA") + f" `{item['state'].upper()}`"
        labels = label_badges(item.get("labels", []))
        updated = fmt_date(item["updated_at"])
        rows.append(f"| [#{number}]({url}) | `{repo}` | [{title}]({url}) | {labels} | {state} | {updated} |")

    return "\n".join(rows) + "\n"


def build_prs_section(items: list[dict]) -> str:
    if not items:
        return "_No pull requests found._\n"

    rows = [
        "| # | Repository | Title | Labels | Status | Updated |",
        "|---|-----------|-------|--------|--------|---------|",
    ]
    for item in items:
        number = item["number"]
        url = item["html_url"]
        repo = repo_from_url(url)
        title = truncate(item["title"])

        if item["state"] == "open":
            state_key = "open"
        elif is_merged(item):
            state_key = "merged"
        else:
            state_key = "closed"

        state = STATE_EMOJI[state_key] + f" `{state_key.upper()}`"
        labels = label_badges(item.get("labels", []))
        updated = fmt_date(item["updated_at"])
        rows.append(f"| [#{number}]({url}) | `{repo}` | [{title}]({url}) | {labels} | {state} | {updated} |")

    return "\n".join(rows) + "\n"


def replace_section(content: str, start_tag: str, end_tag: str, new_body: str) -> str:
    pattern = re.compile(rf"({re.escape(start_tag)}\n).*?(\n{re.escape(end_tag)})", re.DOTALL)
    new_content, count = pattern.subn(rf"\g<1>{new_body}\g<2>", content)
    if count == 0:
        raise ValueError(f"Marker not found: {start_tag!r}")
    return new_content


def main() -> None:
    print("Fetching assigned issues...")
    issues = gh_search(f"assignee:{USERNAME} type:issue")

    print("Fetching authored pull requests...")
    prs = gh_search(f"author:{USERNAME} type:pr")

    timestamp = datetime.now(timezone.utc).strftime("%b %d, %Y %H:%M UTC")
    clock = "\U0001F552"

    issues_md = (
        f"> {clock} _Last updated: **{timestamp}**_ &nbsp;|&nbsp; "
        f"Showing latest {min(len(issues), PER_PAGE)} assigned issues\n\n"
        + build_issues_section(issues)
    )
    prs_md = (
        f"> {clock} _Last updated: **{timestamp}**_ &nbsp;|&nbsp; "
        f"Showing latest {min(len(prs), PER_PAGE)} pull requests\n\n"
        + build_prs_section(prs)
    )

    with open(README, "r", encoding="utf-8") as readme_file:
        content = readme_file.read()

    content = replace_section(content, "<!-- ISSUES_START -->", "<!-- ISSUES_END -->", issues_md)
    content = replace_section(content, "<!-- PRS_START -->", "<!-- PRS_END -->", prs_md)

    with open(README, "w", encoding="utf-8") as readme_file:
        readme_file.write(content)

    print("README.md updated successfully.")


if __name__ == "__main__":
    main()
