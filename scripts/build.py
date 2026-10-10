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

# GitHub's dark and light palettes, plus a violet-to-blue accent taken from the avatar.
THEMES = {
    "dark": {
        "text": "#e6edf3", "muted": "#8b949e", "border": "#30363d", "surface": "#161b22",
        "accent": "#a78bfa", "accent2": "#60a5fa", "wash": 0.14,
        "panel": ("#161b22", "#0d1117"), "live": "#3fb950",
    },
    "light": {
        "text": "#1f2328", "muted": "#59636e", "border": "#d1d9e0", "surface": "#f6f8fa",
        "accent": "#7c3aed", "accent2": "#2563eb", "wash": 0.07,
        "panel": ("#faf7ff", "#ffffff"), "live": "#1a7f37",
    },
}

# The hero is identical in both themes: a dark aurora reads well on either page.
HERO = {
    "base": ("#160c33", "#0a1230"), "blobs": ("#7c3aed", "#2563eb", "#c026d3"),
    "kicker": "#c4b5fd", "soft": "#ddd6fe", "accent": "#a78bfa",
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

# Typing line timing, in seconds.
TYPE_STEP, HOLD, ERASE_STEP, GAP = 0.07, 1.8, 0.03, 0.5


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


def section_rule(text, y, t):
    """Mono section label followed by an accent rule that fades out. Needs the .label class."""
    x = PAD + mono_width(text, 11, 3) + 10
    defs = (
        f'<linearGradient id="rule" x1="0" x2="1"><stop offset="0" stop-color="{t["accent"]}" stop-opacity="0.8"/>'
        f'<stop offset="1" stop-color="{t["accent2"]}" stop-opacity="0"/></linearGradient>'
    )
    body = (
        f'<text x="{PAD}" y="{y}" class="mono label">{escape(text.upper())}</text>\n'
        f'<rect x="{x:.1f}" y="{y - 4}" width="{800 - PAD - x:.1f}" height="1" fill="url(#rule)"/>'
    )
    return defs, body


def typing_timeline(phrases):
    """Discrete (time, phrase, characters shown) frames for a type, hold, erase loop."""
    frames, t = [], 0.0
    for i, phrase in enumerate(phrases):
        for n in range(len(phrase) + 1):
            frames.append((t, i, n))
            t += TYPE_STEP
        t += HOLD - TYPE_STEP
        for n in range(len(phrase) - 1, -1, -1):
            frames.append((t, i, n))
            t += ERASE_STEP
        t += GAP - ERASE_STEP
    return frames, t


def hero(profile):
    h = profile["header"]
    tagline = wrap(h["tagline"], 15, 540, 2, "header.tagline")

    # Typing line. Each phrase is pinned to an exact monospace width with textLength, so
    # a clip that grows one character cell per frame reveals it a letter at a time.
    cw, phrases = 9, h["typing"]
    cap_w = 40 + (len(">") + 1 + max(map(len, phrases)) + 1) * cw
    cap_x = (800 - cap_w) / 2
    x0 = cap_x + 20 + 2 * cw
    frames, total = typing_timeline(phrases)
    key_times = ";".join(f"{ft / total:.5f}" for ft, _, _ in frames)

    def discrete(attr, values):
        return (
            f'<animate attributeName="{attr}" dur="{total:.2f}s" repeatCount="indefinite" calcMode="discrete" '
            f'keyTimes="{key_times}" values="{";".join(values)}"/>'
        )

    clips, typed = [], []
    for i, phrase in enumerate(phrases):
        widths = [str(n * cw if p == i else 0) for _, p, n in frames]
        clips.append(f'<clipPath id="type{i}"><rect x="{x0:.1f}" y="224" width="0" height="26">{discrete("width", widths)}</rect></clipPath>')
        typed.append(
            f'<text x="{x0:.1f}" y="241" textLength="{len(phrase) * cw}" lengthAdjust="spacing" '
            f'clip-path="url(#type{i})" class="mono typed">{escape(phrase)}</text>'
        )
    cursor = discrete("x", [f"{x0 + n * cw:.1f}" for _, _, n in frames])

    chips, widths = [], [round(32 + mono_width(tech.upper(), 10, 0.5)) for tech in h["stack"]]
    x = (800 - sum(widths) - 10 * (len(widths) - 1)) / 2
    for tech, w in zip(h["stack"], widths):
        chips.append(
            f'<rect x="{x:.1f}" y="272" width="{w}" height="24" rx="12" class="chip"/>'
            f'<circle cx="{x + 13:.1f}" cy="284" r="3" fill="{color(tech)}"/>'
            f'<text x="{x + 22:.1f}" y="287.5" class="mono chip-text">{escape(tech.upper())}</text>'
        )
        x += w + 10

    violet, blue, magenta = HERO["blobs"]
    css = f"""
        .kicker {{ font-size: 12px; fill: {HERO["kicker"]}; letter-spacing: 4px; }}
        .name {{ font-size: 64px; font-weight: 800; fill: url(#name); letter-spacing: -1.5px; }}
        .tagline {{ font-size: 15px; fill: {HERO["soft"]}; fill-opacity: 0.85; }}
        .typed {{ font-size: 15px; fill: {HERO["soft"]}; }}
        .prompt {{ font-size: 15px; fill: {HERO["accent"]}; font-weight: 700; }}
        .capsule {{ fill: #000000; fill-opacity: 0.32; stroke: #ffffff; stroke-opacity: 0.14; }}
        .chip {{ fill: #ffffff; fill-opacity: 0.07; stroke: #ffffff; stroke-opacity: 0.16; }}
        .chip-text {{ font-size: 10px; fill: {HERO["soft"]}; letter-spacing: 0.5px; }}
    """
    lines = "\n".join(
        f'<text x="400" y="{174 + 21 * i}" text-anchor="middle" class="sans tagline">{escape(line)}</text>'
        for i, line in enumerate(tagline)
    )
    body = f"""
        <defs>
          <clipPath id="frame"><rect width="800" height="330" rx="16"/></clipPath>
          <linearGradient id="base" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stop-color="{HERO["base"][0]}"/>
            <stop offset="1" stop-color="{HERO["base"][1]}"/>
          </linearGradient>
          <linearGradient id="name" x1="0" x2="1">
            <stop offset="0" stop-color="#ffffff"/>
            <stop offset="1" stop-color="#e9d5ff"/>
          </linearGradient>
          <linearGradient id="scrim" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0.55" stop-color="#000000" stop-opacity="0"/>
            <stop offset="1" stop-color="#000000" stop-opacity="0.35"/>
          </linearGradient>
          <filter id="blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="70"/></filter>
          <pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="#ffffff" fill-opacity="0.07"/></pattern>
          {"".join(clips)}
        </defs>
        <g clip-path="url(#frame)">
          <rect width="800" height="330" fill="url(#base)"/>
          <g filter="url(#blur)">
            <circle cx="170" cy="60" r="170" fill="{violet}" fill-opacity="0.85">
              <animate attributeName="cx" values="170;330;170" dur="16s" repeatCount="indefinite"/>
              <animate attributeName="cy" values="60;160;60" dur="12s" repeatCount="indefinite"/>
            </circle>
            <circle cx="650" cy="290" r="190" fill="{blue}" fill-opacity="0.8">
              <animate attributeName="cx" values="650;480;650" dur="18s" repeatCount="indefinite"/>
              <animate attributeName="cy" values="290;200;290" dur="14s" repeatCount="indefinite"/>
            </circle>
            <circle cx="540" cy="10" r="130" fill="{magenta}" fill-opacity="0.5">
              <animate attributeName="cx" values="540;660;540" dur="11s" repeatCount="indefinite"/>
            </circle>
          </g>
          <rect width="800" height="330" fill="url(#dots)"/>
          <rect width="800" height="330" fill="url(#scrim)"/>
          <rect width="800" height="1" fill="#ffffff" fill-opacity="0.25"/>
          <text x="400" y="74" text-anchor="middle" class="mono kicker">{escape(h["role"].upper())}</text>
          <text x="400" y="140" text-anchor="middle" class="sans name">{escape(h["name"])}</text>
          {lines}
          <rect x="{cap_x:.1f}" y="219" width="{cap_w:.1f}" height="34" rx="17" class="capsule"/>
          <text x="{cap_x + 20:.1f}" y="241" class="mono prompt">&gt;</text>
          {"".join(typed)}
          <rect x="{x0:.1f}" y="229" width="{cw - 1}" height="16" rx="1" fill="{HERO["accent"]}">
            {cursor}
            <animate attributeName="opacity" values="1;0.15" dur="1s" calcMode="discrete" repeatCount="indefinite"/>
          </rect>
          {"".join(chips)}
        </g>
        <rect x="0.5" y="0.5" width="799" height="329" rx="16" fill="none" stroke="#ffffff" stroke-opacity="0.1"/>
    """
    return svg(800, 330, css, body)


def section_label(text, t):
    defs, rule = section_rule(text, 24, t)
    css = f'.label {{ font-size: 11px; fill: {t["muted"]}; letter-spacing: 3px; }}'
    return svg(800, 36, css, f"<defs>{defs}</defs>\n{rule}")


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
        .card {{ fill: url(#wash); stroke: {t["border"]}; }}
        .icon-box {{ fill: {t["accent"]}; fill-opacity: 0.12; stroke: {t["accent"]}; stroke-opacity: 0.4; }}
        .icon {{ fill: none; stroke: {t["accent"]}; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }}
        .float {{ animation: float 6s ease-in-out infinite; }}
        @keyframes float {{ 50% {{ transform: translateY(-2px); }} }}
        .title {{ font-size: 17px; font-weight: 600; fill: {t["text"]}; }}
        .kind {{ font-size: 10px; fill: {t["accent"]}; letter-spacing: 1.5px; }}
        .desc {{ font-size: 13px; fill: {t["muted"]}; }}
        .tag {{ font-size: 11px; fill: {t["muted"]}; }}
        .arrow {{ fill: none; stroke: {t["accent"]}; stroke-width: 1.5; stroke-linecap: round; stroke-linejoin: round; }}
    """
    body = f"""
        <defs>
          <radialGradient id="wash" cx="0" cy="0" r="1">
            <stop offset="0" stop-color="{t["accent"]}" stop-opacity="{t["wash"]}"/>
            <stop offset="1" stop-color="{t["accent"]}" stop-opacity="0"/>
          </radialGradient>
          <linearGradient id="edge" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="{t["accent"]}"/>
            <stop offset="1" stop-color="{t["accent2"]}"/>
          </linearGradient>
        </defs>
        <g transform="translate(8, 8)">
          <rect x="0.5" y="0.5" width="383" height="179" rx="12" class="card"/>
          <rect x="0" y="24" width="3" height="132" rx="1.5" fill="url(#edge)"/>
          <rect x="24" y="24" width="32" height="32" rx="8" class="icon-box"/>
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
    bottom = top + (len(roles) - 1) * step
    rows = []
    for i, r in enumerate(roles):
        y = top + i * step
        current = r["end"].lower() == "present"
        dot = (
            f'<circle cx="48" cy="{y}" r="6" fill="{t["accent"]}"/>'
            f'<circle cx="48" cy="{y}" r="6" fill="none" stroke="{t["accent"]}" stroke-width="1.5">'
            f'<animate attributeName="r" values="6;13" dur="2.4s" repeatCount="indefinite"/>'
            f'<animate attributeName="opacity" values="0.8;0" dur="2.4s" repeatCount="indefinite"/></circle>'
            if current
            else f'<circle cx="48" cy="{y}" r="5" class="dot"/>'
        )
        rows.append(
            f'{dot}\n'
            f'<text x="74" y="{y + 5}" class="sans role">{escape(r["role"])}<tspan class="org"> at {escape(r["org"])}</tspan></text>\n'
            f'<text x="{800 - PAD}" y="{y + 4}" text-anchor="end" class="mono date{" now" if current else ""}">'
            f'{escape(r["start"])} – {escape(r["end"])}</text>'
        )
    defs, rule = section_rule("Experience", 28, t)
    css = f"""
        .label {{ font-size: 11px; fill: {t["muted"]}; letter-spacing: 3px; }}
        .role {{ font-size: 15px; font-weight: 600; fill: {t["text"]}; }}
        .org {{ font-weight: 400; fill: {t["muted"]}; }}
        .date {{ font-size: 11px; fill: {t["muted"]}; }}
        .now {{ fill: {t["accent"]}; font-weight: 700; }}
        .dot {{ fill: {t["surface"]}; stroke: {t["accent"]}; stroke-opacity: 0.55; stroke-width: 2; }}
    """
    body = f"""
        <defs>
          {defs}
          <linearGradient id="line" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="{t["accent"]}"/>
            <stop offset="0.6" stop-color="{t["accent2"]}" stop-opacity="0.6"/>
            <stop offset="1" stop-color="{t["border"]}"/>
          </linearGradient>
        </defs>
        {rule}
        <rect x="47" y="{top}" width="2" height="{bottom - top}" fill="url(#line)"/>
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
        .panel {{ fill: url(#panel); }}
        .label {{ font-size: 11px; fill: {t["accent"]}; letter-spacing: 3px; }}
        .big {{ font-size: 60px; font-weight: 700; fill: url(#num); letter-spacing: -2px; }}
        .sub {{ font-size: 9px; fill: {t["muted"]}; letter-spacing: 2px; }}
        .stat {{ font-size: 22px; font-weight: 600; fill: {t["text"]}; }}
        .lang {{ font-size: 9px; fill: {t["muted"]}; letter-spacing: 1px; }}
        .divider {{ stroke: {t["border"]}; }}
    """
    w = 800 - 2 * EDGE
    body = f"""
        <defs>
          <linearGradient id="panel" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stop-color="{t["panel"][0]}"/>
            <stop offset="1" stop-color="{t["panel"][1]}"/>
          </linearGradient>
          <radialGradient id="glow" cx="0" cy="0" r="0.75">
            <stop offset="0" stop-color="{t["accent"]}" stop-opacity="{t["wash"] * 1.4:.2f}"/>
            <stop offset="1" stop-color="{t["accent"]}" stop-opacity="0"/>
          </radialGradient>
          <linearGradient id="stroke" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stop-color="{t["accent"]}" stop-opacity="0.6"/>
            <stop offset="0.5" stop-color="{t["border"]}"/>
            <stop offset="1" stop-color="{t["accent2"]}" stop-opacity="0.6"/>
          </linearGradient>
          <linearGradient id="num" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stop-color="{t["accent"]}"/>
            <stop offset="1" stop-color="{t["accent2"]}"/>
          </linearGradient>
          <clipPath id="bar"><rect width="218" height="6" rx="3"/></clipPath>
        </defs>
        <g transform="translate({EDGE}, 10)">
          <rect x="0.5" y="0.5" width="{w - 1}" height="189" rx="12" class="panel"/>
          <rect x="0.5" y="0.5" width="{w - 1}" height="189" rx="12" fill="url(#glow)" stroke="url(#stroke)"/>
          <text x="24" y="38" class="mono label">TELEMETRY</text>
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
    # The key uses the deep hero violet and blue in both themes so white text stays readable.
    css = f"""
        .outline {{ fill: none; stroke: {t["border"]}; }}
        .label {{ font-size: 10px; fill: {t["muted"]}; letter-spacing: 1px; font-weight: 500; }}
        .action {{ font-size: 10px; fill: #ffffff; letter-spacing: 1px; font-weight: 700; }}
    """
    body = f"""
        <defs>
          <linearGradient id="key" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stop-color="{HERO["blobs"][0]}"/>
            <stop offset="1" stop-color="{HERO["blobs"][1]}"/>
          </linearGradient>
        </defs>
        <rect x="0.5" y="0.5" width="{width - 1}" height="39" rx="8" class="outline"/>
        <text x="16" y="24" class="mono label">{escape(label)}</text>
        <rect x="{ax:.1f}" y="5" width="{aw:.1f}" height="30" rx="6" fill="url(#key)"/>
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

{themed("hero.svg", header_alt, 'width="100%"')}

{themed("telemetry.svg", "GitHub telemetry: contributions in the past year, stars, repositories, followers and language mix.", 'width="100%"')}

{themed("label-work.svg", "Selected work", 'width="100%"')}
{chr(10).join(" ".join(projects[i:i + 2]) for i in range(0, len(projects), 2))}

{themed("experience.svg", "Experience: %s." % roles, 'width="100%"')}

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
            "hero.svg": hero(profile),
            "telemetry.svg": telemetry(stats, t),
            "label-work.svg": section_label("Selected work", t),
            "experience.svg": experience(profile, t),
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
