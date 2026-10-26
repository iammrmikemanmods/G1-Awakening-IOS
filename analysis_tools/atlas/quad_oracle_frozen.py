#!/usr/bin/env python3
"""Development-only original ARM sprite arithmetic oracle, not product code.

Original function 0x728f0 runs with original code/vector-index helpers. Explicit
boundary substitutions avoid C++ allocation/unwinder and M3G GPU calls: two
unwind registration no-ops, a read-only shallow vector copy, its no-op teardown,
and two GPU-upload no-ops. None computes geometry or texture coordinates.
This does not validate the original parser, M3G upload, or GPU rendering.
"""
import collections
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "native/tests"))
from generate_atlas_reference import RESOURCE_IDS, decode, canonical, sha

sys.path.insert(0, "/tmp/g1-movement-oracle-tools/python")
import unicorn as uc
from unicorn import arm_const as ar

IMAGE = ROOT / "research/binary/G1awakening.armv6"
EXPECTED_SHA = "0d510516fe3676ee4a0f4dff60ba64e1c5bf79a0c9800f420b1bbdb1c12febfd"
PROBE = ROOT / "native/research/atlas_validation/atlas_probe"


class OriginalQuad:
    BOUNDARIES = {
        0xba1f8: "__Unwind_SjLj_Register no-op",
        0xba210: "__Unwind_SjLj_Unregister no-op",
        0x5c8a8: "read-only vector shallow copy",
        0x5c680: "paired vector teardown no-op",
        0x71c20: "position GPU upload no-op (buffer retained)",
        0x72100: "UV GPU upload no-op (buffer retained)",
    }

    def __init__(self, image, descriptor):
        self.u = uc.Uc(uc.UC_ARCH_ARM, uc.UC_MODE_THUMB)
        self.u.mem_map(0x1000, 0xf0000)
        self.u.mem_write(0x1000, image)
        self.u.mem_protect(0x1000, 0xd1000, uc.UC_PROT_READ | uc.UC_PROT_EXEC)
        self.u.mem_map(0x1000000, 0x400000)
        self.u.mem_map(0x2000000, 0x200000)
        self.u.mem_map(0x3000000, 0x1000)
        self.u.reg_write(ar.UC_ARM_REG_C1_C0_2, 0x00f00000)
        self.u.reg_write(ar.UC_ARM_REG_FPEXC, 0x40000000)
        self.next = 0x1000000
        self.sprite = self.alloc(0x100)
        self.position = self.alloc(255 * 24)
        self.uv = self.alloc(255 * 16)
        self.descriptor = descriptor
        self.boundary_counts = collections.Counter()
        self.original_text = bytes(image[:0xd1000])
        self.u.hook_add(uc.UC_HOOK_CODE, self.hook)
        rects = descriptor["rectangles"]
        variants = descriptor["variants"]
        adjusted = []
        for index, orientation in variants:
            x, y, w, h = rects[index]
            adjusted.append([x+1, y if y+1+h > 512 else y+1, w, h])
        for component in range(4):
            self.vector(self.sprite + 8 + component * 8,
                        self.array([r[component] for r in adjusted], "i"), len(variants))
        self.vector(self.sprite + 0x28, self.array([v[1] for v in variants], "B"), len(variants))
        frames = descriptor["frames"]
        for component in range(3):
            outer = self.alloc(8 * len(frames))
            for index, frame in enumerate(frames):
                parts = frame["parts"]
                self.vector(outer + index * 8, self.array([p[component] for p in parts], "h"), len(parts))
            self.vector(self.sprite + 0x30 + component * 8, outer, len(frames))
        self.active = self.array([0], "B")
        self.vector(self.sprite + 0x5c, self.active, 1)
        self.write32(self.sprite + 0x64, 0)
        self.write32(self.sprite + 0xe0, self.position)
        self.write32(self.sprite + 0xe4, self.uv)

    def alloc(self, n):
        address = self.next
        self.next += (max(n, 8) + 7) & ~7
        if self.next > 0x1400000:
            raise RuntimeError("synthetic oracle allocation exceeds bound")
        return address

    def write32(self, address, value):
        self.u.mem_write(address, struct.pack("<I", value & 0xffffffff))

    def array(self, values, fmt):
        address = self.alloc(len(values) * struct.calcsize(fmt))
        if values:
            self.u.mem_write(address, struct.pack("<" + fmt * len(values), *values))
        return address

    def vector(self, address, data, count):
        self.write32(address, data)
        self.write32(address + 4, count)

    def hook(self, instance, address, size, data):
        if address not in self.BOUNDARIES:
            return
        self.boundary_counts[hex(address)] += 1
        if address == 0x5c8a8:
            destination = instance.reg_read(ar.UC_ARM_REG_R0)
            source = instance.reg_read(ar.UC_ARM_REG_R1)
            instance.mem_write(destination, bytes(instance.mem_read(source, 8)))
        instance.reg_write(ar.UC_ARM_REG_PC, instance.reg_read(ar.UC_ARM_REG_LR))

    def frame(self, index):
        self.u.mem_write(self.active, bytes([index]))
        count = len(self.descriptor["frames"][index]["parts"])
        self.write32(self.sprite + 0xc8, count)
        self.u.mem_write(self.position, b"\xa5" * (255 * 24))
        self.u.mem_write(self.uv, b"\xa5" * (255 * 16))
        initial_sp = 0x21ff000
        self.u.reg_write(ar.UC_ARM_REG_CPSR, 0x30)
        self.u.reg_write(ar.UC_ARM_REG_R0, self.sprite)
        self.u.reg_write(ar.UC_ARM_REG_SP, initial_sp)
        self.u.reg_write(ar.UC_ARM_REG_LR, 0x3000001)
        self.u.emu_start(0x728f1, 0x3000000, timeout=2_000_000, count=100_000)
        if self.u.reg_read(ar.UC_ARM_REG_PC) != 0x3000000 or self.u.reg_read(ar.UC_ARM_REG_SP) != initial_sp:
            raise RuntimeError("original quad routine did not return with balanced stack")
        output = []
        for n in range(count):
            pos = struct.unpack("<12h", self.u.mem_read(self.position + n * 24, 24))
            uv = struct.unpack("<8h", self.u.mem_read(self.uv + n * 16, 16))
            output.append({"source_part_index": count - 1 - n,
                           "positions": [list(pos[i:i+3]) for i in range(0, 12, 3)],
                           "quantized_uv": [list(uv[i:i+2]) for i in range(0, 8, 2)]})
        if bytes(self.u.mem_read(0x1000, 0xd1000)) != self.original_text:
            raise RuntimeError("original code bytes changed")
        return output


