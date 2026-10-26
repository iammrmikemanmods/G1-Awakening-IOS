#!/usr/bin/env python3
"""Development-only original ARM reference for the native world bootstrap.

No part of this script or Unicorn is linked into, loaded by, or shipped with
the native game. All input files are explicit local arguments. The original
executable must match the audited SHA256 and is mapped read-only for code.

Executes the original owner assignment and spawn/reset routines with seeded
data. Executes a bounded opcode-9 fragment through its terrain overrides;
only its resource-loader boundary is replaced with explicit archive input.
The spawn routine's imported signed division is supplied as arithmetic.
Neither boundary decides a gameplay result. The full dispatcher, resource
stream loader, rendering, dialogue and campaign are not executed here.
"""
import argparse
import collections
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import zlib

IMAGE_SHA256 = "0d510516fe3676ee4a0f4dff60ba64e1c5bf79a0c9800f420b1bbdb1c12febfd"
ARCHIVE_SHA256 = "663d2888982093ce66b7811ccb7a6ad3acd37fc02ffa85144775b88c39e83cb4"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def resource(archive, wanted):
    """Independent struct/zlib extraction of one original FGIB member."""
    group_start, group_count, member_start, member_count = struct.unpack_from("<4I", archive, 8)
    found = []
    for group in range(group_count):
        base, count, first = struct.unpack_from("<IHH", archive, group_start + group * 8)
        if not base <= wanted < base + count:
            continue
        index = first + wanted - base
        if index >= member_count:
            raise RuntimeError("reference member outside archive table")
        key, begin = struct.unpack_from("<II", archive, member_start + index * 8)
        end = struct.unpack_from("<I", archive, member_start + (index + 1) * 8 + 4)[0]
        if key == 0xf4e02223:
            found.append((begin, end))
    if len(found) != 1:
        raise RuntimeError(f"original resource {wanted} missing/ambiguous")
    begin, end = found[0]
    flags = struct.unpack_from("<I", archive, begin)[0]
    if flags == 4:
        return archive[begin + 4:end]
    if flags != 0x800004:
        raise RuntimeError("unexpected original FGIB flags")
    expanded, stored = struct.unpack_from("<II", archive, begin + 4)
    if stored != end - begin - 12:
        raise RuntimeError("original FGIB compressed span mismatch")
    raw = zlib.decompress(archive[begin + 12:end])
    if len(raw) != expanded:
        raise RuntimeError("original FGIB expanded length mismatch")
    return raw


def decode_definition(data, unit_type, resource_id):
    """Raw field decode derived from the original 0x5a522 read sequence."""
    offset = 0
    def unpack(fmt):
        nonlocal offset
        value = struct.unpack_from(fmt, data, offset)
        offset += struct.calcsize(fmt)
        return value
    def byte_vector():
        length, = unpack(">B")
        return list(unpack(">" + "B" * length))
    texts = list(unpack(">HH"))
    count, = unpack(">B")
    detail = list(unpack(">" + "H" * count))
    scalars = list(unpack(">5B"))
    auxiliary = byte_vector()
    form_count, = unpack(">B")
    forms = [byte_vector() for _ in range(form_count)]
    if offset != len(data) or any(len(form) != 14 for form in forms):
        raise RuntimeError("original definition framing differs from recovered variant")
    return {"type": unit_type, "resource_id": resource_id,
            "raw_text_indices": texts, "raw_detail_text_indices": detail,
            "scalar_fields": scalars, "auxiliary_fields": auxiliary, "forms": forms}


