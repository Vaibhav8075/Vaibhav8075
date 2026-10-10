"""Save every original public repository with its size, language, stars and commit count to data/repos.json.

Input for scripts/repo_city.py. Forks and the profile repository itself are left out. The commit
count is read from the pagination of a one-commit-per-page listing, so each repository costs one
API call; set GITHUB_TOKEN to avoid the 60-calls-per-hour anonymous limit.

    python scripts/fetch_repos.py
"""
import json
import os
import pathlib
import re
import urllib.request

USER = "Vaibhav8075"
OUT = pathlib.Path(__file__).resolve().parent.parent / "data" / "repos.json"
# Short labels for long repository names (Repo City tags and the 3D page).
SHORT = {
    "-Physics-Augmented-1D-CNN": "1D-CNN",
    "Audict-audio-Technology": "Audict",
    "OpenRescue-AI-Driven-Disaster-Response-Resource-Optimization-System": "OpenRescue",
    "Semantic-Segmentation-for-Autonomous-Driving-": "Segmentation",
    "Vaibhav-Goel-Portfolio": "Portfolio",
    "Shortest-path-visualizer": "Path-visualizer",
    "Financial-Technology": "Fintech",
}


def get(url):
    headers = {"User-Agent": f"{USER}-profile", "Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as res:
        return json.load(res), res.headers.get("Link", "")


def commit_count(repo):
    commits, link = get(f"https://api.github.com/repos/{USER}/{repo}/commits?per_page=1")
    last = re.search(r'[?&]page=(\d+)>; rel="last"', link)
    return int(last.group(1)) if last else len(commits)


def main():
    repos, _ = get(f"https://api.github.com/users/{USER}/repos?type=owner&per_page=100")
    out = []
    for r in sorted(repos, key=lambda r: r["name"].lower()):
        if r["fork"] or r["name"] == USER:
            continue
        out.append({"name": r["name"], "label": SHORT.get(r["name"], r["name"].strip("-")),
                    "language": r["language"], "size_kb": r["size"],
                    "stars": r["stargazers_count"], "commits": commit_count(r["name"]),
                    "created": r["created_at"][:10], "pushed": r["pushed_at"][:10]})
        print(f"{r['name']:<45} {str(r['language']):<11} {r['size']:>7} KB {out[-1]['commits']:>4} commits")
    OUT.write_text(json.dumps({"user": USER, "repos": out}, indent=1) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
