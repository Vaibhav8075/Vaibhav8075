"""Save the public contribution calendar (last ~12 months, one entry per day) to data/contributions.json.

Reads github.com/users/<user>/contributions, the same HTML fragment the profile page shows,
so it needs no token. Each day's count comes from its tooltip ("3 contributions on ...").
Input for scripts/skyline.py.

    python scripts/fetch_contributions.py
"""
import json
import pathlib
import re
import urllib.request

USER = "Vaibhav8075"
OUT = pathlib.Path(__file__).resolve().parent.parent / "data" / "contributions.json"


def main():
    req = urllib.request.Request(f"https://github.com/users/{USER}/contributions", headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as res:
        html = res.read().decode("utf-8")
    cells = re.findall(r'data-date="(\d{4}-\d\d-\d\d)"\s+id="(contribution-day-component-\d+-\d+)"\s+data-level="(\d)"', html)
    tips = dict(re.findall(r'<tool-tip[^>]*for="(contribution-day-component-\d+-\d+)"[^>]*>([^<]*)</tool-tip>', html))
    if not cells:
        raise SystemExit("No calendar cells found; GitHub's markup may have changed.")
    days = []
    for date, cell_id, level in cells:
        count = re.match(r"(\d+) contributions?", tips.get(cell_id, ""))
        days.append({"date": date, "count": int(count.group(1)) if count else 0, "level": int(level)})
    days.sort(key=lambda d: d["date"])
    OUT.write_text(json.dumps({"user": USER, "days": days}, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(days)} days, {sum(d['count'] for d in days)} contributions, {days[0]['date']} to {days[-1]['date']}")


if __name__ == "__main__":
    main()
