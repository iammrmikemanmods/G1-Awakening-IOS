#!/usr/bin/env python3
"""Development-only capture reference. Never included in the native product.

Executes intact original 0x4a852, the human coordinate-selection basic-block
region, and capture-mutation prefixes ending before presentation calls.
No instruction patches, function stubs, CPU fallback or iOS runtime is used.
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


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--binary", type=Path, required=True)
    p.add_argument("--movement-oracle", type=Path, required=True)
    p.add_argument("--native-probe", type=Path, required=True)
    p.add_argument("--unicorn-dir", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    sys.path.insert(0, str(a.unicorn_dir))
    import unicorn
    from unicorn import arm_const as ar
    spec = importlib.util.spec_from_file_location("movement_oracle", a.movement_oracle)
    old_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old_module)
    image = a.binary.read_bytes()
    if hashlib.sha256(image).hexdigest() != ORIGINAL_SHA256:
        raise RuntimeError("Wrong original executable")
    rng = random.Random(0x4A852)

    def network(site_count):
        sites = []
        for s in range(site_count):
            groups = []
            for g in range(rng.randrange(4)):
                groups.append([{"owner": rng.choice([-1, 0, 1]), "link": rng.randrange(256),
                                "xy": [s * 10 + g, i + 2]} for i in range(rng.randrange(6))])
            sites.append({"owner": rng.choice([-1, 0, 1]), "xy": [s * 10, 0], "groups": groups})
        return sites

    cases = []
    mappings = [[0, 1], [1, 0], [0, 0], [-1, 1], [0, -1], [-1, -1]]
    # Four independent write-flag combinations over the same randomized state.
    for sample in range(48):
        sites = network(sample % 4)
        for flags in ((0, 0), (0, 1), (1, 0), (1, 1)):
            cases.append({"mode": 0, "factions": mappings[sample % len(mappings)],
                          "flags": flags, "counters": [17, 29], "sites": sites})
    # Deliberate duplicate/signed-coordinate selection cases.
    for sample in range(64):
        sites = network(1 + sample % 3)
        point = [rng.randrange(8), rng.randrange(8)]
        for site in sites:
            if rng.randrange(3) == 0:
                site["xy"] = point.copy()
            for group in site["groups"]:
                for item in group:
                    if rng.randrange(4) == 0:
                        item["xy"] = point.copy()
        if sample % 8 == 0:
            point = [200, 1]
            sites[0]["xy"] = point.copy()
            sites[0]["groups"] = [[{"owner": -1, "link": 9, "xy": point.copy()}]]
        cases.append({"mode": 1, "factions": [0, 1], "flags": [0, 0],
                      "counters": [17, 29], "sites": sites, "point": point})
    # Unique target coordinates with a genuine ownership change.
    for sample in range(48):
        sites = network(1 + sample % 3)
        owner = sample % 2
        s = sample % len(sites)
        if sample % 2:
            sites[s]["owner"] = -1
            point = sites[s]["xy"]
            target = [1, s, 0, 0]
        else:
            sites[s]["groups"] = [[{"owner": -1, "link": 9, "xy": [s * 10 + 1, 3]},
                                   {"owner": 1 - owner, "link": 7, "xy": [s * 10 + 1, 4]}]]
            point = sites[s]["groups"][0][0]["xy"]
            target = [0, s, 0, 0]
        cases.append({"mode": 2, "factions": mappings[sample % len(mappings)], "flags": [0, 1],
                      "counters": [17, 29], "sites": sites, "point": point,
                      "actor_owner": owner, "target": target})

    fixture = {"width": 32, "height": 32,
               "unit": {"type": 11, "owner": 0, "base_budget": 2, "spent_budget": 0,
                        "form": 0, "field6": 0, "x": 5, "y": 7},
               "terrain": [[1, 0]] * 1024, "active_owners": [None] * 1024}
    registers = [getattr(ar, "UC_ARM_REG_R" + str(i)) for i in range(13)]
    results, lines = [], []
    for case in cases:
        old = old_module.OriginalMovement(image, fixture)
        counters = old.array(case["counters"])
        old.vector_at(old.map + 0x68, counters, 2)
        old.vector_at(old.map + 0xA0, old.array(case["factions"], 1), 2)
        owners = old.array([s["owner"] for s in case["sites"]], 1)
        old.vector_at(old.map + 0x3E8, owners, len(case["sites"]))
        outer_items = old.alloc(max(8, 8 * len(case["sites"])))
        outer_links = old.alloc(max(8, 8 * len(case["sites"])))
        outer_coordinates = old.alloc(max(8, 8 * len(case["sites"])))
        site_coordinates = old.alloc(max(8, 8 * len(case["sites"])))
        item_arrays, link_arrays = [], []
        for s, site in enumerate(case["sites"]):
            old.vector_at(site_coordinates + 8 * s, old.array(site["xy"], 1), 2)
            groups = site["groups"]
            gi = old.alloc(max(8, 8 * len(groups)))
            gl = old.alloc(max(8, 8 * len(groups)))
            gc = old.alloc(max(8, 8 * len(groups)))
            item_arrays.append([])
            link_arrays.append([])
            for g, group in enumerate(groups):
                ip = old.array([i["owner"] for i in group], 1)
                lp = old.array([i["link"] for i in group], 1)
                old.vector_at(gi + 8 * g, ip, len(group))
                old.vector_at(gl + 8 * g, lp, len(group))
                pairs = old.alloc(max(8, 8 * len(group)))
                for i, item in enumerate(group):
                    old.vector_at(pairs + 8 * i, old.array(item["xy"], 1), 2)
                old.vector_at(gc + 8 * g, pairs, len(group))
                item_arrays[s].append((ip, len(group)))
                link_arrays[s].append((lp, len(group)))
            for outer, data in ((outer_items, gi), (outer_links, gl), (outer_coordinates, gc)):
                old.vector_at(outer + 8 * s, data, len(groups))
        for offset, data in ((0x3F0, site_coordinates), (0x3F8, outer_items),
                             (0x400, outer_coordinates), (0x408, outer_links)):
            old.vector_at(old.map + offset, data, len(case["sites"]))

        def read32(address):
            return struct.unpack("<I", old.uc.mem_read(address, 4))[0]

        def snapshot():
            return {"counters": list(struct.unpack("<ii", old.uc.mem_read(counters, 8))),
                    "owners": list(struct.unpack("<" + "b" * len(case["sites"]),
                                                old.uc.mem_read(owners, len(case["sites"])))),
                    "items": [[list(struct.unpack("<" + "b" * n, old.uc.mem_read(p, n)))
                               for p, n in groups] for groups in item_arrays],
                    "links": [[list(old.uc.mem_read(p, n)) for p, n in groups] for groups in link_arrays]}

        def setup(arguments):
            for register in registers:
                old.uc.reg_write(register, 0)
            old.uc.reg_write(ar.UC_ARM_REG_CPSR, 0x30)
            old.uc.reg_write(ar.UC_ARM_REG_SP, 0x21FF000)
            old.uc.reg_write(ar.UC_ARM_REG_LR, old.return_address | 1)
            for i, value in enumerate(arguments):
                if i < 4:
                    old.uc.reg_write(registers[i], value & 0xFFFFFFFF)
                else:
                    old.write32(0x21FF000 + 4 * (i - 4), value)

        if case["mode"] == 0:
            old.call(0x4A852, [old.map, *case["flags"]])
            result = snapshot()
        elif case["mode"] == 1:
            old.write32(old.map + 0x3E4, old.unit)
            old.write8(old.unit + 0x3B, case["point"][0])
            old.write8(old.unit + 0x3C, case["point"][1])
            setup([])
            old.write32(0x21FF000 + 0x3C, old.map)
            stops = []

            def stop_on_decision(uc, address, _size, _data):
                if address in (0x5A0A8, 0x5A14C, 0x5A4B2):
                    stops.append(address)
                    uc.emu_stop()

            hook = old.uc.hook_add(unicorn.UC_HOOK_CODE, stop_on_decision)
            old.uc.emu_start(0x59FC5, old.return_address, timeout=5_000_000, count=100_000)
            old.uc.hook_del(hook)
            if len(stops) != 1 or old.uc.reg_read(ar.UC_ARM_REG_SP) != 0x21FF000:
                raise RuntimeError("Selection block failed its natural boundary/stack check")
            if stops[0] == 0x5A0A8:
                result = [0, read32(0x21FF074), read32(0x21FF078), read32(0x21FF07C)]
            elif stops[0] == 0x5A14C:
                result = [1, read32(0x21FF070), 0, 0]
            else:
                result = None
        else:
            kind, s, g, i = case["target"]
            if kind == 0:
                start, stop, frame = 0x548E2, 0x54918, 28
                setup([old.map, s, g, i, case["actor_owner"]])
            else:
                start, stop, frame = 0x5488C, 0x548AC, 20
                setup([old.map, s, case["actor_owner"]])
            old.uc.emu_start(start | 1, stop, timeout=5_000_000, count=500_000)
            if old.uc.reg_read(ar.UC_ARM_REG_PC) != stop or old.uc.reg_read(ar.UC_ARM_REG_SP) != 0x21FF000 - frame:
                raise RuntimeError("Capture prefix failed natural boundary/stack check")
            old.call(0x430F4, [old.unit])
            result = {"network": snapshot(), "flag2c": old.uc.mem_read(old.unit + 0x2C, 1)[0]}
        if bytes(old.uc.mem_read(0x1000, 0xD1000)) != old.original_text:
            raise RuntimeError("Original text was modified")
        results.append(result)
        fields = [case["mode"], *case["factions"], *case["flags"], len(case["sites"]), *case["counters"]]
        for site in case["sites"]:
            fields.extend([site["owner"], *site["xy"], len(site["groups"])])
            for group in site["groups"]:
                fields.append(len(group))
                for item in group:
                    fields.extend([item["owner"], item["link"], *item["xy"]])
        if case["mode"] == 1:
            fields.extend(case["point"])
        if case["mode"] == 2:
            fields.extend([case["actor_owner"], *case["point"]])
        lines.append(" ".join(map(str, fields)))
    proc = subprocess.run([str(a.native_probe.resolve())], input=str(len(lines)) + "\n" + "\n".join(lines) + "\n",
                          text=True, capture_output=True, check=True)
    native = json.loads(proc.stdout)
    if native != results:
        for index, (left, right) in enumerate(zip(native, results)):
            if left != right:
                raise RuntimeError(json.dumps({"case": cases[index], "native": left, "original": right}))
        raise RuntimeError("Result count mismatch")
    report = {"original_sha256": ORIGINAL_SHA256, "unicorn_version": unicorn.__version__,
              "native_original_exact_match": True, "case_count": len(cases),
              "full_network_function_cases": 192, "selection_block_cases": 64,
              "capture_prefix_and_action_flag_cases": 48,
              "full_original_ui_audio_renderer_executed": False,
              "original_entries": ["0x4a852", "0x59fc4", "0x548e2", "0x5488c", "0x430f4"],
              "prefix_stop_before": ["0x54918", "0x548ac"],
              "selection_natural_boundaries": ["0x5a0a8", "0x5a14c", "0x5a4b2"],
              "synthetic_state": True, "instruction_patches": 0, "function_stubs": 0,
              "original_text_readonly_unchanged": True,
              "movement_oracle_sha256": hashlib.sha256(a.movement_oracle.read_bytes()).hexdigest(),
              "cases": cases, "results": results}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("case_count", "native_original_exact_match",
                                            "full_original_ui_audio_renderer_executed")}))


if __name__ == "__main__":
    main()
