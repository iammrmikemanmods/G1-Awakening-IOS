#!/usr/bin/env python3
"""Compare native transient terrain pools with independent original execution.

Only synthetic input/results go into the portable fixture. Original grid/config
payloads remain local; actual-resource evidence contains hashes and counts only.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

from decorations_oracle import OriginalDecorations
from animated_map_oracle import decode_config, GRID_IDS, CONFIG_SHA, TABLES_SHA
from geometry_oracle import IMAGE_SHA, LIBGCC_SHA, digest

STEPS = [0, 249, 1, 250, 1000, 0, 1, 249, 250, 250, 250, 250, 250, 250, 250, 250]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def synthetic(index):
    width, height = 3 + index % 5, 2 + (index // 5) % 4
    gate = 1 + index % 5
    eligible = [1, 2]
    cells = [(i * 7 + index + i // width) % 4 for i in range(width * height)]
    records = [[14, 0, 2, 3, 0], [5, 14, 4, 14, 254],
               [8, 0, 14, 0, 255], [3, 2, 1, 0, 1]]
    if index % 8 == 0:  # Capacity exists but top14 suppresses all registration.
        cells = [1] * len(cells)
        records[1] = [14, 2, 3, 4, 254]
    elif index % 8 == 1:  # No fixed faces; all initial strips belong to the pool.
        cells = [1] * len(cells)
        records[1] = [5, 2, 3, 4, 255]
        gate = 0
    elif index % 8 == 2:  # Clock with no transient slots consumes no random words.
        eligible = []
        cells = [0] * len(cells)
    tables = bytearray(480)
    for i, record in enumerate(records):
        tables[160 + i*5:165 + i*5] = bytes(record)
    config = bytes([3, 0, len(eligible), *eligible, 0, 0, gate, *([0] * gate), 0])
    seeds = [0, 1, 0x47413133, 0xffffffff]
    return bytes([width, height, *cells]), bytes(tables), config, seeds[index % 4]


def native_run(probe, grid, tables, config, seed):
    words = ["G1_TERRAIN_DECORATION_INPUT_V1", str(seed)]
    for data in (grid, tables, config):
        words.extend([str(len(data)), *map(str, data)])
    words.extend([str(len(STEPS)), *map(str, STEPS)])
    result = subprocess.run([str(probe.resolve())], input=" ".join(words), text=True,
                            capture_output=True, check=True, timeout=15)
    return json.loads(result.stdout)


def fixture_case(name, seed, grid, tables, config, original, snapshots, final_words):
    lines = [f"CASE {name} {seed}"]
    for data in (grid, tables, config):
        lines.append("DATA " + " ".join(map(str, [len(data), *data])))
    lines.append("LAYOUT " + " ".join(map(str, [original.capacity, original.registered_candidates,
        original.total_mesh_quads, original.slots, len(original.initial_records), *original.initial_records])))
    lines.append("STATES " + str(len(snapshots)))
    for i, state in enumerate(snapshots):
        words = ["STATE", 0 if i == 0 else STEPS[i-1], state["accumulated_ms"], state["phase"],
                 state["random_index"], state["random_draws"], len(state["candidate_records"]),
                 *state["candidate_records"], len(state["slot_offsets"])]
        for j in range(len(state["slot_offsets"])):
            words.extend([state["slot_phases"][j], state["slot_offsets"][j],
                          *state["positions"][j], *state["uv"][j]])
        lines.append(" ".join(map(str, words)))
    lines.append("RNG " + " ".join(map(str, final_words)))
    lines.append("END")
    return "\n".join(lines)


def check_case(name, seed, grid, tables, config, image, gcc, probe, fixture):
    original = OriginalDecorations(image, gcc)
    layout = original.setup_pool(grid, decode_config(config), tables, seed)
    states = [original.snapshot()] + [original.advance(delta) for delta in STEPS]
    final_words = list(struct.unpack("<624I", original.u.mem_read(original.rng + 0x14, 624 * 4)))
    native = native_run(probe, grid, tables, config, seed)
    for key, value in native["layout"].items():
        if value != layout[key]:
            raise RuntimeError(f"{name}: native/original layout {key} differs")
    if len(native["snapshots"]) != len(states):
        raise RuntimeError(f"{name}: native/original snapshot count differs")
    scalar_checks = 0
    for i, (actual, expected) in enumerate(zip(native["snapshots"], states)):
        words = actual.pop("random_words")
        actual["random_words_sha256"] = digest(struct.pack("<624I", *words))
        for key, value in actual.items():
            if value != expected[key]:
                raise RuntimeError(f"{name}: snapshot{i} native/original {key} differs")
        scalar_checks += len(expected["candidate_records"]) + original.slots * 22 + 4 + 624
    original.check_text()
    if fixture is not None:
        fixture.append(fixture_case(name, seed, grid, tables, config, original, states, final_words))
    return {"name": name, "seed": seed, "grid_sha256": digest(grid),
            "config_sha256": digest(config), "visual_tables_sha256": digest(tables),
            "layout": layout, "snapshots": len(states), "scalar_checks": scalar_checks,
            "final_random_draws": original.pool_draws,
            "failed_selections": sum(p[1] == -1 for state in states for p in state["placements"]),
            "successful_selections": sum(p[1] >= 0 for state in states for p in state["placements"]),
            "initial_unassigned_slots": sum(v < 0 for v in states[0]["slot_offsets"]),
            "original_and_native_snapshots_sha256": digest(canonical([
                {k: v for k, v in state.items() if k != "placements"} for state in states])),
            "original_and_native_rng_sha256": digest(struct.pack("<624I", *final_words)),
            "all_matched": True}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--binary", type=Path, required=True)
    ap.add_argument("--libgcc", type=Path, required=True)
    ap.add_argument("--unicorn-dir", type=Path, required=True)
    ap.add_argument("--native-probe", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--tables", type=Path, required=True)
    ap.add_argument("--fixture", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--synthetic-only", action="store_true")
    args = ap.parse_args()
    sys.path.insert(0, str(args.unicorn_dir))
    import unicorn
    image, gcc = args.binary.read_bytes(), args.libgcc.read_bytes()
    if (digest(image), digest(gcc)) != (IMAGE_SHA, LIBGCC_SHA):
        raise ValueError("source executable differs from audited input")
    lines, synthetic_results, actual_results = [], [], []
    for index in range(24):
        grid, tables, config, seed = synthetic(index)
        result = check_case(f"synthetic_{index:02d}", seed, grid, tables, config,
                            image, gcc, args.native_probe, lines)
        synthetic_results.append(result)
        print(json.dumps({"case": result["name"], "snapshots": result["snapshots"],
                          "draws": result["final_random_draws"], "matched": True}), flush=True)
    args.fixture.parent.mkdir(parents=True, exist_ok=True)
    args.fixture.write_text(f"G1_TERRAIN_DECORATIONS_ORACLE_V1 {len(lines)}\n" + "\n".join(lines) + "\n")
    if not args.synthetic_only:
        manifest = json.loads(args.manifest.read_text())
        resources = {r["resource_id"]: r for r in manifest["resources"] if r["key_hex"] == "0xf4e02223"}
        def resource(rid):
            record = resources[rid]
            data = (args.manifest.parent / "extracted" / record["kind"] / record["extracted_filename"]).read_bytes()
            if digest(data) != record["sha256"]:
                raise ValueError(f"resource{rid} differs from audited manifest")
            return data
        tables, config = args.tables.read_bytes(), resource(307)
        if digest(tables) != TABLES_SHA or digest(config) != CONFIG_SHA:
            raise ValueError("original table/config data differs from pinned inputs")
        for rid in GRID_IDS:
            result = check_case(f"grid{rid}", 0x47413133, resource(rid), tables, config,
                                image, gcc, args.native_probe, None)
            result["grid_resource_id"] = rid
            actual_results.append(result)
            print(json.dumps({"case": result["name"], "snapshots": result["snapshots"],
                              "draws": result["final_random_draws"], "matched": True}), flush=True)
    report = {"scope": "Style1 interior single-batch transient pool, original candidate registration, initial mesh, random selection and clock",
              "original_sha256": IMAGE_SHA, "libgcc_sha256": LIBGCC_SHA,
              "source_ipa_sha256": "b24fbe5cc4d5cb603189a476c4f81dd2a6ecc18b025eae913262055a7fc443fd",
              "unicorn_version": unicorn.__version__, "original_code_readonly_and_unchanged": True,
              "instruction_patches": 0,
              "original_functions": ["0x7acc", "0x7b26", "0x2b43c", "0x64e64", "0x64ebc",
                                     "0x70eb4", "0x71248", "0x714c0", "0x71884", "0x72100", "0x71c20"],
              "original_blocks": ["0x6a3cc..0x6a782", "0x6b1e8..0x6b28c", "0x6b606..0x6b660", "0x6d6ea..0x6d758"],
              "substitutions": ["bounded allocation/free and exact imported memset", "recorded M3G array/object APIs",
                                "engine singleton", "shared RNG singleton returns explicitly seeded original object",
                                "nonthrowing unwind registration", "triangle-strip factory"],
              "random_words_or_selection_hooks": False,
              "synthetic": synthetic_results, "actual": actual_results,
              "synthetic_cases": len(synthetic_results), "actual_cases": len(actual_results),
              "snapshot_count": sum(r["snapshots"] for r in synthetic_results + actual_results),
              "scalar_checks": sum(r["scalar_checks"] for r in synthetic_results + actual_results),
              "all_matched": True, "fixture_sha256": digest(args.fixture.read_bytes()),
              "native_probe_sha256": digest(args.native_probe.read_bytes()),
              "script_sha256": {p.name: digest(p.read_bytes()) for p in [Path(__file__),
                    Path(__file__).with_name("decorations_oracle.py")]},
              "not_established": ["outside camera padding and multi-batch constructor behavior",
                  "complete original update scheduler", "historical wall-clock random seed",
                  "GPU or device execution", "full campaign playthrough"]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report": str(args.output), "snapshots": report["snapshot_count"],
                      "scalar_checks": report["scalar_checks"], "all_matched": True}))


if __name__ == "__main__":
    main()