def main():
    image = IMAGE.read_bytes()
    if sha(image) != EXPECTED_SHA:
        raise RuntimeError("original ARM binary identity mismatch")
    manifest = json.loads((ROOT / "research/assets/results/asset_manifest.json").read_text())
    records, boundaries = [], collections.Counter()
    for resource_id in RESOURCE_IDS:
        member = next(x for x in manifest["resources"] if x["resource_id"] == resource_id and
                      x["key_hex"] == "0xf4e02223")
        path = ROOT / "research/assets/results/extracted/bin" / member["extracted_filename"]
        descriptor = decode(path.read_bytes())
        if not descriptor["rectangles"]:
            continue
        actual = json.loads(subprocess.run([str(PROBE), str(path)], check=True, capture_output=True,
                                           text=True, timeout=5).stdout)
        oracle = OriginalQuad(image, descriptor)
        output = [oracle.frame(i) for i in range(len(descriptor["frames"]))]
        if output != actual["frame_quads"]:
            for i, (a, b) in enumerate(zip(output, actual["frame_quads"])):
                if a != b:
                    raise RuntimeError(f"Original quad mismatch resource={resource_id} frame={i}: {a} != {b}")
            raise RuntimeError("original quad frame count differs")
        boundaries.update(oracle.boundary_counts)
        records.append({"resource_id": resource_id, "frames": len(output),
                        "quads": sum(map(len, output)), "original_output_sha256": sha(canonical(output)),
                        "native_output_matches_original_arithmetic": True})
    result = {"scope": "Development-only original 0x728f0 arithmetic with explicit infrastructure substitutions",
              "original_sha256": EXPECTED_SHA, "unicorn_version": uc.__version__,
              "original_text_readonly_and_unchanged": True, "instruction_patches": 0,
              "boundary_substitutions": {hex(k): v for k, v in OriginalQuad.BOUNDARIES.items()},
              "boundary_call_counts": dict(boundaries), "descriptor_count": len(records),
              "frames_matched": sum(x["frames"] for x in records),
              "quads_matched": sum(x["quads"] for x in records), "results": records,
              "all_passed": True, "gpu_rendered": False,
              "limitations": ["Six explicit boundary substitutions; not whole original-engine execution",
                              "Original parser was not run; vectors seeded from audited descriptors",
                              "Seven empty descriptor paths were excluded",
                              "No UV normalization, M3G upload, camera, animation timing or device validation"]}
    output = ROOT / "native/research/atlas_validation/original_quad_oracle.json"
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"report": str(output), "descriptor_count": len(records),
                      "frames_matched": result["frames_matched"], "quads_matched": result["quads_matched"],
                      "all_passed": True}))


if __name__ == "__main__":
    main()
