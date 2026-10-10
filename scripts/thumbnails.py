"""Render a small 3D object for each project card, from simple procedural geometry.

Runs inside Blender (Cycles) and reuses the helpers of scripts/skyline.py. Every object is
rendered on a transparent background with a soft contact shadow, so one image works on both
README themes; scripts/build.py embeds it at the top of the project's card.

    blender -b -P scripts/thumbnails.py               # all projects -> assets/thumbs/<slug>.webp
    blender -b -P scripts/thumbnails.py -- --only audict
"""
import argparse
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from skyline import ROOT, linear, use_gpu  # noqa: E402

VIEW = (math.radians(64), 0.0, math.radians(32))   # shared camera direction: elevated, from the front left
SIZE = (768, 240)                                   # card banner, 2x its displayed size
GREEN, GREEN_DARK, BLUE = "#2da44e", "#1a7f37", "#4493f8"


# ---------------------------------------------------------------- building blocks
def mat(name, color, roughness=0.5, metallic=0.0, emission=0.0):
    m = bpy.data.materials.new(name)
    if m.node_tree is None:
        m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = linear(color)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if emission:
        bsdf.inputs["Emission Color"].default_value = linear(color)
        bsdf.inputs["Emission Strength"].default_value = emission
    return m


def finish(obj, material, bevel=0.0, smooth=False):
    obj.data.materials.clear()
    obj.data.materials.append(material)
    if bevel:
        mod = obj.modifiers.new("bevel", "BEVEL")
        mod.width, mod.segments, mod.limit_method = bevel, 3, "ANGLE"
    if smooth == "all":
        for poly in obj.data.polygons:
            poly.use_smooth = True
    elif smooth:  # curved sides only, so flat caps stay crisp
        for poly in obj.data.polygons:
            poly.use_smooth = abs(poly.normal.z) < 0.5
    return obj


def box(name, size, loc, material, bevel=0.02):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = size
    bpy.ops.object.transform_apply(scale=True)
    return finish(obj, material, bevel)


def cylinder(name, radius, depth, loc, material, rot=(0, 0, 0), vertices=64, bevel=0.01):
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=depth, location=loc, rotation=rot, vertices=vertices)
    obj = bpy.context.active_object
    obj.name = name
    return finish(obj, material, bevel, smooth=True)


def sphere(name, radius, loc, material, scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=loc, segments=48, ring_count=24)
    obj = bpy.context.active_object
    obj.name, obj.scale = name, scale
    return finish(obj, material, smooth="all")


