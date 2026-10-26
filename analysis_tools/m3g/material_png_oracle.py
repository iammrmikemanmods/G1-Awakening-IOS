#!/usr/bin/env python3
"""Execute the original full PNG decoder for the eleven model replacement PNGs.

Development-only: original 0x7ea68, its libpng/zlib code and ARMv6 libgcc run
unchanged. Image2D initialization is recorded at the public API boundary.
Allocator, libc and successful setjmp boundaries are explicit host substitutes.
No source image bytes or decoded pixels are written to the resulting report.
"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ("image", "libgcc", "manifest", "extracted", "unicorn-path", "output"):
        ap.add_argument("--" + name, type=Path, required=True)
    args = ap.parse_args()
    sys.path.insert(0, str(args.unicorn_path))
    import unicorn
    base_path = Path(__file__).resolve().parents[1] / "sprite" / "render_oracle.py"
    spec = importlib.util.spec_from_file_location("original_material_png_base", base_path)
    base = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(base)
    base.MATH.update({0xba3f0: "___udivsi3", 0xba3fc: "___umodsi3"})
    image, gcc = args.image.read_bytes(), args.libgcc.read_bytes()
    if digest(image) != base.IMAGE_SHA or digest(gcc) != base.LIBGCC_SHA:
        raise ValueError("original executable or libgcc input identity differs")

    class Original(base.OriginalRenderer):
        def __init__(self):
            super().__init__(image, gcc)
            self.engine = self.object({0x10: "image_factory"})
            self.image = self.object({0x4c: "image_raw", 0x50: "image_palette"})
            self.output, self.boundaries = None, Counter()

        def ret(self, value=0):
            self.u.reg_write(self.ar.UC_ARM_REG_R0, value & 0xffffffff)
            self.u.reg_write(self.ar.UC_ARM_REG_PC, self.u.reg_read(self.ar.UC_ARM_REG_LR))

        def bounded_bytes(self, address, count):
            if count > 0x100000:
                raise RuntimeError("original PNG boundary exceeds one MiB")
            return bytes(self.u.mem_read(address, count)) if count else b""

        def string(self, address, maximum=65536):
            if maximum > 65536:
                raise RuntimeError("unbounded original PNG string")
            out = bytearray()
            for i in range(maximum):
                value = self.u.mem_read(address+i, 1)[0]
                if value == 0:
                    return bytes(out)
                out.append(value)
            if maximum == 65536:
                raise RuntimeError("unterminated original PNG string")
            return bytes(out)

        def hook(self, u, address, size, user):
            if not (address in self.handlers or address in self.math or
                    0xba000 <= address < 0xbb000 or address in
                    (0x1f540, 0x1f512, 0x27350, 0x29f0c, 0x29e9c, 0x29ef6)):
                return
            ar = self.ar
            r0, r1, r2, r3 = [u.reg_read(getattr(ar, "UC_ARM_REG_R"+str(i))) for i in range(4)]
            sp = u.reg_read(ar.UC_ARM_REG_SP)
            if address == 0xbab1c:
                self.boundaries["setjmp_success_only"] += 1
                self.ret()
                return
            if address == 0x29f0c:
                self.boundaries["allocate"] += 1
                self.ret(self.alloc(r0))
                return
            if address == 0x29e9c:
                self.boundaries["free_at_oracle_end"] += 1
                self.ret()
                return
            if address == 0xbaa38:
                self.boundaries["memcmp"] += 1
                left, right = self.bounded_bytes(r0, r2), self.bounded_bytes(r1, r2)
                self.ret((left > right) - (left < right))
                return
            if address == 0xbaa5c:
                self.boundaries["memset"] += 1
                if r2 > 0x100000:
                    raise RuntimeError("unbounded original PNG memset")
                if r2:
                    u.mem_write(r0, bytes([r1 & 255])*r2)
                self.ret(r0)
                return
            if address in (0xbabac, 0xbab94, 0xbabb8):
                self.boundaries[{0xbabac: "strlen", 0xbab94: "strcmp", 0xbabb8: "strncmp"}[address]] += 1
                maximum = r2 if address == 0xbabb8 else 65536
                left = self.string(r0, maximum)
                if address == 0xbabac:
                    self.ret(len(left))
                else:
                    right = self.string(r1, maximum)
                    self.ret((left > right) - (left < right))
                return
            if address in (0x29ef6, 0xbaa44):
                self.boundaries["memcpy"] += 1
                data = self.bounded_bytes(r1, r2)
                if data:
                    u.mem_write(r0, data)
                self.ret(r0)
                return
            name = self.handlers.get(address)
            if name == "image_factory":
                self.boundaries[name] += 1
                if r0 != 10:
                    raise RuntimeError("unexpected original PNG factory interface")
                self.word(r1, self.image)
                self.ret()
                return
            if name in ("image_raw", "image_palette"):
                self.boundaries[name] += 1
                if self.output is not None:
                    raise RuntimeError("multiple original image initialization calls")
                count, pointer = self.read_word(sp), self.read_word(sp+4)
                data = self.bounded_bytes(pointer, count)
                if r1 != 99 or r2 == 0 or r3 == 0 or r2 > 1024 or r3 > 1024:
                    raise RuntimeError("replacement PNG did not initialize bounded RGB Image2D")
                output = dict(format=r1, width=r2, height=r3, data_size=count,
                              data_sha256=digest(data), palette=name == "image_palette")
                if name == "image_palette":
                    palette_size, palette_pointer = self.read_word(sp+8), self.read_word(sp+12)
                    palette = self.bounded_bytes(palette_pointer, palette_size)
                    if palette_size == 0 or palette_size > 768 or palette_size % 3 or count != r2*r3:
                        raise RuntimeError("unexpected original RGB palette shape")
                    if any(index >= palette_size//3 for index in data):
                        raise RuntimeError("original palette index exceeds captured palette")
                    rgb = b"".join(palette[index*3:index*3+3] for index in data)
                    output.update(palette_size=palette_size, palette_sha256=digest(palette))
                else:
                    if count != r2*r3*3:
                        raise RuntimeError("unexpected original raw RGB byte count")
                    rgb = data
                rgba = bytearray(r2*r3*4)
                rgba[0::4], rgba[1::4], rgba[2::4], rgba[3::4] = rgb[0::3], rgb[1::3], rgb[2::3], bytes([255])*(r2*r3)
                output.update(rgba_bytes=len(rgba), rgba_sha256=digest(rgba))
                self.output = output
                self.ret()
                return
            if 0xba000 <= address < 0xbb000 and address not in self.math and address not in (0xba1f8, 0xba210, 0xba204):
                raise RuntimeError("unhandled original PNG external boundary " + hex(address))
            super().hook(u, address, size, user)

        def run(self, data):
            pointer, output = self.alloc(len(data)), self.alloc(4)
            self.u.mem_write(pointer, data)
            initial_sp = 0x21ff000
            for i in range(13):
                self.u.reg_write(getattr(self.ar, "UC_ARM_REG_R"+str(i)), 0)
            self.u.reg_write(self.ar.UC_ARM_REG_CPSR, 0x30)
            self.u.reg_write(self.ar.UC_ARM_REG_SP, initial_sp)
            self.u.reg_write(self.ar.UC_ARM_REG_LR, 0x3000001)
            for i, value in enumerate((self.engine, len(data), pointer, output)):
                self.u.reg_write(getattr(self.ar, "UC_ARM_REG_R"+str(i)), value)
            self.u.emu_start(0x7ea69, 0x3000000, count=100_000_000, timeout=30_000_000)
            if self.u.reg_read(self.ar.UC_ARM_REG_PC) != 0x3000000 or self.u.reg_read(self.ar.UC_ARM_REG_SP) != initial_sp:
                raise RuntimeError("original full PNG decoder did not return within bound: "
                    f"PC={self.u.reg_read(self.ar.UC_ARM_REG_PC):#x}, SP={self.u.reg_read(self.ar.UC_ARM_REG_SP):#x}")
            if self.output is None or self.read_word(output) != self.image:
                raise RuntimeError("original full PNG decoder did not return captured image")
            if bytes(self.u.mem_read(0x1000, 0xd1000)) != self.original_text:
                raise RuntimeError("original main instructions changed")
            if bytes(self.u.mem_read(0x40000000, 0x9000)) != self.thin[:0x9000]:
                raise RuntimeError("original libgcc instructions changed")
            return {**self.output, "boundary_calls": dict(self.boundaries), "original_helper_calls": dict(self.calls)}

    manifest_data = args.manifest.read_bytes()
    manifest = json.loads(manifest_data)["resources"]
    table = struct.unpack_from("<48i", image, 0xceb14-0x1000)
    resources = sorted({value & 0xffffff for value in table if value >= 0})
    if len(resources) != 11:
        raise RuntimeError("unexpected original material image resource count")
    results = []
    for rid in resources:
        matches = [row for row in manifest if row["resource_id"] == rid and row["kind"] == "png"]
        if len(matches) != 1:
            raise ValueError("replacement PNG resource is missing or ambiguous")
        row = matches[0]
        data = (args.extracted / "png" / row["extracted_filename"]).read_bytes()
        if digest(data) != row["sha256"]:
            raise ValueError("replacement PNG differs from audited extraction")
        print(json.dumps(dict(decoding_resource=rid)), flush=True)
        result = Original().run(data)
        result.update(resource_id=rid, png_sha256=digest(data), png_bytes=len(data),
                      png_bit_depth=data[24], png_color_type=data[25])
        results.append(result)
    report = dict(scope="Complete unchanged original PNG decoder, recorded Image2D initialization; no GPU",
                  original_sha256=base.IMAGE_SHA, libgcc_sha256=base.LIBGCC_SHA,
                  asset_manifest_sha256=digest(manifest_data), oracle_source_sha256=digest(Path(__file__).read_bytes()),
                  base_source_sha256=digest(base_path.read_bytes()), unicorn_version=unicorn.__version__,
                  entry="0x7ea68", table="0xceb14", resource_count=len(results),
                  original_code_readonly_and_unchanged=True, instruction_patches=0,
                  math="unchanged original ARMv6 libgcc exports", all_returned_with_sp_restored=True,
                  substitutions=["bounded allocator/free lifetime", "bounded libc byte/string operations",
                                 "setjmp returns zero on successful nonthrowing path; errors are not supported",
                                 "Unwind registration/unregistration", "Image2D factory/initialization/ownership recording"],
                  not_established=["malformed PNG exception behavior", "GPU upload or pixels", "device rendering"],
                  results=results, all_passed=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(dict(output=str(args.output), images=len(results), all_format_99=all(x["format"] == 99 for x in results))))


if __name__ == "__main__":
    main()
