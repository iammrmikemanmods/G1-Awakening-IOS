#!/usr/bin/env python3
"""Original ARM functions as a development-only reference, never an app runtime.

Unicorn 2.1.4 and a hash-checked user-supplied executable are required. Profile
mutation and best-record functions execute completely; persistence is an
explicit success/failure input, not a fake successful save. Completion and
handoff execute bounded original function bodies, stopping before the C++
unwind epilogue. String rendering, audio, world cleanup/script installation,
and storage are recorded external requests, not purportedly executed effects.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import random
import struct

IMAGE_SHA256 = "0d510516fe3676ee4a0f4dff60ba64e1c5bf79a0c9800f420b1bbdb1c12febfd"


def s32(value):
    return value if value < 0x80000000 else value - 0x100000000


class Reference:
    def __init__(self, image):
        import unicorn as uc
        from unicorn import arm_const as ar
        self.ar = ar
        self.u = uc.Uc(uc.UC_ARCH_ARM, uc.UC_MODE_THUMB)
        self.u.mem_map(0x1000, 0xf0000)
        self.u.mem_write(0x1000, image)
        self.u.mem_protect(0x1000, 0xd1000, uc.UC_PROT_READ | uc.UC_PROT_EXEC)
        self.u.mem_map(0x1000000, 0x400000)
        self.u.mem_map(0x2000000, 0x200000)
        self.u.mem_map(0x3000000, 0x1000)
        self.sp, self.end, self.next = 0x21fe000, 0x3000000, 0x1000000
        self.allowed, self.events = set(), []
        self.boundaries = collections.Counter()
        self.map = self.alloc(0x600)
        self.app = self.alloc(0x500)
        self.config = self.alloc(0x80)
        self.input = self.alloc(0x20)
        self.snapshot = self.alloc(0x500)
        self.profile = self.alloc(0x50)
        self.error_ui = self.alloc(0x40)
        self.type12 = self.alloc(0x80)
        self.counts = self.array([1, 1], "B")
        self.factions = self.array([0, 1], "B")
        self.controllers = self.array([0, 1], "b")
        self.vector(self.map + 0x7c, self.counts, 2)
        self.vector(self.map + 0xa0, self.factions, 2)
        self.vector(self.map + 0x98, self.controllers, 2)
        self.w32(self.map + 0x290, self.config)
        self.w32(self.map + 0x29c, self.app)
        type_units = [0] * 23
        type_units[12] = self.type12
        self.w32(self.map + 0x90, self.array(type_units, "I"))
        self.command_words = self.array([10, 1], "H")
        self.command_vector = self.alloc(8)
        self.vector(self.command_vector, self.command_words, 2)
        self.vector(self.map + 0x214, self.command_vector, 1)
        self.w32(self.map + 0x21c, 0)
        self.w32(self.app + 0x3a8, self.array([self.profile], "I"))
        self.w32(self.app + 0x3b4, 0)
        self.w32(self.app + 0x2c4, self.error_ui)
        slot, singleton = self.alloc(8), self.alloc(0x60)
        self.w32(0xd2038, slot)
        self.w32(slot, singleton)
        self.w32(singleton + 0x58, self.app)
        self.w32(singleton + 0x5c, self.input)
        self.background = self.alloc(0x20)
        self.w32(self.app + 0x1b8, self.array([self.background], "I"))
        self.record_columns = []
        for offset in (0x10, 0x18, 0x20):
            groups = self.alloc(16)
            columns = [self.array([-1] * count, "i") for count in (17, 8)]
            for group, (column, count) in enumerate(zip(columns, (17, 8))):
                self.vector(groups + group * 8, column, count)
            self.vector(self.profile + offset, groups, 2)
            self.record_columns.append(columns)
        self.u.hook_add(uc.UC_HOOK_CODE, self.hook)

    def alloc(self, size):
        at = self.next
        self.next += (max(size, 8) + 7) & ~7
        if self.next >= 0x1400000: raise RuntimeError("bounded heap exhausted")
        return at

    def array(self, values, kind):
        at = self.alloc(len(values) * struct.calcsize(kind))
        if values: self.u.mem_write(at, struct.pack("<" + kind * len(values), *values))
        return at

    def vector(self, at, pointer, count):
        self.w32(at, pointer); self.w32(at + 4, count)

    def w32(self, at, value):
        self.u.mem_write(at, struct.pack("<I", value & 0xffffffff))

    def w8(self, at, value):
        self.u.mem_write(at, bytes([value & 255]))

    def r32(self, at):
        return struct.unpack("<I", self.u.mem_read(at, 4))[0]

    def r8(self, at):
        return self.u.mem_read(at, 1)[0]

    def hook(self, u, address, size, unused):
        external = {0x2fed8, 0x2ad12, 0x301aa, 0x46df2, 0x604b4,
                    0x47094, 0x52e90, 0x3c020, 0x48cc2, 0x57a54,
                    0x48e38, 0x57c98, 0x3174e, 0x2bdc0, 0x2bd10, 0xba384}
        if address not in external:
            if 0xba1e0 <= address < 0xbaaa0:
                raise RuntimeError(f"unhandled original import {address:#x}")
            return
        if address not in self.allowed:
            raise RuntimeError(f"unexpected external boundary {address:#x}")
        ar = self.ar
        args = [u.reg_read(reg) for reg in (ar.UC_ARM_REG_R0, ar.UC_ARM_REG_R1,
                                          ar.UC_ARM_REG_R2, ar.UC_ARM_REG_R3)]
        self.boundaries[hex(address)] += 1
        if address == 0xba384:
            value = ((args[0] | (args[1] << 32)) *
                     (args[2] | (args[3] << 32))) & ((1 << 64) - 1)
            u.reg_write(ar.UC_ARM_REG_R0, value & 0xffffffff)
            u.reg_write(ar.UC_ARM_REG_R1, value >> 32)
        elif address == 0x2fed8:
            assert args[0] == self.app
            self.events.append(["persist", self.persist_result])
            u.reg_write(ar.UC_ARM_REG_R0, self.persist_result)
        elif address == 0x2ad12:
            assert args[0] == self.app
            self.events.append(["audio", s32(args[1]), s32(args[2])])
        elif address == 0x301aa:
            self.events.append(["text_constructor", args[1]])
        elif address == 0x46df2:
            assert args[0] == self.config and args[2] == 0
            self.events.append(["text_present", 0])
        elif address == 0x47094:
            assert args[0] == self.config
            self.events.append(["menu_or_ending", s32(args[1])])
        elif address == 0x52e90:
            assert args[:2] == [self.map, 0]
            self.events.append(["reset_world", 0])
        elif address == 0x3c020:
            u.reg_write(ar.UC_ARM_REG_R0, self.snapshot)
        elif address == 0x48cc2:
            assert args[1] == self.config
            self.events.append(["load_script", args[2], s32(args[3])])
            self.vector(args[0], 0, 0) # Empty external marshaling object only.
        elif address == 0x57a54:
            assert args[0] == self.map
            self.events.append(["install_script"])
        elif address == 0x57c98:
            assert args[0] == self.map
            self.events.append(["handoff"])
        elif address == 0x3174e:
            assert args[:2] == [self.app, self.error_ui]
            self.events.append(["save_error_ui"])
        elif address in (0x2bdc0, 0x2bd10):
            assert args[0] == self.app
            self.events.append(["results_ui", hex(address)])
        u.reg_write(ar.UC_ARM_REG_PC, u.reg_read(ar.UC_ARM_REG_LR))

    def run(self, entry, args=(), allowed=(), stop=None, seed=None):
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
        if seed: seed()
        self.allowed = set(allowed)
        self.events = []
        end = self.end if stop is None else stop
        self.u.emu_start(entry | 1, end, timeout=2_000_000, count=100_000)
        if self.u.reg_read(ar.UC_ARM_REG_PC) != end:
            raise RuntimeError(f"original {entry:#x} did not reach {end:#x} within bound")
        if self.u.reg_read(ar.UC_ARM_REG_SP) != self.sp:
            raise RuntimeError(f"original {entry:#x} stack imbalance")
        return self.u.reg_read(ar.UC_ARM_REG_R0)

    def configure(self, context, opcode=10, argument=1):
        group, index, count0, count1, type12, faction0, faction1, controller0, controller1 = context
        self.w8(self.config + 12, group)
        self.w32(self.config + 8, index)
        self.w8(self.config + 0x44, 0)
        self.u.mem_write(self.counts, bytes([count0, count1]))
        self.u.mem_write(self.factions, bytes([faction0, faction1]))
        self.u.mem_write(self.controllers, bytes([controller0 & 255, controller1 & 255]))
        self.w8(self.type12 + 13, type12)
        self.w32(self.map + 0x2d8, 6)
        self.w32(self.map + 0x1e0, 99)
        self.u.mem_write(self.command_words, struct.pack("<HH", opcode, argument & 0xffff))

    def prepare_profile(self, context, highest, flags, old, current):
        group, index = context[:2]
        for column in self.record_columns:
            for g, count in enumerate((17, 8)):
                self.u.mem_write(column[g], struct.pack("<" + "i" * count, *([-77] * count)))
        for n, value in enumerate(old):
            if group != 2: self.w32(self.record_columns[n][group] + index * 4, value)
        for n, value in enumerate(current): self.w32(self.map + 0x274 + n * 4, value)
        for n, value in enumerate(highest): self.w32(self.profile + 4 + n * 4, value)
        for n, value in enumerate(flags): self.w8(self.profile + 1 + n, value)
        self.w32(self.map + 0x438, 7777)
        self.w32(self.map + 0x430, 7778)
        self.w32(self.map + 0x434, 7779)
        self.w8(self.map + 0x3c8, 1)

    def profile_output(self, context):
        group, index = context[:2]
        values = ([s32(self.r32(self.record_columns[n][group] + index * 4)) for n in range(3)]
                  if group != 2 else [-77, -77, -77])
        # Every untouched record must remain exactly the seeded sentinel.
        for n, column in enumerate(self.record_columns):
            for g, count in enumerate((17, 8)):
                for i in range(count):
                    if (g, i) != (group, index): assert s32(self.r32(column[g] + i * 4)) == -77
        return [s32(self.r32(self.profile + 4)), s32(self.r32(self.profile + 8)),
                self.r8(self.profile + 1), self.r8(self.profile + 2),
                self.r8(self.map + 0x3c8), *values,
                s32(self.r32(self.map + 0x438)), s32(self.r32(self.map + 0x430)),
                s32(self.r32(self.map + 0x434))]

    def completion(self, context, text_index):
        self.configure(context, 8, text_index)
        self.w32(self.sp + 0x7c, self.map)
        self.w32(self.sp + 0xa4, 0xffffffff)
        self.run(0x5648a, [0, 0, 0, 8],
                 {0x2ad12, 0x301aa, 0x46df2, 0x604b4}, 0x578e4)
        audio = [event[1:] for event in self.events if event[0] == "audio"]
        text = [event[1] for event in self.events if event[0] == "text_constructor"]
        assert len(text) <= 1 and len(audio) in (0, 2)
        result = [self.r32(self.map + 0x1e0), s32(self.r32(self.sp + 0xa4)),
                  len(audio), *(sum(audio, []) if audio else [-1, -1, -1, -1]),
                  -1, self.r8(self.config + 0x44)]
        if text:
            self.w32(self.sp + 4, text[0])
            self.run(0x301de, stop=0x3020e)
            result[-2] = self.u.reg_read(self.ar.UC_ARM_REG_R1)
        return result

    def profile_update(self, context, next_index, highest, flags, old, current, persisted):
        self.configure(context, 10, next_index)
        self.prepare_profile(context, highest, flags, old, current)
        self.persist_result = persisted
        result = self.run(0x4e5a6, [self.map], {0x2fed8})
        assert self.events == [["persist", persisted]]
        return [*self.profile_output(context), result]

    def opcode10(self, context, next_index, persisted):
        self.configure(context, 10, next_index)
        self.prepare_profile(context, [0, 0], [0, 0], [-1, -1, -1], [12, 30, 8])
        self.persist_result = persisted
        self.w8(self.app + 0x2c8, 0)
        self.w32(self.error_ui + 8, 123)
        self.w32(self.map + 0x280, 456)
        self.w32(self.sp + 0x7c, self.map)
        self.run(0x56ee2, allowed={0x2fed8, 0x3174e, 0x2bdc0, 0x2bd10, 0x57c98}, stop=0x578e4)
        assert self.events[0] == ["persist", persisted]
        return [self.r32(self.map + 0x2d8), self.r8(self.app + 0x2c8),
                self.r32(self.error_ui + 8), self.r32(self.map + 0x280),
                int(["handoff"] in self.events), int(["save_error_ui"] in self.events),
                sum(event[0] == "results_ui" for event in self.events)]

    def handoff(self, context, next_index, finished):
        self.configure(context, 10, next_index)
        self.w8(self.map + 0x3c8, finished)
        self.w8(self.snapshot + 0x3f3, 250)
        self.w32(self.app + 0x78, 456)
        self.w32(self.sp + 8, self.map)
        self.run(0x57cca, allowed={0x47094, 0x52e90, 0x3c020, 0x48cc2, 0x57a54, 0x48e38}, stop=0x57e26)
        messages = [event[1] for event in self.events if event[0] == "menu_or_ending"]
        loads = [event[1:] for event in self.events if event[0] == "load_script"]
        assert bool(messages) != bool(loads)
        if messages: assert len(self.events) == 1
        else:
            assert self.events == [["reset_world", 0], ["load_script", *loads[0]], ["install_script"]]
        return [self.r32(self.map + 0x2d8), s32(self.r32(self.config + 8)),
                self.r8(self.snapshot + 0x3f3), self.r32(self.app + 0x78),
                messages[0] if messages else -2, int(bool(loads)),
                *(loads[0] if loads else [-1, -1])]

    def results(self, offset, height, edges, delta):
        self.w32(self.map + 0x280, offset)
        self.w32(self.background + 0x14, height)
        self.w32(self.input + 4, edges)
        self.run(0x57e54, [self.map, delta], {0x57c98, 0xba384})
        return [s32(self.r32(self.map + 0x280)), self.r32(self.input + 4),
                int(["handoff"] in self.events)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    image = args.image.read_bytes()
    if hashlib.sha256(image).hexdigest() != IMAGE_SHA256:
        raise SystemExit("original executable hash mismatch")
    args.output.mkdir(parents=True, exist_ok=True)
    ref = Reference(image)
    contexts = []
    for group, index in ((0, 0), (0, 9), (1, 2), (2, 1)):
        for count0 in (0, 1, 2):
            for type12 in (0, 1):
                for factions, controllers in (((0, 1), (0, 1)), ((1, 0), (1, 0)),
                                              ((0, 1), (-1, 0))):
                    contexts.append([group, index, count0, 1, type12, *factions, *controllers])
    rows = []
    for context in contexts:
        for text_index in (202, 208):
            rows.append([0, *context, text_index, *ref.completion(context, text_index)])
    rng = random.Random(0x4e5a6)
    record_values = [-1, -20, 0, 1, 10, 99, 0x7fffffff, -0x80000000]
    for case, context in enumerate(contexts):
        for next_index in (-2, 1):
            highest = [rng.choice([-1, 0, 1, 12]), rng.choice([-1, 0, 1, 6])]
            flags = [case % 2, (case // 2) % 2]
            old = [rng.choice(record_values) for _ in range(3)]
            current = [rng.choice(record_values) for _ in range(3)]
            persisted = case % 2
            inputs = [*context, next_index, *highest, *flags, *old, *current, persisted]
            rows.append([1, *inputs, *ref.profile_update(context, next_index, highest, flags, old, current, persisted)])
            for finished in (0, 1):
                rows.append([2, *context, next_index, finished, *ref.handoff(context, next_index, finished)])
    for group in range(3):
        context = [group, 0, 1, 1, 0, 0, 1, 0, 1]
        for persisted in (0, 1):
            rows.append([3, group, persisted, *ref.opcode10(context, 1, persisted)])
    for offset, height in ((0, 320), (320 * 65536 - 1, 320), (700 * 65536, 320),
                           (-100, 1), (0x7fffffff, 32767), (-0x80000000, 17)):
        for edges in (0, 1, 16, 64, 128, 0x8000, 0x8051):
            for delta in (0, 30, 65535):
                rows.append([4, offset, height, edges, delta, *ref.results(offset, height, edges, delta)])
    for group, address, count in ((0, 0xcec18, 17), (1, 0xcebf8, 8), (2, 0xcebe4, 5)):
        for index in range(count):
            tagged = struct.unpack_from("<I", image, address - 0x1000 + 4 * index)[0]
            assert tagged >> 24 == 3
            rows.append([5, group, index, tagged & 0xffffff])
    completion_clock = []
    for delta in (0, 1, 10000):
        ref.w32(ref.map + 0x1e0, 8)
        ref.w32(ref.map + 0x21c, 26)
        ref.w32(ref.map + 0x228, 123)
        ref.run(0x57914, [ref.map, delta])
        actual = [ref.r32(ref.map + 0x1e0), ref.r32(ref.map + 0x21c), ref.r32(ref.map + 0x228)]
        assert actual == [99, 26, 123]
        completion_clock.append({"delta_ms": delta, "phase": actual[0], "cursor": actual[1],
                                 "unchanged_wait_storage": actual[2]})
    fixture = args.output / "mission_progression_original_vectors.txt"
    fixture.write_text("# Original function reference; row kinds documented in README.\n" +
                       "\n".join(" ".join(map(str, row)) for row in rows) + "\n")
    counts = collections.Counter(row[0] for row in rows)
    report = {
        "original_executable_sha256": IMAGE_SHA256,
        "unicorn_version": __import__("unicorn").__version__,
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "reference_functions": {"completion_body": ["0x5648a", "0x578e4"],
            "text_conversion_body": ["0x301de", "0x3020e"],
            "profile_complete_function": "0x4e5a6", "record_complete_function": "0x44058",
            "opcode10_body": ["0x56ee2", "0x578e4"],
            "handoff_body": ["0x57cca", "0x57e26"], "results_complete_function": "0x57e54"},
        "case_counts": {"completion": counts[0], "profile": counts[1], "handoff": counts[2],
                        "save_dispatch": counts[3], "results_update": counts[4], "table_entries": counts[5]},
        "external_boundaries": dict(sorted(ref.boundaries.items())),
        "completion_phase8_clock_function_0x57914": completion_clock,
        "fixture_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
        "limitations": ["Original executable is development input only, never shipped or executed in native app.",
            "Persistence is an explicit supplied boundary result; no durable save was performed by this harness.",
            "Rendering/audio/menu/world cleanup/script installation are recorded external requests.",
            "Fragment references omit C++ unwind prologues/epilogues and do not test allocation/serialization.",
            "No campaign playthrough, Apple device run or performance claim follows from these vectors."]}
    (args.output / "original_mission_progression_reference.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
