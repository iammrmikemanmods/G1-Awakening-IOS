#!/usr/bin/env python3
"""Development-only movement route/action reference against original ARM functions.

Needs the privately supplied ARMv6 executable, external Unicorn2.1.4, and the
unchanged analysis_tools/movement/oracle.py. None belongs in the native product.
Original code pages are read-only; no function stubs or instruction patches.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import struct
import subprocess
import sys

ORIGINAL_SHA256 = "0d510516fe3676ee4a0f4dff60ba64e1c5bf79a0c9800f420b1bbdb1c12febfd"
FUNCTIONS = {"route_reset": 0x4A044, "route": 0x49E90, "begin_unit": 0x43E2E,
             "form_zero_field2_predicate": 0x434E4, "tick": 0x4351C,
             "restore_anchor": 0x4324A, "reset_turn": 0x430FC}
STATE_FIELDS = ["tile_x", "tile_y", "offset_x", "offset_y", "facing", "spent_budget",
                "pending_cost", "route_index", "moving", "timer_ms", "flag_38",
                "anchor_x", "anchor_y", "anchor_facing", "flag_2c", "flag_2d",
                "flag_2f", "flag_39", "flag_3a"]


def synthetic_cases():
    rng = random.Random(0x49E904351C)
    cases = []
    for form in (0, 1, 2):
        for dx, dy in ((0, 2), (4, 2), (2, 0), (2, 4), (0, 0), (4, 4), (4, 0), (0, 4)):
            cases.append({"name": f"direction_f{form}_{dx}_{dy}", "width": 5, "height": 5,
                          "unit": {"type": 0, "owner": 0, "base_budget": 8, "spent_budget": 0,
                                   "form": form, "field6": 0, "x": 2, "y": 2},
                          "terrain": [[1, 0]] * 25, "active_owners": [None] * 25,
                          "destination": [dx, dy], "form0_field2": form, "timer_ms": 173,
                          "facing": form, "flag_38": 0})
    for i in range(112):
        w, h = rng.randrange(3, 10), rng.randrange(3, 10)
        x, y = rng.randrange(w), rng.randrange(h)
        spent = rng.choice([0, 0, 1, 2, 253])
        base = rng.randrange(3, 10)
        if spent == 253:
            base = 3  # Exact unsigned-budget wrap: 3 - 253 = 6.
        terrain = [[rng.choice([1, 1, 1, 2, 3, 99]), rng.randrange(2)] for _ in range(w*h)]
        terrain[y*w+x] = [1, 0]
        cases.append({"name": f"weighted_{i:03}", "width": w, "height": h,
                      "unit": {"type": rng.choice([0, 11, 19]), "owner": rng.randrange(2),
                               "base_budget": base, "spent_budget": spent,
                               "form": rng.randrange(3), "field6": 0, "x": x, "y": y},
                      "terrain": terrain, "active_owners": [None]*(w*h),
                      "form0_field2": rng.choice([-128, -1, 0, 1, 2, 127]),
                      "timer_ms": rng.choice([-1, 0, 1, 999, 2147483647]),
                      "facing": rng.randrange(4), "flag_38": rng.choice([0, 1])})
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--movement-oracle", type=Path, required=True)
    parser.add_argument("--unicorn-dir", type=Path, required=True)
    parser.add_argument("--native-probe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.unicorn_dir))
    import unicorn
    spec = importlib.util.spec_from_file_location("g1_original_movement", args.movement_oracle)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    image = args.binary.read_bytes()
    if hashlib.sha256(image).hexdigest() != ORIGINAL_SHA256:
        raise SystemExit("Wrong original executable; no oracle execution")
    results, cases, native_input = [], [], []
    for case in synthetic_cases():
        case.update(flag_2c=len(cases)%2, flag_2f=(len(cases)%3)*7, flag_39=(len(cases)%5)*51)
        old = module.OriginalMovement(image, case)
        read32 = lambda address: struct.unpack("<I", old.uc.mem_read(address, 4))[0]
        readi = lambda address: struct.unpack("<i", old.uc.mem_read(address, 4))[0]
        read8 = lambda address: bytes(old.uc.mem_read(address, 1))[0]
        # Supply exact selected-form stats and form-zero predicate input. This is
        # synthetic decoded data, not a replacement for a game function.
        forms = old.alloc((max(1, case["unit"]["form"]) + 1) * 8)
        for f in range(max(1, case["unit"]["form"]) + 1):
            stats = [0]*12
            stats[0] = case["unit"]["base_budget"]
            stats[2] = case["form0_field2"] if f == 0 else 0
            old.vector_at(forms + 8*f, old.array(stats, 1), len(stats))
        type_records = read32(old.map + 0x174)
        old.vector_at(type_records + 8*case["unit"]["type"], forms,
                      max(1, case["unit"]["form"]) + 1)
        old.call(0x50844, [old.map, old.unit])
        remaining = [readi(old.grid_columns[x] + 4*y)
                     for y in range(old.height) for x in range(old.width)]
        origin = [case["unit"]["x"], case["unit"]["y"]]
        reachable = [[x,y] for y in range(old.height) for x in range(old.width)
                     if remaining[y*old.width+x] >= 0 and remaining[y*old.width+x] != 127
                     and [x,y] != origin]
        if not reachable:
            continue
        destination = case.get("destination", reachable[len(cases) % len(reachable)])
        if destination not in reachable:
            raise RuntimeError("Focused case destination unexpectedly unreachable")
        capacity = 2*(old.width + old.height)
        route_records = old.int_vectors([[-1,-1]] * capacity)
        old.vector_at(old.map + 0xC8, route_records, capacity)
        unit_route_records = old.int_vectors([[-1,-1]] * capacity)
        old.vector_at(old.unit + 0x50, unit_route_records, capacity)
        old.call(FUNCTIONS["route_reset"], [old.map])
        old.call(FUNCTIONS["route"], [old.map, *origin, *destination])
        count = read32(old.map + 0xD8)
        route = [[readi(read32(route_records+8*i)), readi(read32(route_records+8*i)+4)]
                 for i in range(count)]
        if not 0 < count < capacity or count > 256:
            raise RuntimeError("Original route exceeded supported storage")
        if readi(read32(route_records+8*count)) != -1:
            raise RuntimeError("Original route lacks terminator")
        for offset, value in ((0x30, case["timer_ms"]),):
            old.write32(old.unit + offset, value)
        for offset, value in ((0x48, origin[0]), (0x49, origin[1]),
                              (0x4A, case["facing"]), (0x4B, case["facing"]),
                              (0x38, case["flag_38"]), (0x2C, case["flag_2c"]),
                              (0x2F, case["flag_2f"]), (0x39, case["flag_39"])):
            old.write8(old.unit + offset, value)
        if old.call(FUNCTIONS["form_zero_field2_predicate"], [old.unit]):
            # Literal wrapper 0x513b6 store, after executing its original predicate.
            old.write8(old.unit + 0x38, 1)
        old.call(FUNCTIONS["begin_unit"],
                 [old.unit, *destination, old.map + 0xB4, old.map + 0xC8])

        def state():
            u = old.unit
            return [read8(u+0x3B), read8(u+0x3C), readi(u+0x40), readi(u+0x44),
                    read8(u+0x4B), read8(u+0x59), read8(u+0x4C), read8(u+0x58),
                    int(read8(u+8) == 1), readi(u+0x30), read8(u+0x38),
                    read8(u+0x48), read8(u+0x49), read8(u+0x4A), read8(u+0x2C),
                    read8(u+0x2D), read8(u+0x2F), read8(u+0x39), read8(u+0x3A)]

        states = [state()]
        deltas = []
        pattern = [0, 1, 10, 30, 1000, 17, 33, 2147483647]
        for tick in range(12*count + 3):
            delta = pattern[tick % len(pattern)]
            old.call(FUNCTIONS["tick"], [old.unit, delta])
            deltas.append(delta)
            states.append(state())
        if states[-1][8] != 0:
            raise RuntimeError("Original movement did not finish")
        old.call(FUNCTIONS["restore_anchor"], [old.unit])
        old.call(FUNCTIONS["reset_turn"], [old.unit])
        undo = state()
        if bytes(old.uc.mem_read(0x1000, 0xD1000)) != old.original_text:
            raise RuntimeError("Original executable text changed")
        results.append({"name": case["name"], "status": 0, "route": route,
                        "states": states, "undo": undo})
        case.update(destination=destination, remaining=remaining, delta_ms=deltas)
        cases.append(case)
        p = case["unit"]
        header = [case["name"], old.width, old.height, *origin, *destination,
                  p["type"], p["owner"], p["base_budget"], p["spent_budget"], p["form"],
                  case["form0_field2"], case["timer_ms"], case["facing"], case["flag_38"],
                  case["flag_2c"], case["flag_2f"], case["flag_39"], len(deltas)]
        native_input.append(" ".join(map(str, header + remaining + deltas)))
    payload = str(len(cases)) + "\n" + "\n".join(native_input) + "\n"
    completed = subprocess.run([str(args.native_probe.resolve())], input=payload, text=True,
                               capture_output=True, check=True)
    native = json.loads(completed.stdout)
    if native != results:
        for a, b in zip(native, results):
            if a != b:
                raise RuntimeError("Native/original difference: " + json.dumps({"native":a,"original":b}))
        raise RuntimeError("Native/original result count mismatch")
    record = {"kind":"development-only original ARM function comparison",
              "original_sha256":ORIGINAL_SHA256, "unicorn_version":unicorn.__version__,
              "instruction_patches":0, "function_stubs":0,
              "readonly_original_text_verified":True, "synthetic_state":True,
              "full_game_execution":False, "native_original_exact_match":True,
              "original_movement_oracle_sha256":hashlib.sha256(args.movement_oracle.read_bytes()).hexdigest(),
              "functions":{k:hex(v) for k,v in FUNCTIONS.items()}, "state_fields":STATE_FIELDS,
              "case_count":len(cases), "state_count":sum(len(r["states"])+1 for r in results),
              "state_scalar_comparisons":sum((len(r["states"])+1)*len(STATE_FIELDS) for r in results),
              "route_scalar_comparisons":sum(len(r["route"])*2 for r in results),
              "cases":cases, "results":results}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(record,indent=2)+"\n")
    print(json.dumps({k:record[k] for k in ("case_count","state_count","state_scalar_comparisons",
                                           "route_scalar_comparisons","native_original_exact_match")}))


if __name__ == "__main__":
    main()
