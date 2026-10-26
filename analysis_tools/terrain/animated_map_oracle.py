#!/usr/bin/env python3
"""Actual style1 grids compared with unchanged original terrain instruction blocks.

The original first pass counts decoration candidates; the original neighbor and
face-routing blocks produce the two interior surfaces. This remains an isolated
constructor-block oracle, not a full renderer or camera-padded scene execution.
Original resources are read locally and only counts/hashes are written to reports.
"""
import argparse
import json
from pathlib import Path
import struct
import subprocess
import sys

from animated_oracle import OriginalAnimatedTerrain
from map_oracle import OriginalMap, TABLES_SHA, canonical
from geometry_oracle import IMAGE_SHA, LIBGCC_SHA, digest

CONFIG_SHA = "1f3a38cb119bf213df68bc46951a903a9e0f70fa77bfcfe13d15f8248b3df8f6"
GRID_IDS = (258, 259, 260, 261, 262, 265, 266, 267, 269, 275, 279)


def decode_config(data):
    cursor, tables = 0, []
    for _ in range(4):
        count = data[cursor]
        cursor += 1
        rows = []
        for _ in range(count):
            length = data[cursor]
            cursor += 1
            row = data[cursor:cursor + length]
            if len(row) != length:
                raise ValueError("short counted resource307 row")
            rows.append(list(row))
            cursor += length
        tables.append(rows)
    if cursor != len(data) or len(tables[0]) != 3:
        raise ValueError("resource307 framing differs from recovered variant")
    return tables


class OriginalAnimatedMap(OriginalAnimatedTerrain, OriginalMap):
    def hook(self, instance, address, size, user):
        if address == getattr(self, "active_endpoint", None):
            # Explicit endpoint also works when this address is inside a cached
            # Unicorn translation block compiled by a different isolated run.
            instance.emu_stop()
            return
        if address == 0xbaa5c:  # Original imported memset, reached by vector allocation.
            pointer = instance.reg_read(self.ar.UC_ARM_REG_R0)
            value = instance.reg_read(self.ar.UC_ARM_REG_R1)
            count = instance.reg_read(self.ar.UC_ARM_REG_R2)
            if count > 65536 or not 0x1000000 <= pointer <= 0x1400000 - count:
                raise RuntimeError("oracle memset exceeds its allocated guest heap")
            instance.mem_write(pointer, bytes([value & 255]) * count)
            self.calls["imported_memset"] += 1
            instance.reg_write(self.ar.UC_ARM_REG_PC, instance.reg_read(self.ar.UC_ARM_REG_LR))
            return
        super().hook(instance, address, size, user)

    def block(self, start, stop, frame=0x21fe000, extra_registers=()):
        self.active_endpoint = stop
        try:
            return super().block(start, stop, frame, extra_registers)
        finally:
            self.active_endpoint = None

    def neighbor_mask(self, x, y, height):
        self.active_endpoint = 0x6af02
        try:
            return super().neighbor_mask(x, y, height)
        finally:
            self.active_endpoint = None

    def setup(self, grid, config):
        self.setup_grid(grid)
        self.word(self.map_object + 0x22c, 1)
        self.word(0xd95bc, 0xd8f38)
        self.controller, self.shared_config = self.alloc(0xf0), self.alloc(0x50)
        self.word(self.controller + 0xdc, self.shared_config)
        self.word(0xd8dcc, self.controller)
        for table_index, rows in enumerate(config):
            records = self.alloc(len(rows) * 8)
            self.word(self.shared_config + 0x28 + table_index * 8, records)
            self.word(self.shared_config + 0x2c + table_index * 8, len(rows))
            for row_index, row in enumerate(rows):
                values = self.alloc(len(row))
                self.u.mem_write(values, bytes(row))
                self.word(records + row_index * 8, values)
                self.word(records + row_index * 8 + 4, len(row))
        self.call(0x474a0, [self.controller, 1])
        self.style_count = self.u.reg_read(self.ar.UC_ARM_REG_R0)
        self.call(0x45a54, [self.controller])
        self.face14_count = self.u.reg_read(self.ar.UC_ARM_REG_R0)
        if (self.style_count, self.face14_count) != (len(config[0][1]), len(config[2])):
            raise RuntimeError("original config accessors differ from decoded table counts")

    def first_pass(self):
        # Original first pass runs real columns and height+3 rows. Camera padding
        # is explicitly zero here; it does not add candidate columns to this pass.
        frame = 0x21fe000
        self.u.mem_write(frame, bytes(0x300))
        columns = self.alloc(self.width * 4)
        self.word(0xd8ddc, self.width)
        self.word(frame + 0xcc, columns)
        self.word(frame + 0x1fc, 0)
        self.word(frame + 0x298, self.grid_data)
        self.word(frame + 0x29c, len(self.grid))
        ar = self.ar
        for i in range(13):
            self.u.reg_write(getattr(ar, "UC_ARM_REG_R" + str(i)), 0)
        self.u.reg_write(ar.UC_ARM_REG_CPSR, 0x30)
        self.u.reg_write(ar.UC_ARM_REG_SP, frame)
        self.u.reg_write(ar.UC_ARM_REG_LR, 0x3000001)
        self.u.emu_start(0x6a3cd, 0x6a782, count=2_000_000, timeout=10_000_000)
        if self.u.reg_read(ar.UC_ARM_REG_PC) != 0x6a782 or self.u.reg_read(ar.UC_ARM_REG_SP) != frame:
            raise RuntimeError("original candidate-count first pass escaped its endpoint")
        self.check_text()
        return self.read_word(0xd8e1c), self.read_word(0xd8e0c)


