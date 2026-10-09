"""Render the profile README and its cards from data/profile.json and data/stats.json.

Every card is written twice, to assets/dark/ and assets/light/, and README.md
picks the one matching the viewer's GitHub theme with <picture>. This script
owns README.md and those two folders: SVGs it no longer produces are deleted.

    python scripts/build.py
"""
import json
import pathlib
from html import escape

ROOT = pathlib.Path(__file__).resolve().parent.parent
USER = "Vaibhav8075"
RAW = f"https://raw.githubusercontent.com/{USER}/{USER}"

SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, 'SF Mono', 'JetBrains Mono', Menlo, Consolas, monospace"

# GitHub's own dark and light palettes, so the cards blend into either theme.
THEMES = {
    "dark": {
        "text": "#c9d1d9", "muted": "#8b949e", "border": "#30363d", "surface": "#21262d",
        "panel": ("#161b22", "#0d1117"),
        "chrome": ("#ffffff", "#d4d4d8", "#71717a"),
        "glow": ("#3f3f46", 0.3),
        "wave": ("#52525b", "#3f3f46", "#e4e4e7"),
        "tile": ("#09090b", "#27272a", "#c9d1d9", "#71717a"),
        "live": "#3fb950",
    },
    "light": {
        "text": "#1f2328", "muted": "#59636e", "border": "#d1d9e0", "surface": "#f6f8fa",
        "panel": ("#f6f8fa", "#ffffff"),
        "chrome": ("#1f2328", "#3d444d", "#818b98"),
        "glow": ("#d1d9e0", 0.4),
        "wave": ("#afb8c1", "#d1d9e0", "#59636e"),
        "tile": ("#ffffff", "#d1d9e0", "#1f2328", "#818b98"),
        "live": "#1a7f37",
    },
}

# Linguist colours for languages, brand colours for frameworks.
TECH_COLORS = {
    "python": "#3572a5", "typescript": "#3178c6", "javascript": "#f1e05a", "c++": "#f34b7d",
    "c": "#555555", "java": "#b07219", "go": "#00add8", "rust": "#dea584", "jupyter notebook": "#da5b0b",
    "tex": "#3d6117", "latex": "#3d6117", "html": "#e34c26", "css": "#663399", "cmake": "#da3434",
    "react": "#61dafb", "fastapi": "#009688", "pytorch": "#ee4c2c", "tensorflow": "#ff6f00",
    "onnx": "#4d8fd1", "postgresql": "#336791", "redis": "#dc382d", "scikit-learn": "#f7931e",
    "vite": "#646cff", "docker": "#2496ed",
}

