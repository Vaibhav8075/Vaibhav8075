"""Draw the name tags onto the Repo City renders and save them to assets/<theme>/repo-city.png.

Reads build/repo-city-<theme>.png and build/repo-city-labels.json from scripts/repo_city.py.
Each repository gets a pill with its name and commit count above its roof, joined to the roof by
a leader line. Tags never overlap: one that would collide with a placed tag moves up until it is
clear. Drawing happens at 3x and is scaled down, so edges and text stay smooth.

    python scripts/label_city.py
"""
import json
import pathlib

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
FONTS = ["C:/Windows/Fonts/seguisb.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
STYLES = {
    "dark": {"fill": (13, 17, 23, 235), "border": (48, 54, 61, 255), "name": (240, 246, 252, 255),
             "count": (139, 148, 158, 255), "line": (139, 148, 158, 200)},
    "light": {"fill": (255, 255, 255, 240), "border": (208, 215, 222, 255), "name": (31, 35, 40, 255),
              "count": (89, 99, 110, 255), "line": (89, 99, 110, 190)},
}
SS = 3                      # supersampling factor
# Tag metrics in final pixels for an 1800-px-wide render; other widths scale them.
SIZE, PAD, HEIGHT = 26, 14, 42   # font size, horizontal padding, tag height
LIFT, GAP = 34, 6           # tag bottom above the roof; minimum space between tags


def font(size):
    for path in FONTS:
        if pathlib.Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def place(roofs, measure, k):
    """Tag boxes (x0, y0, x1, y1) in final pixels, front buildings first so back tags move up."""
    boxes, height, lift, gap = {}, HEIGHT * k, LIFT * k, GAP * k
    for roof in sorted(roofs, key=lambda r: -r["y"]):
        w = measure(roof)
        x0 = roof["x"] - w / 2
        y1 = roof["y"] - lift
        while any(x0 < b[2] + gap and x0 + w > b[0] - gap and y1 - height < b[3] + gap and y1 > b[1] - gap
                  for b in boxes.values()):
            y1 -= 2 * k
        boxes[roof["name"]] = (x0, y1 - height, x0 + w, y1)
    return boxes


def tag_layer(theme, data, size):
    """Transparent image of the given size with every tag and leader line drawn on it."""
    style = STYLES[theme]
    k = size[0] / 1800
    name_font, count_font = font(round(SIZE * k * SS)), font(round(SIZE * 0.85 * k * SS))
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))

    def parts(roof):
        return roof["name"], f"{roof['commits']}"

    def measure(roof):
        name, count = parts(roof)
        w = probe.textlength(name, font=name_font) + probe.textlength("  " + count, font=count_font)
        return w / SS + 2 * PAD * k

    boxes = place(data["roofs"], measure, k)
    layer = Image.new("RGBA", (size[0] * SS, size[1] * SS), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    s = lambda v: v * SS
    stroke = max(1, round(1.5 * k * SS))
    for roof in data["roofs"]:
        x0, y0, x1, y1 = boxes[roof["name"]]
        cx = (x0 + x1) / 2
        draw.line([(s(roof["x"]), s(roof["y"])), (s(cx), s(y1))], fill=style["line"], width=stroke)
        r = 5 * k
        draw.ellipse([s(roof["x"] - r), s(roof["y"] - r), s(roof["x"] + r), s(roof["y"] + r)],
                     fill=style["fill"], outline=style["line"], width=stroke)
        draw.rounded_rectangle([s(x0), s(y0), s(x1), s(y1)], radius=round(s(HEIGHT * k / 2)), fill=style["fill"],
                               outline=style["border"], width=stroke)
        name, count = parts(roof)
        mid = s((y0 + y1) / 2)
        draw.text((s(x0 + PAD * k), mid), name, font=name_font, fill=style["name"], anchor="lm")
        draw.text((s(x0 + PAD * k) + draw.textlength(name, font=name_font), mid), "  " + count,
                  font=count_font, fill=style["count"], anchor="lm")
    return layer.resize(size, Image.LANCZOS)


def label(theme, data):
    """Still image: the finished render with its tags."""
    base = Image.open(BUILD / f"repo-city-{theme}.png").convert("RGBA")
    out = ROOT / "assets" / theme / "repo-city.png"
    Image.alpha_composite(base, tag_layer(theme, data, base.size)).save(out, optimize=True)
    print(f"Saved {out.relative_to(ROOT)}")


def main():
    data = json.loads((BUILD / "repo-city-labels.json").read_text(encoding="utf-8"))
    for theme in STYLES:
        label(theme, data)


if __name__ == "__main__":
    main()
