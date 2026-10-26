#!/usr/bin/env python3
"""Render exported *native C++* scene data on the CPU for integration review.

This is not a Metal execution or a device screenshot. It reproduces the
inspection renderer's documented sampling/blending/depth choices approximately
using NumPy arithmetic. Hardware raster precision and edge rounding may differ.
The export and generated images contain original artwork: keep them out of Git.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sample(texture: np.ndarray, uv: np.ndarray) -> np.ndarray:
    height, width, _ = texture.shape
    # Normalized Metal coordinates: texel centers are (i + 0.5) / size.
    x = np.clip(uv[:, 0] * width - 0.5, 0, width - 1)
    y = np.clip(uv[:, 1] * height - 0.5, 0, height - 1)
    x0, y0 = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    x1, y1 = np.minimum(x0 + 1, width - 1), np.minimum(y0 + 1, height - 1)
    fx, fy = (x - x0)[:, None], (y - y0)[:, None]
    return ((texture[y0, x0] * (1 - fx) + texture[y0, x1] * fx) * (1 - fy)
            + (texture[y1, x0] * (1 - fx) + texture[y1, x1] * fx) * fy)


def edge(a: np.ndarray, b: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    return (b[0] - a[0]) * (y - a[1]) - (b[1] - a[1]) * (x - a[0])


def top_left(a: np.ndarray, b: np.ndarray) -> bool:
    return bool(b[1] < a[1] or (b[1] == a[1] and b[0] > a[0]))


def render(scene: dict, textures: dict[int, np.ndarray]) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    width, height = scene["width"], scene["height"]
    color = np.empty((height, width, 4), dtype=np.float64)
    color[:] = scene["clear_rgba"]
    depth = np.full((height, width), scene["depth_clear"], dtype=np.float64)
    owner = np.full((height, width), -1, dtype=np.int32)
    terrain_only = None
    reports = []
    for draw_index, draw in enumerate(scene["draws"]):
        vertices = np.asarray(draw["vertices_position_xyzw_uv"], dtype=np.float64)
        clip = np.asarray(draw["clip_positions_xyzw"], dtype=np.float64)
        if (vertices.ndim != 2 or vertices.shape[1] != 6 or len(vertices) > 1_000_000
                or len(vertices) % 3 or clip.shape != (len(vertices), 4)
                or not np.isfinite(vertices).all() or not np.isfinite(clip).all()
                or np.any(clip[:, 3] <= 0)):
            raise ValueError("unsupported or malformed exported triangle list")
        inverse_w = 1 / clip[:, 3]
        ndc = clip[:, :3] * inverse_w[:, None]
        screen = np.column_stack(((ndc[:, 0] * 0.5 + 0.5) * width,
                                  (0.5 - ndc[:, 1] * 0.5) * height))
        candidate = np.zeros((height, width), dtype=bool)
        passed = np.zeros((height, width), dtype=bool)
        color_before = color.copy()
        report = {key: draw[key] for key in ("kind", "texture", "unit_index", "type", "tile",
                                             "descriptor_id", "animation", "frame") if key in draw}
        report.update(triangles=len(vertices) // 3, degenerate_triangles=0,
                      covered_fragments=0, alpha_surviving_fragments=0,
                      depth_passing_fragments=0,
                      screen_bounds_xyxy=[float(screen[:, 0].min()), float(screen[:, 1].min()),
                                          float(screen[:, 0].max()), float(screen[:, 1].max())],
                      clip_depth_range=[float(ndc[:, 2].min()), float(ndc[:, 2].max())],
                      vertices_inside_frustum=int(np.sum((np.abs(ndc[:, 0]) <= 1)
                                                        & (np.abs(ndc[:, 1]) <= 1)
                                                        & (ndc[:, 2] >= 0) & (ndc[:, 2] <= 1))),
                      vertices_total=len(vertices))
        texture = textures[draw["texture"]]
        for start in range(0, len(vertices), 3):
            indices = np.arange(start, start + 3)
            points = screen[indices]
            area = float(edge(points[0], points[1], points[2, 0], points[2, 1]))
            if abs(area) < 1e-12:
                report["degenerate_triangles"] += 1
                continue
            if area < 0:
                indices = indices[[0, 2, 1]]
                points = screen[indices]
                area = -area
            x0, y0 = np.maximum(np.floor(points.min(axis=0)).astype(np.int64), [0, 0])
            x1, y1 = np.minimum(np.ceil(points.max(axis=0)).astype(np.int64), [width, height])
            if x0 >= x1 or y0 >= y1:
                continue
            yy, xx = np.mgrid[y0:y1, x0:x1]
            weights = []
            inside = np.ones(xx.shape, dtype=bool)
            for a, b in ((1, 2), (2, 0), (0, 1)):
                value = edge(points[a], points[b], xx + 0.5, yy + 0.5)
                inside &= (value > 0) | ((value == 0) & top_left(points[a], points[b]))
                weights.append(value / area)
            if not inside.any():
                continue
            ix, iy = xx[inside], yy[inside]
            barycentric = np.column_stack([weight[inside] for weight in weights])
            z = barycentric @ ndc[indices, 2]
            clip_ok = (z >= 0) & (z <= 1)
            ix, iy, z, barycentric = ix[clip_ok], iy[clip_ok], z[clip_ok], barycentric[clip_ok]
            report["covered_fragments"] += len(ix)
            if not len(ix):
                continue
            uv = ((barycentric @ (vertices[indices, 4:] * inverse_w[indices, None]))
                  / (barycentric @ inverse_w[indices])[:, None])
            rgba = sample(texture, uv) * draw["tint"]
            # Match the shader's float literal; 1/255 rounds upward in float32.
            alpha_ok = rgba[:, 3] > float(np.float32(scene["alpha_discard_threshold"]))
            ix, iy, z, rgba = ix[alpha_ok], iy[alpha_ok], z[alpha_ok], rgba[alpha_ok]
            candidate[iy, ix] = True
            report["alpha_surviving_fragments"] += len(ix)
            depth_ok = z <= depth[iy, ix]
            ix, iy, z, rgba = ix[depth_ok], iy[depth_ok], z[depth_ok], rgba[depth_ok]
            passed[iy, ix] = True
            report["depth_passing_fragments"] += len(ix)
            alpha = rgba[:, 3, None]
            color[iy, ix, :3] = rgba[:, :3] * alpha + color[iy, ix, :3] * (1 - alpha)
            color[iy, ix, 3] = rgba[:, 3] + color[iy, ix, 3] * (1 - rgba[:, 3])
            if draw["depth_write"]:
                depth[iy, ix] = z
            owner[iy, ix] = draw_index
        report["unique_alpha_candidate_pixels"] = int(candidate.sum())
        report["unique_depth_passing_pixels"] = int(passed.sum())
        report["pixels_changed_at_least_half_8bit_step"] = int(
            np.any(np.abs(color - color_before) >= 0.5 / 255, axis=2).sum())
        reports.append(report)
        if draw["kind"] == "terrain":
            terrain_only = color.copy()
    for index, report in enumerate(reports):
        final_mask = owner == index
        report["final_pixels_with_draw_as_last_contributor"] = int(final_mask.sum())
        coords = np.argwhere(final_mask)
        report["final_visible_pixel_bounds_xyxy"] = (None if not len(coords) else
            [int(coords[:, 1].min()), int(coords[:, 0].min()),
             int(coords[:, 1].max()) + 1, int(coords[:, 0].max()) + 1])
    if terrain_only is None:
        raise ValueError("export has no terrain draw")
    return color, terrain_only, reports


def save_png(path: Path, pixels: np.ndarray) -> None:
    Image.fromarray(np.round(np.clip(pixels, 0, 1) * 255).astype(np.uint8)).save(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export", type=Path, help="scene.json emitted by the native scene_export tool")
    parser.add_argument("--out", required=True, type=Path, help="new output directory")
    args = parser.parse_args()
    scene = json.loads(args.export.read_text())
    if scene.get("schema") != 1 or not 0 < scene["width"] <= 4096 or not 0 < scene["height"] <= 4096:
        raise ValueError("unsupported export profile")
    textures, texture_report = {}, []
    for item in scene["textures"]:
        path = args.export.parent / item["file"]
        if path.parent.resolve() != args.export.parent.resolve():
            raise ValueError("texture path must be a sibling of scene.json")
        data = path.read_bytes()
        if len(data) != item["width"] * item["height"] * 4:
            raise ValueError("texture byte count mismatch")
        pixels = np.frombuffer(data, dtype=np.uint8).reshape(item["height"], item["width"], 4)
        textures[item["resource_id"]] = pixels.astype(np.float64) / 255
        texture_report.append({**item, "sha256": sha(path)})
    args.out.mkdir(parents=False, exist_ok=False)
    color, terrain, reports = render(scene, textures)
    scene_path = args.out / "cpu_reference_scene.png"
    terrain_path = args.out / "cpu_reference_terrain.png"
    save_png(scene_path, color)
    save_png(terrain_path, terrain)
    report = {
        "kind": "CPU reference of new native C++ scene, not native Metal screenshot",
        "device_or_metal_execution": False,
        "original_camera_parity": False,
        "original_gameplay_execution": False,
        "camera": scene["camera_kind"],
        "viewport_pixels": [scene["width"], scene["height"]],
        "animation_elapsed_ms": scene["animation_elapsed_ms"],
        "scene_json_sha256": sha(args.export),
        "renderer_source_sha256": sha(Path(__file__)),
        "scene_png_sha256": sha(scene_path),
        "terrain_png_sha256": sha(terrain_path),
        "native_textures": texture_report,
        "draws": reports,
        "limits": [
            "Inspection camera, not recovered original playable camera.",
            "NumPy software rasterization; not Metal shader compilation, GPU execution, or XR evidence.",
            "Pixel-edge/subpixel/depth/texture arithmetic may differ from hardware precision and rounding.",
            "Initial animation frame only; no gameplay, timing, UIKit controls, or display performance evaluated.",
            "Known native terrain omissions (including outside-map padding) remain unchanged.",
        ],
    }
    (args.out / "render_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"image": str(scene_path), "draws": reports}, indent=2))


if __name__ == "__main__":
    main()
