#!/usr/bin/env python3
"""Development-only execution of original battle timeline helpers.

Requires the user's private original ARMv6 image and the pinned original
libgcc. Neither input is copied to the result or shipped in the native app.
The original helpers and original libgcc execute without instruction patches.
Object retain/release and virtual slot 0x24 are synthetic recording endpoints;
the last endpoint records its requested integer time, not a rendered pose.
This runner does not execute the complete cinematic state machine.
"""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys


IMAGE_SHA = "0d510516fe3676ee4a0f4dff60ba64e1c5bf79a0c9800f420b1bbdb1c12febfd"
LIBGCC_SHA = "d758fbf1ac952532955d62866bd02df55315c0599f64bdd978ff941fccbdcf83"
FRAME_SCALE_BITS = 0x42055555
START_TABLE = 0xCEAA8
END_TABLE = 0xCEA90


def sha(data):
    return hashlib.sha256(data).hexdigest()


def f32(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--libgcc", type=Path, required=True)
    parser.add_argument("--unicorn-dir", type=Path, required=True)
    parser.add_argument(
        "--combat-oracle", type=Path,
        default=Path(__file__).resolve().parents[1] / "combat" / "oracle.py")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.unicorn_dir.resolve()))
    import unicorn

    image, gcc = args.binary.read_bytes(), args.libgcc.read_bytes()
    if sha(image) != IMAGE_SHA or sha(gcc) != LIBGCC_SHA:
        raise ValueError("original image or libgcc differs from the audited input")
    loader = importlib.util.spec_from_file_location(
        "g1_battle_timeline_original", args.combat_oracle)
    old = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(old)
    old.MATH.update({
        0xBA30C: "___floatsisfvfp",
        0xBA390: "___mulsf3vfp",
        0xBA330: "___gesf2vfp",
        0xBA2C4: "___fixsfsivfp",
    })
    old.BOUNDARIES[0xBA210] = "nonthrowing SjLj unwind unregistration"

    class OriginalTimeline(old.OriginalCombat):
        def __init__(self):
            self.timed_calls = []
            super().__init__(image, gcc)

        def hook(self, instance, address, size, data):
            if address in (0x3000080, 0x3000084, 0x3000088):
                if address == 0x3000088:
                    self.timed_calls.append(
                        old.signed(instance.reg_read(self.ar.UC_ARM_REG_R1)))
                instance.reg_write(
                    self.ar.UC_ARM_REG_PC,
                    instance.reg_read(self.ar.UC_ARM_REG_LR))
                return
            super().hook(instance, address, size, data)

    original = OriginalTimeline()
    vtable, node = original.alloc(0x40), original.alloc(8)
    slot, clock = original.alloc(4), original.alloc(4)
    original.w32(node, vtable)
    original.w32(slot, node)
    for offset, destination in (
            (0, 0x3000081), (4, 0x3000085), (0x24, 0x3000089)):
        original.w32(vtable + offset, destination)

    starts = list(struct.unpack_from("<6h", image, START_TABLE - 0x1000))
    ends = list(struct.unpack_from("<6h", image, END_TABLE - 0x1000))
    scale = struct.unpack("<f", struct.pack("<I", FRAME_SCALE_BITS))[0]
    tables = [{
        "clip": clip,
        "start_frame": starts[clip],
        "end_frame": ends[clip],
        "start_ms": int(f32(starts[clip] * scale)),
        "end_float_ms": f32(ends[clip] * scale),
        "end_clamped_ms": int(f32(ends[clip] * scale)),
    } for clip in range(6)]
    cases = []
    for table in tables:
        clip = table["clip"]
        original.w32(clock, 0x76543210)
        original.timed_calls = []
        original.call(0x3C23A, [0, slot, clip, clock])
        cases.append({
            "name": "start_" + str(clip), "kind": "start", "clip": clip,
            "clock_before": 0x76543210,
            "clock_after": old.signed(original.r32(clock)),
            "virtual_24_calls_ms": original.timed_calls[:],
        })
        end = table["end_clamped_ms"]
        for restart in (False, True):
            inputs = [
                ("before", end - 2, 1),
                ("integer_end", end, 0),
                ("cross", end, 1),
                ("large_step", table["start_ms"], 20000),
            ]
            for name, current, delta in inputs:
                original.w32(clock, current)
                original.timed_calls = []
                result = original.call(
                    0x3C950, [0, slot, delta, clip, int(restart), clock])
                cases.append({
                    "name": f"tick_{clip}_{int(restart)}_{name}",
                    "kind": "tick", "clip": clip, "restart": restart,
                    "clock_before": current, "delta_ms": delta,
                    "clock_after": old.signed(original.r32(clock)),
                    "completion_return": result,
                    "virtual_24_calls_ms": original.timed_calls[:],
                })
    original.check_text()
    report = {
        "schema": 1,
        "kind": "unchanged original battle timeline helper execution",
        "original_image_sha256": IMAGE_SHA,
        "original_libgcc_sha256": LIBGCC_SHA,
        "original_libgcc_armv6_sha256": sha(original.thin),
        "unicorn_version": unicorn.__version__,
        "runner_sha256": sha(Path(__file__).read_bytes()),
        "base_oracle_sha256": sha(args.combat_oracle.read_bytes()),
        "helpers": {"start": "0x3c23a", "tick": "0x3c950"},
        "tables": {"starts": hex(START_TABLE), "ends": hex(END_TABLE),
                   "milliseconds_per_frame_float_bits": hex(FRAME_SCALE_BITS),
                   "clips": tables},
        "case_count": len(cases),
        "case_counts": {"start": 6, "tick": 48},
        "instruction_patches": 0,
        "original_text_readonly_unchanged": True,
        "original_libgcc_readonly_unchanged": True,
        "synthetic_inputs": True,
        "recording_boundaries": [
            "nonthrowing SjLj unwind registration and unregistration",
            "synthetic object retain and release",
            "synthetic public virtual slot 0x24: record signed R1 time only",
        ],
        "scope": {
            "original_timeline_arithmetic_executed": True,
            "actual_model_object_executed": False,
            "complete_cinematic_state_machine_executed": False,
            "gpu_rendering": False,
            "native_comparison": False,
        },
        "cases": cases,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "case_count": len(cases),
        "original_text_readonly_unchanged": True,
        "original_libgcc_readonly_unchanged": True,
        "output": str(args.output),
    }))


if __name__ == "__main__":
    main()
