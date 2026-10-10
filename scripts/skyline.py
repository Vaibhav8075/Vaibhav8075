"""Render the contribution skyline: one bar per day of data/contributions.json on a plinth.

Runs inside Blender (Cycles). Writes a transparent PNG whose only background is the plinth's
soft shadow, so it sits on GitHub's page colour; one render per README theme.

    blender -b -P scripts/skyline.py -- --theme dark  --out assets/dark/skyline.png
    blender -b -P scripts/skyline.py -- --theme light --out assets/light/skyline.png

With --frames N it renders the skyline growing instead (frames in build/skyline-<theme>/), which
scripts/animate.py turns into the animated assets/<theme>/skyline.webp.

Bar height grows with the square root of the day's count, so one very busy day does not flatten
the rest. Each bar takes the colour of its day's activity level (0-4) in GitHub's own contribution
calendar, and days without contributions are low tiles, which keeps the 7 x 53 grid readable.
"""
import argparse
import datetime
import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Solid colours per README theme (sRGB hex): GitHub's contribution-calendar greens for the
# five activity levels, as on the profile's own graph. No gradients anywhere.
THEMES = {
    "dark": {"plinth": "#1c2128", "text": "#adbac7",
             "levels": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]},
    "light": {"plinth": "#bfc7d0", "text": "#424a53",
              "levels": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"]},
}

CELL = 1.0          # calendar cell pitch
BAR = 0.8           # bar footprint
TILE_H = 0.12       # height of a day without contributions
BASE_H, SCALE_H = 0.35, 0.9   # active day: BASE_H + SCALE_H * sqrt(count)
PLINTH_H, PLINTH_FLARE, MARGIN = 2.2, 1.6, 1.2
GROW_SPREAD = 0.55  # animation: share of the run over which the weeks start rising, left to right
FONT = "C:/Windows/Fonts/seguisb.ttf"   # Segoe UI Semibold if present, else Blender's built-in font


def linear(hex_color):
    """sRGB hex -> linear RGBA, which is what Blender material inputs expect."""
    def chan(c):
        c = int(c, 16) / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    h = hex_color.lstrip("#")
    return (chan(h[0:2]), chan(h[2:4]), chan(h[4:6]), 1.0)


def material(name, hex_color, roughness=0.55):
    mat = bpy.data.materials.new(name)
    if mat.node_tree is None:  # Blender < 5 creates materials without a node tree
        mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = linear(hex_color)
    bsdf.inputs["Roughness"].default_value = roughness
    return mat


