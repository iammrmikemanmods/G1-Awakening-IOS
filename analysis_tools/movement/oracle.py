#!/usr/bin/env python3
"""Development-only original-code oracle; never linked into the native product.

Requires a user-provided original G1 1.1.3 ARMv6 executable and external Unicorn
2.1.4. It executes the original movement functions with synthetic, explicitly
seeded data. No instruction patches, function replacements, or iOS HLE are used.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

ORIGINAL_SHA256 = "0d510516fe3676ee4a0f4dff60ba64e1c5bf79a0c9800f420b1bbdb1c12febfd"
FUNCTIONS = {
    "remaining_budget": 0x43724,
    "movement_cost": 0x4A16E,
    "movement_range_wrapper": 0x50844,
    "movement_fill": 0x4A29C,
    "reset_range": 0x49B16,
    "any_unoccupied_destination": 0x49B5A,
}


class OriginalMovement:
    def __init__(self, image, case):
        import unicorn as uc
        from unicorn import arm_const as ar
        self.uc_module, self.ar = uc, ar
        self.uc = uc.Uc(uc.UC_ARCH_ARM, uc.UC_MODE_THUMB)
        self.uc.mem_map(0x1000, 0xF0000)
        self.uc.mem_write(0x1000, image)
        self.original_text = image[:0xD1000]
        self.uc.mem_protect(0x1000, 0xD1000, uc.UC_PROT_READ | uc.UC_PROT_EXEC)
        self.uc.mem_map(0x1000000, 0x400000)
        self.uc.mem_map(0x2000000, 0x200000)
        self.uc.mem_map(0x3000000, 0x1000)
        self.next = 0x1000000
        self.return_address = 0x3000000
        self.case = case
        self.width, self.height = case["width"], case["height"]
        self.profile = case["unit"]
        self.map = self.alloc(0x500)
        self.unit = self.alloc(0x80)
        self.grid_columns = []
        self.seed()

    def alloc(self, size):
        address = self.next
        self.next += (size + 7) & ~7
        if self.next > 0x1400000:
            raise RuntimeError("Synthetic oracle heap exhausted")
        return address

    def write32(self, address, value):
        self.uc.mem_write(address, struct.pack("<I", value & 0xFFFFFFFF))

    def write8(self, address, value):
        self.uc.mem_write(address, bytes([value & 0xFF]))

    def array(self, values, element_size=4):
        address = self.alloc(max(len(values) * element_size, 8))
        if element_size == 1:
            self.uc.mem_write(address, bytes(v & 0xFF for v in values))
        elif values:
            self.uc.mem_write(address, struct.pack("<" + "I" * len(values),
                                                  *(v & 0xFFFFFFFF for v in values)))
        return address

    def vector_at(self, address, data, count):
        self.write32(address, data)
        self.write32(address + 4, count)

    def int_vectors(self, records):
        outer = self.alloc(max(8, 8 * len(records)))
        for i, record in enumerate(records):
            self.vector_at(outer + 8 * i, self.array(record), len(record))
        return outer

    def seed(self):
        p, c, m = self.profile, self.case, self.map
        self.write8(m + 0x15, self.width)
        self.write8(m + 0x16, self.height)

        terrain_types = []
        tile_ids = []
        for fields in c["terrain"]:
            fields = tuple(fields)
            if fields not in terrain_types:
                terrain_types.append(fields)
            tile_ids.append(terrain_types.index(fields))
        if len(terrain_types) > 127:
            raise ValueError("Oracle synthetic tile ids must fit signed original lookup")
        self.vector_at(m + 0x18, self.array(tile_ids, 1), len(tile_ids))
        self.vector_at(m + 0x20, self.array(range(len(terrain_types)), 1), len(terrain_types))
        terrain_records = self.alloc(8 * len(terrain_types))
        for i, (cost, field2) in enumerate(terrain_types):
            self.vector_at(terrain_records + 8 * i, self.array([cost, 0, field2], 1), 3)
        terrain_object = self.alloc(8)
        self.vector_at(terrain_object, terrain_records, len(terrain_types))
        self.write32(m + 0x294, terrain_object)

        grid = self.alloc(self.width * 8)
        for x in range(self.width):
            column = self.array([-1] * self.height)
            self.grid_columns.append(column)
            self.vector_at(grid + x * 8, column, self.height)
        self.vector_at(m + 0xB4, grid, self.width)

        # Type -> form -> byte-stat vectors. Only the selected type is needed.
        type_records = self.alloc((p["type"] + 1) * 8)
        form_records = self.alloc((p.get("form", 0) + 1) * 8)
        stats = [0] * 12
        stats[0], stats[6] = p["base_budget"], p["field6"]
        self.vector_at(form_records + p.get("form", 0) * 8, self.array(stats, 1), len(stats))
        self.vector_at(type_records + p["type"] * 8, form_records, p.get("form", 0) + 1)
        self.vector_at(m + 0x174, type_records, p["type"] + 1)
        for offset, value in ((9, p["type"]), (10, p["owner"]),
                              (12, p.get("form", 0)), (13, 1),
                              (0x3B, p["x"]), (0x3C, p["y"]),
                              (0x59, p["spent_budget"])):
            self.write8(self.unit + offset, value)

        owners = [[], []]
        for index, owner in enumerate(c["active_owners"]):
            if owner is None:
                continue
            occupant = self.alloc(0x80)
            self.write8(occupant + 0xA, owner)
            self.write8(occupant + 0xD, 1)
            self.write8(occupant + 0x3B, index % self.width)
            self.write8(occupant + 0x3C, index // self.width)
            owners[owner].append(occupant)
        count = max(1, *(len(v) for v in owners))
        lists = [self.array(v + [0] * (count - len(v))) for v in owners]
        self.write32(m + 0x54, count)
        self.write32(m + 0x84, self.array(lists))

        points = [[x, y, 0, state] for x, y, state in c.get("points", [])]
        self.vector_at(m + 0x420, self.int_vectors(points), len(points))
        regions = c.get("rectangles", [])
        self.vector_at(m + 0xC, self.int_vectors(regions), len(regions))

        # Seed only runtime data for the original singleton getter at 0x62d1c.
        global_slot, global_object, app = self.alloc(8), self.alloc(0x60), self.alloc(0x400)
        self.write32(0xD2038, global_slot)
        self.write32(global_slot, global_object)
        self.write32(global_object + 0x58, app)
        self.write32(app + 0x3E4, m)

    def call(self, address, arguments):
        ar = self.ar
        registers = [ar.UC_ARM_REG_R0, ar.UC_ARM_REG_R1, ar.UC_ARM_REG_R2,
                     ar.UC_ARM_REG_R3, ar.UC_ARM_REG_R4, ar.UC_ARM_REG_R5,
                     ar.UC_ARM_REG_R6, ar.UC_ARM_REG_R7, ar.UC_ARM_REG_R8,
                     ar.UC_ARM_REG_R9, ar.UC_ARM_REG_R10, ar.UC_ARM_REG_R11,
                     ar.UC_ARM_REG_R12]
        for register in registers:
            self.uc.reg_write(register, 0)
        sp = 0x21FF000
        self.uc.reg_write(ar.UC_ARM_REG_CPSR, 0x30)
        self.uc.reg_write(ar.UC_ARM_REG_SP, sp)
        self.uc.reg_write(ar.UC_ARM_REG_LR, self.return_address | 1)
        for index, value in enumerate(arguments):
            if index < 4:
                self.uc.reg_write(registers[index], value & 0xFFFFFFFF)
            else:
                self.write32(sp + 4 * (index - 4), value)
        self.uc.emu_start(address | 1, self.return_address, timeout=5_000_000,
                          count=8_000_000)
        if self.uc.reg_read(ar.UC_ARM_REG_PC) != self.return_address:
            raise RuntimeError(f"Original function 0x{address:x} did not return within bound")
        if self.uc.reg_read(ar.UC_ARM_REG_SP) != sp:
            raise RuntimeError("Original function failed stack-balance check")
        return self.uc.reg_read(ar.UC_ARM_REG_R0)

    def cost(self, x, y):
        p = self.profile
        return self.call(FUNCTIONS["movement_cost"],
                         [self.map, p["x"], p["y"], x, y,
                          p["type"], p.get("form", 0), p["owner"]])

    def run(self):
        budget = self.call(FUNCTIONS["remaining_budget"], [self.unit])
        available = self.call(FUNCTIONS["movement_range_wrapper"], [self.map, self.unit])
        columns = [struct.unpack("<" + "i" * self.height,
                                 self.uc.mem_read(a, self.height * 4))
                   for a in self.grid_columns]
        remaining = [columns[x][y] for y in range(self.height) for x in range(self.width)]
        costs = [self.cost(x, y) for y in range(self.height) for x in range(self.width)]
        outside_costs = [self.cost(-1, 0), self.cost(0, -1),
                         self.cost(self.width, 0), self.cost(0, self.height)]
        if bytes(self.uc.mem_read(0x1000, 0xD1000)) != self.original_text:
            raise RuntimeError("Original __TEXT changed during oracle execution")
        return {"name": self.case["name"], "remaining_budget": budget,
                "remaining": remaining, "has_unoccupied_destination": bool(available),
                "entry_costs": costs,
                "out_of_bounds_costs": outside_costs}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--unicorn-dir", type=Path)
    args = parser.parse_args()
    if args.unicorn_dir:
        sys.path.insert(0, str(args.unicorn_dir))
    import unicorn
    image = args.binary.read_bytes()
    digest = hashlib.sha256(image).hexdigest()
    if digest != ORIGINAL_SHA256:
        raise SystemExit("Wrong original executable hash; oracle not run")
    cases = json.loads(args.cases.read_text())["cases"]
    results = [OriginalMovement(image, case).run() for case in cases]
    record = {"kind": "development-only original ARM function execution",
              "original_sha256": digest, "unicorn_version": unicorn.__version__,
              "instruction_patches": 0, "function_stubs": 0,
              "original_text_readonly_and_unchanged_all_cases": True,
              "synthetic_state": True, "full_game_execution": False,
              "functions": {name: hex(address) for name, address in FUNCTIONS.items()},
              "case_count": len(cases), "results": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"case_count": len(cases), "status": "original_functions_returned",
                      "output": str(args.output)}))


if __name__ == "__main__":
    main()
