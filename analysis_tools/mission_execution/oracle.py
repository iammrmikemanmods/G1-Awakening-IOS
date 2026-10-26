#!/usr/bin/env python3
"""Development-only original-function reference for native mission flow.

Requires an explicitly supplied, hash-checked original executable and Unicorn
2.1.4. Neither the executable nor Unicorn is part of the native app. Font
metrics are synthetic external inputs; the original dialogue branch and its
input consumption execute unchanged. Multiplication/division imports implement
their ABI arithmetic. Original capture predicate and success/reset functions
execute unchanged, including actual unit 0x430fc. No gameplay result is mocked.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import random
import struct
import sys

IMAGE_SHA256 = "0d510516fe3676ee4a0f4dff60ba64e1c5bf79a0c9800f420b1bbdb1c12febfd"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def s32(value):
    return value if value < 0x80000000 else value - 0x100000000


class Reference:
    def __init__(self, image):
        import unicorn as uc
        from unicorn import arm_const as ar
        self.uc, self.ar = uc, ar
        self.u = uc.Uc(uc.UC_ARCH_ARM, uc.UC_MODE_THUMB)
        self.u.mem_map(0x1000, 0xf0000)
        self.u.mem_write(0x1000, image)
        self.u.mem_protect(0x1000, 0xd1000, uc.UC_PROT_READ | uc.UC_PROT_EXEC)
        self.u.mem_map(0x1000000, 0x400000)
        self.u.mem_map(0x2000000, 0x200000)
        self.u.mem_map(0x3000000, 0x1000)
        self.sp, self.end, self.next = 0x21ff000, 0x3000000, 0x1000000
        self.boundaries = collections.Counter()
        self.allowed = set()
        self.audio = []
        self.metric_a, self.metric_b = 0, 0
        self.map = self.alloc(0x600)
        self.app = self.alloc(0x500)
        self.input = self.alloc(0x20)
        self.lines = self.alloc(0x20)
        self.font_manager = self.alloc(0x20)
        self.font = self.alloc(0x10)
        self.font_vtable = self.alloc(0x20)
        self.w32(self.font, self.font_vtable)
        self.w32(self.font_vtable + 8, 0x3000101)
        self.w32(self.font_vtable + 12, 0x3000105)
        slot, singleton = self.alloc(8), self.alloc(0x60)
        self.w32(0xd2038, slot)
        self.w32(slot, singleton)
        self.w32(singleton + 0x58, self.app)
        self.w32(singleton + 0x5c, self.input)
        self.w32(self.map + 0x29c, self.app)
        self.w32(self.app + 0x27c, self.lines)
        self.config = self.alloc(0x80)
        self.w32(self.map + 0x290, self.config)
        self.unit = self.alloc(0x80)
        self.unit2 = self.alloc(0x80)
        type_units = [0] * 23
        type_units[12] = self.alloc(0x80) # Original first-campaign type 12 exists but is inactive.
        self.w32(self.map + 0x90, self.array(type_units, "I"))
        owner_units = self.array([self.unit, self.unit2] + [0] * 21, "I")
        self.w32(self.map + 0x84, self.array([owner_units, owner_units], "I"))
        self.w32(self.map + 0x54, 23)
        self.w8(self.map + 0xa8, 0)
        self.counts = self.array([2, 1], "B")
        self.vector(self.map + 0x7c, self.counts, 2)
        self.u.hook_add(uc.UC_HOOK_CODE, self.hook)

    def alloc(self, size):
        pointer = self.next
        self.next += (max(size, 8) + 7) & ~7
        if self.next >= 0x1400000:
            raise RuntimeError("bounded synthetic heap exhausted")
        return pointer

    def array(self, values, kind):
        pointer = self.alloc(len(values) * struct.calcsize(kind))
        if values:
            self.u.mem_write(pointer, struct.pack("<" + kind * len(values), *values))
        return pointer

    def vector(self, at, pointer, count):
        self.w32(at, pointer)
        self.w32(at + 4, count)

    def w32(self, at, value):
        self.u.mem_write(at, struct.pack("<I", value & 0xffffffff))

    def w8(self, at, value):
        self.u.mem_write(at, bytes([value & 255]))

    def r32(self, at):
        return struct.unpack("<I", self.u.mem_read(at, 4))[0]

    def r8(self, at):
        return self.u.mem_read(at, 1)[0]

    def hook(self, u, address, size, unused):
        external = {0xba384, 0xba288, 0x6294c, 0x6259c, 0x3000100,
                    0x3000104, 0x2ad12, 0x5608c, 0x553ee}
        if address not in external:
            if 0xba1e0 <= address < 0xbaaa0:
                raise RuntimeError(f"unimplemented original import reached: {address:#x}")
            return
        if address not in self.allowed:
            raise RuntimeError(f"unexpected external reference boundary: {address:#x}")
        ar = self.ar
        r = [u.reg_read(reg) for reg in (ar.UC_ARM_REG_R0, ar.UC_ARM_REG_R1,
                                         ar.UC_ARM_REG_R2, ar.UC_ARM_REG_R3)]
        self.boundaries[hex(address)] += 1
        if address == 0xba384:
            product = ((r[0] | (r[1] << 32)) * (r[2] | (r[3] << 32))) & ((1 << 64) - 1)
            u.reg_write(ar.UC_ARM_REG_R0, product & 0xffffffff)
            u.reg_write(ar.UC_ARM_REG_R1, product >> 32)
        elif address == 0xba288:
            a, b = s32(r[0]), s32(r[1])
            if b == 0 or (a == -0x80000000 and b == -1):
                raise RuntimeError("undefined imported signed division")
            result = abs(a) // abs(b)
            if (a < 0) != (b < 0): result = -result
            u.reg_write(ar.UC_ARM_REG_R0, result & 0xffffffff)
        elif address == 0x6294c:
            u.reg_write(ar.UC_ARM_REG_R0, self.font_manager)
        elif address == 0x6259c:
            if r[:2] != [self.font_manager, 2]:
                raise RuntimeError("unexpected original font lookup")
            u.reg_write(ar.UC_ARM_REG_R0, self.font)
        elif address in (0x3000100, 0x3000104):
            if r[0] != self.font: raise RuntimeError("font virtual call with wrong this")
            value = self.metric_a if address == 0x3000100 else self.metric_b
            u.reg_write(ar.UC_ARM_REG_R0, value & 0xffffffff)
        elif address == 0x2ad12:
            if r[:3] != [self.app, 5, 18]:
                raise RuntimeError("unexpected audio notification from dialogue")
            self.audio.append([5, 18])
        elif address == 0x5608c:
            self.clock_calls.append("dispatch")
        elif address == 0x553ee:
            self.clock_calls.append("gameplay")
        u.reg_write(ar.UC_ARM_REG_PC, u.reg_read(ar.UC_ARM_REG_LR))

    def run(self, entry, args, allowed=()):
        ar = self.ar
        regs = [ar.UC_ARM_REG_R0, ar.UC_ARM_REG_R1, ar.UC_ARM_REG_R2,
                ar.UC_ARM_REG_R3, ar.UC_ARM_REG_R4, ar.UC_ARM_REG_R5,
                ar.UC_ARM_REG_R6, ar.UC_ARM_REG_R7, ar.UC_ARM_REG_R8,
                ar.UC_ARM_REG_R9, ar.UC_ARM_REG_R10, ar.UC_ARM_REG_R11,
                ar.UC_ARM_REG_R12]
        for reg in regs: self.u.reg_write(reg, 0)
        self.u.reg_write(ar.UC_ARM_REG_CPSR, 0x30)
        self.u.reg_write(ar.UC_ARM_REG_SP, self.sp)
        self.u.reg_write(ar.UC_ARM_REG_LR, self.end | 1)
        for reg, value in zip(regs, args): self.u.reg_write(reg, value & 0xffffffff)
        self.allowed = set(allowed)
        self.u.emu_start(entry | 1, self.end, timeout=2_000_000, count=100_000)
        if self.u.reg_read(ar.UC_ARM_REG_PC) != self.end:
            raise RuntimeError(f"original {entry:#x} did not return within bound")
        if self.u.reg_read(ar.UC_ARM_REG_SP) != self.sp:
            raise RuntimeError(f"original {entry:#x} stack imbalance")
        return self.u.reg_read(ar.UC_ARM_REG_R0)

    def dialogue(self, values):
        first, reveal, skip, count, height, a, b, box, full, edges, delta = values
        self.metric_a, self.metric_b = a, b
        self.audio.clear()
        self.w32(self.map + 0x1e0, 3)
        self.w32(self.map + 0x1f8, first)
        self.w8(self.map + 0x1fc, full)
        self.w32(self.map + 0x200, box)
        self.w32(self.map + 0x210, height)
        self.w8(self.map + 0x264, skip)
        self.w32(self.map + 0x26c, reveal)
        self.w32(self.lines + 0x18, count)
        self.w32(self.input + 4, edges)
        self.run(0x4e3bc, [self.map, delta],
                 {0xba384, 0xba288, 0x6294c, 0x6259c, 0x3000100, 0x3000104, 0x2ad12})
        updated_reveal = s32(self.r32(self.map + 0x26c))
        return [s32(self.r32(self.map + 0x1f8)), updated_reveal,
                int(self.r32(self.map + 0x1e0) == 99), self.r8(self.map + 0x264),
                self.r32(self.input + 4), self.r32(self.sp - 36), len(self.audio),
                1000 + (updated_reveal >> 16)]

    def capture(self, sites, indices, active_counts=(2, 1)):
        self.u.mem_write(self.counts, bytes(active_counts))
        self.w32(self.map + 0x1e0, 777)
        self.w32(self.map + 0x21c, 18)
        self.w32(self.map + 0x238, 51)
        self.w32(self.map + 0x23c, 52)
        self.w32(self.map + 0x2d8, 0)
        self.w8(self.map + 0x230, 1)
        self.w32(self.map + 0x248, 1)
        self.vector(self.map + 0x240, self.array(indices, "i"), 4)
        self.vector(self.map + 0x3e8, self.array([s[0] for s in sites], "b"), len(sites))
        site_vectors = self.alloc(len(sites) * 8)
        for n, (_, groups) in enumerate(sites):
            group_vectors = self.alloc(len(groups) * 8)
            for g, items in enumerate(groups):
                self.vector(group_vectors + g * 8, self.array(items, "b"), len(items))
            self.vector(site_vectors + n * 8, group_vectors, len(groups))
        self.vector(self.map + 0x3f8, site_vectors, len(sites))
        for unit in (self.unit, self.unit2):
            self.u.mem_write(unit, bytes([0x5a]) * 0x80)
            self.w8(unit + 0x3b, 5); self.w8(unit + 0x3c, 7)
        self.run(0x559b4, [self.map])
        ready = self.r32(self.map + 0x1e0) == 99
        if ready:
            assert self.r32(self.map + 0x238) == 0xffffffff
            assert self.r32(self.map + 0x23c) == 0xffffffff
            assert self.r32(self.map + 0x2d8) == 6
            assert self.r8(self.map + 0x230) == 0
            assert self.r32(self.map + 0x21c) == 18
            for unit in (self.unit, self.unit2):
                assert all(self.r8(unit + x) == 0 for x in (0x59, 0x2c, 0x2d, 0x38, 0x2f, 0x39, 0x3a))
                assert self.r8(unit + 0x48) == 5 and self.r8(unit + 0x49) == 7
                assert self.r32(unit + 0x40) == 0x5a5a5a5a
        else:
            assert self.r32(self.map + 0x1e0) == 777
            assert self.r8(self.unit + 0x59) == 0x5a
        return int(ready)

    def clock(self, phase, remaining, transition, delta):
        self.w32(self.map + 0x1e0, phase)
        self.w32(self.map + 0x228, remaining)
        self.w32(self.map + 0x220, transition)
        self.w32(self.map + 0x21c, 1)
        self.w32(self.map + 0x218, 3)
        self.w8(self.map + 0x225, 0)
        self.clock_calls = []
        self.run(0x57914, [self.map, delta], {0xba384, 0x5608c, 0x553ee})
        return [self.r32(self.map + 0x1e0), s32(self.r32(self.map + 0x228)),
                s32(self.r32(self.map + 0x220)), self.r8(self.map + 0x225),
                self.r32(self.map + 0x21c), self.clock_calls]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--python-tools", type=Path)
    args = parser.parse_args()
    if args.python_tools: sys.path.insert(0, str(args.python_tools.resolve()))
    image = args.image.read_bytes()
    if sha(image) != IMAGE_SHA256: raise SystemExit("original image SHA256 mismatch")
    import unicorn
    if unicorn.__version__ != "2.1.4": raise SystemExit("reference requires Unicorn 2.1.4")
    reference = Reference(image)
    args.output.mkdir(parents=True, exist_ok=True)
    text_rows = []
    for index in range(486):
        for variant in range(2):
            tag = reference.run(0x445c8, [index, variant])
            if tag >> 16 != 0x21ff: raise RuntimeError("unexpected original localization tag")
            text_rows.append([index, variant, tag & 65535])
    for bad in (-1, 486, 0x7fffffff):
        assert reference.run(0x445c8, [bad, 0]) == 0xffffffff
    (args.output / "text_index_original_vectors.txt").write_text(
        "# Original 0x445c8: index alternate localization_id\n" +
        "".join(" ".join(map(str, row)) + "\n" for row in text_rows))

    randomizer = random.Random(0x47314d495353494f)
    dialogue_cases = []
    # Explicit thresholds, simultaneous input priorities and zero-length pages.
    for count, first, box in ((0, 0, 40), (1, 0, 11), (1, 0, 12),
                              (3, 0, 40), (3, 1, 40), (10, 0, 40), (10, 3, 40)):
        for full in (0, 1):
            for edges in (0, 1, 16, 64, 128, 17, 192, 144, 2):
                dialogue_cases.append([first, -65536000, 0, count, 16, 14, 3, box, full, edges, 16])
    for reveal in (-65536000, -65536, -1, 0, 1):
        for delta in (0, 1, 16, 32, 1000, 32000, 32767, 32768, 65535, 65536):
            dialogue_cases.append([0, reveal, 0, 1, 16, 14, 3, 40, 1, 0, delta])
    for _ in range(300):
        count = randomizer.randrange(0, 30)
        height = randomizer.randrange(4, 40)
        dialogue_cases.append([randomizer.randrange(count + 1), randomizer.randrange(-65536000, 1),
            randomizer.randrange(2), count, height, height - 2, randomizer.randrange(4),
            randomizer.randrange(1, 300), randomizer.randrange(2),
            randomizer.choice([0, 1, 16, 64, 128, 17, 192, 144, 2]), randomizer.randrange(1001)])
    dialogue_rows = [row + reference.dialogue(row) for row in dialogue_cases]
    (args.output / "dialogue_original_vectors.txt").write_text(
        "# Original 0x4e3bc: first reveal skip count line_height metric_a metric_b box fully_revealed edges delta"
        " => first reveal ready skip remaining_edges more_pages skip_audio character_budget\n" +
        "".join(" ".join(map(str, row)) + "\n" for row in dialogue_rows))

    capture_cases = []
    for value in (-128, -1, 0, 1, 127):
        for desired in (-32768, -128, -1, 0, 1, 127, 255, 32767):
            capture_cases.append(([[-1, [[value, 1]]]], [0, 0, 0, desired]))
    for sites in ([], [[0, []]], [[0, [[0]]]], [[-1, [[0]]]],
                  [[0, [[0, 1]]]], [[0, [[0]]], [0, [[0, 0], []]]]):
        for indices in ([-1, 0, 0, 0], [0, -1, 0, 0], [0, 0, -1, 0], [-1, 99, 99, 0]):
            capture_cases.append((sites, indices))
    for _ in range(100):
        sites = [[randomizer.choice([-1, 0, 1]),
                  [[randomizer.choice([-1, 0, 1]) for _ in range(randomizer.randrange(1, 5))]
                   for _ in range(randomizer.randrange(1, 4))]]
                 for _ in range(randomizer.randrange(1, 4))]
        site = randomizer.randrange(len(sites))
        group = randomizer.randrange(len(sites[site][1]))
        item = randomizer.randrange(len(sites[site][1][group]))
        capture_cases.append((sites, [site, group, item, randomizer.choice([-1, 0, 1])]))
    capture_rows = []
    for sites, indices in capture_cases:
        expected = reference.capture(sites, indices)
        first_campaign_expected = reference.capture(sites, indices, (1, 1))
        assert expected == first_campaign_expected
        flat = indices + [expected, len(sites)]
        for owner, groups in sites:
            flat.extend([owner, len(groups)])
            for items in groups: flat.extend([len(items)] + items)
        capture_rows.append(flat)
    (args.output / "capture_original_vectors.txt").write_text(
        "# Original 0x559b4/0x558e4/0x430fc: site group item desired expected site_count then owner group_count {item_count items...}...\n" +
        "".join(" ".join(map(str, row)) + "\n" for row in capture_rows))

    clock_rows = []
    for phase in (1, 2, 5):
        for initial in ([0] if phase != 5 else [-32768, -1, 0, 1, 1000, 32767]):
            for delta in (0, 1, 16, 1000, 32768, 65535):
                expected = reference.clock(phase, initial if phase == 5 else 0, 0, delta)
                assert expected[-1] == []
                clock_rows.append([phase, initial, delta] + expected[:-1])
    advance_case = reference.clock(99, 0, 0, 1000)
    assert advance_case[4] == 2 and advance_case[5] == ["dispatch"]
    (args.output / "mission_clock_original_vectors.txt").write_text(
        "# Original 0x57914: phase initial_delay delta => phase remaining_delay transition flag225 cursor\n" +
        "".join(" ".join(map(str, row)) + "\n" for row in clock_rows))

    report = {
        "original_image_sha256": sha(image), "oracle_source_sha256": sha(Path(__file__).read_bytes()),
        "unicorn_version": unicorn.__version__, "text_mapping_cases": len(text_rows),
        "invalid_mapping_cases": 3, "dialogue_cases": len(dialogue_rows),
        "capture_cases": len(capture_rows), "capture_function_executions": len(capture_rows) * 2,
        "capture_active_unit_counts": [[2, 1], [1, 1]], "clock_cases": len(clock_rows),
        "advance_dispatch_case": advance_case,
        "boundaries": dict(reference.boundaries),
        "executed_original_functions": ["0x445c8", "0x4e3bc", "0x2b9c2", "0x559b4", "0x558e4", "0x430fc", "0x57914"],
        "external_boundaries": {
            "0xba384": "ABI unsigned low-64 multiplication, equivalent signed low-64 product",
            "0xba288": "ABI signed division, truncation toward zero",
            "0x6294c / 0x6259c": "synthetic font selection, no game branch decisions",
            "0x3000100 / 0x3000104": "caller-supplied font metric virtual callbacks",
            "0x2ad12": "records the observed (5,18) audio notification; audio not executed",
            "0x5608c": "clock-only test records next-command dispatcher call, does not execute it",
            "0x553ee": "reserved clock boundary for end-of-stream; not reached in this corpus"},
        "limits": ["Does not execute full original dialogue allocation, font layout or drawing.",
                   "Capture corpus uses normal first-campaign live-player state, not player-loss/alternate branches.",
                   "Does not execute a real capture action, save, mission completion, campaign, iOS app or device."],
        "fixtures": {path.name: {"bytes": path.stat().st_size, "sha256": sha(path.read_bytes())}
                     for path in sorted(args.output.glob("*_vectors.txt"))}}
    (args.output / "original_mission_execution_reference.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ("text_mapping_cases", "dialogue_cases", "capture_cases", "clock_cases")}))


if __name__ == "__main__": main()
