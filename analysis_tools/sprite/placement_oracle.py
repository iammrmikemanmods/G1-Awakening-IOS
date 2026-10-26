#!/usr/bin/env python3
"""Development-only original unit anchor and transform-operation oracle.

Executes original basic block 0x6cf00..0x6cf66 with explicitly seeded caller
locals, stopping at its call to 0x727a4. Then executes complete 0x727a4 with
recording transform/mesh API boundaries and unchanged original libgcc math.
This verifies arguments and operation order, not matrix multiplication or GPU.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import struct
import subprocess
import sys

import render_oracle as base

# Extend only this process's loader table; frozen render_oracle.py is unchanged.
base.MATH.update({0xba228: "___addsf3vfp", 0xba3b4: "___subsf3vfp"})


def signed32(value):
    return struct.unpack("<i", struct.pack("<I", value & 0xffffffff))[0]


class OriginalPlacement(base.OriginalRenderer):
    def __init__(self, image, gcc):
        super().__init__(image, gcc)
        self.operations = []
        self.stop_at_placement = False
        self.transform = self.object({0x1c: "transform_identity", 0x28: "transform_rotation",
                                      0x30: "transform_scale", 0x34: "transform_translation"})
        self.mesh = self.object({0x7c: "mesh_set_transform"})
        self.sprite = self.alloc(0xe8)
        self.word(self.sprite+0xdc, self.transform)
        self.word(self.sprite+0xb0, self.mesh)
        self.unit = self.alloc(0x80)
        self.sprite_table = self.alloc(4)
        self.word(self.sprite_table, self.sprite)
        self.word(0xd8e8c, self.sprite_table)

    def hook(self, instance, address, size, user):
        ar = self.ar
        if self.stop_at_placement and address == 0x727a4:
            sp = instance.reg_read(ar.UC_ARM_REG_SP)
            self.anchor_arguments = [instance.reg_read(getattr(ar, "UC_ARM_REG_R"+str(i))) for i in range(4)]
            self.anchor_arguments += [self.read_word(sp), self.read_word(sp+4)]
            instance.emu_stop()
            return
        name = self.handlers.get(address)
        if name and (name.startswith("transform_") or name == "mesh_set_transform"):
            if name == "transform_identity":
                values = []
            elif name == "mesh_set_transform":
                if instance.reg_read(ar.UC_ARM_REG_R1) != self.transform:
                    raise RuntimeError("original assigned a different transform")
                values = []
            else:
                count = 4 if name == "transform_rotation" else 3
                pointer = instance.reg_read(ar.UC_ARM_REG_R1)
                values = list(struct.unpack("<"+"I"*count, instance.mem_read(pointer, count*4)))
            self.operations.append({"operation": name, "bits": values})
            instance.reg_write(ar.UC_ARM_REG_PC, instance.reg_read(ar.UC_ARM_REG_LR))
            return
        super().hook(instance, address, size, user)

    def run(self, case):
        x, y, form, dx, dy, site, group = case
        ar = self.ar
        self.u.mem_write(self.unit+0x3b, bytes([x, y]))
        self.u.mem_write(self.unit+0xc, bytes([form]))
        self.word(self.unit+0x40, dx)
        self.word(self.unit+0x44, dy)
        sp = 0x21fe000
        for offset, value in ((0x2c, 0), (0x58, self.unit), (0x34, y),
                              (0x8c, dy), (0x70, 5 if group else (20 if site else 0))):
            self.word(sp+offset, value)
        self.u.reg_write(ar.UC_ARM_REG_CPSR, 0x30)
        self.u.reg_write(ar.UC_ARM_REG_SP, sp)
        self.stop_at_placement = True
        self.anchor_arguments = None
        self.u.emu_start(0x6cf01, 0x3000000, count=100000, timeout=2_000_000)
        self.stop_at_placement = False
        if self.anchor_arguments is None:
            raise RuntimeError("original anchor block did not reach expected placement call")
        self.operations = []
        self.call(0x727a4, self.anchor_arguments)
        expected_names = ["transform_identity", "transform_scale", "transform_translation",
                          "transform_rotation", "mesh_set_transform"]
        if [op["operation"] for op in self.operations] != expected_names:
            raise RuntimeError("original transform operation order changed")
        scale = self.operations[1]["bits"]
        if len(set(scale)) != 1:
            raise RuntimeError("original scale was not uniform")
        rotation = self.operations[3]["bits"]
        return [[signed32(x) for x in self.anchor_arguments[1:4]], scale[0],
                self.operations[2]["bits"], rotation[0], rotation[1:]]


def make_cases():
    cases = [[1, 2, 0, 0, 0, 0, 0], [4, 7, 0, 0, 0, 0, 0]]
    rng = random.Random(0x727a4)
    for x in (0, 1, 14, 255):
        for y in (0, 2, 13, 255):
            for form in (0, 1):
                for site in (0, 1):
                    for group in (0, 1):
                        cases.append([x, y, form, rng.randrange(-32, 33), rng.randrange(-32, 33), site, group])
    return cases


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--binary", type=Path, required=True)
    p.add_argument("--libgcc", type=Path, required=True)
    p.add_argument("--unicorn-dir", type=Path, required=True)
    p.add_argument("--native-probe", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    image, gcc = args.binary.read_bytes(), args.libgcc.read_bytes()
    if base.digest(image) != base.IMAGE_SHA or base.digest(gcc) != base.LIBGCC_SHA:
        raise ValueError("original executable/libgcc input hash differs from audited input")
    sys.path.insert(0, str(args.unicorn_dir))
    import unicorn
    cases = make_cases()
    wire = str(len(cases))+"\n"+"\n".join(" ".join(map(str, c)) for c in cases)+"\n"
    result = subprocess.run([str(args.native_probe.resolve())], input=wire, text=True,
                            capture_output=True, check=True, timeout=30)
    actual = [json.loads(line) for line in result.stdout.splitlines()]
    if len(actual) != len(cases):
        raise RuntimeError("native placement probe returned the wrong case count")
    original = OriginalPlacement(image, gcc)
    for case, native in zip(cases, actual):
        expected = original.run(case)
        if expected != native[:5]:
            raise RuntimeError(json.dumps({"case": case, "original": expected, "native": native}))
    report = {"scope": "Original unit anchor block and complete placement function, with recorded transform API boundaries",
              "original_sha256": base.IMAGE_SHA, "libgcc_sha256": base.LIBGCC_SHA,
              "unicorn_version": unicorn.__version__, "original_code_readonly_and_unchanged": True,
              "instruction_patches": 0, "functions": ["0x6cf00..0x6cf66 basic block", "0x727a4 complete function"],
              "caller_locals": "Unit fields, selected sprite pointer, coordinates, offsets, site predicate results explicitly seeded",
              "math_helpers": "unchanged original ARMv6 libgcc instructions",
              "substitutions": ["transform/mesh API recording boundaries"],
              "operations": ["identity", "uniform scale", "translation", "axis-angle rotation", "mesh setTransform"],
              "matrix_multiplication_order_verified": False, "cases": len(cases), "scalar_comparisons": len(cases)*11,
              "first_units": [{"input": c, "recorded_components": a[:5]} for c, a in zip(cases[:2], actual[:2])],
              "oracle_source_sha256": base.digest(Path(__file__).read_bytes()),
              "shared_render_oracle_sha256": base.digest(Path(base.__file__).read_bytes()),
              "native_probe_binary_sha256": base.digest(args.native_probe.read_bytes()),
              "case_sha256": base.digest(wire.encode()), "native_output_sha256": base.digest(result.stdout.encode()),
              "passed": True, "gpu_or_device_test": False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps({k: report[k] for k in ("passed", "cases", "scalar_comparisons", "first_units")}))


if __name__ == "__main__":
    main()
