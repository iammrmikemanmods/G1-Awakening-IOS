#!/usr/bin/env python3
"""Compare admitted same-tile actions with unchanged original ARM functions.

Development only: requires a private original executable and external Unicorn.
The native product does not contain either. All seeded game state is synthetic;
the reference runs the original route reset, route, begin, tick and undo bodies.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys

ORIGINAL_SHA256 = "0d510516fe3676ee4a0f4dff60ba64e1c5bf79a0c9800f420b1bbdb1c12febfd"
FUNCTIONS = {"range": 0x50844, "route_reset": 0x4A044, "route": 0x49E90,
             "begin_unit": 0x43E2E, "form_zero_field2_predicate": 0x434E4,
             "tick": 0x4351C, "restore_anchor": 0x4324A, "reset_turn": 0x430FC}
STATE_FIELDS = ["tile_x", "tile_y", "offset_x", "offset_y", "facing", "spent_budget",
                "pending_cost", "route_index", "moving", "timer_ms", "flag_38",
                "anchor_x", "anchor_y", "anchor_facing", "flag_2c", "flag_2d",
                "flag_2f", "flag_39", "flag_3a"]


def cases():
    budgets = [(0, 0), (3, 0), (8, 1), (3, 253), (127, 0), (128, 0), (255, 0), (0, 255)]
    dimensions = [(1, 1), (2, 3), (5, 4), (3, 3)]
    for i in range(64):
        width, height = dimensions[(i // 8) % len(dimensions)]
        x, y = (i * 3) % width, (i * 7) % height
        base, spent = budgets[i % len(budgets)]
        yield {"name": f"same_tile_{i:02}", "width": width, "height": height,
               "unit": {"type": [0, 11, 19][i % 3], "owner": i % 2,
                        "base_budget": base, "spent_budget": spent,
                        "form": (i // 3) % 3, "field6": 0, "x": x, "y": y},
               "terrain": [[1, 0]] * (width * height),
               "active_owners": [None] * (width * height),
               "form0_field2": [-128, -1, 0, 1, 2, 127][i % 6],
               "timer_ms": [-1, 0, 1, 29, 1000, 2147483647][i % 6],
               "facing": i % 4, "flag_38": i % 2,
               "flag_2c": (i // 2) % 2, "flag_2f": (i % 3) * 7,
               "flag_39": (i % 5) * 51,
               # A separately labelled valid stale-origin budget proves that
               # zero travel does not silently replace deferred cost arithmetic.
               "lower_seeded_origin_budget": i >= 48,
               "delta_ms": [[0, 1, 30], [1, 0, 1000], [30, 30, 0],
                            [2147483647, 0, 30]][i % 4]}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--movement-oracle", type=Path, required=True)
    parser.add_argument("--unicorn-dir", type=Path, required=True)
    parser.add_argument("--native-probe", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.unicorn_dir))
    import unicorn
    spec = importlib.util.spec_from_file_location("g1_empty_original_movement", args.movement_oracle)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    image = args.binary.read_bytes()
    if hashlib.sha256(image).hexdigest() != ORIGINAL_SHA256:
        raise SystemExit("Wrong original executable; no oracle execution")
    results, inputs, records, physical = [], [], [], []
    for case in cases():
        old = module.OriginalMovement(image, case)
        read32 = lambda address: struct.unpack("<I", old.uc.mem_read(address, 4))[0]
        readi = lambda address: struct.unpack("<i", old.uc.mem_read(address, 4))[0]
        read8 = lambda address: bytes(old.uc.mem_read(address, 1))[0]
        p = case["unit"]
        form_count = max(1, p["form"]) + 1
        forms = old.alloc(form_count * 8)
        for f in range(form_count):
            stats = [0] * 12
            stats[0] = p["base_budget"]
            stats[2] = case["form0_field2"] if f == 0 else 0
            old.vector_at(forms + 8*f, old.array(stats, 1), len(stats))
        old.vector_at(read32(old.map + 0x174) + 8*p["type"], forms, form_count)
        old.call(FUNCTIONS["range"], [old.map, old.unit])
        origin = [p["x"], p["y"]]
        if case["lower_seeded_origin_budget"]:
            old.write32(old.grid_columns[p["x"]] + 4*p["y"],
                        ((p["base_budget"] - p["spent_budget"]) & 255) // 2)
        remaining = [readi(old.grid_columns[x] + 4*y)
                     for y in range(old.height) for x in range(old.width)]
        capacity = 2 * (old.width + old.height)
        route_records = old.int_vectors([[-1, -1]] * capacity)
        old.vector_at(old.map + 0xC8, route_records, capacity)
        unit_records = old.int_vectors([[-1, -1]] * capacity)
        old.vector_at(old.unit + 0x50, unit_records, capacity)
        old.call(FUNCTIONS["route_reset"], [old.map])
        old.call(FUNCTIONS["route"], [old.map, *origin, *origin])
        count = read32(old.map + 0xD8)
        entries = [[readi(read32(route_records + 8*i)),
                    readi(read32(route_records + 8*i) + 4)] for i in range(2)]
        if count != 0 or entries != [origin, [-1, -1]]:
            raise RuntimeError("Original same-tile route was not origin followed by sentinel")
        physical.append({"name": case["name"], "count": count, "first_two_records": entries})
        old.write32(old.unit + 0x30, case["timer_ms"])
        for offset, value in ((0x48, origin[0]), (0x49, origin[1]),
                              (0x4A, case["facing"]), (0x4B, case["facing"]),
                              (0x38, case["flag_38"]), (0x2C, case["flag_2c"]),
                              (0x2F, case["flag_2f"]), (0x39, case["flag_39"])):
            old.write8(old.unit + offset, value)
        if old.call(FUNCTIONS["form_zero_field2_predicate"], [old.unit]):
            # Literal wrapper 0x513b6 store after executing its original predicate.
            old.write8(old.unit + 0x38, 1)
        old.call(FUNCTIONS["begin_unit"],
                 [old.unit, *origin, old.map + 0xB4, old.map + 0xC8])

        def state():
            u = old.unit
            return [read8(u+0x3B), read8(u+0x3C), readi(u+0x40), readi(u+0x44),
                    read8(u+0x4B), read8(u+0x59), read8(u+0x4C), read8(u+0x58),
                    int(read8(u+8) == 1), readi(u+0x30), read8(u+0x38),
                    read8(u+0x48), read8(u+0x49), read8(u+0x4A), read8(u+0x2C),
                    read8(u+0x2D), read8(u+0x2F), read8(u+0x39), read8(u+0x3A)]

        states = [state()]
        for delta in case["delta_ms"]:
            old.call(FUNCTIONS["tick"], [old.unit, delta])
            states.append(state())
        if states[0][8] != 1 or any(s[8] for s in states[1:]):
            raise RuntimeError("Original same-tile action did not complete on the first tick")
        if any(s[:5] != states[0][:5] for s in states):
            raise RuntimeError("Original same-tile action changed position or facing")
        old.call(FUNCTIONS["restore_anchor"], [old.unit])
        old.call(FUNCTIONS["reset_turn"], [old.unit])
        undo = state()
        if bytes(old.uc.mem_read(0x1000, 0xD1000)) != old.original_text:
            raise RuntimeError("Original executable text changed")
        results.append({"name": case["name"], "status": 1, "route": [],
                        "states": states, "undo": undo})
        case.update(remaining=remaining)
        records.append(case)
        header = [case["name"], old.width, old.height, *origin, *origin,
                  p["type"], p["owner"], p["base_budget"], p["spent_budget"], p["form"],
                  case["form0_field2"], case["timer_ms"], case["facing"], case["flag_38"],
                  case["flag_2c"], case["flag_2f"], case["flag_39"], len(case["delta_ms"])]
        inputs.append(" ".join(map(str, header + remaining + case["delta_ms"])))
    if args.native_probe:
        payload = str(len(inputs)) + "\n" + "\n".join(inputs) + "\n"
        completed = subprocess.run([str(args.native_probe.resolve())], input=payload,
                                   text=True, capture_output=True, check=True)
        native = json.loads(completed.stdout)
        if native != results:
            for a, b in zip(native, results):
                if a != b:
                    raise RuntimeError("Native/original difference: " + json.dumps({"native": a, "original": b}))
            raise RuntimeError("Native/original result count mismatch")
    record = {"kind": "development-only original same-tile movement comparison",
              "original_sha256": ORIGINAL_SHA256, "unicorn_version": unicorn.__version__,
              "oracle_sha256": digest(Path(__file__)),
              "original_movement_oracle_sha256": digest(args.movement_oracle),
              "instruction_patches": 0, "function_stubs": 0,
              "readonly_original_text_verified": True, "synthetic_state": True,
              "full_game_execution": False,
              "native_original_exact_match": True if args.native_probe else None,
              "native_probe_sha256": digest(args.native_probe) if args.native_probe else None,
              "functions": {k: hex(v) for k, v in FUNCTIONS.items()},
              "state_fields": STATE_FIELDS, "case_count": len(records),
              "state_count": sum(len(r["states"]) + 1 for r in results),
              "state_scalar_comparisons": sum((len(r["states"]) + 1) * len(STATE_FIELDS) for r in results),
              "fresh_original_range_cases": sum(not c["lower_seeded_origin_budget"] for c in records),
              "explicitly_seeded_lower_origin_budget_cases": sum(c["lower_seeded_origin_budget"] for c in records),
              "zero_pending_cost_cases": sum(r["states"][0][6] == 0 for r in results),
              "nonzero_pending_cost_cases": sum(r["states"][0][6] != 0 for r in results),
              "all_begin_moving_then_complete_first_tick": True,
              "all_position_and_facing_unchanged": True,
              "physical_original_routes": physical, "cases": records, "results": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({k: record[k] for k in ("case_count", "state_count", "state_scalar_comparisons",
                                            "nonzero_pending_cost_cases", "native_original_exact_match")}))


if __name__ == "__main__":
    main()
