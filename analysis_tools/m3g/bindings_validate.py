#!/usr/bin/env python3
"""Generate compact original binding fixtures and audit the native helpers.

Original ARM execution is already frozen in original_bindings.json. This tool
does not execute a guest CPU or copy original assets into any output.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess

import reference


ROOT = Path(__file__).resolve().parents[2]
ORIGINAL = ROOT / "native/research/m3g_validation/original_bindings.json"
ORIGINAL_SHA256 = "d6d39b71189bdd1ed6eb53fff342d516f2fabcf4f5d04d534fd2921f6a33300a"
RESOURCE_IDS = [486, 534, 1212, 408, 699, 444, 492, 1300, 561, 369, 565,
                634, 395, 475, 867, 1039, 631, 795, 967, 564, 1299, 829,
                1201, 1070, 489, 490, 500]
NODE_TYPES = {5, 9, 12, 14, 15, 16, 18, 22}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical_sha(value):
    return sha(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def original():
    data = ORIGINAL.read_bytes()
    if sha(data) != ORIGINAL_SHA256:
        raise ValueError("original binding fixture differs from its frozen pin")
    report = json.loads(data)
    if len(report["names"]) != 34 or len(report["trees"]) != 6:
        raise ValueError("unexpected original binding fixture counts")
    return report


def generate(args):
    source = original()
    lines = ["#pragma once", "", "// Generated only from the frozen original execution fixture.",
             "// SHA256: " + ORIGINAL_SHA256, "#include <array>", "#include <cstddef>",
             "#include <cstdint>", "#include <optional>", "#include <string_view>",
             "#include <vector>", "", "namespace g1_binding_test {",
             "struct NameCase { std::string_view hex; bool transform_suffix; std::uint32_t expected; };",
             "inline constexpr std::array<NameCase,34> names{{"]
    for row in source["names"]:
        lines.append('    {"%s",%s,%dU},' % (row["input_hex"], str(row["transform_suffix"]).lower(), row["result"]))
    lines += ["}};", "struct TreeRow { std::size_t index; std::uint32_t user_id; std::vector<std::uint32_t> children; };",
              "struct TreeCase { std::string_view name; std::vector<TreeRow> rows; std::size_t root; std::uint32_t key; std::optional<std::size_t> expected; };",
              "inline const std::array<TreeCase,6> trees{{"]
    for tree in source["trees"]:
        rows = ["{%d,%dU,{%s}}" % (row["index"], row["user_id"], ",".join(str(i)+"U" for i in row["children"]))
                for row in tree["rows"]]
        result = "std::nullopt" if tree["result"] is None else "std::size_t{%d}" % tree["result"]
        lines.append('    {"%s",{%s},%d,%dU,%s},' % (tree["name"], ",".join(rows), tree["root"], tree["key"], result))
    lines += ["}};", "} // namespace g1_binding_test", ""]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines))
    provenance = {"schema": 1, "original_fixture": "native/research/m3g_validation/original_bindings.json",
        "original_fixture_sha256": ORIGINAL_SHA256, "original_runner_sha256": source["runner_sha256"],
        "original_image_sha256": source["original_image_sha256"],
        "original_libgcc_sha256": source["original_libgcc_sha256"],
        "generator_sha256": sha(Path(__file__).read_bytes()), "fixture_sha256": sha(args.output.read_bytes()),
        "name_cases": 34, "tree_cases": 6,
        "expected_values_source": "Frozen unchanged-original execution outputs; never native implementation outputs",
        "scope": source["boundaries"], "original_execution_repeated": False,
        "contains_original_asset_payload": False}
    args.provenance.parent.mkdir(parents=True, exist_ok=True)
    args.provenance.write_text(json.dumps(provenance, indent=2)+"\n")
    print(json.dumps({"fixture_sha256": provenance["fixture_sha256"], "name_cases": 34, "tree_cases": 6}))


def expected_asset(objects, keys):
    worlds = [obj for obj in objects[1:] if obj["type"] == 22]
    if len(worlds) != 1:
        raise ValueError("binding corpus must have one serialized World")
    world = worlds[0]
    children = world["children"]
    if not children:
        raise ValueError("actual World child0 is absent")
    if objects[children[0]]["type"] in (9, 22):
        root = children[0]
    elif len(children) >= 2 and objects[children[1]]["type"] in (9, 22):
        root = children[1]
    else:
        raise ValueError("actual World does not satisfy the explicit first/second Group data shape")

    # Independent recursive reference on these shallow authored trees. The
    # product's traversal is iterative and additionally validates its forest.
    def first(index, key):
        obj = objects[index]
        if obj["type"] not in NODE_TYPES:
            raise ValueError("non-Node in actual child hierarchy")
        if obj["user_id"] == key:
            return index
        for child in obj.get("children", []):
            found = first(child, key)
            if found is not None:
                return found
        return None

    def camera(name):
        outer = first(root, keys[name])
        if outer is None:
            return None
        o = objects[outer]
        if o["type"] not in (9, 22) or not o.get("children"):
            raise ValueError("actual named model camera lacks the Group interface or child0")
        inner = o["children"][0]
        o = objects[inner]
        if o["type"] not in (9, 22) or not o.get("children"):
            raise ValueError("actual model camera inner child0 lacks the Group interface")
        camera_id = o["children"][0]
        if objects[camera_id]["type"] != 5:
            raise ValueError("actual model camera second child0 is not Camera5")
        return {"transform": outer, "inner_group": inner, "camera": camera_id}

    queries = sorted({obj["user_id"] for obj in objects[1:] if obj["type"] in NODE_TYPES} | {0xffffffff})
    return {"world": world["index"], "ordered_world_children": children,
            "selected_group": root,
            "forms": {"robot": first(root, keys["robot"]), "car": first(root, keys["car"])},
            "model_cameras": {"robot": camera("roboCAM"), "vehicle": camera("vehiCAM")},
            "transform_keys": keys, "node_queries": [[key, first(root, key)] for key in queries]}


class Compare:
    def __init__(self):
        self.checks = 0
        self.difference_count = 0
        self.differences = []

    def equal(self, path, expected, actual):
        if isinstance(expected, dict) and isinstance(actual, dict):
            self.equal(path+".keys", sorted(expected), sorted(actual))
            for key in sorted(expected.keys() & actual.keys()):
                self.equal(path+"."+key, expected[key], actual[key])
        elif isinstance(expected, list) and isinstance(actual, list):
            self.equal(path+".length", len(expected), len(actual))
            for i, (a, b) in enumerate(zip(expected, actual)):
                self.equal(f"{path}[{i}]", a, b)
        else:
            self.checks += 1
            if expected != actual:
                self.difference_count += 1
                if len(self.differences) < 100:
                    self.differences.append({"path": path, "expected": expected, "actual": actual})


def run_test(path):
    before = sha(path.read_bytes())
    run = subprocess.run([str(path.resolve())], capture_output=True, text=True, timeout=30)
    if run.returncode or run.stderr:
        raise ValueError("native binding contract test failed: "+run.stderr[:2000])
    report = json.loads(run.stdout)
    if (report["original_hash_cases"], report["original_tree_cases"], report["original_comparisons"]) != (34, 6, 40):
        raise ValueError("native binding test did not compare the complete original fixture")
    if report["contract_checks"] < 30 or sha(path.read_bytes()) != before:
        raise ValueError("binding test count or binary identity changed")
    return {"sha256": before, "exit_code": 0, "stderr_empty": True, **report}


def audit(args):
    recorded = original()
    keys = {}
    for name in ("robot", "car", "roboCAM", "vehiCAM"):
        matches = [n["result"] for n in recorded["names"] if n["transform_suffix"] and n["input_hex"] == name.encode().hex()]
        if len(matches) != 1:
            raise ValueError("ambiguous original transformed-name key")
        keys[name] = matches[0]
    fixture = ROOT / "native/tests/m3g_bindings_fixture.hpp"
    provenance_path = ROOT / "native/tests/m3g_bindings_fixture_provenance.json"
    provenance = json.loads(provenance_path.read_text())
    if (provenance["original_fixture_sha256"] != ORIGINAL_SHA256 or
        provenance["generator_sha256"] != sha(Path(__file__).read_bytes()) or
        provenance["fixture_sha256"] != sha(fixture.read_bytes())):
        raise ValueError("generated binding fixture provenance differs")
    native = run_test(args.native_test)
    sanitized = run_test(args.ubsan_test)
    for field in ("checks", "original_hash_cases", "original_tree_cases", "original_comparisons", "contract_checks"):
        if native[field] != sanitized[field]:
            raise ValueError("optimized and UBSan binding tests cover different cases")
    manifest_path = args.manifest
    corpus_path = ROOT / "native/research/m3g_validation/battle_corpus_coverage.json"
    manifest = json.loads(manifest_path.read_text())
    corpus = json.loads(corpus_path.read_text())
    records = {row["resource_id"]: row for row in corpus["resources"]}
    if len(corpus["resources"]) != 27 or set(records) != set(RESOURCE_IDS):
        raise ValueError("binding corpus resource set differs")
    probe_sha = sha(args.probe.read_bytes())
    base = args.extracted.resolve()
    compare, results = Compare(), []
    for rid in RESOURCE_IDS:
        members = [r for r in manifest["resources"] if r["resource_id"] == rid and r["key_hex"] == "0xf4e02223"]
        if len(members) != 1 or members[0]["kind"] != "m3g":
            raise ValueError("ambiguous original M3G resource")
        member = members[0]
        path = (base / member["kind"] / member["extracted_filename"]).resolve()
        if base not in path.parents:
            raise ValueError("manifest extraction path escapes input directory")
        data = path.read_bytes()
        if sha(data) != member["sha256"] or member["sha256"] != records[rid]["sha256"]:
            raise ValueError("original resource hash differs")
        expected = expected_asset(reference.parse(data), keys)
        if rid == 490 and expected["forms"]["car"] != 331:
            raise ValueError("resource490 independent outer-duplicate evidence changed")
        run = subprocess.run([str(args.probe.resolve()), str(path)], capture_output=True, text=True, timeout=30)
        compare.equal(str(rid)+".exit", 0, run.returncode)
        row = {"resource_id": rid, "sha256": member["sha256"], "byte_length": len(data),
               "exit_code": run.returncode, "stdout_sha256": sha(run.stdout.encode()),
               "expected_sha256": canonical_sha(expected),
               "world": expected["world"], "ordered_world_children": expected["ordered_world_children"],
               "selected_group": expected["selected_group"],
               "selected_child_index": expected["ordered_world_children"].index(expected["selected_group"]),
               "forms": expected["forms"], "model_cameras": expected["model_cameras"],
               "node_query_count": len(expected["node_queries"]),
               "expected_node_queries_sha256": canonical_sha(expected["node_queries"])}
        if run.returncode:
            row["error"] = run.stderr[:1000]
        else:
            actual = json.loads(run.stdout)
            compare.equal(str(rid), expected, actual)
            row["native_sha256"] = canonical_sha(actual)
            row["exact_equal"] = expected == actual
        results.append(row)
    if sha(args.probe.read_bytes()) != probe_sha:
        raise ValueError("binding probe changed during corpus audit")
    files = ["native/include/g1/M3GBindings.hpp", "native/src/M3GBindings.cpp",
             "native/tests/m3g_bindings_test.cpp", "native/tests/m3g_bindings_fixture.hpp",
             "native/tests/m3g_bindings_fixture_provenance.json", "native/tools/m3g_bindings_probe.cpp",
             "analysis_tools/m3g/bindings_validate.py", "analysis_tools/m3g/reference.py",
             "native/include/g1/M3GScene.hpp", "native/src/M3GScene.cpp"]
    summary = {"resources": len(results), "node_lookup_queries": sum(r["node_query_count"] for r in results),
               "container_selection_counts": dict(sorted(Counter(str(r["selected_child_index"]) for r in results).items())),
               "present_robot_form": sum(r["forms"]["robot"] is not None for r in results),
               "present_car_form": sum(r["forms"]["car"] is not None for r in results),
               "present_robot_camera": sum(r["model_cameras"]["robot"] is not None for r in results),
               "present_vehicle_camera": sum(r["model_cameras"]["vehicle"] is not None for r in results),
               "source_data_checks_including_structure": compare.checks,
               "difference_count": compare.difference_count}
    report = {"schema": 1, "passed": compare.difference_count == 0,
              "scope": "Native reversed-name hash and bounded Node/container/form/model-camera binding helpers",
              "original_fixture_sha256": ORIGINAL_SHA256, "original_runner_sha256": recorded["runner_sha256"],
              "original_image_sha256": recorded["original_image_sha256"],
              "probe_sha256": probe_sha, "native_test": native, "ubsan_test": sanitized,
              "manifest_sha256": sha(manifest_path.read_bytes()), "corpus_sha256": sha(corpus_path.read_bytes()),
              "source_sha256": {p: sha((ROOT/p).read_bytes()) for p in files},
              "resources": results, "summary": summary, "differences": compare.differences,
              "actual_data_scope": "Serialized World child lists explicitly supplied as container-selection data-shape inputs; no claim that serialized World is the original loaded-container class",
              "not_established": ["General Object3D reference traversal beyond Node children",
                  "Original full resource-loader execution",
                  "Cache-hit cloning, reparenting, attachment placement or material changes",
                  "Battle phase/camera-ID selection or scene-camera fallback",
                  "Animation or rendering output", "Apple compilation or GPU/device execution"],
              "original_execution_repeated": False, "gpu_execution": False, "iphone_tested": False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps({"passed": report["passed"], **summary, "original_comparisons": native["original_comparisons"],
                      "contract_checks": native["contract_checks"]}))
    if not report["passed"]:
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    fixture = commands.add_parser("fixture")
    fixture.add_argument("--output", type=Path, required=True)
    fixture.add_argument("--provenance", type=Path, required=True)
    fixture.set_defaults(function=generate)
    validation = commands.add_parser("audit")
    for name in ("probe", "native-test", "ubsan-test", "output"):
        validation.add_argument("--"+name, type=Path, required=True)
    validation.add_argument("--manifest", type=Path, default=ROOT/"research/assets/results/asset_manifest.json")
    validation.add_argument("--extracted", type=Path, default=ROOT/"research/assets/results/extracted")
    validation.set_defaults(function=audit)
    args = parser.parse_args()
    args.function(args)


if __name__ == "__main__":
    main()
