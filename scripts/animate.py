"""Turn the Blender growth frames into the animated README images.

    blender -b -P scripts/skyline.py   -- --theme dark --frames 40   (and --theme light)
    blender -b -P scripts/repo_city.py -- --theme dark --frames 40   (and --theme light)
    python scripts/animate.py

Writes assets/<theme>/skyline.webp and assets/<theme>/repo-city.webp. Animated WebP keeps the
transparent background and soft shadows, which GIF cannot. Each run starts flat, grows, holds
the finished picture for a few seconds and loops; in the city the name tags fade in once the
buildings stand.
"""
import json
import pathlib

from PIL import Image

from label_city import tag_layer

ROOT = pathlib.Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
START_MS, STEP_MS, HOLD_MS = 700, 45, 4500   # flat start, each growth frame, finished picture
# Output widths: the README shows these at about 830 px, so this is sharp on 1.7x screens too.
WIDTH = {"skyline": 1500, "repo-city": 1400}
FADE, FADE_MS = 5, 60                         # tag fade-in frames in the city


def frames(name, theme):
    paths = sorted((BUILD / f"{name}-{theme}").glob("*.png"))
    return [Image.open(p).convert("RGBA") for p in paths]


def save(images, durations, out, width):
    """Scale to the output width (after any tags were drawn at full size) and write an animated WebP."""
    if images[0].width > width:
        size = (width, round(images[0].height * width / images[0].width))
        images = [im.resize(size, Image.LANCZOS) for im in images]
    images[0].save(out, save_all=True, append_images=images[1:], duration=durations, loop=0,
                   quality=84, method=4)
    print(f"Saved {out.relative_to(ROOT)} ({len(images)} frames, {out.stat().st_size / 1e6:.1f} MB)")


def main():
    labels = BUILD / "repo-city-labels.json"
    for theme in ("dark", "light"):
        sky = frames("skyline", theme)
        if len(sky) > 1:
            save(sky, [START_MS] + [STEP_MS] * (len(sky) - 2) + [HOLD_MS], ROOT / "assets" / theme / "skyline.webp",
                 WIDTH["skyline"])

        city = frames("repo-city", theme)
        if len(city) > 1:
            last = city[-1]
            tags = tag_layer(theme, json.loads(labels.read_text(encoding="utf-8")), last.size)
            alpha = tags.getchannel("A")
            fades = []
            for i in range(1, FADE + 1):
                layer = tags.copy()
                layer.putalpha(alpha.point(lambda a, i=i: a * i // FADE))
                fades.append(Image.alpha_composite(last, layer))
            durations = [START_MS] + [STEP_MS] * (len(city) - 2) + [FADE_MS] * (FADE - 1) + [HOLD_MS]
            save(city[:-1] + fades, durations, ROOT / "assets" / theme / "repo-city.webp", WIDTH["repo-city"])


if __name__ == "__main__":
    main()
