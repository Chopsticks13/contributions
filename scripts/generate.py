#!/usr/bin/env python3
"""Fetch public PRs from GitHub and generate a static HTML page."""

import json
import os
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone

GITHUB_USER = "Chopsticks13"
TEMPLATE_PATH = "templates/index.html.tmpl"
OUTPUT_PATH = "index.html"


def fetch_prs():
    """Fetch all public PRs authored by the user via GitHub Search API."""
    prs = []
    page = 1
    token = os.environ.get("GITHUB_TOKEN", "")

    while True:
        query = f"author:{GITHUB_USER}+type:pr+is:public"
        url = f"https://api.github.com/search/issues?q={query}&per_page=100&page={page}&sort=created&order=desc"

        req = urllib.request.Request(url)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("User-Agent", GITHUB_USER)
        if token:
            req.add_header("Authorization", f"Bearer {token}")

        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())

        items = data.get("items", [])
        if not items:
            break

        prs.extend(items)
        page += 1

        if len(prs) >= data.get("total_count", 0):
            break

    return prs


def parse_pr(pr):
    """Extract relevant fields from a PR search result."""
    repo_url = pr["repository_url"]
    repo_name = "/".join(repo_url.split("/")[-2:])

    if pr.get("pull_request", {}).get("merged_at"):
        status = "merged"
    elif pr["state"] == "open":
        status = "open"
    else:
        status = "closed"

    created = pr["created_at"][:10]
    merged_at = (pr.get("pull_request", {}).get("merged_at") or "")[:10]

    return {
        "title": pr["title"],
        "number": pr["number"],
        "url": pr["html_url"],
        "repo": repo_name,
        "repo_url": f"https://github.com/{repo_name}",
        "status": status,
        "created": created,
        "date": merged_at if status == "merged" else created,
    }


def status_sort_key(pr):
    """Sort order: merged first, then open, then closed."""
    order = {"merged": 0, "open": 1, "closed": 2}
    return (order.get(pr["status"], 3), pr["date"])


def render_pr(pr):
    """Render a single PR as HTML."""
    return f"""        <div class="pr">
            <span class="badge {pr['status']}">{pr['status'].upper()}</span>
            <div class="pr-info">
                <div class="pr-title"><a href="{pr['url']}">#{pr['number']} {pr['title']}</a></div>
                <div class="pr-meta">{pr['date']}</div>
            </div>
        </div>"""


def render_page(prs):
    """Render the full HTML page from template."""
    parsed = [parse_pr(pr) for pr in prs]

    # Filter out closed (not merged) and personal repos
    exclude_repos = {"Chopsticks13/chopsticks13.github.io"}
    parsed = [
        p for p in parsed
        if p["status"] in ("merged", "open") and p["repo"] not in exclude_repos
    ]

    # Group by repo
    by_repo = defaultdict(list)
    for pr in parsed:
        by_repo[pr["repo"]].append(pr)

    # Sort PRs within each repo
    for repo in by_repo:
        by_repo[repo].sort(key=status_sort_key)

    # Sort repos: external repos first (by merged count), personal repos last
    personal_repos = {"Chopsticks13/gcp-foundation-modules"}
    sorted_repos = sorted(
        by_repo.keys(),
        key=lambda r: (
            r in personal_repos,
            -sum(1 for p in by_repo[r] if p["status"] == "merged"),
        ),
    )

    # Build content
    content_parts = []
    for repo in sorted_repos:
        repo_prs = by_repo[repo]
        repo_url = repo_prs[0]["repo_url"]
        pr_html = "\n".join(render_pr(pr) for pr in repo_prs)
        is_personal = repo in personal_repos

        # Add section divider before first personal repo
        if is_personal and not any(
            r in personal_repos for r in sorted_repos[:sorted_repos.index(repo)]
        ):
            content_parts.append(
                '    <div class="section-divider">Personal Projects</div>'
            )

        content_parts.append(
            f"""    <div class="repo-group">
        <h2><a href="{repo_url}">{repo}</a></h2>
{pr_html}
    </div>"""
        )

    content = "\n\n".join(content_parts)

    # Stats
    total = len(parsed)
    merged = sum(1 for p in parsed if p["status"] == "merged")
    open_count = sum(1 for p in parsed if p["status"] == "open")
    repos = len(sorted_repos)
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Render template
    with open(TEMPLATE_PATH) as f:
        template = f.read()

    html = (
        template.replace("{{total}}", str(total))
        .replace("{{merged}}", str(merged))
        .replace("{{open}}", str(open_count))
        .replace("{{repos}}", str(repos))
        .replace("{{content}}", content)
        .replace("{{updated}}", updated)
    )

    with open(OUTPUT_PATH, "w") as f:
        f.write(html)

    print(f"Generated {OUTPUT_PATH}: {total} PRs ({merged} merged, {open_count} open) across {repos} repos")


if __name__ == "__main__":
    prs = fetch_prs()
    render_page(prs)