def cone(name, radius, depth, loc, material, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cone_add(radius1=radius, depth=depth, location=loc, rotation=rot, vertices=48)
    obj = bpy.context.active_object
    obj.name = name
    return finish(obj, material, smooth=True)


def ring(name, r_in, r_out, height, loc, material, segments=128):
    """Flat ring with a rectangular cross-section (a bearing race)."""
    bm = bmesh.new()
    rings = []
    for r, z in ((r_out, -height / 2), (r_out, height / 2), (r_in, height / 2), (r_in, -height / 2)):
        rings.append([bm.verts.new((r * math.cos(2 * math.pi * i / segments), r * math.sin(2 * math.pi * i / segments), z))
                      for i in range(segments)])
    for a, b in zip(rings, rings[1:] + rings[:1]):
        for i in range(segments):
            j = (i + 1) % segments
            bm.faces.new([a[i], a[j], b[j], b[i]])
    mesh = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = loc
    bpy.context.scene.collection.objects.link(obj)
    return finish(obj, material, bevel=0.02, smooth=True)


def group(objects, rotation=(0, 0, 0), location=(0, 0, 0)):
    """Parent objects to an empty so a whole model can be posed at once."""
    root = bpy.data.objects.new("root", None)
    bpy.context.scene.collection.objects.link(root)
    for obj in objects:
        obj.parent = root
    root.rotation_euler, root.location = rotation, location
    return root


# ---------------------------------------------------------------- the five models
def bearing():
    steel = mat("steel", "#c9d1d9", 0.22, 1.0)
    dark_steel = mat("dark steel", "#6e7681", 0.35, 1.0)
    spall = mat("spall", "#22272e", 0.9)
    # Rings lower than the balls are wide, so the balls show between them, as on a real bearing.
    parts = [ring("outer", 1.58, 2.0, 0.4, (0, 0, 0), steel), ring("inner", 0.7, 1.1, 0.4, (0, 0, 0), steel),
             ring("cage", 1.25, 1.43, 0.12, (0, 0, 0), dark_steel)]
    for i in range(9):
        a = 2 * math.pi * i / 9
        parts.append(sphere(f"ball{i}", 0.24, (1.34 * math.cos(a), 1.34 * math.sin(a), 0), steel))
    # The defect: a dark, irregular spall on the outer race's front face.
    parts.append(sphere("spall", 0.14, (1.79 * math.cos(-1.3), 1.79 * math.sin(-1.3), 0.195), spall, scale=(1.5, 0.75, 0.15)))
    group(parts, rotation=(math.radians(52), 0, math.radians(8)))


def car():
    road, lane = mat("road", "#30363d", 0.85), mat("lane", "#e6edf3", 0.6)
    walk = mat("sidewalk", "#8c959f", 0.85)
    body, glass, tyre = mat("car", BLUE, 0.45), mat("glass", "#0d1117", 0.15), mat("tyre", "#1f2328", 0.8)
    parts = [box("road", (6.2, 2.6, 0.08), (0, 0, -0.04), road, 0.01),
             box("sidewalk", (6.2, 0.7, 0.18), (0, 1.65, 0.01), walk, 0.02)]
    for x in (-2.5, -1.0, 0.5, 2.0):
        parts.append(box(f"dash{x}", (0.8, 0.09, 0.01), (x, -0.85, 0.005), lane, 0.0))
    parts += [box("body", (2.3, 1.0, 0.42), (0, 0, 0.42), body, 0.12),
              box("cabin", (1.25, 0.86, 0.38), (-0.12, 0, 0.8), glass, 0.12)]
    for x in (-0.75, 0.75):
        for y in (-0.5, 0.5):
            parts.append(cylinder(f"wheel{x}{y}", 0.22, 0.16, (x, y, 0.22), tyre, rot=(math.pi / 2, 0, 0)))
    group(parts, rotation=(0, 0, math.radians(-8)))


def esp32():
    pcb, shield = mat("pcb", "#1f2328", 0.55), mat("shield", "#c9d1d9", 0.25, 1.0)
    pin, chip, led = mat("pin", "#d0d7de", 0.3, 1.0), mat("chip", "#0d1117", 0.4), mat("led", "#3fb950", 0.3, 0, 6.0)
    trace = mat("trace", "#57606a", 0.4, 1.0)
    parts = [box("pcb", (3.2, 1.25, 0.08), (0, 0, 0.04), pcb, 0.02),
             box("module", (1.25, 0.9, 0.06), (0.95, 0, 0.11), pcb, 0.01),
             box("shield", (0.95, 0.82, 0.14), (0.8, 0, 0.21), shield, 0.03),
             box("usb", (0.34, 0.42, 0.16), (-1.5, 0, 0.16), shield, 0.06),
             box("chip", (0.32, 0.32, 0.06), (-0.75, 0.15, 0.11), chip, 0.01),
             box("regulator", (0.2, 0.26, 0.08), (-0.35, -0.25, 0.12), chip, 0.01),
             box("led", (0.08, 0.06, 0.05), (-1.1, -0.38, 0.105), led, 0.01)]
    # Antenna: a meander trace at the end of the module.
    for k in range(5):
        parts.append(box(f"ant{k}", (0.04, 0.6, 0.012), (1.45 + k * 0.05, 0, 0.145), trace, 0.0))
    for side in (-1, 1):
        for i in range(15):
            x = -1.4 + i * 0.2
            parts.append(box(f"header{side}{i}", (0.18, 0.16, 0.16), (x, side * 0.54, 0.16), chip, 0.01))
            parts.append(box(f"pin{side}{i}", (0.05, 0.05, 0.2), (x, side * 0.54, 0.34), pin, 0.0))
    group(parts, rotation=(0, 0, math.radians(-6)))


def coins():
    silver, edge = mat("silver", "#d0d7de", 0.25, 1.0), mat("edge", "#8c959f", 0.35, 1.0)
    green = mat("trend", GREEN, 0.4)
    parts = []
    for s, (x, n) in enumerate(((-1.6, 3), (-0.3, 6), (1.0, 10))):
        for k in range(n):
            jitter = ((k * 37 + s * 11) % 7 - 3) * 0.012
            parts.append(cylinder(f"coin{s}{k}", 0.52, 0.11, (x + jitter, jitter, 0.06 + k * 0.12),
                                  silver if k % 2 else edge, bevel=0.02))
    # Forecast arrow rising over the stacks.
    shaft = box("shaft", (3.6, 0.09, 0.09), (-0.2, -0.75, 1.75), green, 0.03)
    shaft.rotation_euler = (0, math.radians(-17), 0)
    head = cone("head", 0.24, 0.45, (1.68, -0.75, 2.32), green, rot=(0, math.radians(73), 0))
    parts += [shaft, head]
    group(parts)


def microphone():
    metal, grille = mat("metal", "#6e7681", 0.3, 1.0), mat("grille", "#adbac7", 0.45, 1.0)
    dark, green = mat("dark", "#22272e", 0.5), mat("wave", GREEN, 0.4)
    parts = [cylinder("base", 0.7, 0.12, (-1.1, 0, 0.06), dark, bevel=0.03),
             cylinder("stand", 0.06, 0.9, (-1.1, 0, 0.55), metal),
             cylinder("body", 0.3, 1.3, (-1.1, 0, 1.55), metal, bevel=0.03),
             cylinder("capsule", 0.36, 0.7, (-1.1, 0, 2.45), grille, bevel=0.02),
             sphere("cap", 0.36, (-1.1, 0, 2.8), grille, scale=(1, 1, 0.55)),
             cylinder("band", 0.37, 0.08, (-1.1, 0, 2.1), dark, bevel=0.01)]
    for i, h in enumerate((0.5, 1.1, 1.8, 2.4, 1.6, 2.1, 1.2, 0.7, 0.4)):
        parts.append(box(f"wave{i}", (0.16, 0.16, h), (0.0 + i * 0.3, 0, h / 2), green if i % 3 else mat("wd", GREEN_DARK, 0.4), 0.06))
    group(parts)


MODELS = {"pac-1dcnn": bearing, "semantic-segmentation": car, "iot-fire-detection": esp32,
          "agentic-ledger": coins, "audict": microphone}


# ---------------------------------------------------------------- staging
def frame_camera(scene):
    """Orthographic camera along VIEW, fitted to every visible object's bounding box."""
    bpy.context.view_layer.update()
    cam = bpy.data.objects.new("camera", bpy.data.cameras.new("camera"))
    cam.data.type = "ORTHO"
    cam.rotation_euler = VIEW
    scene.collection.objects.link(cam)
    scene.camera = cam
    bpy.context.view_layer.update()
    right, up, forward = (cam.matrix_world.to_3x3() @ Vector(v) for v in ((1, 0, 0), (0, 1, 0), (0, 0, -1)))
    points = [o.matrix_world @ Vector(c) for o in scene.objects
              if o.type == "MESH" and not o.is_shadow_catcher for c in o.bound_box]
    xs, ys = [p.dot(right) for p in points], [p.dot(up) for p in points]
    aspect = SIZE[0] / SIZE[1]
    width, height = max(xs) - min(xs), max(ys) - min(ys)
    cam.data.ortho_scale = max(width, height * aspect) * 1.12
    centre = right * (max(xs) + min(xs)) / 2 + up * (max(ys) + min(ys)) / 2
    depth = sum(p.dot(forward) for p in points) / len(points)
    cam.location = centre + forward * (depth - 40)


def stage(scene, samples):
    bpy.context.view_layer.update()  # world matrices of the posed models are stale until evaluated
    floor_z = min((o.matrix_world @ Vector(c)).z for o in scene.objects if o.type == "MESH" for c in o.bound_box)
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, floor_z))
    bpy.context.active_object.is_shadow_catcher = True
    for name, energy, size, loc, rot in (
        ("key", 900, 6, (-6, -6, 9), (math.radians(45), 0, math.radians(-45))),
        ("fill", 300, 8, (8, -4, 5), (math.radians(60), 0, math.radians(60))),
        ("rim", 500, 4, (2, 8, 6), (math.radians(-60), 0, math.radians(165))),
    ):
        light = bpy.data.objects.new(name, bpy.data.lights.new(name, "AREA"))
        light.data.energy, light.data.size = energy, size
        light.location, light.rotation_euler = loc, rot
        scene.collection.objects.link(light)
    world = bpy.data.worlds.new("world")
    if world.node_tree is None:
        world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.55, 0.57, 0.6, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6
    scene.world = world
    frame_camera(scene)

    scene.render.engine = "CYCLES"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.film_transparent = True
    scene.render.resolution_x, scene.render.resolution_y = SIZE
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "WEBP"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.quality = 88
    scene.view_settings.view_transform = "Standard"
    use_gpu(scene)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=MODELS)
    parser.add_argument("--samples", type=int, default=160)
    args = parser.parse_args(argv)
    out_dir = os.path.join(ROOT, "assets", "thumbs")
    os.makedirs(out_dir, exist_ok=True)
    for slug, build in MODELS.items():
        if args.only and slug != args.only:
            continue
        bpy.ops.wm.read_factory_settings(use_empty=True)
        build()
        scene = bpy.context.scene
        stage(scene, args.samples)
        scene.render.filepath = os.path.join(out_dir, f"{slug}.webp")
        bpy.ops.render.render(write_still=True)
        print(f"Saved {scene.render.filepath}")


if __name__ == "__main__":
    main()