def without_normalized(quads):
    return [{k: v for k, v in quad.items() if k != "normalized_uv"} for quad in quads]


def compare(actual, expected, name):
    if actual == expected:
        return
    for i, pair in enumerate(zip(actual, expected)):
        if pair[0] != pair[1]:
            raise RuntimeError(f"{name} first mismatch at {i}: {pair}")
    raise RuntimeError(f"{name} count differs: native{len(actual)}, original{len(expected)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--binary", type=Path, required=True)
    ap.add_argument("--libgcc", type=Path, required=True)
    ap.add_argument("--unicorn-dir", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--tables", type=Path, required=True)
    ap.add_argument("--native-probe", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    sys.path.insert(0, str(args.unicorn_dir))
    import unicorn
    image, gcc, tables = args.binary.read_bytes(), args.libgcc.read_bytes(), args.tables.read_bytes()
    if (digest(image), digest(gcc), digest(tables)) != (IMAGE_SHA, LIBGCC_SHA, TABLES_SHA):
        raise ValueError("oracle executable, helper or visual table differs from audited input")
    manifest = json.loads(args.manifest.read_text())
    resources = {r["resource_id"]: r for r in manifest["resources"] if r["key_hex"] == "0xf4e02223"}

    def resource(rid):
        r = resources[rid]
        path = args.manifest.parent / "extracted" / r["kind"] / r["extracted_filename"]
        data = path.read_bytes()
        if digest(data) != r["sha256"]:
            raise ValueError(f"local resource{rid} differs from independently audited manifest")
        return path, data

    config_path, config_data = resource(307)
    if digest(config_data) != CONFIG_SHA:
        raise ValueError("resource307 differs from audited config")
    config = decode_config(config_data)
    native_config = json.loads(subprocess.run([str(args.native_probe.resolve()), "animation_config",
        str(config_path)], text=True, capture_output=True, check=True).stdout)
    if native_config != config:
        raise RuntimeError("native resource307 decoder differs from independent counted-row framing")
    cases = []
    for rid in GRID_IDS:
        path, grid = resource(rid)
        original = OriginalAnimatedMap(image, gcc)
        original.setup(grid, config)
        candidates, slots = original.first_pass()
        expected_base, expected_animated, masks = [], [], []
        for y in range(original.height):
            previous = 16
            for x in range(original.width):
                tile = original.grid[y * original.width + x]
                record = tables[160 + tile * 5:160 + tile * 5 + 5]
                height = struct.unpack("b", record[4:5])[0]
                mask, bottom = original.neighbor_mask(x, y, height)
                result = original.routed_cell([x * 32, y * 32, height * 32, bottom * 32,
                    mask, previous, original.face14_count != 0, slots, *record[:4]])
                for name, destination in (("base", expected_base), ("animated", expected_animated)):
                    for quad in result[name]:
                        quad.update({"tile_x": x, "tile_y": y})
                    destination.extend(result[name])
                masks.append([x, y, mask, bottom])
                previous = mask
        native = json.loads(subprocess.run([str(args.native_probe.resolve()), "mesh", str(path),
            str(args.tables), "1", str(config_path)], text=True, capture_output=True, check=True).stdout)
        surface = native.get("animated_surface")
        if not surface or surface["atlas_resource_id"] != 420 or surface["decoration_slots"] != slots:
            raise RuntimeError(f"resource{rid} animated material or original pool count differs")
        compare(without_normalized(native["quads"]), expected_base, f"resource{rid} base")
        compare(without_normalized(surface["quads"]), expected_animated, f"resource{rid} animated")
        original.check_text()
        case = {"grid_resource_id": rid, "grid_sha256": digest(grid),
                "grid_dimensions": [original.width, original.height], "cells": len(masks),
                "original_candidate_count": candidates, "original_decoration_slots": slots,
                "base_quads": len(expected_base), "animated_quads": len(expected_animated),
                "original_neighbor_masks_sha256": digest(canonical(masks)),
                "original_and_native_base_sha256": digest(canonical(expected_base)),
                "original_and_native_animated_sha256": digest(canonical(expected_animated)),
                "all_native_positions_uv_and_pool_counts_match": True}
        cases.append(case)
        print(json.dumps({k: case[k] for k in ("grid_resource_id", "base_quads", "animated_quads",
                                             "original_decoration_slots")}), flush=True)
    report = {"scope": "Eleven actual style1 campaign grids, original first-pass count and interior two-surface geometry",
              "source_ipa_sha256": "b24fbe5cc4d5cb603189a476c4f81dd2a6ecc18b025eae913262055a7fc443fd",
              "original_sha256": IMAGE_SHA, "libgcc_sha256": LIBGCC_SHA,
              "tables_sha256": TABLES_SHA, "config_resource_id": 307, "config_sha256": CONFIG_SHA,
              "config_row_counts": list(map(len, config)),
              "resource_manifest_sha256": digest(args.manifest.read_bytes()),
              "unicorn_version": unicorn.__version__, "original_code_readonly_and_unchanged": True,
              "instruction_patches": 0, "oracle_source_sha256": digest(Path(__file__).read_bytes()),
              "native_probe_sha256": digest(args.native_probe.read_bytes()),
              "original_blocks": ["0x6a3cc..0x6a782", "0x6ae1a..0x6af02", "0x6af02..0x6b1e8"],
              "original_functions": ["0x474a0", "0x45a54", "0x45a5e", "0x65310", "0x714c0"],
              "substitutions": ["bounded allocation/free and exact imported memset", "M3G API recording and ownership",
                                "engine singleton", "unwind registration", "triangle-strip factory"],
              "entry_state": "Actual grid and config data in original object layout; zero camera padding and previous_mask16 at each interior row",
              "cases": cases, "case_count": len(cases), "cells": sum(c["cells"] for c in cases),
              "base_quads": sum(c["base_quads"] for c in cases),
              "animated_quads": sum(c["animated_quads"] for c in cases),
              "all_passed": True,
              "not_established": ["complete padded constructor", "transient random-decoration placement",
                                  "GPU pixel parity", "device execution", "full campaign playthrough"]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report": str(args.output), "cases": len(cases), "all_passed": True}))


if __name__ == "__main__":
    main()
