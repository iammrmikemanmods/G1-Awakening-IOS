#!/usr/bin/env python3
"""Compare native rigid geometry against an independent original-data reader.

Matrix comparisons use independent double-precision Rodrigues math, with an
explicit tolerance; this is not an original-engine bit-identity claim.
Vertex and image bytes are compared exactly for the supplied static asset.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import subprocess

import reference


def f32(value): return struct.unpack("<f", struct.pack("<f", value))[0]
def digest(value): return hashlib.sha256(value).hexdigest()


def multiply(a, b):
    return [sum(a[k * 4 + row] * b[col * 4 + k] for k in range(4))
            for col in range(4) for row in range(4)]


def matrix(obj):
    x, y, z = obj["axis"]
    angle = math.radians(obj["angle"])
    result = [float(i % 5 == 0) for i in range(16)]
    if angle:
        norm = math.sqrt(x * x + y * y + z * z)
        x, y, z = x / norm, y / norm, z / norm
        c, s = math.cos(angle), math.sin(angle)
        q = 1 - c
        result = [c+x*x*q, y*x*q+z*s, z*x*q-y*s, 0,
                  x*y*q-z*s, c+y*y*q, z*y*q+x*s, 0,
                  x*z*q+y*s, y*z*q-x*s, c+z*z*q, 0, 0, 0, 0, 1]
    for col in range(3):
        for row in range(3): result[col * 4 + row] *= obj["scale"][col]
    result[12:15] = obj["translation"]
    raw = obj["matrix_row_major"]
    return multiply(result, [raw[row * 4 + col] for col in range(4) for row in range(4)])


def image_rgba(obj):
    components = {96: 1, 97: 1, 98: 2, 99: 3, 100: 4}[obj["format"]]
    palette, pixels = obj["palette"], obj["pixels"]
    result = bytearray()
    for index in range(obj["width"] * obj["height"]):
        position = pixels[index] * components if palette else index * components
        pixel = (palette if palette else pixels)[position:position + components]
        if obj["format"] == 96: rgba = [255, 255, 255, pixel[0]]
        elif obj["format"] == 97: rgba = [pixel[0]] * 3 + [255]
        elif obj["format"] == 98: rgba = [pixel[0]] * 3 + [pixel[1]]
        elif obj["format"] == 99: rgba = pixel + [255]
        else: rgba = pixel
        result.extend(rgba)
    return bytes(result)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--native-probe", type=Path, required=True)
    parser.add_argument("--user-id", type=int, required=True)
    parser.add_argument("--private-export", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = args.model.read_bytes()
    objects = reference.parse(source)
    roots = [o["index"] for o in objects[1:] if o.get("user_id") == args.user_id]
    if len(roots) != 1: raise ValueError("ambiguous independent root")
    parents = {}
    for obj in objects[1:]:
        for child in obj.get("children", []):
            if child in parents: raise ValueError("multiply parented original node")
            parents[child] = obj["index"]
    command = [str(args.native_probe.resolve()), str(args.model.resolve()), "--user-id", str(args.user_id),
               "--export", str(args.private_export.resolve())]
    actual = json.loads(subprocess.run(command, check=True, capture_output=True, text=True, timeout=30).stdout)
    if actual["objects"] != len(objects) - 1 or actual["root"] != roots[0]:
        raise ValueError("native object/root identity differs")
    maximum_matrix_error = 0.
    matrix_scalars = 0
    for node in actual["nodes"]:
        obj = objects[node["index"]]
        if node["parent"] != parents.get(node["index"]) or node["children"] != obj.get("children", []):
            raise ValueError("native hierarchy differs")
        expected = matrix(obj)
        for a, b in zip(node["local_matrix"], expected):
            maximum_matrix_error = max(maximum_matrix_error, abs(a - b)); matrix_scalars += 1
    matrices = {}

    def world_matrix(index):
        if index not in matrices:
            value = matrix(objects[index])
            if index in parents: value = multiply(world_matrix(parents[index]), value)
            matrices[index] = value
        return matrices[index]

    surfaces = []

    def visit(index, enabled=True):
        obj = objects[index]
        enabled = enabled and obj.get("render_enabled", True)
        if not enabled: return
        if obj["type"] == 14 and obj.get("scope", 0xffffffff):
            for part, (indices, appearance) in enumerate(obj["submeshes"]):
                if appearance: surfaces.append((obj, part, indices, appearance))
        for child in obj.get("children", []): visit(child, enabled)

    visit(roots[0])
    if len(surfaces) != len(actual["surfaces"]): raise ValueError("surface count differs")
    compared_bytes = compared_vertices = 0
    comparisons = []
    for number, (expected, native) in enumerate(zip(surfaces, actual["surfaces"])):
        obj, part, index_id, appearance_id = expected
        if (obj["index"], part, obj["vertex_buffer"], index_id, appearance_id) != (
                native["mesh"], native["submesh"], native["vertex_buffer"], native["index_buffer"], native["appearance"]):
            raise ValueError("surface references differ")
        for a, b in zip(native["model"], world_matrix(obj["index"])):
            maximum_matrix_error = max(maximum_matrix_error, abs(a - b)); matrix_scalars += 1
        buffer, indices, appearance = objects[obj["vertex_buffer"]], objects[index_id], objects[appearance_id]
        positions = objects[buffer["positions"]]
        colors = objects[buffer["colors"]] if buffer["colors"] else None
        normals = objects[buffer["normals"]] if buffer["normals"] else None
        texture = objects[appearance["textures"][0]] if appearance["textures"] else None
        texcoords = objects[buffer["texcoords"][0]["array"]] if texture else None
        if texture and matrix(texture) != [float(i % 5 == 0) for i in range(16)]:
            raise ValueError("exact-byte reference currently requires an identity texture transform")
        vertex_indices = indices["indices"]
        if indices["encoding"] < 128:
            vertex_indices = list(range(vertex_indices[0], vertex_indices[0] + sum(indices["strip_lengths"])))
        triangle_indices, start = [], 0
        for length in indices["strip_lengths"]:
            for triangle in range(length - 2):
                tri = vertex_indices[start + triangle:start + triangle + 3]
                if triangle & 1: tri[0], tri[1] = tri[1], tri[0]
                triangle_indices.extend(tri)
            start += length
        raw = bytearray()
        for index in triangle_indices:
            p = [f32(f32(positions["values"][index * 3 + c] * buffer["position_scale"]) + buffer["position_bias"][c])
                 for c in range(3)] + [1.]
            n = [0., 0., 0., 0.]
            if normals:
                n[:3] = [f32((2 * normals["values"][index * 3 + c] + 1) / (255 if normals["component_size"] == 1 else 65535))
                         for c in range(3)]
            color = [f32(v / 255) for v in buffer["default_color"]]
            if colors:
                color = [f32((v & 255) / 255) for v in colors["values"][index * colors["components"]:(index + 1) * colors["components"]]]
                if len(color) == 3: color.append(1.)
            uv = [0., 0., 0., 1.]
            if texcoords:
                mapping = buffer["texcoords"][0]
                for c in range(texcoords["components"]):
                    uv[c] = f32(f32(texcoords["values"][index * texcoords["components"] + c] * mapping["scale"]) + mapping["bias"][c])
            raw.extend(struct.pack("<16f", *(p + n + color + uv)))
        native_bytes = (args.private_export / f"surface_{number}.f32").read_bytes()
        if bytes(raw) != native_bytes:
            offset = next(i for i, (a, b) in enumerate(zip(raw, native_bytes)) if a != b) if len(raw) == len(native_bytes) else -1
            raise ValueError(f"surface {number} exact vertex bytes differ at byte {offset}")
        compared_bytes += len(raw); compared_vertices += len(triangle_indices)
        comparisons.append({"mesh": obj["index"], "submesh": part, "vertices": len(triangle_indices),
                            "geometry_sha256": digest(raw)})
    if maximum_matrix_error > 0.00002:
        raise ValueError(f"matrix comparison exceeds explicit tolerance: {maximum_matrix_error}")
    image_comparisons = []
    for image in actual["images"]:
        data = image_rgba(objects[image["object"]])
        if data != (args.private_export / f"image_{image['object']}.rgba").read_bytes():
            raise ValueError("RGBA image bytes differ")
        image_comparisons.append({**image, "rgba_sha256": digest(data), "bytes": len(data)})
    report = {
        "scope": "Native serialized rigid subtree geometry versus independent original-data decoder",
        "model_sha256": digest(source), "native_probe_sha256": digest(args.native_probe.read_bytes()),
        "user_id": args.user_id, "root_object": roots[0], "objects": len(objects) - 1,
        "mesh_count": len({s[0]["index"] for s in surfaces}), "surface_count": len(surfaces),
        "vertex_count": compared_vertices, "exact_vertex_bytes_compared": compared_bytes,
        "matrix_scalar_comparisons": matrix_scalars, "maximum_matrix_absolute_error": maximum_matrix_error,
        "matrix_tolerance": 0.00002, "matrix_reference": "Independent double Rodrigues/TRSM and hierarchy, not original engine execution",
        "surfaces": comparisons, "images": image_comparisons,
        "serialized_pose_only": True, "animation_evaluated": False,
        "gpu_execution": False, "iphone_tested": False, "passed": True,
        "source_sha256": {p.name: digest(p.read_bytes()) for p in (Path(__file__), Path(reference.__file__))},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("passed", "mesh_count", "surface_count", "vertex_count",
                     "exact_vertex_bytes_compared", "maximum_matrix_absolute_error")}))


if __name__ == "__main__": main()
