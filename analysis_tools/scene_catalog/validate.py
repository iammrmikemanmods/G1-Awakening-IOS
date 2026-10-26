#!/usr/bin/env python3
"""Build portable scene loaders and check privately supplied original data.

No original executable, CPU emulator, Apple SDK or GPU is used. Proprietary
inputs are supplied by the operator; none is copied into the repository.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--terrain", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--compiler", default="g++")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    native = root / "native"
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    build = out / "build"
    build.mkdir(exist_ok=True)
    source_names = ["Archive", "Atlas", "Image", "SpriteGeometry", "Terrain",
                    "World", "Mission", "Movement", "Scene", "InitialPresentation",
                    "SpritePlacement"]
    sources = [native / "src" / (name + ".cpp") for name in source_names]
    sources.append(native / "third_party/lodepng/lodepng.cpp")
    flags = ["-std=c++17", "-O1", "-Wall", "-Wextra", "-Wconversion", "-Werror",
             "-I", str(native / "include"), "-I", str(native / "third_party/lodepng")]
    commands, objects = [], []
    for source in sources:
        obj = build / (source.stem + ".o")
        command = [args.compiler, *flags, "-c", str(source), "-o", str(obj)]
        # Third-party decoder is unchanged and has its own compiler conventions.
        if source.name == "lodepng.cpp":
            command = [args.compiler, "-std=c++17", "-O1", "-c", str(source), "-o", str(obj)]
        commands.append(command)
        subprocess.run(command, check=True, capture_output=True, text=True)
        objects.append(obj)
    results = {}
    for name in ("scene_probe", "scene_catalog_probe"):
        source = native / "tools" / (name + ".cpp")
        sources.append(source)
        executable = out / name
        command = [args.compiler, *flags, str(source), *map(str, objects), "-lz", "-o", str(executable)]
        commands.append(command)
        subprocess.run(command, check=True, capture_output=True, text=True)
        command = [str(executable), str(args.archive.resolve()), str(args.terrain.resolve())]
        run = subprocess.run(command, check=True, capture_output=True, text=True)
        result = json.loads(run.stdout)
        (out / (name + ".json")).write_text(json.dumps(result, indent=2) + "\n")
        results[name] = result
    baseline_path = native / "research/scene_validation/first_scene_load.json"
    baseline = json.loads(baseline_path.read_text())
    if results["scene_probe"] != baseline:
        raise RuntimeError("existing first-scene report differs from the frozen baseline")
    atlas_reference_path = native / "research/atlas_validation/native_atlas_validation.json"
    reference = json.loads(atlas_reference_path.read_text())
    by_id = {row["resource_id"]: row for row in reference["source_matches"]}
    for sprite in results["scene_catalog_probe"]["types"]:
        expected = by_id[sprite["descriptor"]]
        if sprite["frames"] != expected["frames"] or sprite["animations"] != expected["animations"]:
            raise RuntimeError("catalog metadata differs from independent descriptor reference")
    sources.extend([native / "include/g1/Scene.hpp", Path(__file__).resolve()])
    report = {
        "scope": "Portable native scene construction, exact first-scene regression and actual asset coverage",
        "compiler": subprocess.run([args.compiler, "--version"], check=True, capture_output=True,
                                   text=True).stdout.splitlines()[0],
        "archive_sha256": sha(args.archive), "terrain_tables_sha256": sha(args.terrain),
        "commands": commands,
        "source_sha256": {str(path.relative_to(root)): sha(path) for path in sources},
        "first_scene_unchanged": True, "baseline_sha256": sha(baseline_path),
        "descriptor_reference_sha256": sha(atlas_reference_path),
        "descriptor_reference_matches": len(results["scene_catalog_probe"]["types"]),
        "catalog": results["scene_catalog_probe"],
        "apple_compilation_performed": False, "gpu_execution": False,
        "device_performance_verified": False, "campaign_completion_verified": False,
    }
    (out / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    for obj in objects:
        obj.unlink()
    build.rmdir()
    print(json.dumps({key: report[key] for key in (
        "first_scene_unchanged", "descriptor_reference_matches", "apple_compilation_performed")}))
    print(json.dumps({key: report["catalog"][key] for key in (
        "supported_map_style_pairs", "unsupported_map_style_pairs", "all_frame_vertices")}))


if __name__ == "__main__":
    main()