def add_box(bm, x0, x1, y0, y1, z0, z1, mat_index):
    v = [bm.verts.new(p) for p in [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                                   (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]]
    for idx in [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]:
        bm.faces.new([v[i] for i in idx]).material_index = mat_index


def mesh_object(name, bm, materials, bevel):
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    for mat in materials:
        obj.data.materials.append(mat)
    mod = obj.modifiers.new("bevel", "BEVEL")
    mod.width, mod.segments, mod.limit_method = bevel, 3, "ANGLE"
    bpy.context.scene.collection.objects.link(obj)
    return obj


def text(body, size, x, align, mat, slope):
    """Embossed text lying on the plinth's sloped front face."""
    curve = bpy.data.curves.new(body, "FONT")
    curve.body = body
    if os.path.exists(FONT):
        curve.font = bpy.data.fonts.load(FONT)
    curve.size, curve.extrude, curve.align_x, curve.align_y = size, 0.04, align, "CENTER"
    obj = bpy.data.objects.new(body, curve)
    obj.data.materials.append(mat)
    half_w, half_d = slope["half_w"], slope["half_d"]
    # Centre of the front face, nudged out along its normal so the letters stand on it.
    normal = Vector((0, -PLINTH_H, PLINTH_FLARE)).normalized()
    centre = Vector((x, -(half_d + PLINTH_FLARE / 2), -PLINTH_H / 2)) + normal * 0.045
    obj.location = centre
    obj.rotation_euler = (math.atan2(PLINTH_H, PLINTH_FLARE), 0, 0)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def ease(p):
    """Ease-out cubic on [0, 1]: fast rise, gentle landing."""
    p = min(max(p, 0.0), 1.0)
    return 1 - (1 - p) ** 3


def bar_specs(days, weeks, first):
    """(x, y, full height, material index, week) for every day of the calendar."""
    specs = []
    offset = (first.weekday() + 1) % 7   # Python: Monday=0; calendar rows start on Sunday
    for i, day in enumerate(days):
        week, row = divmod(i + offset, 7)
        count = day["count"]
        height = TILE_H if count == 0 else BASE_H + SCALE_H * math.sqrt(count)
        index = 0 if count == 0 else max(1, min(4, day["level"]))
        specs.append(((week + 0.5) * CELL - weeks * CELL / 2, (3 - row) * CELL, height, index, week))
    return specs


def bars_mesh(specs, weeks, progress):
    """Bars at growth progress 0..1: the year rises from left to right, empty days stay tiles."""
    bm = bmesh.new()
    for cx, cy, height, index, week in specs:
        grown = ease((progress - week / weeks * GROW_SPREAD) / (1 - GROW_SPREAD))
        h = TILE_H + (height - TILE_H) * grown
        add_box(bm, cx - BAR / 2, cx + BAR / 2, cy - BAR / 2, cy + BAR / 2, 0.0, h, index)
    return bm


def build(days, theme):
    t = THEMES[theme]
    first = datetime.date.fromisoformat(days[0]["date"])
    weeks = (datetime.date.fromisoformat(days[-1]["date"]) - first).days // 7 + 1
    half_w, half_d = weeks * CELL / 2 + MARGIN, 7 * CELL / 2 + MARGIN
    mats = [material(f"level{i}", c) for i, c in enumerate(t["levels"])]

    # Bars: week along x, weekday along y (Sunday at the back, as on GitHub's calendar).
    specs = bar_specs(days, weeks, first)
    bars = mesh_object("bars", bars_mesh(specs, weeks, 1.0), mats, 0.03)

    # Plinth: a frustum whose sides flare out towards the floor.
    bm = bmesh.new()
    top = [(-half_w, -half_d), (half_w, -half_d), (half_w, half_d), (-half_w, half_d)]
    f = PLINTH_FLARE
    bottom = [(-half_w - f, -half_d - f), (half_w + f, -half_d - f), (half_w + f, half_d + f), (-half_w - f, half_d + f)]
    vt = [bm.verts.new((x, y, 0.0)) for x, y in top]
    vb = [bm.verts.new((x, y, -PLINTH_H)) for x, y in bottom]
    bm.faces.new(vt)
    bm.faces.new(list(reversed(vb)))
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new([vb[i], vb[j], vt[j], vt[i]])
    mesh_object("plinth", bm, [material("plinth", t["plinth"], 0.6)], 0.08)

    label = material("label", t["text"], 0.5)
    slope = {"half_w": half_w, "half_d": half_d}
    last = datetime.date.fromisoformat(days[-1]["date"])
    text(f"@{USER}", 1.35, -half_w + 1.2, "LEFT", label, slope)
    text(f"{first:%b %Y} – {last:%b %Y}", 1.35, half_w - 1.2, "RIGHT", label, slope)
    return half_w, half_d, bars, lambda progress: bars_mesh(specs, weeks, progress)


def stage(half_w, half_d, resolution, samples):
    scene = bpy.context.scene
    # Floor that only receives shadows; with a transparent film it renders as shadow alone.
    bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 0, -PLINTH_H))
    bpy.context.active_object.is_shadow_catcher = True

    target = bpy.data.objects.new("target", None)
    target.location = (0, 0, 0.9)
    scene.collection.objects.link(target)
    cam = bpy.data.objects.new("camera", bpy.data.cameras.new("camera"))
    cam.data.lens = 85
    cam.location = (0, -152, 58)
    track = cam.constraints.new("TRACK_TO")
    track.target, track.track_axis, track.up_axis = target, "TRACK_NEGATIVE_Z", "UP_Y"
    scene.collection.objects.link(cam)
    scene.camera = cam

    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy, sun.data.angle = 3.0, math.radians(14)
    sun.rotation_euler = (math.radians(30), math.radians(-18), math.radians(-30))
    scene.collection.objects.link(sun)
    fill = bpy.data.objects.new("fill", bpy.data.lights.new("fill", "AREA"))
    fill.data.energy, fill.data.size = 25000, 60
    fill.location = (40, -70, 50)
    fill.rotation_euler = (math.radians(55), 0, math.radians(30))
    scene.collection.objects.link(fill)

    world = bpy.data.worlds.new("world")
    if world.node_tree is None:
        world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.5, 0.5, 0.5, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.25
    scene.world = world

    scene.render.engine = "CYCLES"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.film_transparent = True
    scene.render.resolution_x, scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.view_transform = "Standard"
    use_gpu(scene)


def use_gpu(scene):
    """Render on the GPU when Cycles finds one (OptiX, then CUDA); otherwise stay on the CPU."""
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for backend in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = backend
            prefs.get_devices()
        except TypeError:
            continue
        gpus = [d for d in prefs.devices if d.type == backend]
        if gpus:
            for d in prefs.devices:
                d.use = d.type == backend
            scene.cycles.device = "GPU"
            print(f"Rendering on {backend}: {', '.join(d.name for d in gpus)}")
            return
    print("No GPU found; rendering on the CPU")


USER = "Vaibhav8075"


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--theme", choices=THEMES, default="dark")
    parser.add_argument("--out", help="still image path (the finished skyline)")
    parser.add_argument("--frames", type=int, default=0,
                        help="render this many growth frames to build/skyline-<theme>/ instead of a still")
    parser.add_argument("--samples", type=int, default=192)
    parser.add_argument("--res", default="1800x420")
    args = parser.parse_args(argv)
    if not args.out and not args.frames:
        parser.error("give --out for a still or --frames for an animation")

    with open(os.path.join(ROOT, "data", "contributions.json"), encoding="utf-8") as fh:
        days = json.load(fh)["days"]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    half_w, half_d, bars, grow = build(days, args.theme)
    stage(half_w, half_d, tuple(int(v) for v in args.res.split("x")), args.samples)
    scene = bpy.context.scene
    if not args.frames:
        scene.render.filepath = os.path.abspath(os.path.join(ROOT, args.out))
        bpy.ops.render.render(write_still=True)
        print(f"Saved {scene.render.filepath}")
        return
    out_dir = os.path.join(ROOT, "build", f"skyline-{args.theme}")
    os.makedirs(out_dir, exist_ok=True)
    for f in range(args.frames):
        bm = grow(f / (args.frames - 1))
        bm.to_mesh(bars.data)
        bm.free()
        scene.render.filepath = os.path.join(out_dir, f"{f:04d}.png")
        bpy.ops.render.render(write_still=True)
    print(f"Saved {args.frames} frames to {out_dir}")


if __name__ == "__main__":
    main()