class Reference:
    BOUNDARIES = {
        0xba288: "imported ___divsi3: signed integer division truncating toward zero",
        0x507fc: "map resource I/O: record resource tags and supply decoded lookup bytes",
    }

    def __init__(self, image, definitions, archive):
        import unicorn as uc
        from unicorn import arm_const as ar
        self.uc_module, self.ar = uc, ar
        self.u = uc.Uc(uc.UC_ARCH_ARM, uc.UC_MODE_THUMB)
        self.u.mem_map(0x1000, 0xf0000)
        self.u.mem_write(0x1000, image)
        self.text = image[:0xd1000]
        self.u.mem_protect(0x1000, 0xd1000, uc.UC_PROT_READ | uc.UC_PROT_EXEC)
        self.u.mem_map(0x1000000, 0x400000)
        self.u.mem_map(0x2000000, 0x200000)
        self.u.mem_map(0x3000000, 0x1000)
        self.next = 0x1000000
        self.sp, self.return_address = 0x21ff000, 0x3000000
        self.archive = archive
        self.definitions = definitions
        self.boundaries = collections.Counter()
        self.active_boundaries = set()
        self.load_requests = []
        self.u.hook_add(uc.UC_HOOK_CODE, self.hook)
        self.map = self.alloc(0x600)
        self.app = self.alloc(0x500)
        slot, singleton = self.alloc(8), self.alloc(0x60)
        self.w32(0xd2038, slot)
        self.w32(slot, singleton)
        self.w32(singleton + 0x58, self.app)
        self.w32(self.app + 0x3e4, self.map)
        self.units = []
        types = self.alloc(len(definitions) * 8)
        for definition in definitions:
            unit = self.alloc(0x80)
            self.w8(unit + 9, definition["type"])
            self.w8(unit + 0xb, definition["scalar_fields"][0])
            self.units.append(unit)
            forms = self.alloc(len(definition["forms"]) * 8)
            for form, values in enumerate(definition["forms"]):
                self.vector(forms + form * 8, self.array(values, "B"), len(values))
            self.vector(types + definition["type"] * 8, forms, len(definition["forms"]))
        self.vector(self.map + 0x174, types, len(definitions))
        self.w32(self.map + 0x90, self.array(self.units, "I"))
        self.w8(self.map + 0x130, len(self.units))
        self.owner_arrays = [self.array([0] * len(self.units), "I") for _ in range(2)]
        self.w32(self.map + 0x84, self.array(self.owner_arrays, "I"))

    def alloc(self, size):
        pointer = self.next
        self.next += (max(size, 8) + 7) & ~7
        if self.next > 0x1400000:
            raise RuntimeError("reference synthetic heap exceeds bound")
        return pointer

    def w32(self, address, value):
        self.u.mem_write(address, struct.pack("<I", value & 0xffffffff))

    def w8(self, address, value):
        self.u.mem_write(address, bytes([value & 255]))

    def r32(self, address):
        return struct.unpack("<I", self.u.mem_read(address, 4))[0]

    def r8(self, address):
        return self.u.mem_read(address, 1)[0]

    def array(self, values, fmt):
        pointer = self.alloc(len(values) * struct.calcsize(fmt))
        if values:
            self.u.mem_write(pointer, struct.pack("<" + fmt * len(values), *values))
        return pointer

    def vector(self, address, pointer, count):
        self.w32(address, pointer)
        self.w32(address + 4, count)

    @staticmethod
    def signed32(value):
        return value if value < 0x80000000 else value - 0x100000000

    def hook(self, instance, address, size, user_data):
        ar = self.ar
        if address in self.BOUNDARIES:
            if address not in self.active_boundaries:
                raise RuntimeError(f"unapproved reference boundary reached: {address:#x}")
            self.boundaries[hex(address)] += 1
            r0, r1, r2 = [instance.reg_read(register) for register in
                           (ar.UC_ARM_REG_R0, ar.UC_ARM_REG_R1, ar.UC_ARM_REG_R2)]
            if address == 0xba288:
                left, right = self.signed32(r0), self.signed32(r1)
                if right == 0 or (left == -0x80000000 and right == -1):
                    raise RuntimeError("undefined signed division at original boundary")
                result = abs(left) // abs(right)
                if (left < 0) != (right < 0):
                    result = -result
                instance.reg_write(ar.UC_ARM_REG_R0, result & 0xffffffff)
            elif address == 0x507fc:
                if r0 != self.map or r1 >> 24 != 3 or r2 >> 24 != 3:
                    raise RuntimeError("unexpected original map loader arguments")
                lookup_id = r2 & 0xffffff
                raw = resource(self.archive, lookup_id)
                if len(raw) != 33 or raw[0] != 1:
                    raise RuntimeError("lookup boundary received unsupported raw data")
                self.vector(self.map + 0x20, self.array(list(raw[1:]), "B"), 32)
                self.load_requests.append({"grid_resource_id": r1 & 0xffffff,
                                           "lookup_resource_id": lookup_id})
            instance.reg_write(ar.UC_ARM_REG_PC, instance.reg_read(ar.UC_ARM_REG_LR))
        elif 0xba1e0 <= address < 0xbaaa0:
            raise RuntimeError(f"unimplemented original import reached: {address:#x}")

    def start(self, entry, args, end=None, check_stack=True):
        ar = self.ar
        registers = [ar.UC_ARM_REG_R0, ar.UC_ARM_REG_R1, ar.UC_ARM_REG_R2,
                     ar.UC_ARM_REG_R3, ar.UC_ARM_REG_R4, ar.UC_ARM_REG_R5,
                     ar.UC_ARM_REG_R6, ar.UC_ARM_REG_R7, ar.UC_ARM_REG_R8,
                     ar.UC_ARM_REG_R9, ar.UC_ARM_REG_R10, ar.UC_ARM_REG_R11,
                     ar.UC_ARM_REG_R12]
        for register in registers:
            self.u.reg_write(register, 0)
        self.u.reg_write(ar.UC_ARM_REG_CPSR, 0x30)
        self.u.reg_write(ar.UC_ARM_REG_SP, self.sp)
        self.u.reg_write(ar.UC_ARM_REG_LR, self.return_address | 1)
        for i, value in enumerate(args):
            if i < 4:
                self.u.reg_write(registers[i], value & 0xffffffff)
            else:
                self.w32(self.sp + (i - 4) * 4, value)
        stop = self.return_address if end is None else end
        self.u.emu_start(entry | 1, stop, timeout=2_000_000, count=1_000_000)
        if self.u.reg_read(ar.UC_ARM_REG_PC) != stop:
            raise RuntimeError(f"original {entry:#x} did not reach its bounded stop")
        if check_stack and self.u.reg_read(ar.UC_ARM_REG_SP) != self.sp:
            raise RuntimeError("original stack-balance check failed")
        if bytes(self.u.mem_read(0x1000, 0xd1000)) != self.text:
            raise RuntimeError("original text changed during reference execution")

    def owners(self, factions):
        self.active_boundaries = set()
        self.vector(self.map + 0xa0, self.array(factions, "B"), len(factions))
        for unit in self.units:
            self.w8(unit + 0xa, 0xff)
        for pointer in self.owner_arrays:
            self.u.mem_write(pointer, b"\0" * (len(self.units) * 4))
        self.start(0x496e4, [self.map])
        owners = [self.r8(unit + 0xa) for unit in self.units]
        ordered_types = []
        for pointer in self.owner_arrays:
            addresses = struct.unpack("<" + "I" * len(self.units),
                                      self.u.mem_read(pointer, len(self.units) * 4))
            ordered_types.append([self.r8(unit + 9) for unit in addresses if unit])
        return {"player_factions": factions, "owners_by_type": owners,
                "ordered_types_by_owner": ordered_types}

    def spawn(self, unit_type, x, y):
        self.active_boundaries = {0xba288}
        unit = self.units[unit_type]
        self.w8(unit + 0xc, 1)  # Prove original spawn resets a previously selected form.
        self.w8(unit + 0x59, 99)
        self.w32(unit + 0x40, 0x12345678)
        self.w32(unit + 0x44, 0x12345678)
        self.start(0x4333a, [unit, x, y])
        return {"type": self.r8(unit + 9), "faction": self.r8(unit + 0xb),
                "owner": self.r8(unit + 0xa), "form": self.r8(unit + 0xc),
                "active": bool(self.r8(unit + 0xd)), "x": self.r8(unit + 0x3b),
                "y": self.r8(unit + 0x3c), "spent_budget": self.r8(unit + 0x59),
                "exclusion_fields_40_44": [self.r32(unit + 0x40), self.r32(unit + 0x44)]}

    def style(self, map_index, style):
        self.active_boundaries = {0x507fc}
        commands = self.alloc(8)
        self.vector(commands, self.array([9, map_index, style], "H"), 3)
        self.vector(self.map + 0x214, commands, 1)
        self.w32(self.map + 0x21c, 0)
        self.w32(self.map + 0x22c, 0)
        # The dispatcher frame is deliberately seeded at the original live-map slot.
        self.w32(self.sp + 0x7c, self.map)
        before = len(self.load_requests)
        self.start(0x56c90, [], end=0x56de2)
        if len(self.load_requests) != before + 1:
            raise RuntimeError("style fragment did not invoke exactly one original loader call")
        return {"map_index": map_index, "style": self.r32(self.map + 0x22c),
                **self.load_requests[-1],
                "effective": list(self.u.mem_read(self.r32(self.map + 0x20), 32))}


