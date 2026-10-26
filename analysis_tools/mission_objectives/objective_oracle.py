#!/usr/bin/env python3
"""Development-only complete original objective/success-function reference.

Imports the pinned, adjacent progression reference's memory/ABI harness via an
explicit path. Actual0x559b4,0x558e4 and0x430fc run unchanged. No world mutation,
objective satisfaction, success callback, CPU instruction or import is stubbed.
The native product never loads this development dependency or original code.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import struct

SUPPORT_SHA256 = "f0505848b34b88b6653cbb8ebe5f74fa8fd5394f4e1727fa93f0b3f2c18374ad"
IMAGE_SHA256 = "0d510516fe3676ee4a0f4dff60ba64e1c5bf79a0c9800f420b1bbdb1c12febfd"


def script(shape):
    values = [5] * 40
    values[10] = 12
    if shape == 0: values[30], values[36] = 1, 1
    if shape == 1: values[20] = 1
    return values


def setup(ref):
    ref.goal_units = [ref.alloc(0x80) for _ in range(23)]
    ref.goal_types = ref.array(ref.goal_units, "I")
    ref.goal_owners = [ref.array([0] * 23, "I") for _ in range(2)]
    ref.w32(ref.map + 0x90, ref.goal_types)
    ref.w32(ref.map + 0x84, ref.array(ref.goal_owners, "I"))
    ref.w32(ref.map + 0x54, 23)
    ref.goal_commands = ref.alloc(40 * 8)
    ref.goal_words = [ref.array([5], "H") for _ in range(40)]
    for index, words in enumerate(ref.goal_words):
        ref.vector(ref.goal_commands + index * 8, words, 1)
    ref.vector(ref.map + 0x214, ref.goal_commands, 40)
    ref.goal_parameters = ref.array([0] * 4, "i")
    ref.vector(ref.map + 0x240, ref.goal_parameters, 4)


def execute(ref, context, current_owner, shape, kind, parameters, units, sites):
    ref.configure(context)
    # configure uses the old command storage only; our script vector remains.
    ref.w32(ref.map + 0x248, kind)
    for index, value in enumerate(parameters): ref.w32(ref.goal_parameters + 4 * index, value)
    ref.w32(ref.map + 0x21c, 10)
    ref.w32(ref.map + 0x1e0, 777)
    ref.w32(ref.map + 0x238, 42)
    ref.w32(ref.map + 0x23c, 43)
    ref.w32(ref.map + 0x2d8, 0)
    ref.w8(ref.map + 0x230, 1)
    ref.w8(ref.map + 0x231, 0)
    ref.w8(ref.map + 0xa8, current_owner)
    for index, opcode in enumerate(script(shape)):
        ref.u.mem_write(ref.goal_words[index], struct.pack("<H", opcode))
    owner_lists = [[], []]
    for index, (present, active, owner, x, y, dx, dy) in enumerate(units):
        pointer = ref.goal_units[index]
        ref.u.mem_write(pointer, bytes([0x5a]) * 0x80)
        ref.w8(pointer + 0xd, active)
        ref.w8(pointer + 0x3b, x); ref.w8(pointer + 0x3c, y)
        ref.w32(pointer + 0x40, dx); ref.w32(pointer + 0x44, dy)
        ref.w32(ref.goal_types + index * 4, pointer if present else 0)
        if present: owner_lists[owner].append(pointer)
    for owner, pointers in enumerate(owner_lists):
        ref.u.mem_write(ref.goal_owners[owner], struct.pack("<" + "I" * 23,
                                                         *(pointers + [0] * (23 - len(pointers)))))
    site_states = ref.array([site[0] for site in sites], "b")
    ref.vector(ref.map + 0x3e8, site_states, len(sites))
    site_vectors = ref.alloc(len(sites) * 8)
    for s, (_, groups) in enumerate(sites):
        group_vectors = ref.alloc(len(groups) * 8)
        for g, items in enumerate(groups):
            ref.vector(group_vectors + g * 8, ref.array(items, "b"), len(items))
        ref.vector(site_vectors + s * 8, group_vectors, len(groups))
    ref.vector(ref.map + 0x3f8, site_vectors, len(sites))
    ref.run(0x559b4, [ref.map])
    assert not ref.events
    phase = ref.r32(ref.map + 0x1e0)
    ready = phase == 99
    reset_count = 0
    for index, (present, active, owner, x, y, dx, dy) in enumerate(units):
        pointer = ref.goal_units[index]
        cleared = all(ref.r8(pointer + off) == 0 for off in (0x59, 0x2c, 0x2d, 0x38, 0x2f, 0x39, 0x3a))
        if ready and present and owner == current_owner:
            assert cleared and ref.r8(pointer + 0x48) == x and ref.r8(pointer + 0x49) == y
            reset_count += 1
        else:
            assert all(ref.r8(pointer + off) == 0x5a for off in (0x59, 0x2c, 0x2d, 0x38, 0x2f, 0x39, 0x3a))
        assert ref.r32(pointer + 0x40) == dx & 0xffffffff
        assert ref.r32(pointer + 0x44) == dy & 0xffffffff
    if ready: assert ref.r32(ref.map + 0x238) == ref.r32(ref.map + 0x23c) == 0xffffffff
    else: assert (ref.r32(ref.map + 0x238), ref.r32(ref.map + 0x23c)) == (42, 43)
    cursor = ref.r32(ref.map + 0x21c)
    if cursor >= 0x80000000: cursor -= 0x100000000
    return [int(ready), cursor, ref.r8(ref.map + 0x231), phase,
            ref.r32(ref.map + 0x2d8), ref.r8(ref.map + 0x230), reset_count]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--image", type=Path, required=True)
    p.add_argument("--support", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    image, support = args.image.read_bytes(), args.support.read_bytes()
    if hashlib.sha256(image).hexdigest() != IMAGE_SHA256: raise SystemExit("wrong original executable")
    if hashlib.sha256(support).hexdigest() != SUPPORT_SHA256: raise SystemExit("wrong reference support module")
    spec = importlib.util.spec_from_file_location("progression_reference", args.support)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    ref = module.Reference(image); setup(ref)
    random = __import__("random").Random(0x559b4)
    cases = []
    objectives = [(0, [-1, 0]), (0, [0, 1]), (1, [0, 0, 0, 0]),
                  (1, [-1, 0, 0, 0]), (2, [-1]), (2, [-2]), (2, [0]),
                  (2, [21]), (3, [-3, 5, 7]), (3, [11, 5, 7])]
    for index in range(320):
        group, mission = random.choice([(0, 0), (0, 1), (0, 9), (0, 16), (1, 2), (2, 1)])
        kind, parameters = objectives[index % len(objectives)]
        swap = (index // 2) % 2
        context = [group, mission, random.choice([0, 1, 2]), random.choice([0, 1, 2]),
                   0, swap, 1 - swap, random.choice([0, 1, -1]), random.choice([0, 1, -1])]
        units = [[1, int(random.randrange(6) == 0), int(t >= 12), 0, 0, 0, 0] for t in range(23)]
        for target in (0, 11, 12, 21):
            units[target][1] = random.randrange(2)
            units[target][3:] = [random.choice([0, 5]), random.choice([0, 7]),
                                 random.choice([0, 0, -1]), random.choice([0, 0, 256])]
        if index % 13 == 0: units[21][0] = 0
        context[4] = units[12][0] and units[12][1]
        if index % 8 == 0: sites = [] if kind != 0 or parameters[0] == -1 else [[0, [[0, 1]]]]
        else: sites = [[random.choice([-1, 0, 1]), [[random.choice([-1, 0, 1]), 0]]], [0, [[0], []]]]
        if kind == 1 and parameters[0] == 0 and not sites: sites = [[0, [[0]]]]
        cases.append((context, random.randrange(2), random.randrange(3), kind, parameters, units, sites))
    # Directed finite-state cases resolve meaningful non-random semantic risks.
    for kind, parameters in objectives:
        for variant in range(8):
            context = [0, 0, 2, 1, 0, 0, 1, 0, 1]
            units = [[1, 0, int(t >= 12), 0, 0, 0, 0] for t in range(23)]
            units[11] = [1, variant % 2, 0, 5, 7, 0 if variant < 4 else 1, 0]
            units[12][1] = variant // 4
            context[4] = units[12][1]
            if variant == 2: context[2] = 0
            if variant == 3: context[3] = 0
            if variant == 4: context[0:2] = [0, 9]; context[2] = 1
            if variant == 5: context[0:2] = [0, 16]; context[2] = 0
            if variant == 6: context[5:7] = [1, 0]
            if variant == 7: context[7:9] = [1, 0]
            sites = [[0, [[0, 0], [0]]], [0, [[]]]]
            cases.append((context, 0, variant % 3, kind, parameters, units, sites))
    rows = []
    counts = [0] * 4
    for context, owner, shape, kind, parameters, units, sites in cases:
        counts[kind] += 1
        result = execute(ref, context, owner, shape, kind, parameters, units, sites)
        row = [*context, owner, shape, kind, len(parameters), *parameters, len(units)]
        for value in units: row.extend(value)
        row.append(len(sites))
        for state, groups in sites:
            row.extend([state, len(groups)])
            for items in groups: row.extend([len(items), *items])
        rows.append(row + result)
    args.output.mkdir(parents=True, exist_ok=True)
    fixture = args.output / "mission_objectives_original_vectors.txt"
    fixture.write_text("# Context9,current_owner,script_shape,kind,param_count,params,unit_count,units7,sites,outputs7\n" +
                       "\n".join(" ".join(map(str, row)) for row in rows) + "\n")
    report = {"original_executable_sha256": IMAGE_SHA256, "support_sha256": SUPPORT_SHA256,
              "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "unicorn_version": __import__("unicorn").__version__,
              "complete_original_functions_executed": ["0x559b4", "0x558e4", "0x430fc"],
              "external_boundaries_replaced": [], "cases": len(rows), "cases_by_kind": counts,
              "original_function_fixtures_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
              "limits": ["Synthetic independent world observations, not a live campaign playthrough.",
                         "Original CPU and proprietary executable are development-only inputs, not native app dependencies.",
                         "The native API returns control-flow/action-reset requests; real world mutation remains the caller's duty."]}
    (args.output / "original_mission_objectives_reference.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__": main()
