"""
update_readme.py
Fetches assigned issues and authored PRs for GITHUB_USERNAME,
then rewrites the two marker blocks in README.md.
"""

import os
import re
import requests
from datetime import datetime, timezone

USERNAME = os.environ.get("GITHUB_USERNAME", "shyam-medh")
TOKEN    = os.environ.get("GITHUB_TOKEN", "")
README   = "README.md"
PER_PAGE = 10          # items shown per section

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

STATE_EMOJI = {
    "open":   "🟢",
    "closed": "🔴",
    "merged": "🟣",
}

LABEL_COLORS = {
    "bug":           "e11d48",
    "enhancement":   "7c3aed",
    "documentation": "0ea5e9",
    "help wanted":   "f59e0b",
    "question":      "6366f1",
    "good first issue": "22c55e",
}


def gh_search(query: str, kind: str = "issue") -> list[dict]:
    """Return up to PER_PAGE items from GitHub code-search."""
    url = "https://api.github.com/search/issues"
    params = {"q": query, "per_page": PER_PAGE, "sort": "updated", "order": "desc"}
    resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json().get("items", [])


def is_merged(pr: dict) -> bool:
    """Check if a PR was merged (requires extra API call for closed PRs)."""
    if pr.get("state") == "open":
        return False
    pr_url = pr.get("pull_request", {}).get("url", "")
    if not pr_url:
        return False
    r = requests.get(pr_url, headers=HEADERS, timeout=10)
    if r.status_code != 200:
        return False
    return bool(r.json().get("merged_at"))


def fmt_date(iso: str) -> str:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return dt.strftime("%b %d, %Y")


def label_badges(labels: list[dict]) -> str:
    badges = []
    for lbl in labels[:3]:
        name  = lbl["name"]
        color = lbl.get("color") or LABEL_COLORS.get(name.lower(), "6b7280")
        safe  = name.replace(" ", "%20").replace("-", "--")
        badges.append(
            f"![{name}](https://img.shields.io/badge/{safe}-{color}?style=flat-square)"
        )
    return " ".join(badges)


def build_issues_section(items: list[dict]) -> str:
    if not items:
        return "_No assigned issues found._\n"

    rows = [
        "| # | Repository | Title | Labels | Status | Updated |",
        "|---|-----------|-------|--------|--------|---------|",
    ]
    for item in items:
        num   = item["number"]
        title = item["title"][:60] + ("…" if len(item["title"]) > 60 else "")
        url   = item["html_url"]
        repo  = "/".join(url.split("/")[3:5])
        state = STATE_EMOJI.get(item["state"], "⚪") + f" `{item['state'].upper()}`"
        lbls  = label_badges(item.get("labels", []))
        date  = fmt_date(item["updated_at"])
        rows.append(f"| [#{num}]({url}) | `{repo}` | [{title}]({url}) | {lbls} | {state} | {date} |")

    return "\n".join(rows) + "\n"


def build_prs_section(items: list[dict]) -> str:
    if not items:
        return "_No pull requests found._\n"

    rows = [
        "| # | Repository | Title | Labels | Status | Updated |",
        "|---|-----------|-------|--------|--------|---------|",
    ]
    for item in items:
        num   = item["number"]
        title = item["title"][:60] + ("…" if len(item["title"]) > 60 else "")
        url   = item["html_url"]
        repo  = "/".join(url.split("/")[3:5])

        if item["state"] == "open":
            state_key = "open"
        elif is_merged(item):
            state_key = "merged"
        else:
            state_key = "closed"

        state = STATE_EMOJI[state_key] + f" `{state_key.upper()}`"
        lbls  = label_badges(item.get("labels", []))
        date  = fmt_date(item["updated_at"])
        rows.append(f"| [#{num}]({url}) | `{repo}` | [{title}]({url}) | {lbls} | {state} | {date} |")

    return "\n".join(rows) + "\n"


def replace_section(content: str, start_tag: str, end_tag: str, new_body: str) -> str:
    pattern = re.compile(
        rf"({re.escape(start_tag)}\n).*?(\n{re.escape(end_tag)})",
        re.DOTALL,
    )
    replacement = rf"\g<1>{new_body}\g<2>"
    new_content, n = pattern.subn(replacement, content)
    if n == 0:
        raise ValueError(f"Marker not found: {start_tag!r}")
    return new_content


def main() -> None:
    # ── fetch data ──────────────────────────────────────────────────────────
    print("🔍 Fetching assigned issues …")
    issues = gh_search(f"assignee:{USERNAME} type:issue")

    print("🔍 Fetching raised pull requests …")
    prs = gh_search(f"author:{USERNAME} type:pr")

    # ── build markdown ───────────────────────────────────────────────────────
    ts = datetime.now(timezone.utc).strftime("%b %d, %Y %H:%M UTC")

    issues_md = (
        f"> 🕒 _Last updated: **{ts}**_ &nbsp;|&nbsp; "
        f"Showing latest {min(len(issues), PER_PAGE)} assigned issues\n\n"
        + build_issues_section(issues)
    )
    prs_md = (
        f"> 🕒 _Last updated: **{ts}**_ &nbsp;|&nbsp; "
        f"Showing latest {min(len(prs), PER_PAGE)} pull requests\n\n"
        + build_prs_section(prs)
    )

    # ── patch README ─────────────────────────────────────────────────────────
    with open(README, "r", encoding="utf-8") as fh:
        content = fh.read()

    content = replace_section(content, "<!-- ISSUES_START -->", "<!-- ISSUES_END -->", issues_md)
    content = replace_section(content, "<!-- PRS_START -->",    "<!-- PRS_END -->",    prs_md)

    with open(README, "w", encoding="utf-8") as fh:
        fh.write(content)

    print("✅ README.md updated successfully!")


if __name__ == "__main__":
    main()
