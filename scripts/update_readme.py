"""
Fetch assigned issues, authored issues, and authored pull requests for GITHUB_USERNAME,
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
README = "README.md"`r`nGSSOC_PROFILE_ID = "5fbedb80-8027-48e2-b0ae-26c9d96f735c"`r`nGSSOC_PROFILE_URL = f"https://gssoc.girlscript.org/profile/{GSSOC_PROFILE_ID}"`r`nGSSOC_API_URL = f"https://gssoc.girlscript.org/api/profile/{GSSOC_PROFILE_ID}"
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


def gh_search(query: str, per_page: int = PER_PAGE) -> tuple[int, list[dict]]:
    url = "https://api.github.com/search/issues"
    params = {"q": query, "per_page": per_page, "sort": "updated", "order": "desc"}
    payload = github_get(url, params=params)
    return int(payload.get("total_count", 0)), payload.get("items", [])


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


def build_table(items: list[dict], *, is_pr_table: bool) -> str:
    if not items:
        return "_No items found._\n"

    rows = [
        "| # | Repository | Title | Labels | Status | Updated |",
        "|---|-----------|-------|--------|--------|---------|",
    ]
    for item in items:
        number = item["number"]
        url = item["html_url"]
        repo = repo_from_url(url)
        title = truncate(item["title"])

        if is_pr_table:
            if item["state"] == "open":
                state_key = "open"
            elif is_merged(item):
                state_key = "merged"
            else:
                state_key = "closed"
        else:
            state_key = item["state"]

        state = STATE_EMOJI.get(state_key, "\u26AA") + f" `{state_key.upper()}`"
        labels = label_badges(item.get("labels", []))
        updated = fmt_date(item["updated_at"])
        rows.append(f"| [#{number}]({url}) | `{repo}` | [{title}]({url}) | {labels} | {state} | {updated} |")

    return "\n".join(rows) + "\n"


def build_dropdown(
    *,
    title: str,
    total_count: int,
    items: list[dict],
    search_url: str,
    is_pr_table: bool,
) -> str:
    shown_count = min(len(items), PER_PAGE)

    if not items:
        return (
            f"<details>\n"
            f"<summary><b>{title}</b> · Total: <b>{total_count}</b></summary>\n\n"
            f"_No {title.lower()} found._\n\n"
            f"</details>\n"
        )

    table = build_table(items, is_pr_table=is_pr_table)
    return (
        f"<details>\n"
        f"<summary><b>{title}</b> · Total: <b>{total_count}</b> · Showing latest <b>{shown_count}</b></summary>\n\n"
        f"{table}\n"
        f"[View all {title.lower()}]({search_url})\n\n"
        f"</details>\n"
    )


def build_issues_section(
    *,
    assigned_total: int,
    assigned_items: list[dict],
    assigned_url: str,
    raised_total: int,
    raised_items: list[dict],
    raised_url: str,
) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%b %d, %Y %H:%M UTC")
    return (
        f"> Last updated: **{timestamp}** &nbsp;|&nbsp; Assigned: **{assigned_total}** &nbsp;|&nbsp; Raised: **{raised_total}**\n\n"
        + build_dropdown(
            title="Assigned Issues",
            total_count=assigned_total,
            items=assigned_items,
            search_url=assigned_url,
            is_pr_table=False,
        )
        + "\n"
        + build_dropdown(
            title="Issues Raised By Me",
            total_count=raised_total,
            items=raised_items,
            search_url=raised_url,
            is_pr_table=False,
        )
    )


def build_prs_section(*, total_count: int, items: list[dict], search_url: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%b %d, %Y %H:%M UTC")
    return (
        f"> Last updated: **{timestamp}** &nbsp;|&nbsp; Total: **{total_count}**\n\n"
        + build_dropdown(
            title="Pull Requests",
            total_count=total_count,
            items=items,
            search_url=search_url,
            is_pr_table=True,
        )
    )

def fmt_int(value: int | float | None) -> str:
    return f"{int(value or 0):,}"


def gssoc_badges(data: dict) -> list[tuple[str, str, str]]:
    profile = data.get("profile") or {}
    app = data.get("app") or {}
    score = int(data.get("score") or 0)
    rank = data.get("rank")
    bounty_count = int(data.get("bountyCount") or 0)
    merged_pr_count = int(data.get("mergedPrCount") or 0)
    streak = int(data.get("streak") or 0)
    roles = app.get("accepted_roles") or app.get("roles") or []
    applied_at = app.get("applied_at")

    badges: list[tuple[str, str, str]] = []
    if app or profile:
        badges.append(("First Steps", "Universal", "Applied to GSSoC 2026"))
    if applied_at and datetime.fromisoformat(applied_at.replace("Z", "+00:00")) < datetime.fromisoformat("2026-03-27T00:00:00+00:00"):
        badges.append(("Early Bird", "Universal", "Applied in the first 48 hours"))
    if profile.get("discord_user_id"):
        badges.append(("Discord Verified", "Universal", "Connected Discord account"))
    if "contributor" in roles:
        badges.append(("Code Warrior", "Roles", "Accepted as Contributor"))
    if score >= 500:
        badges.append(("Point Scorer", "Points", "500+ points"))
    if score >= 1000:
        badges.append(("Rising Star", "Points", "1,000+ points"))
    if score >= 2500:
        badges.append(("Power Contributor", "Points", "2,500+ points"))
    if rank and rank <= 100:
        badges.append(("Top 100", "Leaderboard", "Ranked in top 100"))
    if bounty_count >= 1:
        badges.append(("Bounty Hunter", "Bounty", "First bounty task"))
    if bounty_count >= 5:
        badges.append(("Bounty Master", "Bounty", "Bounty milestone completed"))
    if merged_pr_count >= 5:
        badges.append(("Getting Started", "Contributions", "5 PRs merged"))
    if streak >= 1:
        badges.append(("Week One", "Streaks", "Active week 1"))
    return badges


def build_gssoc_section(data: dict) -> str:
    app = data.get("app") or {}
    score = int(data.get("score") or 0)
    rank = data.get("rank")
    total_participants = data.get("totalParticipants")
    bounty_points = int(data.get("bountyPoints") or 0)
    prs = [pr for pr in data.get("prs", []) if not pr.get("is_excluded")]
    pr_points = sum(int(pr.get("points") or 0) for pr in prs)
    other_points = max(0, score - bounty_points - pr_points)
    bounty_rows = data.get("bountyRows") or []
    tracks = ", ".join(app.get("preferred_track") or []) if isinstance(app.get("preferred_track"), list) else str(app.get("preferred_track") or "Open Source Track")
    tracks = tracks.replace('["', '').replace('"]', '').replace('","', ' + ')

    pr_rows = "\n".join(
        f"| `{markdown_cell(pr.get('repo_full') or pr.get('repo_name') or 'Unknown')}` | [{markdown_cell(pr.get('pr_title') or 'Pull Request')}]({pr.get('pr_url')}) | {markdown_cell(str(pr.get('difficulty') or 'unlabelled').replace('level:', '').title())}{' · ' + markdown_cell(str(pr.get('quality')).replace('quality:', '').title()) if pr.get('quality') else ''} | **{fmt_int(pr.get('points'))}** |"
        for pr in prs
    ) or "| _No scored PRs yet_ | - | - | 0 |"

    bounty_labels = {
        "follow_twitter": "Follow X/Twitter",
        "follow_instagram": "Follow Instagram",
        "share_linkedin": "Share on LinkedIn",
        "subscribe_substack": "Subscribe to newsletter",
        "ai_idea_submission": "AI idea submission",
    }
    bounty_note = ", ".join(bounty_labels.get(row.get("task_id"), str(row.get("task_id", "Bounty"))) for row in bounty_rows) or "Community bounty tasks"
    badge_rows = "\n".join(f"| {name} | {category} | {criteria} |" for name, category, criteria in gssoc_badges(data))

    return f'''## 🌟 GSSoC '26

<div align="center">

<a href="{GSSOC_PROFILE_URL}">
  <img src="https://img.shields.io/badge/GSSoC%2726-Contributor-FF6B35?style=for-the-badge&logo=opensourceinitiative&logoColor=white" alt="GSSoC 26 Contributor"/>
</a>
<a href="{GSSOC_PROFILE_URL}">
  <img src="https://img.shields.io/badge/Rank-%23{rank}%20of%20{total_participants}-7C3AED?style=for-the-badge&logo=leaderboard&logoColor=white" alt="GSSoC Rank"/>
</a>
<a href="{GSSOC_PROFILE_URL}">
  <img src="https://img.shields.io/badge/Points-{score}-1FB6A6?style=for-the-badge&logo=starship&logoColor=white" alt="GSSoC Points"/>
</a>

</div>

| Metric | Value |
| ------ | ----- |
| Role | **Contributor** |
| Status | **{markdown_cell(app.get('status', 'accepted')).title()}** |
| Track | **{markdown_cell(tracks)}** |
| Total Points | **{fmt_int(score)}** |
| Global Rank | **#{fmt_int(rank)} / {fmt_int(total_participants)}** |
| Merged PRs | **{fmt_int(data.get('mergedPrCount'))}** across **{fmt_int(data.get('projectsCount'))}** projects |
| Bounty Tasks | **{fmt_int(data.get('bountyCount'))}** completed |

<details>
<summary><b>Point Distribution</b></summary>

| Source | Points | Notes |
| ------ | -----: | ----- |
| Community Bounties | **{fmt_int(bounty_points)}** | {markdown_cell(bounty_note)} |
| Merged Pull Requests | **{fmt_int(pr_points)}** | {fmt_int(data.get('mergedPrCount'))} scored PRs |
| Profile, role, and program milestones | **{fmt_int(other_points)}** | Selection/profile/program scoring from GSSoC |
| **Total** | **{fmt_int(score)}** | Current public profile score |

</details>

<details>
<summary><b>Scored Pull Requests</b></summary>

| Project | PR | Level | Points |
| ------- | -- | ----- | -----: |
{pr_rows}

</details>

<details>
<summary><b>Earned Badges</b></summary>

| Badge | Category | Unlock Criteria |
| ----- | -------- | --------------- |
{badge_rows}

</details>

[View Official GSSoC Profile]({GSSOC_PROFILE_URL})
'''


def replace_gssoc_section(content: str, new_body: str) -> str:
    pattern = re.compile(r"## 🌟 GSSoC '26\n.*?(?=\n---\n\n## 🎮 GitHub Trophies)", re.DOTALL)
    new_content, count = pattern.subn(new_body.rstrip() + "\n", content)
    if count == 0:
        raise ValueError("GSSoC section marker not found")
    return new_content


def replace_section(content: str, start_tag: str, end_tag: str, new_body: str) -> str:
    pattern = re.compile(rf"({re.escape(start_tag)}\n).*?(\n{re.escape(end_tag)})", re.DOTALL)
    new_content, count = pattern.subn(rf"\g<1>{new_body}\g<2>", content)
    if count == 0:
        raise ValueError(f"Marker not found: {start_tag!r}")
    return new_content


def normalize_readme(content: str) -> str:
    content = re.sub(r"\n---\n\n---\n", "\n---\n", content)
    return content


def main() -> None:
    print("Fetching assigned issues...")
    assigned_issues_query = f"assignee:{USERNAME} type:issue"
    assigned_issue_total, assigned_issues = gh_search(assigned_issues_query)

    print("Fetching issues raised by me...")
    raised_issues_query = f"author:{USERNAME} type:issue"
    raised_issue_total, raised_issues = gh_search(raised_issues_query)

    print("Fetching authored pull requests...")`r`n    prs_query = f"author:{USERNAME} type:pr"
    pr_total, prs = gh_search(prs_query)

    issues_md = build_issues_section(
        assigned_total=assigned_issue_total,
        assigned_items=assigned_issues,
        assigned_url=f"https://github.com/issues/assigned?q={quote(assigned_issues_query)}",
        raised_total=raised_issue_total,
        raised_items=raised_issues,
        raised_url=f"https://github.com/search?q={quote(raised_issues_query)}&type=issues",
    )
    prs_md = build_prs_section(
        total_count=pr_total,
        items=prs,
        search_url=f"https://github.com/search?q={quote(prs_query)}&type=pullrequests",
    )
`r`n    print("Fetching GSSoC profile...")`r`n    gssoc_md = build_gssoc_section(github_get(GSSOC_API_URL))`r`n
    with open(README, "r", encoding="utf-8") as readme_file:
        content = readme_file.read()

    content = normalize_readme(content)
    content = replace_section(content, "<!-- ISSUES_START -->", "<!-- ISSUES_END -->", issues_md)
    content = replace_section(content, "<!-- PRS_START -->", "<!-- PRS_END -->", prs_md)
    content = replace_gssoc_section(content, gssoc_md)`r`n
    with open(README, "w", encoding="utf-8") as readme_file:
        readme_file.write(content)

    print("README.md updated successfully.")


if __name__ == "__main__":
    main()