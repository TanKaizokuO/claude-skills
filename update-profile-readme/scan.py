#!/usr/bin/env python3
"""Collect facts for suggesting updates to the GitHub profile repo.

Read-only. Uses the `gh` CLI (must be authenticated). Prints one JSON object:

    python3 scan.py <profile-repo-dir> [--days 60]

Sections:
  featured      repos linked under "# Featured Projects" in README.md, each with
                exists / archived / renamed / pushed_at / days_since_push
  candidates    own non-fork public repos pushed in the last --days days that
                are NOT featured, newest first, with description + languages
  stack         language bytes summed over recently-pushed repos vs. the
                languages listed in profile.json
  workflow      last 5 runs of the profile card workflow
  profile_rows  every label/value row in profile.json (for the agent to eyeball)
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def gh(*args: str) -> object:
    out = subprocess.run(["gh", *args], capture_output=True, text=True)
    if out.returncode != 0:
        return {"error": out.stderr.strip()}
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        return out.stdout


def days_since(iso: str | None) -> int | None:
    if not iso:
        return None
    t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - t).days


def main() -> None:
    args = sys.argv[1:]
    if not args:
        sys.exit("usage: scan.py <profile-repo-dir> [--days N]")
    root = Path(args[0]).expanduser()
    days = int(args[args.index("--days") + 1]) if "--days" in args else 60

    owner = gh("api", "user", "--jq", ".login")
    owner = owner.strip() if isinstance(owner, str) else "TanKaizokuO"

    readme = (root / "README.md").read_text()
    featured_part = readme.split("# Featured Projects", 1)[-1]
    links = re.findall(r"\[([^\]]+)\]\(https://github\.com/([^/\s)]+)/([^/\s)#]+)\)", featured_part)

    featured = []
    featured_names = set()
    for title, o, name in links:
        info = gh("api", f"repos/{o}/{name}")
        entry = {"title": title, "link": f"{o}/{name}"}
        if isinstance(info, dict) and "error" not in info:
            entry.update(
                exists=True,
                archived=info.get("archived"),
                private=info.get("private"),
                renamed_to=info["full_name"] if info["full_name"].lower() != f"{o}/{name}".lower() else None,
                pushed_at=info.get("pushed_at"),
                days_since_push=days_since(info.get("pushed_at")),
                description=info.get("description"),
                stars=info.get("stargazers_count"),
            )
            featured_names.add(info["full_name"].lower())
        else:
            entry["exists"] = False
        featured_names.add(f"{o}/{name}".lower())
        featured.append(entry)

    repos = gh(
        "repo", "list", owner, "--limit", "200", "--source", "--visibility", "public",
        "--json", "nameWithOwner,description,pushedAt,isArchived,stargazerCount,primaryLanguage,languages,repositoryTopics,homepageUrl",
    )
    repos = repos if isinstance(repos, list) else []

    recent = [
        r for r in repos
        if not r["isArchived"]
        and (days_since(r["pushedAt"]) or 10**6) <= days
        and r["nameWithOwner"].lower() != f"{owner}/{owner}".lower()
    ]
    candidates = [
        {
            "repo": r["nameWithOwner"],
            "description": r["description"],
            "pushed_at": r["pushedAt"],
            "days_since_push": days_since(r["pushedAt"]),
            "stars": r["stargazerCount"],
            "languages": [l["node"]["name"] for l in r.get("languages", [])][:5]
            if r.get("languages") and "node" in r["languages"][0]
            else [l.get("name") for l in r.get("languages", [])][:5],
            "topics": [t.get("name") for t in (r.get("repositoryTopics") or [])],
        }
        for r in sorted(recent, key=lambda r: r["pushedAt"], reverse=True)
        if r["nameWithOwner"].lower() not in featured_names
    ]

    # markup / build glue that never belongs on a "Languages" line
    not_langs = {"HTML", "CSS", "SCSS", "Jinja", "Dockerfile", "CMake", "Makefile",
                 "Jupyter Notebook", "Procfile", "Batchfile", "PowerShell", "Nix", "TeX"}
    lang_bytes: Counter[str] = Counter()
    for r in recent:
        for l in r.get("languages") or []:
            name = l.get("node", {}).get("name") or l.get("name")
            size = l.get("size", 0)
            if name and name not in not_langs:
                lang_bytes[name] += size or 1

    profile = json.loads((root / "profile.json").read_text())
    rows = [row for s in profile.get("sections", []) for row in s.get("rows", [])]
    listed_langs = next((v for k, v in rows if k == "Languages"), "")
    listed = [x.strip() for x in listed_langs.split(",") if x.strip()]

    total = sum(lang_bytes.values()) or 1
    stack = {
        "listed_in_profile": listed,
        "recent_repo_languages": [
            {"language": k, "share_pct": round(100 * v / total, 1)} for k, v in lang_bytes.most_common(12)
        ],
        "listed_but_unused_recently": [x for x in listed if x not in lang_bytes],
        "used_but_not_listed": [k for k, v in lang_bytes.most_common() if k not in listed and 100 * v / total >= 3],
    }

    workflow = gh(
        "run", "list", "-R", f"{owner}/{owner}", "-L", "5",
        "--json", "displayTitle,event,status,conclusion,createdAt,url",
    )

    print(json.dumps(
        {
            "owner": owner,
            "window_days": days,
            "featured": featured,
            "candidates": candidates,
            "stack": stack,
            "workflow": workflow,
            "profile_rows": rows,
        },
        indent=2,
    ))


if __name__ == "__main__":
    main()
