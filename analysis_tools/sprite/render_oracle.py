#!/usr/bin/env python3
"""Development-only original sprite setup oracle; excluded from native product.

Runs original 0x70eb4/0x71248/0x71884/0x72100/0x715d0 with synthetic
M3G objects. Object ownership and GPU API boundaries are recorded substitutes.
Float/integer helper calls execute unchanged ARMv6 libgcc instructions from an
explicit local input, rather than using Python to reproduce their arithmetic.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import sys

IMAGE_SHA = "0d510516fe3676ee4a0f4dff60ba64e1c5bf79a0c9800f420b1bbdb1c12febfd"
LIBGCC_SHA = "d758fbf1ac952532955d62866bd02df55315c0599f64bdd978ff941fccbdcf83"
MATH = {0xba27c: "___divsf3vfp", 0xba390: "___mulsf3vfp",
        0xba30c: "___floatsisfvfp", 0xba2c4: "___fixsfsivfp",
        0xba348: "___gtsf2vfp", 0xba39c: "___nesf2vfp",
        0xba288: "___divsi3", 0xba36c: "___modsi3"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def float_bits(value):
    return struct.unpack("<I", struct.pack("<f", value))[0]


def load_libgcc(data):
    magic, count = struct.unpack_from(">II", data)
    if magic != 0xcafebabe:
        raise ValueError("expected audited fat libgcc input")
    candidates = [struct.unpack_from(">5I", data, 8 + i*20) for i in range(count)]
    _, _, offset, size, _ = next(x for x in candidates if x[0] == 12 and x[1] == 6)
    thin = data[offset:offset+size]
    commands = struct.unpack_from("<I", thin, 16)[0]
    cursor, segments = 28, []
    for _ in range(commands):
        command, length = struct.unpack_from("<II", thin, cursor)
        if command == 1:
            segments.append(struct.unpack_from("<4I", thin, cursor + 24))
        elif command == 2:
            symbols, count, strings, _ = struct.unpack_from("<4I", thin, cursor + 8)
        cursor += length
    exports = {}
    for i in range(count):
        name_offset, symbol_type, section, description, value = struct.unpack_from("<IBBHI", thin, symbols + i*12)
        name = thin[strings+name_offset:thin.index(b"\0", strings+name_offset)].decode()
        if name in MATH.values():
            exports[name] = value | (1 if description & 8 else 0)
    if set(exports) != set(MATH.values()):
        raise ValueError("ARMv6 libgcc missing required original helpers")
    return thin, segments, exports


class OriginalRenderer:
    def __init__(self, image, gcc):
        import unicorn as uc
        from unicorn import arm_const as ar
        self.uc_api, self.ar = uc, ar
        self.u = uc.Uc(uc.UC_ARCH_ARM, uc.UC_MODE_THUMB)
        self.u.mem_map(0x1000, 0xf0000)
        self.u.mem_write(0x1000, image)
        self.u.mem_protect(0x1000, 0xd1000, uc.UC_PROT_READ | uc.UC_PROT_EXEC)
        self.original_text = image[:0xd1000]
        self.u.mem_map(0x1000000, 0x400000)
        self.u.mem_map(0x2000000, 0x200000)
        self.u.mem_map(0x3000000, 0x200000)
        self.u.mem_map(0x40000000, 0x10000)
        self.thin, segments, exports = load_libgcc(gcc)
        for vm, vmsize, offset, size in segments:
            self.u.mem_write(0x40000000+vm, self.thin[offset:offset+size])
        self.u.mem_protect(0x40000000, 0x9000, uc.UC_PROT_READ | uc.UC_PROT_EXEC)
        self.math = {address: 0x40000000+exports[name] for address, name in MATH.items()}
        self.u.reg_write(ar.UC_ARM_REG_C1_C0_2, 0x00f00000)
        self.u.reg_write(ar.UC_ARM_REG_FPEXC, 0x40000000)
        self.next = 0x1000000
        self.calls, self.transforms, self.arrays, self.strips = Counter(), {}, {}, []
        self.vbo = self.object({0x68: "get_positions", 0x6c: "set_positions",
                               0x70: "get_uv", 0x74: "set_uv"})
        self.positions = self.object({0x60: "array_set"})
        self.uv = self.object({0x60: "array_set"})
        self.indices = self.object({})
        self.engine = self.object({0x1c: "identity"})
        self.app = self.alloc(16)
        self.word(self.app+8, self.engine)
        self.table = self.alloc(4)
        self.word(self.table, self.vbo)
        self.word(0xd9128, self.table)
        self.word(0xd9138, 0)
        self.u.hook_add(uc.UC_HOOK_CODE, self.hook)

    def alloc(self, size):
        address = self.next
        self.next += (max(8, size)+7) & ~7
        if self.next > 0x1400000:
            raise RuntimeError("oracle heap bound exceeded")
        return address

    def word(self, address, value):
        self.u.mem_write(address, struct.pack("<I", value & 0xffffffff))

    def read_word(self, address):
        return struct.unpack("<I", self.u.mem_read(address, 4))[0]

    def object(self, methods):
        if not hasattr(self, "handlers"):
            self.handlers, self.next_handler = {}, 0x3100000
        obj, table = self.alloc(8), self.alloc(0x100)
        self.word(obj, table)
        for offset, name in {0: "retain", 4: "release", **methods}.items():
            address = self.next_handler
            self.next_handler += 4
            self.handlers[address] = name
            self.word(table+offset, address | 1)
        return obj

    def hook(self, instance, address, size, user):
        ar = self.ar
        if address in self.math:
            self.calls[MATH[address]] += 1
            instance.reg_write(ar.UC_ARM_REG_PC, self.math[address])
            return
        registers = [instance.reg_read(r) for r in (ar.UC_ARM_REG_R0, ar.UC_ARM_REG_R1,
                                                     ar.UC_ARM_REG_R2, ar.UC_ARM_REG_R3)]
        r0, r1, r2, r3 = registers
        sp = instance.reg_read(ar.UC_ARM_REG_SP)
        name = self.handlers.get(address)
        if address in (0xba1f8, 0xba210, 0x1f512):
            name = {0xba1f8: "unwind_register", 0xba210: "unwind_unregister", 0x1f512: "free"}[address]
        elif address == 0x1f540:
            name = "allocate"
            instance.reg_write(ar.UC_ARM_REG_R0, self.alloc(r0))
        elif address == 0x27350:
            name = "engine_singleton"
            instance.reg_write(ar.UC_ARM_REG_R0, self.app)
        elif address == 0x7236e:
            name = "create_triangle_strips"
            lengths = self.read_word(sp)
            self.strips.append({"start_index": r2, "lengths": list(struct.unpack(
                "<"+"I"*r3, instance.mem_read(lengths, r3*4)))})
            self.word(r0, self.indices)
        elif address == 0xba204:
            raise RuntimeError("unexpected original exception path")
        if name is None:
            return
        self.calls[name] += 1
        if name in ("set_positions", "set_uv"):
            count = r3 if name == "set_positions" else self.read_word(sp)
            bias_pointer = self.read_word(sp) if name == "set_positions" else self.read_word(sp+4)
            self.transforms[name] = {"array": r1 if name == "set_positions" else r2,
                                     "scale_bits": r2 if name == "set_positions" else r3,
                                     "bias_bits": list(struct.unpack("<"+"I"*count,
                                         instance.mem_read(bias_pointer, count*4)))}
        elif name == "get_uv":
            value = self.transforms["set_uv"]
            self.word(self.read_word(sp), value["array"])
            instance.mem_write(r3, struct.pack("<III", value["scale_bits"], *value["bias_bits"]))
        elif name == "array_set":
            pointer = self.read_word(sp)
            self.arrays[r0] = {"first": r1, "count": r2, "components": r3,
                               "bytes_sha256": digest(bytes(instance.mem_read(pointer, r3*2)))}
        instance.reg_write(ar.UC_ARM_REG_PC, instance.reg_read(ar.UC_ARM_REG_LR))

    def call(self, function, arguments):
        ar = self.ar
        registers = [getattr(ar, "UC_ARM_REG_R"+str(i)) for i in range(13)]
        for register in registers:
            self.u.reg_write(register, 0)
        initial_sp = 0x21ff000
        self.u.reg_write(ar.UC_ARM_REG_CPSR, 0x30)
        self.u.reg_write(ar.UC_ARM_REG_SP, initial_sp)
        self.u.reg_write(ar.UC_ARM_REG_LR, 0x3000001)
        for i, value in enumerate(arguments):
            if i < 4:
                self.u.reg_write(registers[i], value & 0xffffffff)
            else:
                self.word(initial_sp+(i-4)*4, value)
        self.u.emu_start(function | 1, 0x3000000, count=500000, timeout=3_000_000)
        if (self.u.reg_read(ar.UC_ARM_REG_PC) != 0x3000000 or
                self.u.reg_read(ar.UC_ARM_REG_SP) != initial_sp):
            raise RuntimeError(f"original function {function:#x} did not return within bound")
        if bytes(self.u.mem_read(0x1000, 0xd1000)) != self.original_text:
            raise RuntimeError("original main code changed")
        if bytes(self.u.mem_read(0x40000000, 0x9000)) != self.thin[:0x9000]:
            raise RuntimeError("original libgcc code changed")

    def run_sprite_setup(self, maximum_parts):
        # State initialized by 0x71eec, plus explicitly allocated dummy buffers.
        position_buffer = self.alloc(maximum_parts*24)
        uv_buffer = self.alloc(maximum_parts*16)
        atlas = self.alloc(16)
        self.word(atlas, 1) # Non-null image, no rect table => original full UV quad.
        for address, value in ((0xd913c, 0), (0xd964c, 0), (0xd9144, position_buffer),
                               (0xd9140, uv_buffer), (0xd914c, float_bits(1.0)),
                               (0xd9150, atlas), (0xd9644, self.positions), (0xd9648, self.uv)):
            self.word(address, value)
        vector, values = self.alloc(8), self.alloc(maximum_parts*4)
        self.word(vector, values)
        self.word(vector+4, 1)
        self.call(0x70eb4, [0, 32, 0, 0, 0, 0])
        self.call(0x71248, [vector, maximum_parts, maximum_parts, 1, 1, 32, 32, 0, 32, 0, 0])
        scale_after_dummy = self.read_word(0xd914c)
        self.call(0x71884, [0, float_bits(2.0)])
        transforms = json.loads(json.dumps(self.transforms))
        before = self.calls["set_uv"]
        update = self.alloc(16)
        self.u.mem_write(update, struct.pack("<8h", -32767, -16000, -32767, 500,
                                           30000, -16000, 30000, 500))
        self.call(0x72100, [0, 0, 4, update])
        if self.transforms != transforms or self.calls["set_uv"] != before:
            raise RuntimeError("existing UV array update changed original transform")
        strips_pointer = self.alloc(4)
        self.call(0x715d0, [strips_pointer, maximum_parts])
        return {"maximum_parts": maximum_parts, "scale_after_dummy_bits": scale_after_dummy,
                "position_scale_bits": transforms["set_positions"]["scale_bits"],
                "position_bias_bits": transforms["set_positions"]["bias_bits"],
                "uv_scale_bits": transforms["set_uv"]["scale_bits"],
                "uv_bias_bits": transforms["set_uv"]["bias_bits"],
                "frame_update_preserves_uv_transform": True, "strips": self.strips[-1],
                "calls": dict(self.calls)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--binary", type=Path, required=True)
    ap.add_argument("--libgcc", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--unicorn-dir", type=Path)
    args = ap.parse_args()
    if args.unicorn_dir:
        sys.path.insert(0, str(args.unicorn_dir))
    import unicorn
    image, gcc = args.binary.read_bytes(), args.libgcc.read_bytes()
    if digest(image) != IMAGE_SHA or digest(gcc) != LIBGCC_SHA:
        raise ValueError("original executable or libgcc hash differs from audited input")
    results = [OriginalRenderer(image, gcc).run_sprite_setup(n) for n in (1, 3, 4, 8, 9, 10, 11, 13, 14, 16)]
    for result in results:
        expected = (float_bits(1.0), float_bits(0.005), [0, 0, 0], float_bits(1/65536),
                    [float_bits(0.5), float_bits(0.5)])
        actual = tuple(result[k] for k in ("scale_after_dummy_bits", "position_scale_bits", "position_bias_bits",
                                           "uv_scale_bits", "uv_bias_bits"))
        if actual != expected or result["strips"] != {"start_index": 0, "lengths": [4]*result["maximum_parts"]}:
            raise RuntimeError(f"original setup differs from recovered constants: {result}")
    output = {"scope": "Original sprite mesh setup and existing UV-array update with synthetic M3G API boundaries",
              "original_sha256": IMAGE_SHA, "libgcc_sha256": LIBGCC_SHA,
              "libgcc_armv6_slice_sha256": digest(load_libgcc(gcc)[0]),
              "unicorn_version": unicorn.__version__, "oracle_source_sha256": digest(Path(__file__).read_bytes()),
              "original_code_readonly_and_unchanged": True, "instruction_patches": 0,
              "functions": ["0x70eb4", "0x71248", "0x71884", "0x72100", "0x715d0"],
              "math_helpers": "unchanged original ARMv6 libgcc instructions, import calls redirected to mapped exports",
              "substitutions": ["M3G object API recording / identity / ownership", "engine singleton",
                                "allocation/free", "unwind registration/unregistration", "triangle-strip factory boundary"],
              "results": results, "all_passed": True, "gpu_rendered": False, "device_tested": False,
              "not_established": ["M3G implementation/GPU pixel fidelity", "world camera", "animation time units"]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2)+"\n")
    print(json.dumps({"output": str(args.output), "cases": len(results), "all_passed": True}))


if __name__ == "__main__":
    main()
