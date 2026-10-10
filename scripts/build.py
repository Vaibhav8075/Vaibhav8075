"""Render the profile README and its cards from data/profile.json and data/stats.json.

Every card is written twice, to assets/dark/ and assets/light/, and README.md
picks the one matching the viewer's GitHub theme with <picture>. This script
owns README.md and those two folders: SVGs it no longer produces are deleted.

    python scripts/build.py
"""
import json
import pathlib
import shutil
from html import escape

ROOT = pathlib.Path(__file__).resolve().parent.parent
USER = "Vaibhav8075"
RAW = f"https://raw.githubusercontent.com/{USER}/{USER}"
PAGES = f"https://{USER.lower()}.github.io/{USER}/"   # GitHub Pages site from docs/: the 3D view

SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, 'SF Mono', 'JetBrains Mono', Menlo, Consolas, monospace"

# GitHub's own dark and light palettes; the accent is Primer's link blue, used sparingly.
# Everything is a solid colour: no gradients, glows or blurs.
THEMES = {
    "dark": {
        "text": "#f0f6fc", "muted": "#8b949e", "border": "#30363d", "surface": "#161b22",
        "accent": "#4493f8", "accent_fill": "#1f6feb", "on_accent": "#ffffff", "live": "#3fb950",
    },
    "light": {
        "text": "#1f2328", "muted": "#59636e", "border": "#d1d9e0", "surface": "#f6f8fa",
        "accent": "#0969da", "accent_fill": "#0969da", "on_accent": "#ffffff", "live": "#1a7f37",
    },
}

# GitHub's linguist colours for programming languages, as on its own repository cards.
# Frameworks and tools get the neutral fallback.
TECH_COLORS = {
    "python": "#3572a5", "typescript": "#3178c6", "javascript": "#f1e05a", "c++": "#f34b7d",
    "c": "#555555", "java": "#b07219", "go": "#00add8", "rust": "#dea584",
    "tex": "#3d6117", "latex": "#3d6117", "cmake": "#da3434",
}

# 32x32 line icons, drawn in a box whose top-left corner is (24, 24).
ICONS = {
    "trend": "M30 44 L36 37 L41 41 L50 32",
    "wave": "M29 40 C 33 30, 36 30, 40 40 S 47 50, 51 40",
    "code": "M35 33 L29 40 L35 47 M45 33 L51 40 L45 47 M42 31 L38 49",
    "audio": "M31 37 V43 M35.5 33 V47 M40 30 V50 M44.5 34 V46 M49 37 V43",
    "photo": "M30 31 H50 V49 H30 Z M30 46 L37 39 L42 44 L45 41 L50 46",
    "signal": "M30 38 A 12 12 0 0 1 50 38 M34 42 A 7 7 0 0 1 46 42",
    "road": "M30 49 L37 31 M50 49 L43 31 M40 49 V45 M40 41 V38 M40 35 V33",
}

# Edges shared by all cards so they line up when stacked in the README.
EDGE = 14   # x of a full-width panel's border
PAD = 38    # x of full-width content; equals a project card's inner edge at 49% width


def color(tech):
    return TECH_COLORS.get(tech.lower(), "#8b949e")


def text_width(s, size):
    """Rough rendered width of proportional sans text, erring wide."""
    em = 0
    for ch in s:
        if ch in "fijlrtI.,:;'!|()[] ":
            em += 0.3
        elif ch in "mwMW@%":
            em += 0.84
        elif ch.isupper():
            em += 0.68
        elif ch.isdigit():
            em += 0.57
        else:
            em += 0.54
    return em * size


def mono_width(s, size, spacing=0.0):
    return len(s) * (0.6 * size + spacing)


def wrap(text, size, width, max_lines, what):
    lines = [""]
    for word in text.split():
        candidate = f"{lines[-1]} {word}".strip()
        if lines[-1] and text_width(candidate, size) > width:
            lines.append(word)
        else:
            lines[-1] = candidate
    if len(lines) > max_lines:
        raise SystemExit(f"{what} needs {len(lines)} lines, at most {max_lines} fit; shorten it.")
    return lines


def svg(width, height, css, body):
    def lines(block, indent):
        return "\n".join(indent + line.strip() for line in block.splitlines() if line.strip())

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">\n'
        f"  <style>\n"
        f"    .sans {{ font-family: {SANS}; }}\n"
        f"    .mono {{ font-family: {MONO}; }}\n"
        f"{lines(css, '    ')}\n"
        f"  </style>\n"
        f"{lines(body, '  ')}\n"
        f"</svg>\n"
    )


