#!/usr/bin/env python3
"""Record the original tactical camera setup and bounded immediate focus path.

Original client instructions and ARMv6 libgcc arithmetic are unchanged. Four
libSystem trigonometric imports use explicit host libm implementations; their
rounding is not claimed identical to historical iOS libm. M3G setter boundaries
are recorded, not rendered. The oracle and all original-code dependencies are
excluded from the native product.
"""
import argparse
import ctypes
import ctypes.util
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sprite"))
import render_oracle as base

EXTRA_MATH = {0xba228: "___addsf3vfp", 0xba264: "___divdf3vfp",
              0xba2ac: "___extendsfdf2vfp", 0xba2b8: "___fixdfsivfp",
              0xba300: "___floatsidfvfp", 0xba378: "___muldf3vfp",
              0xba3a8: "___subdf3vfp", 0xba3b4: "___subsf3vfp",
              0xba3d8: "___truncdfsf2vfp"}
base.MATH.update(EXTRA_MATH)
LIBM = {0xba558: ("atanf", "f"), 0xba594: ("cos", "d"),
        0xbabe8: ("tan", "d"), 0xbabf4: ("tanf", "f")}


def floats(bits):
    return [struct.unpack("<f", struct.pack("<I", v))[0] for v in bits]


class OriginalCamera(base.OriginalRenderer):
    def __init__(self, image, gcc, width, height, map_width, map_height):
        self.recorded = []
        self.math_samples = []
        self.libm_name = ctypes.util.find_library("m")
        if not self.libm_name:
            raise RuntimeError("host libm is unavailable")
        self.libm = ctypes.CDLL(self.libm_name)
        for name, kind in LIBM.values():
            function = getattr(self.libm, name)
            function.argtypes = [ctypes.c_float if kind == "f" else ctypes.c_double]
            function.restype = function.argtypes[0]
        super().__init__(image, gcc)
        self.context = self.alloc(0x100)
        self.word(self.context + 0x10, width)
        self.word(self.context + 0x14, height)
        self.camera = self.object({0xc8: "camera_projection", 0x60: "camera_orientation",
                                   0x50: "camera_translation", 0x80: "camera_transform_interface"})
        self.word(0xd963c, self.camera)
        self.word(0xd8de0, map_width)
        self.word(0xd8de4, map_height)

    def hook(self, instance, address, size, user):
        ar = self.ar
        if address in LIBM:
            name, kind = LIBM[address]
            low = instance.reg_read(ar.UC_ARM_REG_R0)
            high = instance.reg_read(ar.UC_ARM_REG_R1)
            argument = struct.unpack("<" + kind, struct.pack("<I", low) if kind == "f"
                                     else struct.pack("<II", low, high))[0]
            result = getattr(self.libm, name)(argument)
            encoded = struct.pack("<" + kind, result)
            instance.reg_write(ar.UC_ARM_REG_R0, struct.unpack_from("<I", encoded)[0])
            if kind == "d":
                instance.reg_write(ar.UC_ARM_REG_R1, struct.unpack_from("<I", encoded, 4)[0])
            self.math_samples.append({"name": name, "input": argument, "output": result})
            self.calls["host_libm:" + name] += 1
            instance.reg_write(ar.UC_ARM_REG_PC, instance.reg_read(ar.UC_ARM_REG_LR))
            return
        if address == 0x62d0c:
            self.calls["logical_screen_context"] += 1
            instance.reg_write(ar.UC_ARM_REG_R0, self.context)
            instance.reg_write(ar.UC_ARM_REG_PC, instance.reg_read(ar.UC_ARM_REG_LR))
            return
        registers = [instance.reg_read(getattr(ar, "UC_ARM_REG_R" + str(i))) for i in range(4)]
        name = self.handlers.get(address)
        if name == "camera_projection":
            values = [*registers[1:], self.read_word(instance.reg_read(ar.UC_ARM_REG_SP))]
            self.recorded.append({"operation": name, "float_bits": values, "values": floats(values)})
        elif name in ("camera_orientation", "camera_translation"):
            count = 4 if name == "camera_orientation" else 3
            values = list(struct.unpack("<" + "I" * count, instance.mem_read(registers[1], count * 4)))
            self.recorded.append({"operation": name, "float_bits": values, "values": floats(values)})
        elif name == "camera_transform_interface":
            # The explicitly supplied synthetic M3G object implements both
            # camera and transform interfaces; no original object is inferred.
            self.word(registers[1], self.camera)
        elif address == 0x6688c:
            self.recorded.append({"operation": "camera_position_target", "float_bits": registers,
                                  "values": floats(registers)})
            self.calls["camera_position_target_boundary"] += 1
            instance.reg_write(ar.UC_ARM_REG_PC, instance.reg_read(ar.UC_ARM_REG_LR))
            return
        super().hook(instance, address, size, user)

    def block(self, start, end, frame):
        ar = self.ar
        for i in range(13):
            self.u.reg_write(getattr(ar, "UC_ARM_REG_R" + str(i)), 0)
        self.u.reg_write(ar.UC_ARM_REG_CPSR, 0x30)
        self.u.reg_write(ar.UC_ARM_REG_SP, frame)
        self.u.reg_write(ar.UC_ARM_REG_LR, 0x3000001)
        self.u.emu_start(start | 1, end, count=100000, timeout=2_000_000)
        if self.u.reg_read(ar.UC_ARM_REG_PC) != end or self.u.reg_read(ar.UC_ARM_REG_SP) != frame:
            raise RuntimeError("original camera block escaped its bounded endpoint")

    def setup(self):
        frame = 0x21fe000
        self.word(frame + 0x60, self.context)
        self.block(0x6e40a, 0x6e460, frame)
        self.block(0x6e4e8, 0x6e52e, frame)
        self.call(0x6585e, [])
        bounds = {"minimum_row_world_float": floats([self.read_word(0xd8e48)])[0],
                  "maximum_row_world_float": floats([self.read_word(0xd8e4c)])[0],
                  "border_half_width_world": self.read_word(0xd8e50),
                  "minimum_column_world": self.read_word(0xd8e54),
                  "height_world": self.read_word(0xd8e68),
                  "depth_world": self.read_word(0xd8e6c)}
        setup = list(self.recorded)
        positions = []
        for x, y in ((1, 2), (5, 7), (0, 0), (14, 13)):
            self.call(0x66c20, [x, y, 0, 0, 1])
            positions.append({"tile_target": [x, y], "immediate": True,
                              "clamped_world": [self.read_word(0xd8e58), self.read_word(0xd8e5c)],
                              "call_to_6688c": self.recorded[-1]})
        return setup, bounds, positions


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--binary", type=Path, required=True)
    ap.add_argument("--libgcc", type=Path, required=True)
    ap.add_argument("--unicorn-dir", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    if args.unicorn_dir:
        sys.path.insert(0, str(args.unicorn_dir))
    import unicorn
    image, gcc = args.binary.read_bytes(), args.libgcc.read_bytes()
    if base.digest(image) != base.IMAGE_SHA or base.digest(gcc) != base.LIBGCC_SHA:
        raise ValueError("original camera inputs differ from pinned sources")
    cases = []
    for width, height in ((320, 480), (480, 320)):
        original = OriginalCamera(image, gcc, width, height, 15, 14)
        setup, bounds, positions = original.setup()
        if setup[0]["values"] != [30.0, floats([base.float_bits(width / height)])[0], 1.0, 8.0]:
            raise RuntimeError("original projection arguments differ from recovered setup")
        if setup[1]["values"] != [-45.0, 1.0, 0.0, 0.0]:
            raise RuntimeError("original camera orientation differs")
        if bytes(original.u.mem_read(0x1000, 0xd1000)) != original.original_text:
            raise RuntimeError("original camera code changed")
        cases.append({"supplied_logical_viewport": [width, height], "map_dimensions": [15, 14],
                      "original_setter_calls": setup, "original_bound_results_with_host_libm": bounds,
                      "focus_results": positions, "trigonometric_calls": original.math_samples,
                      "call_counts": dict(original.calls)})
    report = {"scope": "Original camera setter/focus behavior under TWO supplied viewport inputs; neither is an observed live viewport",
              "original_sha256": base.IMAGE_SHA, "libgcc_sha256": base.LIBGCC_SHA,
              "oracle_source_sha256": base.digest(Path(__file__).read_bytes()),
              "shared_renderer_oracle_sha256": base.digest((Path(__file__).resolve().parents[1] /
                                                              "sprite/render_oracle.py").read_bytes()),
              "original_functions": ["0x6e40a..0x6e460", "0x6e4e8..0x6e52e", "0x6585e", "0x66c20"],
              "unicorn_version": unicorn.__version__, "cases": cases,
              "live_game_viewport_observed_by_this_oracle": False,
              "actual_initial_playable_camera_claimed": False,
              "original_client_code_and_libgcc_unchanged": True, "instruction_patches": 0,
              "libm_boundary": {"implementation": original.libm_name,
                                "functions": [x[0] for x in LIBM.values()],
                                "historical_ios_bit_identity_claimed": False},
              "other_substitutions": ["logical viewport context", "M3G setter recording/ownership",
                                      "camera target function0x6688c recording boundary"],
              "gpu_rendered": False, "device_tested": False,
              "not_established": ["full camera scene hierarchy/matrix execution", "animated pan interpolation",
                                  "live logical viewport/orientation binding", "scene hierarchy/90-degree display rotation",
                                  "historical libSystem trigonometric bit parity", "GPU pixel parity"]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report": str(args.output), "conditional_cases": [
        {"viewport": c["supplied_logical_viewport"], "projection": c["original_setter_calls"][0]["values"],
         "bounds": c["original_bound_results_with_host_libm"], "first_focus": c["focus_results"][0]}
        for c in cases], "actual_initial_playable_camera_claimed": False}))


if __name__ == "__main__":
    main()
