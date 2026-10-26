#!/usr/bin/env python3
"""Independent development reader for JSR184 object bodies and rigid assets.

Reads operator-supplied M3G data. It is not linked into the native product and
does not execute original ARM code. Body order follows the Nokia M3G1.1 file
format specification; source URLs and limits are in the module report.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import zlib


class Reader:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def read(self, size):
        if size < 0 or self.pos + size > len(self.data):
            raise ValueError("truncated M3G body")
        result = self.data[self.pos:self.pos + size]
        self.pos += size
        return result

    def unpack(self, fmt):
        return struct.unpack("<" + fmt, self.read(struct.calcsize("<" + fmt)))

    def u8(self): return self.unpack("B")[0]
    def u16(self): return self.unpack("H")[0]
    def u32(self): return self.unpack("I")[0]

    def boolean(self):
        value = self.u8()
        if value not in (0, 1): raise ValueError("nonboolean M3G flag")
        return bool(value)

    def floats(self, count):
        values = self.unpack("f" * count)
        if not all(math.isfinite(v) for v in values): raise ValueError("nonfinite M3G value")
        return list(values)

    def counted(self, fmt):
        count = self.u32()
        if count > len(self.data): raise ValueError("unbounded M3G array")
        return list(self.unpack(fmt * count))

    def done(self):
        if self.pos != len(self.data):
            raise ValueError(f"M3G body has {len(self.data) - self.pos} trailing bytes")


def base(c):
    result = {"user_id": c.u32(), "animation_tracks": c.counted("I")}
    params = c.u32()
    ids = set()
    for _ in range(params):
        uid = c.u32()
        if uid in ids: raise ValueError("duplicate parameter")
        ids.add(uid)
        c.read(c.u32())
    return result


def transform(c, result):
    if c.boolean():
        result.update(translation=c.floats(3), scale=c.floats(3), angle=c.floats(1)[0], axis=c.floats(3))
    else:
        result.update(translation=[0., 0., 0.], scale=[1., 1., 1.], angle=0., axis=[0., 0., 0.])
    result["matrix_row_major"] = c.floats(16) if c.boolean() else [float(i % 5 == 0) for i in range(16)]


def node(c, result):
    transform(c, result)
    result.update(render_enabled=c.boolean(), pick_enabled=c.boolean(), alpha=c.u8(), scope=c.u32())
    result["alignment"] = [c.u8(), c.u8(), c.u32(), c.u32()] if c.boolean() else None


def parse(data):
    if data[:12] != b"\xabJSR184\xbb\r\n\x1a\n": raise ValueError("M3G signature")
    objects, cursor, author = [None], 12, ""
    while cursor < len(data):
        scheme, length, raw_size = struct.unpack_from("<BII", data, cursor)
        if scheme not in (0, 1) or length < 13 or cursor + length > len(data): raise ValueError("section bounds")
        if zlib.adler32(data[cursor:cursor + length - 4]) != struct.unpack_from("<I", data, cursor + length - 4)[0]:
            raise ValueError("section checksum")
        packed = data[cursor + 9:cursor + length - 4]
        raw = zlib.decompress(packed) if scheme else packed
        if len(raw) != raw_size: raise ValueError("section size")
        section = Reader(raw)
        while section.pos < len(raw):
            typ, size = section.unpack("BI")
            c = Reader(section.read(size))
            if typ == 0:
                major, minor, external, file_size, approximate = c.unpack("BBBII")
                if (major, minor) != (1, 0) or file_size != len(data) or external:
                    raise ValueError("unsupported M3G file header")
                author = c.read(len(c.data) - c.pos).rstrip(b"\0").decode("utf-8")
                obj = {}
            elif typ == 255:
                raise ValueError("external M3G reference")
            else:
                obj = base(c)
                if typ in (5, 9, 12, 14, 15, 16, 18, 22): node(c, obj)
                elif typ == 17: transform(c, obj)
                if typ == 1:
                    obj["controller"] = list(c.unpack("ffii fi".replace(" ", "")))
                elif typ == 2:
                    obj["track"] = list(c.unpack("III"))
                elif typ == 3:
                    obj["layer"] = c.unpack("b")[0]
                    obj.update(compositing=c.u32(), fog=c.u32(), polygon=c.u32(), material=c.u32(), textures=c.counted("I"))
                elif typ == 4:
                    obj["background"] = list(c.unpack("4B I 2B 4i 2B".replace(" ", "")))
                elif typ == 5:
                    obj["projection_type"] = c.u8()
                    obj["projection"] = c.floats(16 if obj["projection_type"] == 48 else 4)
                elif typ == 6:
                    obj["compositing_values"] = [c.boolean() for _ in range(4)] + [c.u8(), c.u8()] + c.floats(2)
                elif typ == 7:
                    obj["fog_color"] = list(c.read(3)); obj["fog_mode"] = c.u8()
                    obj["fog_parameters"] = c.floats(1 if obj["fog_mode"] == 80 else 2)
                elif typ == 8:
                    obj["polygon_values"] = [c.u8() for _ in range(3)] + [c.boolean() for _ in range(3)]
                elif typ in (9, 22):
                    obj["children"] = c.counted("I")
                    if typ == 22: obj.update(active_camera=c.u32(), background=c.u32())
                elif typ == 10:
                    obj.update(format=c.u8(), mutable=c.boolean(), width=c.u32(), height=c.u32())
                    if not obj["mutable"]:
                        obj["palette"] = list(c.read(c.u32())); obj["pixels"] = list(c.read(c.u32()))
                elif typ == 11:
                    encoding = c.u8()
                    if encoding not in (0, 1, 2, 128, 129, 130): raise ValueError("strip encoding")
                    fmt = {0: "I", 1: "B", 2: "H"}[encoding & 127]
                    obj["encoding"] = encoding
                    obj["indices"] = c.counted(fmt) if encoding & 128 else [c.unpack(fmt)[0]]
                    obj["strip_lengths"] = c.counted("I")
                elif typ == 12:
                    obj["attenuation"] = c.floats(3); obj["light_color"] = list(c.read(3))
                    obj["light_mode"] = c.u8(); obj["light_parameters"] = c.floats(3)
                elif typ == 13:
                    obj["material_colors"] = list(c.read(13))
                    obj["shininess"] = c.floats(1)[0]; obj["color_tracking"] = c.boolean()
                elif typ in (14, 15, 16):
                    obj["vertex_buffer"] = c.u32()
                    obj["submeshes"] = [list(c.unpack("II")) for _ in range(c.u32())]
                    if typ != 14: raise ValueError("nonrigid mesh is outside this reference scope")
                elif typ == 17:
                    obj["image"] = c.u32(); obj["blend_color"] = list(c.read(3))
                    obj["texture_modes"] = list(c.read(5))
                elif typ == 18:
                    obj["sprite"] = list(c.unpack("II B iiii".replace(" ", "")))
                elif typ == 19:
                    obj["interpolation"], obj["repeat_mode"], obj["encoding"] = c.unpack("BBB")
                    duration, first, last, components, count = c.unpack("IIIII")
                    obj.update(duration=duration, first=first, last=last, components=components)
                    encoding = obj["encoding"]
                    if encoding not in (0, 1, 2): raise ValueError("keyframe encoding")
                    if encoding: obj.update(bias=c.floats(components), scale=c.floats(components))
                    fmt = {0: "f", 1: "B", 2: "H"}[encoding]
                    obj["keyframes"] = [[c.u32(), list(c.unpack(fmt * components))] for _ in range(count)]
                elif typ == 20:
                    width, components, encoding = c.unpack("BBB"); count = c.u16()
                    if width not in (1, 2) or components not in (2, 3, 4) or encoding not in (0, 1):
                        raise ValueError("vertex format")
                    values = c.unpack(({1: "B", 2: "H"}[width]) * components * count)
                    accum = [0] * components; decoded = []; modulus = 1 << (width * 8)
                    for i, value in enumerate(values):
                        component = i % components
                        accum[component] = ((accum[component] if encoding else 0) + value) % modulus
                        value = accum[component]
                        decoded.append(value if value < modulus // 2 else value - modulus)
                    obj.update(component_size=width, components=components, count=count, values=decoded)
                elif typ == 21:
                    obj["default_color"] = list(c.read(4)); obj["positions"] = c.u32()
                    obj["position_bias"] = c.floats(3); obj["position_scale"] = c.floats(1)[0]
                    obj.update(normals=c.u32(), colors=c.u32())
                    obj["texcoords"] = [{"array": c.u32(), "bias": c.floats(3), "scale": c.floats(1)[0]}
                                        for _ in range(c.u32())]
                else:
                    raise ValueError(f"unhandled object type {typ}")
            c.done()
            obj.update(index=len(objects), type=typ)
            objects.append(obj)
        cursor += length
    names = {}
    match = re.search(r"<SwerveAuthor2NameTable>\s*(.*?)</SwerveAuthor2NameTable>", author, re.S)
    if match:
        for line in match.group(1).splitlines():
            parts = line.strip().split(" ", 1)
            if len(parts) == 2 and parts[0].isdigit(): names[int(parts[0])] = parts[1]
    for obj in objects[1:]:
        if obj.get("user_id") in names: obj["name"] = names[obj["user_id"]]
    return objects


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    objects = parse(args.input.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(objects, indent=2) + "\n")
    selected = [{k: v for k, v in obj.items() if k not in ("values", "pixels", "palette", "keyframes")}
                for obj in objects[1:] if obj["type"] in (3, 6, 8, 10, 17, 21) or "name" in obj]
    print(json.dumps({"sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
                      "objects": len(objects) - 1, "selected": selected}, indent=2))


if __name__ == "__main__": main()
