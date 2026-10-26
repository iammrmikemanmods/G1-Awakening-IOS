#!/usr/bin/env python3
"""Development-only comparison of native playback with original ARM functions.

Original 0x72d80 and 0x72cc0 execute unchanged. Allocation/free, byte-buffer
initialization and geometry refresh are recorded boundary substitutions.
No clock arithmetic, duration lookup, repeat logic or step decision is mocked.
The original executable and external Unicorn are explicit local inputs only.
"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import struct
import subprocess
import sys

IMAGE_SHA = "0d510516fe3676ee4a0f4dff60ba64e1c5bf79a0c9800f420b1bbdb1c12febfd"


def digest(value):
    return hashlib.sha256(value).hexdigest()


class OriginalAnimation:
    def __init__(self, image):
        import unicorn as uc
        from unicorn import arm_const as ar
        self.ar, self.uc_api = ar, uc
        self.u = uc.Uc(uc.UC_ARCH_ARM, uc.UC_MODE_THUMB)
        self.u.mem_map(0x1000, 0xf0000)
        self.u.mem_write(0x1000, image)
        self.text = image[:0xd1000]
        self.u.mem_protect(0x1000, 0xd1000, uc.UC_PROT_READ | uc.UC_PROT_EXEC)
        self.u.mem_map(0x1000000, 0x400000)
        self.u.mem_map(0x2000000, 0x200000)
        self.u.mem_map(0x3000000, 0x1000)
        self.next, self.refreshes, self.calls = 0x1000000, 0, Counter()
        self.u.hook_add(uc.UC_HOOK_CODE, self.hook)

    def alloc(self, size):
        address = self.next
        self.next += (max(8, size)+7) & ~7
        if self.next > 0x1400000:
            raise RuntimeError("synthetic animation heap exhausted")
        self.u.mem_write(address, b"\0" * max(8, size))
        return address

    def word(self, address, value):
        self.u.mem_write(address, struct.pack("<I", value & 0xffffffff))

    def read_word(self, address, signed=False):
        return struct.unpack("<i" if signed else "<I", self.u.mem_read(address, 4))[0]

    def vector(self, address, data, count):
        self.word(address, data)
        self.word(address+4, count)

    def hook(self, instance, address, size, user):
        ar = self.ar
        if address == 0x728f0:
            self.refreshes += 1
            self.calls["geometry_refresh"] += 1
        elif address == 0x1f540:
            instance.reg_write(ar.UC_ARM_REG_R0, self.alloc(instance.reg_read(ar.UC_ARM_REG_R0)))
            self.calls["allocate"] += 1
        elif address == 0x1f512:
            self.calls["free"] += 1
        elif address == 0x1f4e0:
            pointer = instance.reg_read(ar.UC_ARM_REG_R0)
            fill = instance.reg_read(ar.UC_ARM_REG_R1) & 255
            count = instance.reg_read(ar.UC_ARM_REG_R2)
            if count > 255:
                raise RuntimeError("unexpected original byte-buffer initialization size")
            instance.mem_write(pointer, bytes([fill])*count)
            self.calls["byte_buffer_initialize"] += 1
        else:
            return
        instance.reg_write(ar.UC_ARM_REG_PC, instance.reg_read(ar.UC_ARM_REG_LR))

    def call(self, function, arguments):
        ar = self.ar
        for i in range(13):
            self.u.reg_write(getattr(ar, "UC_ARM_REG_R"+str(i)), 0)
        self.u.reg_write(ar.UC_ARM_REG_CPSR, 0x30)
        self.u.reg_write(ar.UC_ARM_REG_SP, 0x21ff000)
        self.u.reg_write(ar.UC_ARM_REG_LR, 0x3000001)
        for i, value in enumerate(arguments):
            self.u.reg_write(getattr(ar, "UC_ARM_REG_R"+str(i)), value & 0xffffffff)
        self.u.emu_start(function | 1, 0x3000000, count=1000000, timeout=2_000_000)
        if (self.u.reg_read(ar.UC_ARM_REG_PC) != 0x3000000 or
                self.u.reg_read(ar.UC_ARM_REG_SP) != 0x21ff000):
            raise RuntimeError(f"original function {function:#x} did not return within bound")

    def state(self, sprite, changed):
        index = self.read_word(sprite+0x64)
        count = self.read_word(sprite+0x60)
        if not 0 <= index < count:
            raise RuntimeError("original animation step escaped the seeded sequence")
        frames = self.read_word(sprite+0x5c)
        return [index, self.u.mem_read(frames+index, 1)[0],
                self.read_word(sprite+0x78, True), self.read_word(sprite+0x70, True),
                self.u.mem_read(sprite+0xc4, 1)[0], self.u.mem_read(sprite+0x75, 1)[0], int(changed)]

    def run(self, case):
        self.next = 0x1000000
        sprite = self.alloc(0xd0)
        frames_outer, durations_outer = self.alloc(24), self.alloc(24)
        frames, durations = self.alloc(len(case["steps"])), self.alloc(2*len(case["steps"]))
        self.u.mem_write(frames, bytes(x[0] for x in case["steps"]))
        self.u.mem_write(durations, struct.pack("<"+"h"*len(case["steps"]), *(x[1] for x in case["steps"])))
        self.vector(frames_outer+16, frames, len(case["steps"]))
        self.vector(durations_outer+16, durations, len(case["steps"]))
        self.vector(sprite+0x48, frames_outer, 3)
        self.vector(sprite+0x50, durations_outer, 3)
        previous = self.refreshes
        self.call(0x72d80, [sprite, 2, case["repeat"], case["reverse"]])
        states = [self.state(sprite, self.refreshes != previous)]
        for delta in case["deltas"]:
            previous = self.refreshes
            self.call(0x72cc0, [sprite, delta])
            states.append(self.state(sprite, self.refreshes != previous))
        return states


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--binary", type=Path, required=True)
    p.add_argument("--unicorn-dir", type=Path, required=True)
    p.add_argument("--atlas-decoder", type=Path, required=True)
    p.add_argument("--audit-dir", type=Path, required=True)
    p.add_argument("--native-probe", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    image = args.binary.read_bytes()
    if digest(image) != IMAGE_SHA:
        raise ValueError("original image hash differs from the audited input")
    sys.path.insert(0, str(args.unicorn_dir))
    import unicorn
    spec = importlib.util.spec_from_file_location("atlas_reference", args.atlas_decoder)
    decoder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(decoder)
    manifest = json.loads((args.audit_dir/"results/asset_manifest.json").read_text())
    sequences, inputs = [], []
    for resource in decoder.RESOURCE_IDS:
        item = next(x for x in manifest["resources"] if x["resource_id"] == resource and x["key_hex"] == "0xf4e02223")
        data = (args.audit_dir/"results/extracted/bin"/item["extracted_filename"]).read_bytes()
        if digest(data) != item["sha256"]:
            raise ValueError("descriptor hash differs from original asset audit")
        inputs.append({"resource": resource, "sha256": digest(data)})
        for i, steps in enumerate(decoder.decode(data)["animations"]):
            if not steps:
                raise ValueError("unexpected empty original animation")
            sequences.append((f"resource{resource}/animation{i}", steps))
    corpus_count = len(sequences)
    rng = random.Random(0x72cc0)
    sequences += [("synthetic-single", [[42, 1]]),
                  ("synthetic-unequal", [[7, 100], [8, 30], [9, 200]])]
    for i in range(30):
        sequences.append((f"synthetic-{i}", [[rng.randrange(256), rng.randrange(1, 1001)]
                                             for _ in range(rng.randrange(1, 16))]))
    cases = []
    for name, steps in sequences:
        for repeat in (-1, 0, 1, 3):
            for reverse in (0, 1):
                d = steps[-1 if reverse else 0][1]
                cases.append({"name": name, "steps": steps, "repeat": repeat, "reverse": reverse,
                              "deltas": [0, d-1, 1, 16, 17, 33, 100, max(x[1] for x in steps)*3+1, 1000, 0]})
    lines = [str(len(cases))]
    for case in cases:
        line = [len(case["steps"]), case["repeat"], case["reverse"], len(case["deltas"])]
        line += [value for step in case["steps"] for value in step]
        line += case["deltas"]
        lines.append(" ".join(map(str, line)))
    native = subprocess.run([str(args.native_probe.resolve())], input="\n".join(lines)+"\n",
                            text=True, capture_output=True, check=True, timeout=30)
    native_states = [json.loads(x) for x in native.stdout.splitlines()]
    if len(native_states) != len(cases):
        raise RuntimeError("native probe returned the wrong case count")
    original = OriginalAnimation(image)
    comparisons = 0
    for i, (case, actual) in enumerate(zip(cases, native_states)):
        expected = original.run(case)
        if expected != actual:
            raise RuntimeError(json.dumps({"case": case, "original": expected, "native": actual}))
        comparisons += sum(len(x) for x in expected)
    if bytes(original.u.mem_read(0x1000, 0xd1000)) != original.text:
        raise RuntimeError("original executable instructions changed")
    report = {"scope": "Native sprite animation start/advance state versus unchanged original routines",
              "original_sha256": IMAGE_SHA, "unicorn_version": unicorn.__version__,
              "oracle_source_sha256": digest(Path(__file__).read_bytes()),
              "decoder_source_sha256": digest(args.atlas_decoder.read_bytes()),
              "native_probe_binary_sha256": digest(args.native_probe.read_bytes()),
              "functions": ["0x72d80", "0x72cc0"], "original_code_readonly_and_unchanged": True,
              "instruction_patches": 0,
              "substitutions": ["allocation/free", "byte buffer initialization", "geometry refresh observer"],
              "original_descriptor_inputs": inputs, "original_animations": corpus_count,
              "synthetic_sequences": len(sequences)-corpus_count, "cases": len(cases),
              "states": sum(len(x) for x in native_states), "scalar_comparisons": comparisons,
              "state_fields": ["step", "frame", "elapsed_ms", "repeat_count", "reverse", "complete", "geometry_refresh"],
              "case_sha256": digest(json.dumps(cases, sort_keys=True).encode()),
              "native_state_sha256": digest(native.stdout.encode()), "boundary_calls": dict(original.calls),
              "passed": True, "gameplay_or_gpu_or_device_test": False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps({k: report[k] for k in ("passed", "cases", "states", "scalar_comparisons")}))


if __name__ == "__main__":
    main()
