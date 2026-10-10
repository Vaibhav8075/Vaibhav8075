"""Render "Repo City": one building per original public repository, from data/repos.json.

Runs inside Blender (Cycles) and reuses the helpers of scripts/skyline.py. Height grows with the
square root of the repository's commit count, the footprint with the logarithm of its size, and
the roof takes GitHub's contribution-calendar green for its commit level. The busiest
repositories stand at the back, so every roof is in view. Names are not part of the scene: the render
goes to build/ with the image position of every roof, and scripts/label_city.py draws the name
tags on top so a taller building can never hide one.

    blender -b -P scripts/repo_city.py -- --theme dark
    blender -b -P scripts/repo_city.py -- --theme light
    python scripts/label_city.py

With --frames N it renders the city rising instead (frames in build/repo-city-<theme>/), which
scripts/animate.py turns into the animated assets/<theme>/repo-city.webp, tags fading in last.
"""
import argparse
import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from skyline import FONT, ROOT, add_box, ease, linear, material, mesh_object, use_gpu  # noqa: E402

THEMES = {
    "dark": {"plinth": "#1c2128", "street": "#22272e", "plot": "#2d333b", "facade": "#57606a",
             "window": "#22272e",
             "levels": ["#0e4429", "#006d32", "#26a641", "#39d353"]},
    "light": {"plinth": "#bfc7d0", "street": "#d0d7de", "plot": "#e6eaef", "facade": "#d8dee4",
              "window": "#8c959f",
              "levels": ["#9be9a8", "#40c463", "#30a14e", "#216e39"]},
}
COLS, ROWS, PITCH = 5, 4, 7.0
PLINTH_H = 1.4
GROUND = 0.08                    # top of a plot
GROW_SPREAD = 0.5               # animation: share of the run over which buildings start rising


def windows_material(t):
    """Facade with a grid of windows on every side.

    A window is where both frac((x + y) / WIN_W) and frac(z / WIN_H) fall below their fill
    ratios; x + y changes along the faces that point along either axis, z up every face.
    """
    mat = material("facade", t["facade"], 0.7)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    xyz = nodes.new("ShaderNodeSeparateXYZ")
    links.new(nodes.new("ShaderNodeTexCoord").outputs["Object"], xyz.inputs[0])

    def op(name, a, b):
        node = nodes.new("ShaderNodeMath")
        node.operation = name
        for i, v in enumerate((a, b)):
            if isinstance(v, (int, float)):
                node.inputs[i].default_value = v
            else:
                links.new(v, node.inputs[i])
        return node.outputs[0]

    across = op("FRACT", op("DIVIDE", op("ADD", xyz.outputs["X"], xyz.outputs["Y"]), 0.7), 0.0)
    up = op("FRACT", op("DIVIDE", xyz.outputs["Z"], 0.8), 0.0)
    is_window = op("MULTIPLY", op("LESS_THAN", across, 0.55), op("LESS_THAN", up, 0.5))
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    ramp.color_ramp.elements[0].color = linear(t["facade"])
    ramp.color_ramp.elements[1].position = 0.5
    ramp.color_ramp.elements[1].color = linear(t["window"])
    links.new(is_window, ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], nodes["Principled BSDF"].inputs["Base Color"])
    return mat


CAM_ROT = (math.radians(58), 0.0, math.radians(-38))


def build(repos, theme):
    t = THEMES[theme]
    # Plots ordered from the back of the view to the front, so the most committed (tallest)
    # repositories stand behind the shorter ones and every roof stays visible to the camera.
    cells = [(c, r) for c in range(COLS) for r in range(ROWS)]
    cx, cy = (COLS - 1) / 2, (ROWS - 1) / 2
    turn = -CAM_ROT[2]
    depth = lambda p: (p[0] - cx) * math.sin(turn) + (p[1] - cy) * math.cos(turn)
    cells.sort(key=lambda p: (-depth(p), p))
    ranked = sorted(repos, key=lambda r: (-r["commits"], r["name"]))
    commits = sorted(r["commits"] for r in repos)
    quartiles = [commits[int(len(commits) * q)] for q in (0.25, 0.5, 0.75)]

    half_w, half_d = COLS * PITCH / 2 + 1.0, ROWS * PITCH / 2 + 1.0
    bm = bmesh.new()
    add_box(bm, -half_w, half_w, -half_d, half_d, -PLINTH_H, 0.0, 0)
    mesh_object("plinth", bm, [material("plinth", t["plinth"], 0.6)], 0.15)

    plot_mat, facade = material("plot", t["plot"], 0.8), windows_material(t)
    roofs = [material(f"roof{i}", c, 0.5) for i, c in enumerate(t["levels"])]
    plots, specs, anchors = bmesh.new(), [], []  # anchors: roof centres, for scripts/label_city.py
    for i, (repo, (c, r)) in enumerate(zip(ranked, cells)):
        x = (c - cx) * PITCH
        y = (r - cy) * PITCH
        add_box(plots, x - PITCH * 0.42, x + PITCH * 0.42, y - PITCH * 0.42, y + PITCH * 0.42, 0.0, GROUND, 0)
        w = 1.9 + 0.55 * math.log10(max(repo["size_kb"], 10))
        h = 1.2 + 2.1 * math.sqrt(repo["commits"])
        level = sum(repo["commits"] > q for q in quartiles)
        rise = (len(ranked) - 1 - i) / (len(ranked) - 1)   # front (short) buildings rise first
        specs.append((x, y, w, h, level, rise))
        anchors.append({"name": repo["label"], "commits": repo["commits"], "roof": (x, y, h + 0.35)})
    mesh_object("plots", plots, [plot_mat], 0.04)
    bodies_bm, caps_bm = city_meshes(specs, 1.0)
    bodies = mesh_object("buildings", bodies_bm, [facade], 0.03)
    caps = mesh_object("roofs", caps_bm, roofs, 0.05)
    return anchors, (bodies, caps), lambda progress: city_meshes(specs, progress)