def section_heading(number, text, y, t):
    """'01  SELECTED WORK ────' in mono, with the number in the accent colour."""
    num, label = f"{number:02d}", text.upper()
    lx = PAD + mono_width(num, 11, 3) + 8
    rx = lx + mono_width(label, 11, 3) + 8
    css = f"""
        .heading {{ font-size: 11px; fill: {t["muted"]}; letter-spacing: 3px; }}
        .heading-num {{ fill: {t["accent"]}; font-weight: 700; }}
    """
    body = (
        f'<text x="{PAD}" y="{y}" class="mono heading heading-num">{num}</text>\n'
        f'<text x="{lx:.1f}" y="{y}" class="mono heading">{escape(label)}</text>\n'
        f'<rect x="{rx:.1f}" y="{y - 4}" width="{800 - PAD - rx:.1f}" height="1" fill="{t["border"]}"/>'
    )
    return css, body


def hero(profile, t):
    h = profile["header"]
    tagline = wrap(h["tagline"], 16, 620, 2, "header.tagline")

    # Bottom row: the current role (the experience entry ending "Present") and the stack.
    base = 262
    current = next((r for r in profile["experience"] if r["end"].lower() == "present"), None)
    now_label = "CURRENTLY"
    now_x = PAD + mono_width(now_label, 11, 2) + 12
    now_text = f'{current["role"]} at {current["org"]}' if current else ""
    stack = " · ".join(s.upper() for s in h["stack"])
    if now_x + text_width(now_text, 14) + 24 > 800 - PAD - mono_width(stack, 11, 0.5):
        raise SystemExit("The current role and header.stack are too long to share the hero's bottom row; shorten one.")

    css = f"""
        .panel {{ fill: {t["surface"]}; stroke: {t["border"]}; }}
        .meta {{ font-size: 11px; fill: {t["muted"]}; letter-spacing: 2px; }}
        .name {{ font-size: 76px; font-weight: 800; fill: {t["text"]}; letter-spacing: -2.5px; }}
        .tagline {{ font-size: 16px; fill: {t["muted"]}; }}
        .now-label {{ font-size: 11px; fill: {t["accent"]}; letter-spacing: 2px; font-weight: 700; }}
        .now {{ font-size: 14px; fill: {t["text"]}; font-weight: 600; }}
        .stack {{ font-size: 11px; fill: {t["muted"]}; letter-spacing: 0.5px; }}
    """
    lines = "\n".join(
        f'<text x="{PAD}" y="{180 + 22 * i}" class="sans tagline">{escape(line)}</text>' for i, line in enumerate(tagline)
    )
    now = (
        f'<text x="{PAD}" y="{base}" class="mono now-label">{now_label}</text>\n'
        f'<text x="{now_x:.1f}" y="{base}" class="sans now">{escape(now_text)}</text>'
        if current else ""
    )
    body = f"""
        <rect x="{EDGE + 0.5}" y="0.5" width="{800 - 2 * EDGE - 1}" height="295" rx="12" class="panel"/>
        <text x="{PAD}" y="42" class="mono meta">{escape(h["role"].upper())}</text>
        <text x="{800 - PAD}" y="42" text-anchor="end" class="mono meta">{escape(h["location"].upper())}</text>
        <rect x="{PAD}" y="58" width="{800 - 2 * PAD}" height="1" fill="{t["border"]}"/>
        <text x="{PAD - 4}" y="140" class="sans name">{escape(h["name"])}</text>
        {lines}
        <rect x="{PAD}" y="230" width="{800 - 2 * PAD}" height="1" fill="{t["border"]}"/>
        {now}
        <text x="{800 - PAD}" y="{base}" text-anchor="end" class="mono stack">{escape(stack)}</text>
    """
    return svg(800, 296, css, body)


def section_label(number, text, t):
    css, body = section_heading(number, text, 24, t)
    return svg(800, 36, css, body)


