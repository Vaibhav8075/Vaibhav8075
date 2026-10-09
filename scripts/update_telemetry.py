"""Fetch live GitHub stats for the telemetry card into data/stats.json.

The contribution count is only exposed by the GraphQL API, which needs a token
(GITHUB_TOKEN, set from the PAT secret in CI). Without one, or if the query
fails, the previous count is kept rather than replaced with a guess.

    python scripts/update_telemetry.py && python scripts/build.py
"""
import json
import os
import pathlib
import urllib.request
from datetime import datetime, timezone

USER = "Vaibhav8075"
STATS = pathlib.Path(__file__).resolve().parent.parent / "data" / "stats.json"

# Markup, docs and build files, left out of the language mix.
IGNORED_LANGUAGES = {
    "HTML", "CSS", "SCSS", "TeX", "Markdown", "Shell", "PowerShell", "Batchfile",
    "Dockerfile", "Makefile", "CMake", "Procfile",
}
TOP_LANGUAGES = 4


def request(url, token, body=None):
    headers = {"User-Agent": f"{USER}-profile", "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers), timeout=30) as res:
        return json.load(res)


def owned_repos(token):
    page = 1
    while batch := request(f"https://api.github.com/users/{USER}/repos?type=owner&per_page=100&page={page}", token):
        yield from batch
        page += 1


def contributions(token):
    query = "query($login: String!) { user(login: $login) { contributionsCollection { contributionCalendar { totalContributions } } } }"
    res = request("https://api.github.com/graphql", token, {"query": query, "variables": {"login": USER}})
    return res["data"]["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]


def language_mix(repos, token):
    """Top languages by bytes across original repos, as percentages of all counted code."""
    totals = {}
    for repo in repos:
        if repo["fork"] or repo["name"] == USER:
            continue
        for lang, size in request(repo["languages_url"], token).items():
            if lang not in IGNORED_LANGUAGES:
                totals[lang] = totals.get(lang, 0) + size
    total = sum(totals.values()) or 1
    top = sorted(totals.items(), key=lambda kv: -kv[1])[:TOP_LANGUAGES]
    return [[lang, round(size / total * 100, 1)] for lang, size in top]


def main():
    token = os.environ.get("GITHUB_TOKEN")
    previous = json.loads(STATS.read_text(encoding="utf-8")) if STATS.exists() else {}

    user = request(f"https://api.github.com/users/{USER}", token)
    repos = list(owned_repos(token))

    count = previous.get("contributions")
    if token:
        try:
            count = contributions(token)
        except Exception as e:  # keep the last known count
            print(f"Contribution query failed, keeping {count}: {e}")
    else:
        print(f"No GITHUB_TOKEN; keeping contribution count {count}")

    stats = {
        "contributions": count,
        "stars": sum(r["stargazers_count"] for r in repos),
        "repositories": user["public_repos"],
        "followers": user["followers"],
        "languages": language_mix(repos, token),
        "synced": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    STATS.parent.mkdir(exist_ok=True)
    STATS.write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(stats))


if __name__ == "__main__":
    main()
