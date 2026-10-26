#!/usr/bin/env python3
"""First-grid terrain differential check using original neighbor-mask instructions.

Executes 0x6ae1a..0x6af02 with explicit grid/frame state, then unchanged 0x65310
and its geometry/UV callees. This is an isolated interior-cell oracle, not an
execution of the complete camera-padded original scene constructor. The native
product contains none of this development-only instruction execution.
"""
import argparse
import json
from pathlib import Path
import struct
import subprocess
import sys

from geometry_oracle import OriginalTerrain, IMAGE_SHA, LIBGCC_SHA, digest

GRID_SHA = "cdd071f319ba2d8160699df363f7dd666342a23abd6e276b23fc36b73c95a5b5"
TABLES_SHA = "b870e3d74244741003c8068178e7f58bb5fbe35599599c918e024227463725a8"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


class OriginalMap(OriginalTerrain):
    def setup_grid(self, encoded):
        self.width, self.height = encoded[:2]
        self.grid = encoded[2:]
        if len(self.grid) != self.width * self.height:
            raise ValueError("grid shape mismatch")
        self.grid_data = self.alloc(len(self.grid))
        self.u.mem_write(self.grid_data, self.grid)
        self.map_object = self.alloc(0x300)
        self.word(self.map_object + 0x22c, 0)
        self.word(0xd8dd0, self.map_object)
        self.word(0xd8de0, self.width)
        self.word(0xd8de4, self.height)
        self.word(0xd95bc, 0xd9084)

    def neighbor_mask(self, x, y, height):
        frame = 0x21fe000
        for offset, value in ((0x140, x), (0x14c, y * self.width + x), (0x204, y),
                              (0x1ec, height & 255), (0x298, self.grid_data),
                              (0x29c, len(self.grid))):
            self.word(frame + offset, value)
        ar = self.ar
        for i in range(13):
            self.u.reg_write(getattr(ar, "UC_ARM_REG_R" + str(i)), 0)
        self.u.reg_write(ar.UC_ARM_REG_CPSR, 0x30)
        self.u.reg_write(ar.UC_ARM_REG_SP, frame)
        self.u.reg_write(ar.UC_ARM_REG_LR, 0x3000001)
        self.u.emu_start(0x6ae1b, 0x6af02, count=10000, timeout=1_000_000)
        if self.u.reg_read(ar.UC_ARM_REG_PC) != 0x6af02 or self.u.reg_read(ar.UC_ARM_REG_SP) != frame:
            raise RuntimeError("original neighbor-height block escaped its bounded endpoint")
        mask = self.read_word(frame + 0x138)
        bottom = struct.unpack("<i", self.u.mem_read(frame + 0x158, 4))[0]
        return mask, bottom


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--binary", type=Path, required=True)
    ap.add_argument("--libgcc", type=Path, required=True)
    ap.add_argument("--unicorn-dir", type=Path)
    ap.add_argument("--grid", type=Path, required=True)
    ap.add_argument("--tables", type=Path, required=True)
    ap.add_argument("--native-probe", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    if args.unicorn_dir:
        sys.path.insert(0, str(args.unicorn_dir))
    import unicorn
    image, gcc = args.binary.read_bytes(), args.libgcc.read_bytes()
    grid, tables = args.grid.read_bytes(), args.tables.read_bytes()
    if (digest(image), digest(gcc), digest(grid), digest(tables)) != (IMAGE_SHA, LIBGCC_SHA, GRID_SHA, TABLES_SHA):
        raise ValueError("oracle source data differs from the reviewed first-grid inputs")
    original = OriginalMap(image, gcc)
    original.setup_grid(grid)
    expected, masks = [], []
    for y in range(original.height):
        previous = 0x10  # Explicit interior-only row boundary, outside padding excluded.
        for x in range(original.width):
            tile = original.grid[y * original.width + x]
            record = tables[tile * 5:tile * 5 + 5]
            height = struct.unpack("b", record[4:5])[0]
            mask, bottom = original.neighbor_mask(x, y, height)
            quads, _ = original.cell([x * 32, y * 32, height * 32, bottom * 32,
                                      mask, previous, 1, *record[:4]])
            face_order = [face for bit, face in ((1, 1), (2, 3), (8, 2), (16, 0)) if mask & bit]
            if len(face_order) != len(quads):
                raise RuntimeError("original face count disagrees with original mask")
            for face, quad in zip(face_order, quads):
                quad.update({"face": face, "tile_x": x, "tile_y": y})
            expected.extend(quads)
            masks.append([x, y, mask, bottom])
            previous = mask
    native_run = subprocess.run([str(args.native_probe.resolve()), "mesh", str(args.grid),
                                 str(args.tables), "0"], text=True, capture_output=True, check=True)
    native = json.loads(native_run.stdout)
    native_quads = [{k: v for k, v in quad.items() if k != "normalized_uv"} for quad in native["quads"]]
    if native_quads != expected:
        for i, pair in enumerate(zip(native_quads, expected)):
            if pair[0] != pair[1]:
                raise RuntimeError(f"first-grid original/native quad mismatch {i}: {pair}")
        raise RuntimeError("first-grid original/native quad count differs")
    if bytes(original.u.mem_read(0x1000, 0xd1000)) != original.original_text:
        raise RuntimeError("original main code changed")
    report = {"scope": "First mission grid268/style0 interior neighbor masks and raw terrain geometry",
              "source_ipa_sha256": "b24fbe5cc4d5cb603189a476c4f81dd2a6ecc18b025eae913262055a7fc443fd",
              "original_sha256": IMAGE_SHA, "libgcc_sha256": LIBGCC_SHA,
              "grid_resource_id": 268, "grid_sha256": GRID_SHA, "tables_sha256": TABLES_SHA,
              "grid_dimensions": [original.width, original.height], "cells": len(masks),
              "quad_count": len(expected), "scalar_position_uv_count": len(expected) * 20,
              "original_neighbor_mask_sha256": digest(canonical(masks)),
              "original_and_native_quad_sha256": digest(canonical(expected)),
              "native_probe_sha256": digest(args.native_probe.read_bytes()),
              "oracle_source_sha256": digest(Path(__file__).read_bytes()),
              "geometry_oracle_source_sha256": digest((Path(__file__).parent / "geometry_oracle.py").read_bytes()),
              "unicorn_version": unicorn.__version__, "original_code_readonly_and_unchanged": True,
              "instruction_patches": 0, "all_native_positions_and_quantized_uv_match": True,
              "original_neighbor_block": "0x6ae1a..0x6af02", "original_face_function": "0x65310",
              "entry_state": "actual decoded grid/style0 table; explicit interior row previous_mask0x10",
              "substitutions": "same documented infrastructure boundaries as original_terrain_oracle.json",
              "not_established": ["complete padded map constructor", "outer-column boundary interactions",
                                  "style1 animated terrain", "GPU pixel parity", "device execution"]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report": str(args.output), "cells": len(masks), "quads": len(expected),
                      "all_native_positions_and_quantized_uv_match": True}))


if __name__ == "__main__":
    main()