def project(index, total, p, t):
    description = wrap(p["description"], 13, 316, 3, f'project "{p["name"]}" description')
    tags, x = [], 24
    for tag in p["tags"]:
        tags.append(
            f'<circle cx="{x + 4}" cy="152" r="4" fill="{color(tag)}"/>'
            f'<text x="{x + 14}" y="156" class="mono tag">{escape(tag)}</text>'
        )
        x += round(14 + mono_width(tag, 11) + 18)
    lines = "\n".join(
        f'<text x="24" y="{92 + 20 * i}" class="sans desc">{escape(line)}</text>' for i, line in enumerate(description)
    )
    css = f"""
        .card {{ fill: none; stroke: {t["border"]}; }}
        .icon-box {{ fill: {t["surface"]}; stroke: {t["border"]}; }}
        .icon {{ fill: none; stroke: {t["text"]}; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }}
        .title {{ font-size: 17px; font-weight: 600; fill: {t["text"]}; }}
        .kind {{ font-size: 10px; fill: {t["muted"]}; letter-spacing: 1.5px; font-weight: 600; }}
        .index {{ font-size: 10px; fill: {t["muted"]}; letter-spacing: 1px; }}
        .desc {{ font-size: 13px; fill: {t["muted"]}; }}
        .tag {{ font-size: 11px; fill: {t["muted"]}; }}
        .arrow {{ fill: none; stroke: {t["muted"]}; stroke-width: 1.5; stroke-linecap: round; stroke-linejoin: round; }}
    """
    body = f"""
        <g transform="translate(8, 8)">
          <rect x="0.5" y="0.5" width="383" height="179" rx="10" class="card"/>
          <rect x="24" y="24" width="32" height="32" rx="6" class="icon-box"/>
          <path d="{ICONS[p["icon"]]}" class="icon"/>
          <text x="72" y="39" class="sans title">{escape(p["name"])}</text>
          <text x="72" y="56" class="mono kind">{escape(p["kind"].upper())}</text>
          <text x="360" y="36" text-anchor="end" class="mono index">{index:02d}/{total:02d}</text>
          {lines}
          {"".join(tags)}
          <path d="M350 158 L360 148 M352.5 148 H360 V155.5" class="arrow"/>
        </g>
    """
    return svg(400, 196, css, body)


def experience(profile, t, number):
    roles = profile["experience"]
    top, step = 72, 52
    bottom = top + (len(roles) - 1) * step
    rows = []
    for i, r in enumerate(roles):
        y = top + i * step
        current = r["end"].lower() == "present"
        dot = (f'<circle cx="48" cy="{y}" r="6" fill="{t["accent"]}"/>' if current
               else f'<circle cx="48" cy="{y}" r="5" class="dot"/>')
        rows.append(
            f'{dot}\n'
            f'<text x="74" y="{y + 5}" class="sans role">{escape(r["role"])}<tspan class="org"> at {escape(r["org"])}</tspan></text>\n'
            f'<text x="{800 - PAD}" y="{y + 4}" text-anchor="end" class="mono date{" now" if current else ""}">'
            f'{escape(r["start"])} – {escape(r["end"])}</text>'
        )
    heading_css, heading = section_heading(number, "Experience", 28, t)
    css = heading_css + f"""
        .role {{ font-size: 15px; font-weight: 600; fill: {t["text"]}; }}
        .org {{ font-weight: 400; fill: {t["muted"]}; }}
        .date {{ font-size: 11px; fill: {t["muted"]}; }}
        .now {{ fill: {t["accent"]}; font-weight: 700; }}
        .dot {{ fill: {t["surface"]}; stroke: {t["muted"]}; stroke-width: 2; }}
    """
    body = f"""
        {heading}
        <rect x="47" y="{top}" width="2" height="{bottom - top}" fill="{t["border"]}"/>
        {chr(10).join(rows)}
    """
    return svg(800, bottom + 28, css, body)


