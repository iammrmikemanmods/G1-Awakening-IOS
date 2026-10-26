#!/usr/bin/env python3
"""Development-only reference for original full0x54016 and opcode6 modifiers."""
import argparse
import collections
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import struct

IMAGE_SHA256 = "0d510516fe3676ee4a0f4dff60ba64e1c5bf79a0c9800f420b1bbdb1c12febfd"
SUPPORT_SHA256 = "2c1fc1e53e27c8c0a16a248b4d724f6225f9fdcba05456a9d840cc21d1bc6a79"


def sha(data): return hashlib.sha256(data).hexdigest()
def signed(value, bits=32): return value if value < 1 << (bits - 1) else value - (1 << bits)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--support", type=Path, required=True, help="unchanged world/world_oracle.py")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    image = args.image.read_bytes()
    if sha(image) != IMAGE_SHA256 or sha(args.support.read_bytes()) != SUPPORT_SHA256:
        raise SystemExit("original image/reference support hash mismatch")
    spec = importlib.util.spec_from_file_location("world_support", args.support)
    support = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(support)

    class Reference(support.Reference):
        def __init__(self, definitions):
            self.external_events = []
            super().__init__(image, definitions, b"")
            self.owners([0, 1])
            self.config = self.alloc(0x100)
            self.w32(self.map + 0x290, self.config)
            self.renderer = self.alloc(8)
            self.w32(self.map + 0x298, self.renderer)
            self.vector(self.map + 0x98, self.array([0, 0], "b"), 2)
            self.count_data = self.array([17, 17], "B")
            self.vector(self.map + 0x7c, self.count_data, 2)
            self.funds_data = self.array([0, 0], "i")
            self.vector(self.map + 0x58, self.funds_data, 2)
            self.vector(self.map + 0x60, self.alloc(16), 2)
            self.cost_data = self.array([0] * 23, "B")
            self.vector(self.map + 0x14c, self.cost_data, 23)
            self.w8(self.map + 0x15, 4)
            self.w8(self.map + 0x16, 4)
            self.vector(self.map + 0x18, self.array([0] * 16, "B"), 16)
            self.vector(self.map + 0x20, self.array([0] * 32, "B"), 32)
            self.rule_bytes = self.array([0, 0, 0], "B")
            inner = self.alloc(8)
            self.vector(inner, self.rule_bytes, 3)
            outer = self.alloc(8)
            self.vector(outer, inner, 1)
            self.w32(self.map + 0x294, outer)

        def hook(self, u, address, size, unused):
            if address in (0x60800, 0x60b70, 0x5ca7e):
                ar = self.ar
                r0, r1 = [u.reg_read(r) for r in (ar.UC_ARM_REG_R0, ar.UC_ARM_REG_R1)]
                self.boundaries[hex(address)] += 1
                if address == 0x5ca7e:
                    assert r0 == self.renderer
                    self.external_events.append(["spawn_renderer", r1])
                elif address == 0x60b70:
                    self.external_events.append(["funds_string", signed(r1)])
                u.reg_write(ar.UC_ARM_REG_PC, u.reg_read(ar.UC_ARM_REG_LR))
            else:
                super().hook(u, address, size, unused)

        def r16s(self, at): return struct.unpack("<h", self.u.mem_read(at, 2))[0]

    rows = []
    boundaries = collections.Counter()
    for index, (unit_type, field6, terrain0, terrain2, special, grant) in enumerate(
            itertools.product((0, 11, 21, 22), (0, 1, 255), (1, 99), (0, 1), (0, 1), (0, 1))):
        definitions = []
        for t in range(23):
            form0 = [3, 1, 1, 250, 20, 128, 0, 0, 0, 0, 1, 0, 0, 0]
            form1 = [6, 1, 1, 1, 2, 3, field6 if t == unit_type else 0, 0, 0, 0, 1, 0, 0, 1]
            definitions.append({"type": t, "scalar_fields": [t % 2, 0, 0, 0, 0], "forms": [form0, form1]})
        ref = Reference(definitions)
        owner = unit_type % 2
        unit = ref.units[unit_type]
        preset, bonus = index * 7 - 200, index * 3 - 50
        x, y = index % 4, index // 4 % 4
        funds, raw_cost = (-3, 0, 1, 50, 2147483647)[index % 5], index * 37 % 256
        ref.w8(ref.cost_data + unit_type, raw_cost)
        ref.w32(ref.sp + 0xf0, unit_type)
        ref.w32(ref.sp + 0x4c, ref.map + 0x14c)
        ref.start(0x5a8ce, [], end=0x5a8e0)
        for at, value in {0xc:1, 0xd:index % 2, 0x18:1, 0x19:1, 0x1a:7,
                          0x2c:1, 0x2d:2, 0x2e:171, 0x2f:3, 0x38:4, 0x39:5, 0x3a:6,
                          0x3b:3, 0x3c:3, 0x48:2, 0x49:2, 0x4a:0, 0x4b:3, 0x59:99, 0x5a:13}.items():
            ref.w8(unit + at, value)
        for at, value in {0x24:12, 0x30:12345, 0x34:preset, 0x40:0x1234, 0x44:-7, 0x5c:bonus}.items():
            ref.w32(unit + at, value)
        ref.w32(ref.funds_data + owner * 4, funds)
        ref.u.mem_write(ref.rule_bytes, bytes([terrain0, 0, terrain2]))
        ref.active_boundaries = {0xba288}
        ref.start(0x54016, [ref.map, unit_type, owner, x, y])
        assert ref.r8(ref.count_data + owner) == 18
        assert ref.r8(ref.count_data + (1-owner)) == 17
        assert ref.external_events == [["funds_string", signed(ref.r32(ref.funds_data + owner * 4))],
                                       ["spawn_renderer", unit_type]]
        ref.w32(ref.sp + 0x7c, ref.map)
        ref.w32(ref.sp + 0xbc, special)
        ref.w32(ref.sp + 0x114, unit_type)
        ref.w32(ref.sp + 0x11c, owner)
        ref.w8(ref.config + 0xd9, grant)
        ref.start(0x56792, [], end=0x567f6)
        assert ref.r8(unit + 0x2e) == 171
        rb, ri = lambda at: ref.r8(unit + at), lambda at: signed(ref.r32(unit + at))
        movement = [rb(0xd), rb(0xc), rb(0x3b), rb(0x3c), ri(0x40), ri(0x44), rb(0x4b),
                    rb(0x59), ri(0x30), rb(0x48), rb(0x49), rb(0x4a), rb(0x2c), rb(0x2d),
                    rb(0x2f), rb(0x38), rb(0x39), rb(0x3a)]
        combat = [rb(0xd), rb(0xc), rb(0x5a), rb(0x1a), rb(0x19),
                  ref.r16s(unit+0x1c), ref.r16s(unit+0x1e), ref.r16s(unit+0x20),
                  ri(0x5c), ri(0x34), ri(0x30), rb(0x38)]
        output = movement + combat + [rb(0xc), rb(0x5a), rb(0x18), rb(0x19),
                  signed(ref.r8(ref.cost_data + unit_type),8),
                  signed(ref.r32(ref.funds_data + owner * 4)), ri(0x24)]
        inputs = [unit_type, field6, terrain0, terrain2, special, grant, preset, bonus, x, y, funds, raw_cost]
        assert len(output) == 37 and len(inputs) == 12
        rows.append(inputs + output)
        boundaries.update(ref.boundaries)
    args.output.mkdir(parents=True, exist_ok=True)
    fixture = (f"G1UNITSPAWN1 {len(rows)} 12 37\n" +
               "".join(" ".join(map(str,row)) + "\n" for row in rows)).encode()
    (args.output / "unit_spawn_original_vectors.txt").write_bytes(fixture)
    report = {"status":"passed", "cases":len(rows), "original_sha256":IMAGE_SHA256,
        "support_sha256":SUPPORT_SHA256, "oracle_sha256":sha(Path(__file__).read_bytes()),
        "fixture_sha256":sha(fixture), "complete_original_functions":["0x54016", "0x4333a", "0x4328a", "0x430fc", "0x43a54"],
        "original_fragments":["0x5a8ce..0x5a8e0", "0x56792..0x567f6"],
        "external_boundaries":dict(boundaries),
        "boundary_meanings":{"0xba288":"imported signed division, exact arithmetic",
                             "0x60800":"funds string clear, output boundary",
                             "0x60b70":"funds number formatting request, recorded",
                             "0x5ca7e":"renderer spawn notification, recorded"},
        "extra_assertions":["Actual owner active count increments once; other owner unchanged.",
                            "Exactly one correct funds formatting and spawn renderer request.",
                            "Untouched animation byte2e retained171."],
        "limits":["Synthetic state only; original executable is required locally and not included.",
                  "Renderer and number/string output are recorded, not drawn.",
                  "No production admission, campaign, Apple build, or device-playthrough claim."]}
    (args.output / "original_unit_spawn_reference.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report))


if __name__ == "__main__": main()
