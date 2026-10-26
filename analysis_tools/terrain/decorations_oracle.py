#!/usr/bin/env python3
"""Development-only style1 transient pool oracle using unchanged original code.

Explicitly seeded shared generator, original candidate registration/selection,
mesh initialization, slot placement and gated update. Synthetic M3G methods
record exact array writes; they do not replace geometry or random arithmetic.
"""
import argparse
import json
from pathlib import Path
import struct
import sys

from animated_map_oracle import OriginalAnimatedMap, decode_config
from geometry_oracle import IMAGE_SHA, LIBGCC_SHA, digest, float_bits


class OriginalDecorations(OriginalAnimatedMap):
    def __init__(self, image, gcc):
        self.pool_draws = 0
        self.generated_words = []
        self.slot_geometry = []
        self.slot_uv = []
        self.slot_offsets = []
        self.selected_slot = None
        self.placements = []
        super().__init__(image, gcc)
        self.rng = self.alloc(0x9d4)
        self.word(self.rng + 0xc, 0)
        self.word(self.rng + 0x10, 0x9908b0df)

    def call(self, function, arguments):
        # The original initial mesh can contain hundreds of allocated strips.
        # Keep a larger explicit instruction bound than the four-face harness.
        ar, initial_sp = self.ar, 0x21ff000
        for i in range(13):
            self.u.reg_write(getattr(ar, "UC_ARM_REG_R" + str(i)), 0)
        self.u.reg_write(ar.UC_ARM_REG_CPSR, 0x30)
        self.u.reg_write(ar.UC_ARM_REG_SP, initial_sp)
        self.u.reg_write(ar.UC_ARM_REG_LR, 0x3000001)
        for i, value in enumerate(arguments):
            if i < 4:
                self.u.reg_write(getattr(ar, "UC_ARM_REG_R" + str(i)), value & 0xffffffff)
            else:
                self.word(initial_sp + (i - 4) * 4, value)
        self.u.emu_start(function | 1, 0x3000000, count=12_000_000, timeout=30_000_000)
        if self.u.reg_read(ar.UC_ARM_REG_PC) != 0x3000000 or self.u.reg_read(ar.UC_ARM_REG_SP) != initial_sp:
            raise RuntimeError(f"bounded original call {function:#x} did not return; pc={self.u.reg_read(ar.UC_ARM_REG_PC):#x}")
        self.check_text()

    def hook(self, instance, address, size, user):
        ar = self.ar
        if address == 0x2b46c:
            self.calls["shared_random_singleton"] += 1
            instance.reg_write(ar.UC_ARM_REG_R0, self.rng)
            instance.reg_write(ar.UC_ARM_REG_PC, instance.reg_read(ar.UC_ARM_REG_LR))
            return
        if address == 0x1adc4:
            raise RuntimeError("explicitly seeded oracle attempted wall-clock seeding")
        if address == 0x7b26:
            self.pool_draws += 1
        if address == 0x7c0a:
            self.generated_words.append(instance.reg_read(ar.UC_ARM_REG_R0))
        if address == 0x64ebc:
            self.selected_slot = instance.reg_read(ar.UC_ARM_REG_R0)
        if address == 0x64faa:
            offset = instance.reg_read(ar.UC_ARM_REG_R0)
            offset = offset if offset < 0x80000000 else offset - 0x100000000
            self.placements.append([self.selected_slot, offset])
            if offset >= 0:
                self.slot_offsets[self.selected_slot] = offset
        name = self.handlers.get(address)
        if name == "get_positions":
            count = instance.reg_read(ar.UC_ARM_REG_R1)
            out = instance.reg_read(ar.UC_ARM_REG_R2)
            array_out = instance.reg_read(ar.UC_ARM_REG_R3)
            transform = self.transforms["set_positions"]
            if count != 4:
                raise RuntimeError("unexpected original position-transform extent")
            instance.mem_write(out, struct.pack("<4I", transform["scale_bits"], *transform["bias_bits"]))
            self.word(array_out, self.positions)
        elif name == "array_set" and self.slot_geometry:
            array = instance.reg_read(ar.UC_ARM_REG_R0)
            first = instance.reg_read(ar.UC_ARM_REG_R1)
            count = instance.reg_read(ar.UC_ARM_REG_R2)
            components = instance.reg_read(ar.UC_ARM_REG_R3)
            pointer = self.read_word(instance.reg_read(ar.UC_ARM_REG_SP))
            if first % 4 or count != 4 or first // 4 >= len(self.slot_geometry):
                raise RuntimeError("original pool write exceeded one transient slot")
            slot = first // 4
            if array == self.positions and components == 12:
                self.slot_geometry[slot] = list(struct.unpack("<12h", instance.mem_read(pointer, 24)))
            elif array == self.uv and components == 8:
                self.slot_uv[slot] = list(struct.unpack("<8h", instance.mem_read(pointer, 16)))
            else:
                raise RuntimeError("unexpected original pool array update")
        super().hook(instance, address, size, user)

    def register_candidates(self, capacity, config, tables):
        self.candidate_pointer = self.alloc(capacity * 3)
        self.u.mem_write(self.candidate_pointer, bytes([127]) * capacity * 3)
        self.word(0xd8e18, self.candidate_pointer)
        self.word(0xd8dfc, self.alloc(capacity * 4))
        frame, offset = 0x21fe000, 0
        for y in range(self.height):
            for x in range(self.width):
                tile = self.grid[y * self.width + x]
                if config[2] and tables[160 + tile * 5] == 14:
                    tile = 255
                self.u.mem_write(frame, bytes(0x300))
                for at, value in ((0x150, tile), (0x1e0, x), (0x204, y), (0x140, x),
                                  (0x128, 0), (0xec, offset)):
                    self.word(frame + at, value)
                stop = 0x6b2b4 if tile == 255 else 0x6b28c
                self.block(0x6b1e8, stop, frame)
                offset = self.read_word(frame + 0xec)
        if offset > capacity * 3 or offset % 3:
            raise RuntimeError("original registration exceeded counted candidate capacity")
        self.registered_candidates = offset // 3
        return bytes(self.u.mem_read(self.candidate_pointer, capacity * 3))

    def setup_pool(self, grid, config, tables, seed):
        self.setup(grid, config)
        self.u.mem_write(0xd8f38, tables[160:320]) # Explicit input data, never code.
        self.word(self.map_object + 0x18, self.grid_data)
        self.word(self.map_object + 0x1c, len(self.grid))
        candidate_count, slots = self.first_pass()
        potential_faces = self.read_word(0x21fe000 + 0xd4)
        column_count = self.read_word(0x21fe000 + 0xd0)
        self.initial_records = self.register_candidates(candidate_count, config, tables)
        self.capacity, self.slots = candidate_count, slots
        self.total_mesh_quads = slots + potential_faces
        if not 0 < self.total_mesh_quads < 4096:
            raise ValueError("oracle requires a nonempty bounded original animated mesh")
        pos, uv = self.alloc(self.total_mesh_quads * 24), self.alloc(self.total_mesh_quads * 16)
        selectors, values = self.alloc(8), self.alloc(self.total_mesh_quads * 4)
        self.word(selectors, values)
        self.word(selectors + 4, self.total_mesh_quads)
        for i in range(self.total_mesh_quads):
            self.word(values + i * 4, i % 4 if i < slots else 0)
        for address, value in ((0xd913c, 0), (0xd964c, 0), (0xd9144, pos),
                               (0xd9140, uv), (0xd914c, float_bits(1.0)),
                               (0xd9150, self.animated_atlas),
                               (0xd9644, self.positions), (0xd9648, self.uv)):
            self.word(address, value)
        self.call(0x70eb4, [0, 0, 0, 0, 0, self.height * 32])
        self.call(0x71248, [selectors, self.total_mesh_quads, self.total_mesh_quads, 1,
            1, self.width * 32, 0, 0, self.width * 32, 0, self.height * 32])
        self.call(0x71884, [1, float_bits(1.0)])
        self.slot_geometry = [list(struct.unpack("<12h", self.u.mem_read(pos + i*24, 24))) for i in range(slots)]
        self.slot_uv = [list(struct.unpack("<8h", self.u.mem_read(uv + i*16, 16))) for i in range(slots)]
        self.initial_geometry = json.loads(json.dumps(self.slot_geometry))
        self.initial_uv = json.loads(json.dumps(self.slot_uv))
        self.slot_offsets = [-1] * slots
        app = self.alloc(0x400)
        self.word(self.controller + 0xe4, app)
        self.word(app + 0x3e8, self.rng)
        self.u.mem_write(0xd95ac, bytes(self.u.mem_read(self.animated_atlas, 16)))
        self.word(0xd8e04, self.alloc(24))
        self.word(0xd8e00, 0)  # Recorded M3G mesh index0.
        self.word(0xd8e24, 4)
        self.call(0x7acc, [self.rng, seed])
        self.pool_draws = 0
        self.generated_words = []
        self.placements = []
        self.u.mem_write(0x21fe000, bytes(0x300))
        self.block(0x6b606, 0x6b660)
        self.check_text()
        return {"candidate_capacity": candidate_count, "registered_candidates": self.registered_candidates,
                "slot_count": slots, "original_face_capacity": potential_faces,
                "original_base_allocation_count": column_count,
                "total_mesh_quads": self.total_mesh_quads}

    def snapshot(self):
        phase_pointer = self.read_word(0xd8e14)
        return {"candidate_records": list(self.u.mem_read(self.candidate_pointer, self.capacity * 3)),
                "slot_offsets": self.slot_offsets[:],
                "slot_phases": list(struct.unpack("<" + "I" * self.slots,
                    self.u.mem_read(phase_pointer, self.slots * 4))),
                "positions": json.loads(json.dumps(self.slot_geometry)),
                "uv": json.loads(json.dumps(self.slot_uv)),
                "accumulated_ms": self.read_word(0xd8e20), "phase": self.read_word(0xd8e28),
                "random_index": self.read_word(self.rng + 8), "random_draws": self.pool_draws,
                "random_words_sha256": digest(bytes(self.u.mem_read(self.rng + 0x14, 624 * 4))),
                "placements": self.placements[:]}

    def advance(self, delta):
        before = self.read_word(0xd8e20)
        self.word(0x21fe000 + 0xc, delta)
        stop = 0x6d758 if before + delta >= 250 else 0x6d82a
        self.placements = []
        self.block(0x6d6ea, stop)
        return self.snapshot()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--binary", type=Path, required=True)
    ap.add_argument("--libgcc", type=Path, required=True)
    ap.add_argument("--unicorn-dir", type=Path, required=True)
    ap.add_argument("--grid", type=Path, required=True)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--tables", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    sys.path.insert(0, str(args.unicorn_dir))
    image, gcc = args.binary.read_bytes(), args.libgcc.read_bytes()
    if (digest(image), digest(gcc)) != (IMAGE_SHA, LIBGCC_SHA):
        raise ValueError("source image differs from audited originals")
    original = OriginalDecorations(image, gcc)
    layout = original.setup_pool(args.grid.read_bytes(), decode_config(args.config.read_bytes()),
                                 args.tables.read_bytes(), 0x47413133)
    snapshots = [original.snapshot()]
    for delta in (0, 249, 1, 250, 1000, 0, 1, 249, 250, 250, 250, 250, 250, 250, 250, 250):
        snapshots.append(original.advance(delta))
    report = {"layout": layout, "snapshots": snapshots,
              "initial_dummy_positions": original.initial_geometry, "initial_dummy_uv": original.initial_uv,
              "calls": dict(original.calls), "original_code_unchanged": True,
              "original_sha256": IMAGE_SHA, "libgcc_sha256": LIBGCC_SHA,
              "seed": 0x47413133, "oracle_source_sha256": digest(Path(__file__).read_bytes())}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, separators=(",", ":")) + "\n")
    print(json.dumps({"layout": layout, "snapshots": len(snapshots), "final_draws": original.pool_draws,
                      "report": str(args.output)}))


if __name__ == "__main__":
    main()
