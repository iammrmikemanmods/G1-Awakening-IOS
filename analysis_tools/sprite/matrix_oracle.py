#!/usr/bin/env python3
"""Development-only original CssTransform matrix oracle, never product code.

Runs original identity/scale/translation/quaternion rotation and matrix combine
routines. Original ARMv6 libgcc executes float arithmetic. External sinf/cosf
and memcpy use host libc boundaries; this is not an iOS libm pixel-fidelity test.
"""
import argparse
import ctypes
import ctypes.util
import json
from pathlib import Path
import struct
import subprocess
import sys

import render_oracle as base
import placement_oracle

base.MATH.update({0xba228: "___addsf3vfp", 0xba3b4: "___subsf3vfp",
                  0xba294: "___eqsf2vfp", 0xba408: "___unordsf2vfp"})


def float_value(bits):
    return struct.unpack("<f", struct.pack("<I", bits))[0]


class OriginalMatrix(base.OriginalRenderer):
    def __init__(self, image, gcc):
        super().__init__(image, gcc)
        self.libm = ctypes.CDLL(ctypes.util.find_library("m"))
        for name in ("sinf", "cosf"):
            f = getattr(self.libm, name)
            f.argtypes, f.restype = [ctypes.c_float], ctypes.c_float
        self.libm_calls = []
        # Seed the scalar dispatch targets with symbol-identified original code.
        # No vector arithmetic is replaced: these functions execute unchanged.
        self.word(0xd22c8, 0xb97e1)  # CssVector3D::Magnitude2() const
        self.word(0xd23ac, 0x9fe6b)  # CssVector3D::operator*=(float)
        self.transform_core = self.alloc(0x50)
        self.vector = self.alloc(16)
        self.quaternion = self.alloc(16)

    def hook(self, instance, address, size, user):
        ar = self.ar
        if address in (0xbab40, 0xba5a0):
            name = "sinf" if address == 0xbab40 else "cosf"
            source = instance.reg_read(ar.UC_ARM_REG_R0)
            result = base.float_bits(getattr(self.libm, name)(float_value(source)))
            self.libm_calls.append({"function": name, "input_bits": source, "output_bits": result})
            instance.reg_write(ar.UC_ARM_REG_R0, result)
            instance.reg_write(ar.UC_ARM_REG_PC, instance.reg_read(ar.UC_ARM_REG_LR))
            return
        if address == 0xbaa44:
            dst, src, count = [instance.reg_read(r) for r in
                              (ar.UC_ARM_REG_R0, ar.UC_ARM_REG_R1, ar.UC_ARM_REG_R2)]
            if count > 4096:
                raise RuntimeError("unexpected large matrix memcpy")
            instance.mem_write(dst, bytes(instance.mem_read(src, count)))
            instance.reg_write(ar.UC_ARM_REG_PC, instance.reg_read(ar.UC_ARM_REG_LR))
            return
        super().hook(instance, address, size, user)

    def matrix_bits(self):
        return list(struct.unpack("<16I", self.u.mem_read(self.transform_core+0xc, 64)))

    def run(self, components):
        _, scale, translation, angle, axis = components
        self.call(0xa6848, [self.transform_core])
        self.u.mem_write(self.vector, struct.pack("<3I", *([scale]*3)))
        self.call(0xa6a44, [self.transform_core, self.vector])
        after_scale = self.matrix_bits()
        self.u.mem_write(self.vector, struct.pack("<3I", *translation))
        self.call(0xa6766, [self.transform_core, self.vector])
        after_translation = self.matrix_bits()
        # Same multiply executed by wrapper 0xb25dc..0xb25de.
        self.call(0xba390, [angle, 0x3c8efa35])
        radians = self.u.reg_read(self.ar.UC_ARM_REG_R0)
        self.u.mem_write(self.vector, struct.pack("<3I", *axis))
        self.call(0x9fbd4, [self.quaternion, radians, self.vector])
        quaternion = list(struct.unpack("<4I", self.u.mem_read(self.quaternion, 16)))
        self.call(0xa69b0, [self.transform_core, self.quaternion])
        return {"after_scale_bits": after_scale,
                "after_translation_bits": after_translation,
                "quaternion_bits": quaternion, "matrix_bits": self.matrix_bits()}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ("binary", "libgcc", "unicorn-dir", "native-probe", "output"):
        ap.add_argument("--"+name, type=Path, required=True)
    args = ap.parse_args()
    sys.path.insert(0, str(args.unicorn_dir))
    import unicorn
    image, gcc = args.binary.read_bytes(), args.libgcc.read_bytes()
    if base.digest(image) != base.IMAGE_SHA or base.digest(gcc) != base.LIBGCC_SHA:
        raise ValueError("original input hash differs from audited input")
    cases = placement_oracle.make_cases()
    wire = str(len(cases))+"\n"+"\n".join(" ".join(map(str, c)) for c in cases)+"\n"
    native_result = subprocess.run([str(args.native_probe.resolve())], input=wire, text=True,
                                   capture_output=True, check=True, timeout=30)
    native = [json.loads(line) for line in native_result.stdout.splitlines()]
    if len(native) != len(cases):
        raise RuntimeError("native probe case count differs")
    placement = placement_oracle.OriginalPlacement(image, gcc)
    original = OriginalMatrix(image, gcc)
    results = []
    for case, actual in zip(cases, native):
        components = placement.run(case)
        if components != actual[:5]:
            raise RuntimeError("original/native placement components differ")
        result = original.run(components)
        if result["matrix_bits"] != actual[5]:
            raise RuntimeError(json.dumps({"case": case, "original": result, "native": actual}))
        if len(results) < 2:
            results.append(dict(input=case, **result))
    output = {"scope": "Original transform matrix core and native column-major matrix comparison",
              "original_sha256": base.IMAGE_SHA, "libgcc_sha256": base.LIBGCC_SHA,
              "unicorn_version": unicorn.__version__,
              "functions": ["0xa6848", "0xa6a44", "0xa6766", "0x9fbd4", "0xa69b0", "0x95a0c"],
              "original_code_readonly_and_unchanged": True, "instruction_patches": 0,
              "substitutions": ["external memcpy", "external sinf/cosf using host libm",
                                "unwind registration/unregistration"],
              "dispatch_seeds": {"0xd22c8": "original CssVector3D::Magnitude2 at 0xb97e0",
                                 "0xd23ac": "original CssVector3D::operator*=(float) at 0x9fe6a"},
              "libm_call_count": len(original.libm_calls),
              "libm_distinct_calls": list({json.dumps(c, sort_keys=True): c for c in original.libm_calls}.values()),
              "results": results,
              "cases": len(cases), "matrix_scalar_comparisons": len(cases)*16,
              "component_scalar_comparisons": len(cases)*11,
              "matrix_multiplication_order_verified": "column-major dst = dst * src; final S*T*Rx",
              "passed": True,
              "source_sha256": base.digest(Path(__file__).read_bytes()),
              "shared_render_oracle_sha256": base.digest(Path(base.__file__).read_bytes()),
              "placement_oracle_sha256": base.digest(Path(placement_oracle.__file__).read_bytes()),
              "case_sha256": base.digest(wire.encode()),
              "native_output_sha256": base.digest(native_result.stdout.encode()),
              "native_probe_sha256": base.digest(args.native_probe.read_bytes()),
              "gpu_or_device_test": False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2)+"\n")
    print(json.dumps({k: output[k] for k in ("passed", "cases", "matrix_scalar_comparisons", "results")}))


if __name__ == "__main__":
    main()