def city_meshes(specs, progress):
    """Building bodies and roofs at growth progress 0..1: flat roofs on the plots at 0, full height at 1."""
    bodies, caps = bmesh.new(), bmesh.new()
    for x, y, w, h, level, rise in specs:
        grown = ease((progress - rise * GROW_SPREAD) / (1 - GROW_SPREAD))
        top = GROUND + 0.12 + (h - GROUND - 0.12) * grown
        add_box(bodies, x - w / 2, x + w / 2, y - w / 2, y + w / 2, GROUND, top, 0)
        add_box(caps, x - w / 2 - 0.08, x + w / 2 + 0.08, y - w / 2 - 0.08, y + w / 2 + 0.08, top, top + 0.35, level)
    return bodies, caps


def stage(resolution, samples):
    scene = bpy.context.scene
    bpy.ops.mesh.primitive_plane_add(size=600, location=(0, 0, -PLINTH_H))
    bpy.context.active_object.is_shadow_catcher = True

    cam = bpy.data.objects.new("camera", bpy.data.cameras.new("camera"))
    cam.data.type, cam.data.ortho_scale = "ORTHO", 72
    # Orthographic, so only the view direction matters: back away from the target along it.
    tilt, turn, distance, target_z = CAM_ROT[0], -CAM_ROT[2], 150, 12.0
    cam.rotation_euler = CAM_ROT
    cam.location = (-distance * math.sin(tilt) * math.sin(turn),
                    -distance * math.sin(tilt) * math.cos(turn),
                    distance * math.cos(tilt) + target_z)
    scene.collection.objects.link(cam)
    scene.camera = cam

    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy, sun.data.angle = 3.0, math.radians(10)
    sun.rotation_euler = (math.radians(25), math.radians(10), math.radians(-60))
    scene.collection.objects.link(sun)
    world = bpy.data.worlds.new("world")
    if world.node_tree is None:
        world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.5, 0.5, 0.5, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.45
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


def roof_pixels(anchors, resolution):
    """Image position (px from the top left) of every roof centre."""
    from bpy_extras.object_utils import world_to_camera_view
    scene, (w, h) = bpy.context.scene, resolution
    bpy.context.view_layer.update()  # the camera's world matrix is stale until the scene is evaluated
    out = []
    for a in anchors:
        u, v, _ = world_to_camera_view(scene, scene.camera, Vector(a["roof"]))
        out.append({"name": a["name"], "commits": a["commits"], "x": round(u * w, 1), "y": round((1 - v) * h, 1)})
    return out


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--theme", choices=THEMES, default="dark")
    parser.add_argument("--frames", type=int, default=0,
                        help="render this many growth frames to build/repo-city-<theme>/ instead of a still")
    parser.add_argument("--samples", type=int, default=192)
    parser.add_argument("--res", default="1800x1150")
    args = parser.parse_args(argv)
    resolution = tuple(int(v) for v in args.res.split("x"))

    with open(os.path.join(ROOT, "data", "repos.json"), encoding="utf-8") as fh:
        repos = json.load(fh)["repos"]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    anchors, objects, grow = build(repos, args.theme)
    stage(resolution, args.samples)
    scene, out_dir = bpy.context.scene, os.path.join(ROOT, "build")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "repo-city-labels.json"), "w", encoding="utf-8") as fh:
        json.dump({"size": resolution, "roofs": roof_pixels(anchors, resolution)}, fh, indent=1)
    if not args.frames:
        scene.render.filepath = os.path.join(out_dir, f"repo-city-{args.theme}.png")
        bpy.ops.render.render(write_still=True)
        print(f"Saved {scene.render.filepath}")
        return
    frame_dir = os.path.join(out_dir, f"repo-city-{args.theme}")
    os.makedirs(frame_dir, exist_ok=True)
    for f in range(args.frames):
        for obj, bm in zip(objects, grow(f / (args.frames - 1))):
            bm.to_mesh(obj.data)
            bm.free()
        scene.render.filepath = os.path.join(frame_dir, f"{f:04d}.png")
        bpy.ops.render.render(write_still=True)
    print(f"Saved {args.frames} frames to {frame_dir}")


if __name__ == "__main__":
    main()