def telemetry(stats, t):
    def num(key):
        value = stats.get(key)
        return "—" if value is None else f"{value:,}"

    langs = stats.get("languages", [])
    segments, legend, x = [], [], 0.0
    for i, (name, pct) in enumerate(langs):
        w = 218 * pct / 100
        segments.append(f'<rect x="{x:.1f}" width="{max(w - 2, 1):.1f}" height="6" fill="{color(name)}"/>')
        y = 26 + 18 * i
        legend.append(
            f'<circle cx="4" cy="{y - 3.5}" r="3.5" fill="{color(name)}"/>'
            f'<text x="14" y="{y}" class="mono lang">{escape(name.upper())}</text>'
            f'<text x="218" y="{y}" text-anchor="end" class="mono lang">{pct:.0f}%</text>'
        )
        x += w
    if langs:
        segments.append(f'<rect x="{x:.1f}" width="{max(218 - x, 0):.1f}" height="6" fill="{t["border"]}"/>')

    stat_rows = "\n".join(
        f'<text x="56" y="{40 * i}" text-anchor="end" class="sans stat">{num(key)}</text>'
        f'<text x="70" y="{40 * i - 2}" class="mono sub">{label}</text>'
        for i, (key, label) in enumerate([("stars", "STARS"), ("repositories", "REPOSITORIES"), ("followers", "FOLLOWERS")])
    )
    synced = stats.get("synced", "—")
    css = f"""
        .panel {{ fill: {t["surface"]}; stroke: {t["border"]}; }}
        .label {{ font-size: 11px; fill: {t["muted"]}; letter-spacing: 3px; }}
        .big {{ font-size: 60px; font-weight: 800; fill: {t["text"]}; letter-spacing: -2px; }}
        .sub {{ font-size: 9px; fill: {t["muted"]}; letter-spacing: 2px; }}
        .stat {{ font-size: 22px; font-weight: 700; fill: {t["text"]}; }}
        .lang {{ font-size: 9px; fill: {t["muted"]}; letter-spacing: 1px; }}
        .divider {{ stroke: {t["border"]}; }}
    """
    w = 800 - 2 * EDGE
    body = f"""
        <defs><clipPath id="bar"><rect width="218" height="6" rx="3"/></clipPath></defs>
        <g transform="translate({EDGE}, 10)">
          <rect x="0.5" y="0.5" width="{w - 1}" height="189" rx="12" class="panel"/>
          <rect x="24" y="30" width="8" height="8" fill="{t["accent"]}"/>
          <text x="40" y="38" class="mono label">GITHUB ACTIVITY</text>
          <text x="21" y="116" class="sans big">{num("contributions")}</text>
          <text x="24" y="142" class="mono sub">CONTRIBUTIONS · PAST YEAR</text>
          <line x1="270" y1="30" x2="270" y2="160" class="divider"/>
          <g transform="translate(300, 66)">
            {stat_rows}
          </g>
          <line x1="500" y1="30" x2="500" y2="160" class="divider"/>
          <g transform="translate(530, 38)">
            <text class="mono label">LANGUAGES</text>
            <g transform="translate(0, 14)" clip-path="url(#bar)">{"".join(segments)}</g>
            <g transform="translate(0, 14)">{"".join(legend)}</g>
          </g>
          <circle cx="{w - 24 - mono_width("SYNCED " + synced, 9, 2) - 8:.1f}" cy="168.5" r="2.5" fill="{t["live"]}"/>
          <text x="{w - 24}" y="172" text-anchor="end" class="mono sub">SYNCED {escape(synced)}</text>
        </g>
    """
    return svg(800, 210, css, body)


def button(link, t):
    label, action = link["label"].upper(), link["action"].upper()
    lw, aw = mono_width(label, 10, 1), mono_width(action, 10, 1) + 24
    width = round(16 + lw + 12 + aw + 6)
    ax = width - 6 - aw
    css = f"""
        .outline {{ fill: none; stroke: {t["border"]}; }}
        .label {{ font-size: 10px; fill: {t["muted"]}; letter-spacing: 1px; font-weight: 500; }}
        .action {{ font-size: 10px; fill: {t["on_accent"]}; letter-spacing: 1px; font-weight: 700; }}
    """
    body = f"""
        <rect x="0.5" y="0.5" width="{width - 1}" height="39" rx="8" class="outline"/>
        <text x="16" y="24" class="mono label">{escape(label)}</text>
        <rect x="{ax:.1f}" y="5" width="{aw:.1f}" height="30" rx="6" fill="{t["accent_fill"]}"/>
        <text x="{ax + aw / 2 + 0.5:.1f}" y="24" text-anchor="middle" class="mono action">{escape(action)}</text>
    """
    return svg(width, 40, css, body)


def themed(name, alt, size):
    """<picture> that follows the viewer's GitHub theme."""
    dark, light = f"{RAW}/main/assets/dark/{name}", f"{RAW}/main/assets/light/{name}"
    return (
        f'<picture><source media="(prefers-color-scheme: dark)" srcset="{dark}">'
        f'<source media="(prefers-color-scheme: light)" srcset="{light}">'
        f'<img src="{light}" {size} alt="{escape(alt)}"></picture>'
    )