def load_module(path):
    spec = importlib.util.spec_from_file_location("g1_original_movement_reference", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--binary", type=Path, required=True)
    ap.add_argument("--archive", type=Path, required=True)
    ap.add_argument("--native-probe", type=Path, required=True)
    ap.add_argument("--movement-oracle", type=Path, required=True)
    ap.add_argument("--unicorn-dir", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    if args.unicorn_dir:
        sys.path.insert(0, str(args.unicorn_dir))
    import unicorn
    image, archive = args.binary.read_bytes(), args.archive.read_bytes()
    if sha(image) != IMAGE_SHA256 or sha(archive) != ARCHIVE_SHA256:
        raise RuntimeError("original source hashes differ; reference execution refused")
    native = json.loads(subprocess.run([str(args.native_probe.resolve()), str(args.archive.resolve())],
                                      check=True, capture_output=True, text=True, timeout=30).stdout)
    tables = {}
    for name, address, count in [("unit_resources", 0xcecc0, 23),
                                 ("campaign_resources", 0xcec18, 17),
                                 ("grid_resources", 0xcec60, 22)]:
        words = struct.unpack_from("<" + "I" * count, image, address - 0x1000)
        if any(word >> 24 != 3 for word in words):
            raise RuntimeError("original resource table tag differs")
        tables[name] = [word & 0xffffff for word in words]
    definitions = [decode_definition(resource(archive, rid), t, rid)
                   for t, rid in enumerate(tables["unit_resources"])]
    if definitions != native["definitions"]:
        raise RuntimeError("native definition fields differ from independent raw decode")
    for name in ("campaign_resources", "grid_resources"):
        if tables[name] != native[name]:
            raise RuntimeError(f"native resource table differs: {name}")
    reference = Reference(image, definitions, archive)
    ownership = reference.owners([0, 1])
    for unit in native["units"]:
        if ownership["owners_by_type"][unit["type"]] != unit["owner"]:
            raise RuntimeError("native unit owner differs from original assignment")
    spawns = []
    for unit in native["units"]:
        original = reference.spawn(unit["type"], unit["x"], unit["y"])
        if any(original[k] != unit[k] for k in original if k != "exclusion_fields_40_44"):
            raise RuntimeError("native first placement fields differ from original spawn")
        if original["exclusion_fields_40_44"] != [0, 0]:
            raise RuntimeError("original spawn did not clear exclusion state")
        spawns.append(original)
    styles = []
    for map_index in range(22):
        for style in range(3):
            original = reference.style(map_index, style)
            expected = native["style_lookups"][style]
            if (original["grid_resource_id"] != native["grid_resources"][map_index] or
                    original["lookup_resource_id"] != expected["resource_id"] or
                    original["style"] != style or original["effective"] != expected["effective"]):
                raise RuntimeError("native map/style selection or overrides differ from original")
            styles.append(original)
    movement_module = load_module(args.movement_oracle)
    movement_results = []
    terrain = [[native["terrain_rules"][native["effective_lookup"][tile]][field] for field in (0, 2)]
               for tile in native["tiles"]]
    owners = [None] * len(terrain)
    for unit in native["units"]:
        owners[unit["y"] * native["width"] + unit["x"]] = unit["owner"]
    for unit in native["units"]:
        case = {"name": f"first_campaign_type_{unit['type']}",
                "width": native["width"], "height": native["height"],
                "terrain": terrain, "active_owners": owners,
                "unit": {k: unit[k] for k in ("type", "owner", "form", "x", "y",
                                              "base_budget", "spent_budget", "field6")}}
        original = movement_module.OriginalMovement(image, case).run()
        for key in ("remaining_budget", "remaining", "has_unoccupied_destination", "entry_costs"):
            if original[key] != unit[key]:
                raise RuntimeError(f"native integrated movement differs: type={unit['type']}, field={key}")
        movement_results.append({"type": unit["type"], "cell_count": len(terrain),
                                 "reachable_cells_including_origin": sum(v >= 0 for v in original["remaining"]),
                                 "original_result_sha256": sha(canonical(original)),
                                 "native_matches_original": True})
    result = {
        "kind": "development-only original ARM world initialization reference",
        "original_sha256": IMAGE_SHA256, "archive_sha256": ARCHIVE_SHA256,
        "reference_script_sha256": sha(Path(__file__).read_bytes()),
        "movement_reference_script_sha256": sha(args.movement_oracle.read_bytes()),
        "native_probe_sha256": sha(args.native_probe.read_bytes()),
        "unicorn_version": unicorn.__version__, "all_passed": True,
        "original_text_readonly_and_unchanged": True, "instruction_patches": 0,
        "boundary_substitutions": {hex(k): v for k, v in Reference.BOUNDARIES.items()},
        "boundary_call_counts": dict(reference.boundaries),
        "definition_payloads_independently_decoded_and_matched": len(definitions),
        "definition_decode_sha256": sha(canonical(definitions)),
        "resource_tables_match_original": tables,
        "owner_function": "0x496e4", "owner_result": ownership,
        "spawn_function": "0x4333a -> 0x4328a / 0x430fc", "spawn_results": spawns,
        "map_style_fragment": {"begin": "0x56c90", "stop_before": "0x56de2",
                               "cases_matched": len(styles),
                               "all_case_results_sha256": sha(canonical(styles)),
                               "map0_cases": styles[:3]},
        "movement_integration": movement_results,
        "native_world_summary": {k: native[k] for k in (
            "mission_resource_id", "grid_resource_id", "lookup_resource_id", "style",
            "width", "height", "command_count", "next_command_index", "next_opcode", "stop",
            "title_text_index", "flag_225", "last_phase_opcode", "camera", "available_types", "sites")},
        "limitations": [
            "Original object layout and call-frame inputs are explicitly seeded; no whole engine boot",
            "Original resource stream loader and unit definition parser are not executed",
            "Two explicit non-gameplay boundary substitutions; no silent import fallback",
            "Opcode9 is a bounded control-flow fragment, not the full staged dispatcher",
            "Native unit subset is checked against original owner/spawn behavior, not every side effect",
            "Movement comparison seeds decoded board/profile inputs; it does not execute a move",
            "No dialogue, objective, AI, combat, save/load, complete campaign or iOS device validation"]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"all_passed": True, "definitions": len(definitions),
                      "spawns": len(spawns), "map_style_cases": len(styles),
                      "movement_integrations": len(movement_results), "output": str(args.output)}))


if __name__ == "__main__":
    main()