# 32x32 line icons, drawn in a box whose top-left corner is (24, 24).
ICONS = {
    "trend": "M30 44 L36 37 L41 41 L50 32",
    "wave": "M29 40 C 33 30, 36 30, 40 40 S 47 50, 51 40",
    "code": "M35 33 L29 40 L35 47 M45 33 L51 40 L45 47 M42 31 L38 49",
    "audio": "M31 37 V43 M35.5 33 V47 M40 30 V50 M44.5 34 V46 M49 37 V43",
    "photo": "M30 31 H50 V49 H30 Z M30 46 L37 39 L42 44 L45 41 L50 46",
    "signal": "M30 38 A 12 12 0 0 1 50 38 M34 42 A 7 7 0 0 1 46 42",
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


def header(profile, t):
    h = profile["header"]
    tagline = wrap(h["tagline"], 14, 430, 2, "header.tagline")
    chips, x = [], 0
    for tech in h["stack"]:
        label = tech.upper()
        w = round(32 + mono_width(label, 10, 0.5))
        chips.append(
            f'<rect x="{x}" width="{w}" height="24" rx="4" class="chip"/>'
            f'<circle cx="{x + 12}" cy="12" r="3" fill="{color(tech)}"/>'
            f'<text x="{x + 22}" y="15.5" class="mono chip-text">{escape(label)}</text>'
        )
        x += w + 10
    glow, glow_opacity = t["glow"]
    tile_bg, tile_border, tile_stroke, tile_inner = t["tile"]
    wave_a, wave_b, node = t["wave"]
    css = f"""
        .name {{ font-size: 42px; font-weight: 700; fill: url(#chrome); letter-spacing: -1px; }}
        .role {{ font-size: 13px; fill: {t["muted"]}; letter-spacing: 2px; }}
        .tagline {{ font-size: 14px; fill: {t["muted"]}; }}
        .chip {{ fill: {t["surface"]}; stroke: {t["border"]}; }}
        .chip-text {{ font-size: 10px; fill: {t["muted"]}; letter-spacing: 0.5px; }}
    """
    lines = "\n".join(
        f'<text x="117" y="{130 + 22 * i}" class="sans tagline">{escape(line)}</text>' for i, line in enumerate(tagline)
    )
    body = f"""
        <defs>
          <radialGradient id="glow" cx="50%" cy="0%" r="80%" fx="50%" fy="0%">
            <stop offset="0%" stop-color="{glow}" stop-opacity="{glow_opacity}"/>
            <stop offset="100%" stop-color="{glow}" stop-opacity="0"/>
          </radialGradient>
          <linearGradient id="chrome" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="{t["chrome"][0]}"/>
            <stop offset="40%" stop-color="{t["chrome"][1]}"/>
            <stop offset="100%" stop-color="{t["chrome"][2]}"/>
          </linearGradient>
        </defs>
        <rect width="800" height="228" rx="12" fill="url(#glow)"/>
        <g transform="translate({PAD}, 40)">
          <rect width="56" height="56" rx="12" fill="{tile_bg}" stroke="{tile_border}"/>
          <path d="M18 16 L28 40 L38 16" fill="none" stroke="{tile_stroke}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          <path d="M23 16 L28 28 L33 16" fill="none" stroke="{tile_inner}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          <circle cx="28" cy="40" r="2.5" fill="{tile_stroke}"/>
        </g>
        <text x="114" y="70" class="sans name">{escape(h["name"])}</text>
        <text x="117" y="94" class="mono role">{escape(h["role"].upper())}</text>
        {lines}
        <g transform="translate(117, 176)">
          {"".join(chips)}
        </g>
        <g transform="translate(590, 40)" opacity="0.6" fill="none" stroke-width="1.5" stroke-linecap="round">
          <path stroke="{wave_a}">
            <animate attributeName="d" dur="8s" repeatCount="indefinite"
              values="M 0 100 C 40 100, 60 30, 100 30 C 140 30, 160 120, 200 120;M 0 100 C 40 100, 60 80, 100 80 C 140 80, 160 50, 200 50;M 0 100 C 40 100, 60 30, 100 30 C 140 30, 160 120, 200 120"/>
          </path>
          <path stroke="{wave_b}">
            <animate attributeName="d" dur="6s" repeatCount="indefinite"
              values="M 0 100 C 40 100, 60 60, 100 60 C 140 60, 160 90, 200 90;M 0 100 C 40 100, 60 120, 100 120 C 140 120, 160 40, 200 40;M 0 100 C 40 100, 60 60, 100 60 C 140 60, 160 90, 200 90"/>
          </path>
          <circle r="3" fill="{node}" stroke="none">
            <animateMotion dur="8s" repeatCount="indefinite" path="M 0 100 C 40 100, 60 30, 100 30 C 140 30, 160 120, 200 120"/>
            <animate attributeName="opacity" values="0;1;0" dur="8s" repeatCount="indefinite"/>
          </circle>
        </g>
    """
    return svg(800, 228, css, body)


def section_label(text, t):
    css = f'.label {{ font-size: 11px; fill: {t["muted"]}; letter-spacing: 3px; }}'
    return svg(800, 36, css, f'<text x="{PAD}" y="24" class="mono label">{escape(text.upper())}</text>')


def project(p, t):
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
        .float {{ animation: float 6s ease-in-out infinite; }}
        @keyframes float {{ 50% {{ transform: translateY(-2px); }} }}
        .title {{ font-size: 17px; font-weight: 600; fill: {t["text"]}; }}
        .kind {{ font-size: 10px; fill: {t["muted"]}; letter-spacing: 1.5px; }}
        .desc {{ font-size: 13px; fill: {t["muted"]}; }}
        .tag {{ font-size: 11px; fill: {t["muted"]}; }}
        .arrow {{ fill: none; stroke: {t["muted"]}; stroke-width: 1.5; stroke-linecap: round; stroke-linejoin: round; }}
    """
    body = f"""
        <g transform="translate(8, 8)">
          <rect x="0.5" y="0.5" width="383" height="179" rx="12" class="card"/>
          <rect x="24" y="24" width="32" height="32" rx="6" class="icon-box"/>
          <path d="{ICONS[p["icon"]]}" class="icon float"/>
          <text x="72" y="39" class="sans title">{escape(p["name"])}</text>
          <text x="72" y="56" class="mono kind">{escape(p["kind"].upper())}</text>
          {lines}
          {"".join(tags)}
          <path d="M350 158 L360 148 M352.5 148 H360 V155.5" class="arrow"/>
        </g>
    """
    return svg(400, 196, css, body)


def experience(profile, t):
    roles = profile["experience"]
    top, step = 72, 52
    rows = []
    for i, r in enumerate(roles):
        y = top + i * step
        current = r["end"].lower() == "present"
        dot = (
            f'<circle cx="48" cy="{y}" r="5" fill="{t["live"]}"/>'
            f'<circle cx="48" cy="{y}" r="5" fill="none" stroke="{t["live"]}" stroke-width="1.5">'
            f'<animate attributeName="r" values="5;11" dur="2.4s" repeatCount="indefinite"/>'
            f'<animate attributeName="opacity" values="0.7;0" dur="2.4s" repeatCount="indefinite"/></circle>'
            if current
            else f'<circle cx="48" cy="{y}" r="5" class="dot"/>'
        )
        rows.append(
            f'{dot}\n'
            f'<text x="72" y="{y + 5}" class="sans role">{escape(r["role"])}<tspan class="org"> at {escape(r["org"])}</tspan></text>\n'
            f'<text x="{800 - PAD}" y="{y + 4}" text-anchor="end" class="mono date">{escape(r["start"])} – {escape(r["end"])}</text>'
        )
    height = top + (len(roles) - 1) * step + 28
    css = f"""
        .label {{ font-size: 11px; fill: {t["muted"]}; letter-spacing: 3px; }}
        .role {{ font-size: 15px; font-weight: 600; fill: {t["text"]}; }}
        .org {{ font-weight: 400; fill: {t["muted"]}; }}
        .date {{ font-size: 11px; fill: {t["muted"]}; }}
        .dot {{ fill: {t["surface"]}; stroke: {t["border"]}; stroke-width: 2; }}
    """
    body = (
        f'<text x="{PAD}" y="28" class="mono label">EXPERIENCE</text>\n'
        f'<path d="M48 {top} V{top + (len(roles) - 1) * step}" stroke="{t["border"]}" stroke-width="2"/>\n'
        + "\n".join(rows)
    )
    return svg(800, height, css, body)


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
    css = f"""
        .panel {{ fill: url(#panel); stroke: {t["border"]}; }}
        .label {{ font-size: 11px; fill: {t["muted"]}; letter-spacing: 3px; }}
        .big {{ font-size: 56px; font-weight: 600; fill: url(#chrome); letter-spacing: -2px; }}
        .sub {{ font-size: 9px; fill: {t["muted"]}; letter-spacing: 2px; }}
        .stat {{ font-size: 22px; font-weight: 500; fill: {t["text"]}; }}
        .lang {{ font-size: 9px; fill: {t["muted"]}; letter-spacing: 1px; }}
        .divider {{ stroke: {t["border"]}; }}
    """
    w = 800 - 2 * EDGE
    body = f"""
        <defs>
          <linearGradient id="panel" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="{t["panel"][0]}"/>
            <stop offset="100%" stop-color="{t["panel"][1]}"/>
          </linearGradient>
          <linearGradient id="chrome" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="{t["chrome"][0]}"/>
            <stop offset="50%" stop-color="{t["chrome"][1]}"/>
            <stop offset="100%" stop-color="{t["chrome"][2]}"/>
          </linearGradient>
          <clipPath id="bar"><rect width="218" height="6" rx="3"/></clipPath>
        </defs>
        <g transform="translate({EDGE}, 10)">
          <rect x="0.5" y="0.5" width="{w - 1}" height="189" rx="12" class="panel"/>
          <text x="24" y="38" class="mono label">TELEMETRY</text>
          <text x="22" y="114" class="sans big">{num("contributions")}</text>
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
          <circle cx="{w - 24 - mono_width("SYNCED " + stats.get("synced", ""), 9, 2) - 8}" cy="168.5" r="2.5" fill="{t["live"]}"/>
          <text x="{w - 24}" y="172" text-anchor="end" class="mono sub">SYNCED {escape(stats.get("synced", "—"))}</text>
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
        .key {{ fill: {t["surface"]}; stroke: {t["border"]}; }}
        .label {{ font-size: 10px; fill: {t["muted"]}; letter-spacing: 1px; font-weight: 500; }}
        .action {{ font-size: 10px; fill: {t["text"]}; letter-spacing: 1px; font-weight: 700; }}
    """
    body = f"""
        <rect x="0.5" y="0.5" width="{width - 1}" height="39" rx="6" class="outline"/>
        <text x="16" y="24" class="mono label">{escape(label)}</text>
        <rect x="{ax:.1f}" y="5" width="{aw:.1f}" height="30" rx="4" class="key"/>
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
    header_alt = f'{h["name"]}, {h["role"].replace(" · ", ", ")}. {h["tagline"]} Stack: {", ".join(h["stack"])}.'
    projects = []
    for p in profile["projects"]:
        card = themed("project-%s.svg" % p["slug"], "%s (%s): %s" % (p["name"], p["kind"], p["description"]), 'width="49%"')
        projects.append(f'<a href="{p["url"]}">{card}</a>')
    buttons = []
    for link in profile["links"]:
        button = themed("button-%s.svg" % link["slug"], link["label"], 'height="40"')
        buttons.append(f'<a href="{link["url"]}">{button}</a>')
    roles = "; ".join("%s at %s, %s – %s" % (r["role"], r["org"], r["start"], r["end"]) for r in profile["experience"])
    snake = f"{RAW}/output/github-contribution-grid-snake"
    return f"""\
<!-- Generated by scripts/build.py from data/profile.json. Edit that file instead: changes made here are overwritten. -->
<div align="center">

{themed("header.svg", header_alt, 'width="100%"')}

{themed("label-work.svg", "Selected work", 'width="100%"')}
{chr(10).join(" ".join(projects[i:i + 2]) for i in range(0, len(projects), 2))}

{themed("experience.svg", "Experience: %s." % roles, 'width="100%"')}

{themed("telemetry.svg", "GitHub telemetry: contributions in the past year, stars, repositories, followers and language mix.", 'width="100%"')}

{"&nbsp;&nbsp;".join(buttons)}

<code>{escape(h["motto"])}</code>

<picture><source media="(prefers-color-scheme: dark)" srcset="{snake}-dark.svg"><source media="(prefers-color-scheme: light)" srcset="{snake}.svg"><img src="{snake}.svg" width="100%" alt="Contribution graph being eaten by a snake"></picture>

</div>
"""


def render(profile, stats):
    """Map of file name to SVG source, per theme."""
    out = {}
    for theme, t in THEMES.items():
        files = {
            "header.svg": header(profile, t),
            "label-work.svg": section_label("Selected work", t),
            "experience.svg": experience(profile, t),
            "telemetry.svg": telemetry(stats, t),
        }
        for p in profile["projects"]:
            files[f'project-{p["slug"]}.svg'] = project(p, t)
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
    print(f"Rendered README.md and {sum(map(len, themes.values()))} cards into assets/dark and assets/light")


if __name__ == "__main__":
    main()
