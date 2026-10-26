#!/usr/bin/env python3
"""Original-instruction terrain face/UV oracle; never linked into the product.

Runs the unchanged original 0x714c0 atlas setup and 0x65310 face builder,
including 0x70eb4, 0x71248 and 0x70f70. The original ARMv6 libgcc performs all
integer and floating-point helpers. The shared sprite oracle records bounded
allocation, ownership and M3G calls; no geometry/UV instruction is replaced.
The emitted fixture contains synthetic inputs and resulting scalar values,
not the original visual tables, resources or executable bytes.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sprite"))
from render_oracle import OriginalRenderer, IMAGE_SHA, LIBGCC_SHA, digest, float_bits


class OriginalTerrain(OriginalRenderer):
    def __init__(self, image, gcc):
        self.face_calls = []
        super().__init__(image, gcc)
        self.position_buffer = self.alloc(4 * 24)
        self.uv_buffer = self.alloc(4 * 16)
        self.atlas = self.alloc(16)
        self.word(self.atlas, 1)
        self.word(self.atlas + 8, 512)
        self.word(self.atlas + 12, 256)
        self.call(0x714c0, [self.atlas, 64, 64])
        self.original_uv_table = bytes(self.u.mem_read(self.read_word(self.atlas + 4), 512))
        self.faces = self.alloc(4 * 8)
        self.face_values = self.alloc(4 * 4)
        for i in range(4):
            self.word(self.faces + i * 8, self.face_values + i * 4)
            self.word(self.faces + i * 8 + 4, 1)

    def hook(self, instance, address, size, user):
        if address == 0x70f70:
            self.face_calls.append(instance.reg_read(self.ar.UC_ARM_REG_R0))
        super().hook(instance, address, size, user)

    def cell(self, inputs, finalize=False):
        x, z, top, bottom, mask, previous, bevel, *cells = inputs
        self.face_calls = []
        for i, cell in enumerate(cells):
            self.word(self.face_values + 4 * i, cell)
        for address, value in ((0xd913c, 0), (0xd964c, 0),
                               (0xd9144, self.position_buffer), (0xd9140, self.uv_buffer),
                               (0xd914c, float_bits(1.0)), (0xd9150, self.atlas),
                               (0xd9644, self.positions), (0xd9648, self.uv)):
            self.word(address, value)
        self.u.mem_write(self.position_buffer, b"\xa5" * 96)
        self.u.mem_write(self.uv_buffer, b"\xa5" * 64)
        self.call(0x65310, [x, z, self.faces, top, bottom, mask, bevel, previous, 0])
        count = len(self.face_calls)
        if (self.read_word(0xd913c) != count * 12 or self.read_word(0xd964c) != count * 8 or
                self.u.reg_read(self.ar.UC_ARM_REG_R0) != count * 4):
            raise RuntimeError("original output counters disagree")
        output = []
        for i, cell in enumerate(self.face_calls):
            pos = struct.unpack("<12h", self.u.mem_read(self.position_buffer + i * 24, 24))
            uv = struct.unpack("<8h", self.u.mem_read(self.uv_buffer + i * 16, 16))
            output.append({"face": cells.index(cell), "atlas_cell": cell,
                           "positions": [list(pos[j:j + 3]) for j in range(0, 12, 3)],
                           "quantized_uv": [list(uv[j:j + 2]) for j in range(0, 8, 2)]})
        if self.read_word(0xd914c) != float_bits(1.0):
            raise RuntimeError("single-cell original UV ratio is not one")
        transform = None
        if finalize:
            self.call(0x71884, [1, float_bits(1.0)])
            strip_pointer = self.alloc(4)
            self.call(0x715d0, [strip_pointer, count])
            transform = {"position_scale_bits": self.transforms["set_positions"]["scale_bits"],
                         "position_bias_bits": self.transforms["set_positions"]["bias_bits"],
                         "uv_scale_bits": self.transforms["set_uv"]["scale_bits"],
                         "uv_bias_bits": self.transforms["set_uv"]["bias_bits"],
                         "strips": self.strips[-1]}
        return output, transform


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--binary", type=Path, required=True)
    ap.add_argument("--libgcc", type=Path, required=True)
    ap.add_argument("--unicorn-dir", type=Path)
    ap.add_argument("--fixture", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    if args.unicorn_dir:
        sys.path.insert(0, str(args.unicorn_dir))
    import unicorn
    image, gcc = args.binary.read_bytes(), args.libgcc.read_bytes()
    if digest(image) != IMAGE_SHA or digest(gcc) != LIBGCC_SHA:
        raise ValueError("source image or libgcc differs from the reviewed original")
    original = OriginalTerrain(image, gcc)
    cases, lines, cells_seen = [], [], set()
    transform = None
    for bevel in (0, 1):
        for previous in (16, 18):
            for bits in range(16):
                mask = sum(bit for i, bit in enumerate((1, 2, 8, 16)) if bits & (1 << i))
                for offset in (0, 16):
                    n = len(cases)
                    cells = [(n + offset + 2 * bevel + d) % 32 for d in (0, 3, 11, 23)]
                    inputs = [(n % 5) * 32 - 32, (n % 7) * 32, -(n % 3) * 32,
                              -96, mask, previous, bevel, *cells]
                    output, captured = original.cell(inputs, finalize=(mask == 27 and transform is None))
                    if captured is not None:
                        transform = captured
                    name = f"cell_{n:03d}"
                    line = [name, *inputs, len(output)]
                    for quad in output:
                        cells_seen.add(quad["atlas_cell"])
                        line.extend([quad["face"], quad["atlas_cell"]])
                        line.extend(x for row in quad["positions"] for x in row)
                        line.extend(x for row in quad["quantized_uv"] for x in row)
                    lines.append(" ".join(map(str, line)))
                    cases.append({"name": name, "input": inputs, "quad_count": len(output),
                                  "original_output_sha256": digest(json.dumps(output, sort_keys=True,
                                                          separators=(",", ":")).encode())})
    expected_transform = {"position_scale_bits": float_bits(0.01), "position_bias_bits": [0, 0, 0],
                          "uv_scale_bits": float_bits(1 / 65535),
                          "uv_bias_bits": [0x3f000080, 0x3f000080],
                          "strips": {"start_index": 0, "lengths": [4, 4, 4, 4]}}
    if transform != expected_transform or cells_seen != set(range(32)):
        raise RuntimeError("original terrain transform/atlas coverage differs from recovered constraints")
    args.fixture.parent.mkdir(parents=True, exist_ok=True)
    args.fixture.write_text("G1_TERRAIN_ORACLE_V1 " + str(len(cases)) + "\n" + "\n".join(lines) + "\n")
    report = {"scope": "Original terrain face builder and512x256 atlas setup on synthetic inputs",
              "original_sha256": IMAGE_SHA, "libgcc_sha256": LIBGCC_SHA,
              "unicorn_version": unicorn.__version__, "oracle_source_sha256": digest(Path(__file__).read_bytes()),
              "shared_oracle_sha256": digest((Path(__file__).resolve().parents[1] / "sprite/render_oracle.py").read_bytes()),
              "fixture_sha256": digest(args.fixture.read_bytes()), "case_count": len(cases),
              "quad_count": sum(c["quad_count"] for c in cases), "atlas_cells_covered": sorted(cells_seen),
              "original_uv_table_sha256": digest(original.original_uv_table), "original_transform": transform,
              "original_code_readonly_and_unchanged": True, "instruction_patches": 0,
              "math_helpers": "unchanged original ARMv6 libgcc, redirected import destinations",
              "substitutions": ["bounded allocation/free", "M3G API recording and ownership",
                                "engine singleton", "unwind registration", "triangle-strip factory"],
              "original_call_counts": dict(original.calls), "cases": cases,
              "native_comparison_in_separate_test": True, "gpu_rendered": False, "device_tested": False,
              "not_established": ["full map-constructor execution", "camera and outside padding",
                                  "style1 animated terrain", "native GPU pixel parity"]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report": str(args.output), "fixture": str(args.fixture),
                      "cases": len(cases), "quads": report["quad_count"],
                      "atlas_cells": len(cells_seen), "original_execution_complete": True}))


if __name__ == "__main__":
    main()