def readme(profile):
    # Each <a> is kept on one line: whitespace inside it renders as an underlined gap.
    # Project cards go two per line, so the grid holds whether GitHub renders a
    # newline as a space or as <br>.
    h = profile["header"]
    header_alt = f'{h["name"]}, {h["role"].replace(" · ", ", ")}, {h["location"]}. {h["tagline"]} Stack: {", ".join(h["stack"])}.'
    projects = []
    for p in profile["projects"]:
        card = themed("project-%s.svg" % p["slug"], "%s (%s): %s" % (p["name"], p["kind"], p["description"]), 'width="49%"')
        projects.append(f'<a href="{p["url"]}">{card}</a>')
    buttons = []
    for link in profile["links"]:
        button = themed("button-%s.svg" % link["slug"], link["label"], 'height="40"')
        buttons.append(f'<a href="{link["url"]}">{button}</a>')
    roles = "; ".join("%s at %s, %s – %s" % (r["role"], r["org"], r["start"], r["end"]) for r in profile["experience"])
    # The 3D renders come from Blender (scripts/skyline.py, scripts/repo_city.py), not from here.
    # Each is shown once both of its theme versions exist, animated when scripts/animate.py has
    # made one, and links to its interactive version on the 3D page in docs/.
    skyline = city = ""
    sky_file, city_file = render_file("skyline"), render_file("repo-city")
    if sky_file:
        skyline_alt = (f"3D skyline of {h['name']}'s GitHub contributions over the past year: one bar per "
                       "day, taller for more contributions. Opens the interactive 3D view.")
        sky_img = themed(sky_file, skyline_alt, 'width="100%"')
        skyline = f'<a href="{PAGES}#skyline">{sky_img}</a>' + "\n\n"
    if city_file:
        city_alt = (f"Repo City: each of {h['name']}'s public repositories as a building with its name and "
                    "commit count; taller buildings and greener roofs mean more commits. "
                    "Opens the interactive 3D view.")
        city_img = themed(city_file, city_alt, 'width="100%"')
        city = (themed("label-city.svg", "Repo city", 'width="100%"') + "\n"
                + f'<a href="{PAGES}#city">{city_img}</a>' + "\n\n")
    return f"""\
<!-- Generated by scripts/build.py from data/profile.json. Edit that file instead: changes made here are overwritten. -->
<div align="center">

{skyline}{themed("hero.svg", header_alt, 'width="100%"')}

{themed("telemetry.svg", "GitHub activity: contributions in the past year, stars, repositories, followers and language mix.", 'width="100%"')}

{themed("label-work.svg", "Selected work", 'width="100%"')}
{chr(10).join(" ".join(projects[i:i + 2]) for i in range(0, len(projects), 2))}

{city}{themed("experience.svg", "Experience: %s." % roles, 'width="100%"')}

{"&nbsp;&nbsp;".join(buttons)}

<code>{escape(h["motto"])}</code>

</div>
"""


def render_file(stem):
    """File name of a Blender render present for every theme, preferring the animation."""
    for name in (f"{stem}.webp", f"{stem}.png"):
        if all((ROOT / "assets" / theme / name).exists() for theme in THEMES):
            return name
    return None


def render(profile, stats):
    """Map of file name to SVG source, per theme."""
    out = {}
    projects = profile["projects"]
    city = render_file("repo-city") is not None
    for theme, t in THEMES.items():
        files = {
            "hero.svg": hero(profile, t),
            "telemetry.svg": telemetry(stats, t),
            "label-work.svg": section_label(1, "Selected work", t),
            "experience.svg": experience(profile, t, 3 if city else 2),
        }
        if city:
            files["label-city.svg"] = section_label(2, "Repo city", t)
        for i, p in enumerate(projects, 1):
            files[f'project-{p["slug"]}.svg'] = project(i, len(projects), p, t)
        for link in profile["links"]:
            files[f'button-{link["slug"]}.svg'] = button(link, t)
        out[theme] = files
    return out


def main():
    profile = json.loads((ROOT / "data" / "profile.json").read_text(encoding="utf-8"))
    stats_path = ROOT / "data" / "stats.json"
    stats = json.loads(stats_path.read_text(encoding="utf-8")) if stats_path.exists() else {}
    themes = render(profile, stats)
    for theme, files in themes.items():
        folder = ROOT / "assets" / theme
        folder.mkdir(parents=True, exist_ok=True)
        for stale in {p.name for p in folder.glob("*.svg")} - set(files):
            (folder / stale).unlink()
        for name, source in files.items():
            (folder / name).write_text(source, encoding="utf-8", newline="\n")
    (ROOT / "README.md").write_text(readme(profile), encoding="utf-8", newline="\n")
    # GitHub Pages serves only docs/, so the 3D page gets its own copy of the data it reads.
    (ROOT / "docs" / "data").mkdir(parents=True, exist_ok=True)
    for name in ("contributions.json", "repos.json"):
        if (ROOT / "data" / name).exists():
            shutil.copyfile(ROOT / "data" / name, ROOT / "docs" / "data" / name)
    print(f"Rendered README.md and {sum(map(len, themes.values()))} cards into assets/dark and assets/light")


if __name__ == "__main__":
    main()
