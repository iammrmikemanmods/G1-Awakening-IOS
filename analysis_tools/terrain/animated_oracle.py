#!/usr/bin/env python3
"""Development-only original style1 face14 geometry, UV and clock oracle.

Original instruction blocks run unchanged with explicit synthetic frame locals.
The imported renderer records allocation/M3G boundaries and executes original
ARMv6 libgcc. It is not part of the native product or a full scene execution.
"""
import argparse
import json
from pathlib import Path
import struct
import sys

from geometry_oracle import OriginalTerrain, IMAGE_SHA, LIBGCC_SHA, digest, float_bits


class OriginalAnimatedTerrain(OriginalTerrain):
    def __init__(self, image, gcc):
        self.animated_faces = []
        self.texture_translations = []
        super().__init__(image, gcc)
        self.animated_positions = self.alloc(96)
        self.animated_selectors = self.alloc(1024)
        self.animated_atlas = self.alloc(16)
        self.word(self.animated_atlas, 1)
        self.word(self.animated_atlas + 8, 256)
        self.word(self.animated_atlas + 12, 32)
        self.call(0x714c0, [self.animated_atlas, 32, 32])
        self.animated_uv = bytes(self.u.mem_read(self.read_word(self.animated_atlas + 4), 128))
        self.texture_object = self.object({0x50: "texture_translation"})
        self.phase_pointer = self.alloc(4)

    def hook(self, instance, address, size, user):
        if address in (0x6af3c, 0x6afd2, 0x6b08c, 0x6b124):
            self.animated_faces.append({0x6af3c: 0, 0x6afd2: 2,
                                        0x6b08c: 3, 0x6b124: 1}[address])
        if self.handlers.get(address) == "texture_translation":
            p = instance.reg_read(self.ar.UC_ARM_REG_R1)
            self.texture_translations.append(list(struct.unpack("<3I", instance.mem_read(p, 12))))
        super().hook(instance, address, size, user)

    def block(self, start, stop, frame=0x21fe000, extra_registers=()):
        ar = self.ar
        for i in range(13):
            self.u.reg_write(getattr(ar, "UC_ARM_REG_R" + str(i)), 0)
        self.u.reg_write(ar.UC_ARM_REG_CPSR, 0x30)
        self.u.reg_write(ar.UC_ARM_REG_SP, frame)
        self.u.reg_write(ar.UC_ARM_REG_LR, 0x3000001)
        for register, value in extra_registers:
            self.u.reg_write(register, value)
        self.u.emu_start(start | 1, stop, count=100000, timeout=1_000_000)
        if self.u.reg_read(ar.UC_ARM_REG_PC) != stop or self.u.reg_read(ar.UC_ARM_REG_SP) != frame:
            raise RuntimeError(f"original block {start:#x} escaped its endpoint {stop:#x}")
        self.check_text()

    def check_text(self):
        if bytes(self.u.mem_read(0x1000, 0xd1000)) != self.original_text:
            raise RuntimeError("original main code changed")
        if bytes(self.u.mem_read(0x40000000, 0x9000)) != self.thin[:0x9000]:
            raise RuntimeError("original libgcc code changed")

    def routed_cell(self, inputs):
        x, z, top, bottom, mask, previous, enabled, slots, *cells = inputs
        if top % 32 or not -128 <= top // 32 <= 127 or slots > 200:
            raise ValueError("oracle synthetic state exceeds its bounded frame")
        frame = 0x21fe000
        self.animated_faces = []
        self.u.mem_write(frame, bytes(0x300))
        self.u.mem_write(self.animated_positions, b"\xa5" * 96)
        self.u.mem_write(self.animated_selectors, b"\xa5" * 1024)
        for offset, value in ((0x154, top // 32), (0x138, mask), (0x150, 0),
                              (0xdc, 5 if enabled else 0), (0xe4, self.animated_positions),
                              (0xe8, 0), (0x194, x), (0xb8, z), (0xbc, z + 32)):
            self.word(frame + offset, value)
        self.word(0xd8e0c, slots)
        self.word(0xd8e24, 4)
        self.word(frame + 0x280, self.animated_selectors)
        self.word(frame + 0x284, slots + 4)
        for i, cell in enumerate(cells):
            self.word(self.face_values + 4*i, cell)
            self.word(frame + 0x240 + 8*i, self.face_values + 4*i)
            self.word(frame + 0x244 + 8*i, 1)
        self.block(0x6af02, 0x6b1e8, frame)
        scalar_count = self.read_word(frame + 0xe8)
        if scalar_count % 12 or scalar_count // 12 != len(self.animated_faces):
            raise RuntimeError("original animated geometry counters disagree")
        animated = []
        for i, face in enumerate(self.animated_faces):
            pos = struct.unpack("<12h", self.u.mem_read(self.animated_positions + i*24, 24))
            selector = self.read_word(self.animated_selectors + (slots + i)*4)
            if selector >= 8:
                raise RuntimeError("original selected outside the actual420 atlas")
            uv = struct.unpack_from("<8h", self.animated_uv, selector*16)
            animated.append({"face": face, "atlas_cell": selector,
                             "positions": [list(pos[j:j+3]) for j in range(0, 12, 3)],
                             "quantized_uv": [list(uv[j:j+2]) for j in range(0, 8, 2)]})
        mutated = list(struct.unpack("<4i", self.u.mem_read(self.face_values, 16)))
        suppressed = self.read_word(frame + 0x150) == 255
        base = []
        if not suppressed:
            self.face_calls = []
            for address, value in ((0xd913c, 0), (0xd964c, 0),
                                   (0xd9144, self.position_buffer), (0xd9140, self.uv_buffer),
                                   (0xd914c, float_bits(1.0)), (0xd9150, self.atlas)):
                self.word(address, value)
            self.call(0x65310, [x, z, self.faces, top, bottom, mask, 0, previous, 0])
            count = self.read_word(0xd913c) // 12
            order = [face for bit, face in ((1, 1), (2, 3), (8, 2), (16, 0))
                     if mask & bit and mutated[face] >= 0]
            if count != len(order) or count != len(self.face_calls):
                raise RuntimeError("original base geometry counters disagree after routing")
            for i, face in enumerate(order):
                pos = struct.unpack("<12h", self.u.mem_read(self.position_buffer + i*24, 24))
                uv = struct.unpack("<8h", self.u.mem_read(self.uv_buffer + i*16, 16))
                base.append({"face": face, "atlas_cell": self.face_calls[i],
                             "positions": [list(pos[j:j+3]) for j in range(0, 12, 3)],
                             "quantized_uv": [list(uv[j:j+2]) for j in range(0, 8, 2)]})
        self.check_text()
        return {"base": base, "animated": animated,
                "mutated_original_face_selectors": mutated,
                "original_suppressed_base_cell": suppressed}

    def animated_transform(self):
        # Same subdivision ratios as0x6b4b8..6b4fa, with eight synthetic slots.
        pos, uv = self.alloc(8*24), self.alloc(8*16)
        for address, value in ((0xd913c, 0), (0xd964c, 0), (0xd9144, pos),
                               (0xd9140, uv), (0xd914c, float_bits(1.0)),
                               (0xd9150, self.animated_atlas),
                               (0xd9644, self.positions), (0xd9648, self.uv)):
            self.word(address, value)
        vector, values = self.alloc(8), self.alloc(32)
        self.word(vector, values)
        self.word(vector + 4, 8)
        for i in range(8):
            self.word(values + 4*i, i)
        self.call(0x70eb4, [0, 0, 0, 0, 0, 14*32])
        self.call(0x71248, [vector, 8, 8, 1, 1, 15*32, 0, 0, 15*32, 0, 14*32])
        actual_uv = bytes(self.u.mem_read(uv, 8*16))
        if actual_uv != self.animated_uv or self.read_word(0xd914c) != float_bits(1.0):
            raise RuntimeError("original animated initialization changed atlas UV or unit ratio")
        self.call(0x71884, [1, float_bits(1.0)])
        return {"position_scale_bits": self.transforms["set_positions"]["scale_bits"],
                "position_bias_bits": self.transforms["set_positions"]["bias_bits"],
                "uv_scale_bits": self.transforms["set_uv"]["scale_bits"],
                "uv_bias_bits": self.transforms["set_uv"]["bias_bits"],
                "uv_table": [list(struct.unpack_from("<8h", self.animated_uv, i*16)) for i in range(8)]}

    def clock(self, accumulated, phase, delta):
        frame = 0x21fe000
        self.word(frame + 0xc, delta)
        self.word(0xd8e20, accumulated)
        self.word(0xd8e28, phase)
        self.word(0xd8e24, 4)
        self.word(0xd8e0c, 0) # No transient slots: no random selection callbacks.
        stop = 0x6d758 if accumulated + delta >= 250 else 0x6d82a
        self.block(0x6d6ea, stop, frame)
        new_accumulated, new_phase = self.read_word(0xd8e20), self.read_word(0xd8e28)
        self.word(frame + 8, self.phase_pointer)
        self.word(self.phase_pointer, new_phase)
        self.word(frame + 0x58, self.texture_object)
        self.texture_translations = []
        self.block(0x6d7aa, 0x6d7c8, frame)
        if len(self.texture_translations) != 1:
            raise RuntimeError("original texture translation was not observed once")
        return [new_accumulated, new_phase, *self.texture_translations[0]]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--binary", type=Path, required=True)
    ap.add_argument("--libgcc", type=Path, required=True)
    ap.add_argument("--unicorn-dir", type=Path, required=True)
    ap.add_argument("--fixture", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    sys.path.insert(0, str(args.unicorn_dir))
    import unicorn
    image, gcc = args.binary.read_bytes(), args.libgcc.read_bytes()
    if digest(image) != IMAGE_SHA or digest(gcc) != LIBGCC_SHA:
        raise ValueError("original inputs differ from the audited pinned sources")
    original = OriginalAnimatedTerrain(image, gcc)
    cases, lines = [], []
    for enabled in (0, 1):
        for slots in (0, 10):
            for bits in range(8):
                mask = 16 | sum(v for i, v in enumerate((1, 2, 8)) if bits & (1 << i))
                for cells in ((1, 14, 14, 14), (14, 2, 14, 4), (1, 2, 3, 4), (14, 14, 14, 14)):
                    n = len(cases)
                    inputs = [(n % 5)*32 - 32, (n % 7)*32, -(n % 3)*32,
                              -128, mask, 16, enabled, slots, *cells]
                    output = original.routed_cell(inputs)
                    line = [f"animated_{n:03}", *inputs]
                    for surface in ("base", "animated"):
                        line.append(len(output[surface]))
                        for q in output[surface]:
                            line.extend([q["face"], q["atlas_cell"]])
                            line.extend(x for v in q["positions"] for x in v)
                            line.extend(x for v in q["quantized_uv"] for x in v)
                    lines.append(" ".join(map(str, line)))
                    cases.append({"input": inputs, "result": output})
    clocks = []
    for accumulated in (0, 249, 250, 999):
        for phase in range(4):
            for delta in (0, 1, 250, 1000):
                clocks.append({"input": [accumulated, phase, delta],
                               "result": original.clock(accumulated, phase, delta)})
    transform = original.animated_transform()
    expected_transform = {"position_scale_bits": float_bits(0.01), "position_bias_bits": [0, 0, 0],
                          "uv_scale_bits": float_bits(1/65535), "uv_bias_bits": [0x3f000080]*2}
    if any(transform[k] != v for k, v in expected_transform.items()):
        raise RuntimeError("original animated transform differs from recovered mode1")
    text = "G1_ANIMATED_TERRAIN_ORACLE_V1 " + str(len(cases)) + "\n" + "\n".join(lines)
    text += "\nCLOCKS " + str(len(clocks)) + "\n"
    text += "\n".join(" ".join(map(str, c["input"] + c["result"])) for c in clocks) + "\n"
    args.fixture.parent.mkdir(parents=True, exist_ok=True)
    args.fixture.write_text(text)
    report = {"scope": "Original style1 fixed face14 routing,256x32 atlas setup and phase clock",
              "original_sha256": IMAGE_SHA, "libgcc_sha256": LIBGCC_SHA,
              "unicorn_version": unicorn.__version__, "oracle_sha256": digest(Path(__file__).read_bytes()),
              "fixture_sha256": digest(args.fixture.read_bytes()),
              "original_code_readonly_and_unchanged": True, "instruction_patches": 0,
              "geometry_or_clock_substitutions": 0,
              "substitutions": ["shared bounded allocation/free and M3G API recording/ownership",
                                "engine singleton and nonthrowing unwind registration",
                                "original ARMv6 libgcc import redirection"],
              "geometry_block": "0x6af02..0x6b1e8; original0x65310 for remaining base faces",
              "clock_blocks": ["0x6d6ea..0x6d758 or0x6d82a with zero transient slots",
                               "0x6d7aa..0x6d7c8 including original0x42928 translation dispatch"],
              "case_count": len(cases), "clock_cases": len(clocks),
              "base_quads": sum(len(c["result"]["base"]) for c in cases),
              "animated_quads": sum(len(c["result"]["animated"]) for c in cases),
              "transform": transform, "cases": cases, "clocks": clocks,
              "native_comparison_separate": True, "full_scene_or_device_execution": False,
              "not_established": ["RNG-selected transient decorations", "outside padding",
                                  "GPU pixel parity", "full campaign playthrough"]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("case_count", "clock_cases", "base_quads", "animated_quads")}))


if __name__ == "__main__":
    main()
