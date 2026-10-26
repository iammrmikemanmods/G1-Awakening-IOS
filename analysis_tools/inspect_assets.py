#!/usr/bin/env python3
"""Inspect/extract the observed G1 Awakening FGIB resource archive.

Only the schema verified against the supplied iOS 1.1.3 archive is accepted.
This tool does not reconstruct gameplay or claim to compile an iOS app.
Uses Python's standard library. Original assets are only written with --extract.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import struct
import zipfile
import zlib

MAX_INPUT = 256 * 1024 * 1024
MAX_RESOURCE = 32 * 1024 * 1024
M3G_MAGIC = b"\xabJSR184\xbb\r\n\x1a\n"
M3G_TYPES = {0: "Header", 1: "AnimationController", 2: "AnimationTrack",
    3: "Appearance", 4: "Background", 5: "Camera", 6: "CompositingMode",
    7: "Fog", 8: "PolygonMode", 9: "Group", 10: "Image2D",
    11: "TriangleStripArray", 12: "Light", 13: "Material", 14: "Mesh",
    15: "MorphingMesh", 16: "SkinnedMesh", 17: "Texture2D", 18: "Sprite3D",
    19: "KeyframeSequence", 20: "VertexArray", 21: "VertexBuffer", 22: "World",
    255: "ExternalReference"}


class FormatError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise FormatError(message)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def checked_zlib(data, expected):
    require(0 <= expected <= MAX_RESOURCE, "inflated resource exceeds size bound")
    obj = zlib.decompressobj()
    out = obj.decompress(data, expected + 1)
    require(len(out) == expected, "zlib expanded length differs from declared size")
    require(obj.eof and not obj.unused_data and not obj.unconsumed_tail,
            "zlib stream is truncated, concatenated, or contains trailing bytes")
    return out


class Cursor:
    def __init__(self, data):
        self.data = data
        self.pos = 0

    def read(self, n):
        require(0 <= n <= len(self.data) - self.pos, "object read exceeds bounds")
        result = self.data[self.pos:self.pos+n]
        self.pos += n
        return result

    def unpack(self, fmt):
        return struct.unpack(fmt, self.read(struct.calcsize(fmt)))

    def u8(self): return self.unpack("<B")[0]
    def u16(self): return self.unpack("<H")[0]
    def u32(self): return self.unpack("<I")[0]
    def f32(self): return self.unpack("<f")[0]

    def string(self):
        end = self.data.find(b"\0", self.pos)
        require(end >= self.pos, "unterminated string")
        return self.read(end-self.pos+1)[:-1].decode("utf-8")

    def uint_array(self):
        count = self.u32()
        require(count <= (len(self.data)-self.pos)//4, "array exceeds object bounds")
        return list(self.unpack("<" + "I" * count))


def read_input(path):
    require(path.stat().st_size <= MAX_INPUT, "input exceeds size limit")
    data = path.read_bytes()
    origin = {"filename": path.name, "sha256": sha256(data), "size": len(data)}
    if data[:4] == b"FGIB":
        return data, origin
    require(zipfile.is_zipfile(path), "input is neither FGIB nor ZIP/IPA")
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        names = [i.filename for i in members]
        require(len(names) == len(set(names)), "ZIP contains duplicate member paths")
        for info in members:
            pp = PurePosixPath(info.filename)
            require(not pp.is_absolute() and ".." not in pp.parts and "\\" not in info.filename,
                    "ZIP contains unsafe member path")
            require(info.file_size <= MAX_INPUT, "ZIP member exceeds size limit")
        candidates = [i for i in members if re.fullmatch(r"Payload/[^/]+\.app/iphone\.big", i.filename)]
        require(len(candidates) == 1, "IPA must contain exactly one iphone.big")
        origin["zip_member"] = candidates[0].filename
        # ZipFile.read checks the original member CRC.
        return archive.read(candidates[0]), origin


def classify(data):
    if data.startswith(M3G_MAGIC): return "m3g"
    if data.startswith(b"\x89PNG\r\n\x1a\n"): return "png"
    if data.startswith(b"BM"): return "bmp"
    if data.startswith(b"OggS"): return "ogg"
    return "bin"


def parse_big(data):
    require(32 <= len(data) <= MAX_INPUT, "invalid FGIB length")
    magic, flags, group_offset, ngroups, member_offset, nfiles, body_offset, body_size = struct.unpack_from("<8I", data)
    require(data[:4] == b"FGIB" and flags == 0x00800001, "unsupported FGIB magic/version flags")
    require(group_offset == 32 and 0 < ngroups <= 65535 and 0 < nfiles <= 65535,
            "unsupported FGIB table header")
    require(group_offset + ngroups * 8 == member_offset, "group table length mismatch")
    require(member_offset + (nfiles+1) * 8 == body_offset, "member table length mismatch")
    require(body_offset + body_size == len(data), "body length mismatch")
    groups = []
    owners = [None] * nfiles
    prior_group_end = -1
    for n in range(ngroups):
        group_id, count, first = struct.unpack_from("<IHH", data, group_offset+n*8)
        require(group_id >= prior_group_end, "resource ID ranges overlap or are not ordered")
        require(group_id + count <= 0x100000000, "resource ID range overflows 32 bits")
        require(count > 0 and first+count <= nfiles, "group member range is invalid")
        for j in range(first, first+count):
            require(owners[j] is None, "overlapping group member ranges")
            owners[j] = (group_id, j-first)
        groups.append({"id": group_id, "first_member": first, "member_count": count})
        prior_group_end = group_id + count
    require(all(i is not None for i in owners), "members are not fully covered by groups")
    entries = [struct.unpack_from("<II", data, member_offset+i*8) for i in range(nfiles+1)]
    require(entries[0][1] == body_offset, "first member offset mismatch")
    require(entries[-1] == (0, len(data)), "invalid final sentinel")
    resources = []
    for index, ((key, start), (_, end)) in enumerate(zip(entries, entries[1:])):
        require(body_offset <= start < end <= len(data) and end-start >= 4, "invalid member span")
        mode = struct.unpack_from("<I", data, start)[0]
        if mode == 4:
            payload = data[start+4:end]
            compression = "raw"
        elif mode == 0x00800004:
            require(end-start >= 12, "compressed member header is truncated")
            raw_size, compressed_size = struct.unpack_from("<II", data, start+4)
            require(start+12+compressed_size == end, "compressed member length mismatch")
            payload = checked_zlib(data[start+12:end], raw_size)
            compression = "zlib"
        else:
            raise FormatError(f"unsupported flags 0x{mode:08x} at member {index}")
        require(len(payload) <= MAX_RESOURCE, "resource exceeds size bound")
        group_id, ordinal = owners[index]
        resources.append(({"index": index, "group_id": group_id, "group_ordinal": ordinal,
            "resource_id": group_id + ordinal,
            "key_hex": f"0x{key:08x}", "offset": start, "stored_size": end-start,
            "compression": compression, "size": len(payload), "sha256": sha256(payload),
            "kind": classify(payload)}, payload))
    return groups, resources


def object3d(cursor):
    user_id = cursor.u32()
    tracks = cursor.uint_array()
    params = cursor.u32()
    require(params <= len(cursor.data)//8, "user parameter count exceeds bounds")
    ids = set()
    for _ in range(params):
        pid = cursor.u32()
        require(pid not in ids, "duplicate user parameter")
        ids.add(pid)
        cursor.read(cursor.u32())
    return user_id, tracks


def inspect_m3g(data):
    require(data.startswith(M3G_MAGIC), "invalid M3G magic")
    offset = 12
    sections = []
    objects = []
    authoring = ""
    total_expanded = 0
    while offset < len(data):
        require(offset+13 <= len(data), "truncated M3G section")
        scheme, total, raw_size = struct.unpack_from("<BII", data, offset)
        require(total >= 13 and offset+total <= len(data), "M3G section length out of bounds")
        require(scheme in (0, 1), "unsupported M3G section compression")
        total_expanded += raw_size
        require(total_expanded <= MAX_INPUT, "M3G cumulative expansion exceeds bound")
        expected_adler = struct.unpack_from("<I", data, offset+total-4)[0]
        actual_adler = zlib.adler32(data[offset:offset+total-4]) & 0xffffffff
        require(actual_adler == expected_adler, "M3G section checksum mismatch")
        packed = data[offset+9:offset+total-4]
        raw = checked_zlib(packed, raw_size) if scheme else packed
        require(len(raw) == raw_size, "M3G section expanded size mismatch")
        pos = 0
        section_index = len(sections)
        section_object_count = 0
        while pos < len(raw):
            require(pos+5 <= len(raw), "truncated M3G object header")
            typ, length = struct.unpack_from("<BI", raw, pos)
            require(typ in M3G_TYPES and pos+5+length <= len(raw), "invalid M3G object")
            payload = raw[pos+5:pos+5+length]
            c = Cursor(payload)
            obj = {"index": len(objects)+1, "type": M3G_TYPES[typ], "size": length, "section": section_index}
            if typ == 0:
                require(not objects and not sections and scheme == 0, "M3G header position invalid")
                version = list(c.unpack("<BB"))
                external = c.u8()
                require(version == [1,0] and external in (0,1), "unsupported M3G header version/flag")
                declared_size, approx_size = c.unpack("<II")
                require(declared_size == len(data), "M3G header file size mismatch")
                authoring = c.string()
                require(c.pos == len(payload), "unexpected trailing M3G header data")
                obj.update(version=version, has_external_references=bool(external),
                           declared_file_size=declared_size, approximate_content_size=approx_size)
            elif typ == 255:
                obj["uri"] = c.string()
                require(c.pos == len(payload), "unexpected external reference trailing data")
            else:
                uid, tracks = object3d(c)
                require(all(0 <= t <= obj["index"] for t in tracks), "invalid M3G animation reference")
                obj.update(user_id=uid, animation_tracks=tracks)
                if typ == 2:
                    sequence, controller, prop = c.unpack("<III")
                    require(sequence <= obj["index"] and controller <= obj["index"], "forward animation reference")
                    obj.update(sequence_index=sequence, controller_index=controller, property_id=prop)
                    require(c.pos == len(payload), "animation track size mismatch")
                elif typ == 1:
                    speed, weight, begin, end, seq_time, world_time = c.unpack("<ffii fi".replace(" ", ""))
                    obj.update(speed=speed, weight=weight, active_interval=[begin, end],
                               reference_sequence_time=seq_time, reference_world_time=world_time)
                    require(c.pos == len(payload), "animation controller size mismatch")
                elif typ == 19:
                    interpolation, repeat, encoding = c.unpack("<BBB")
                    duration, first, last, components, count = c.unpack("<IIIII")
                    require(encoding in (0, 1, 2) and 0 < components <= 256 and count <= 1000000,
                            "unsupported keyframe layout")
                    if encoding:
                        c.read(components*8)
                    times = []
                    value_bytes = components * {0:4, 1:1, 2:2}[encoding]
                    for _ in range(count):
                        times.append(c.u32())
                        c.read(value_bytes)
                    require(c.pos == len(payload), "keyframe sequence size mismatch")
                    obj.update(interpolation=interpolation, repeat_mode=repeat, encoding=encoding,
                        duration=duration, valid_range=[first,last], components=components,
                        keyframe_count=count, first_time=min(times) if times else None,
                        last_time=max(times) if times else None)
                elif typ == 20:
                    size, components, encoding = c.unpack("<BBB")
                    vertices = c.u16()
                    require(size in (1, 2) and components in (2, 3, 4) and encoding in (0,1),
                            "invalid vertex array layout")
                    c.read(size*components*vertices)
                    require(c.pos == len(payload), "vertex array size mismatch")
                    obj.update(component_size=size, components=components, encoding=encoding, vertex_count=vertices)
            objects.append(obj)
            section_object_count += 1
            pos += 5+length
        sections.append({"offset": offset, "size": total, "compression": scheme,
                         "expanded_size": raw_size, "checksum_valid": True,
                         "object_count": section_object_count})
        offset += total
    require(len(sections) >= 2 and sum(s["object_count"] for s in sections[1:]) > 0
            and sections[0]["object_count"] == 1 and objects[0]["type"] == "Header",
            "incomplete M3G file")
    paths = [line for line in authoring.splitlines() if line.lower().endswith(".m3g")]
    names = {}
    table_match = re.search(r"<SwerveAuthor2NameTable>\s*(.*?)</SwerveAuthor2NameTable>", authoring, re.S)
    if table_match:
        for line in table_match.group(1).splitlines():
            parts = line.strip().split(" ",1)
            if len(parts) == 2 and parts[0].isdigit(): names[int(parts[0])] = parts[1]
    for obj in objects:
        if obj.get("user_id") in names: obj["name"] = names[obj["user_id"]]
    return {"source_path": paths[0] if paths else None,
            "authoring_tool": authoring.splitlines()[0] if authoring else None,
            "sections": sections, "object_counts": dict(Counter(o["type"] for o in objects)),
            "objects": objects, "name_table": names,
            "validation_scope": "section bounds/checksums; object framing; Object3D metadata; animation/controller/keyframe and vertex-array payload layouts. Mesh graph/rendering is not validated."}


def inspect_png(data):
    offset = 8
    ihdr = None
    saw_end = False
    while offset < len(data):
        require(offset+12 <= len(data), "truncated PNG chunk")
        n = struct.unpack_from(">I", data, offset)[0]
        require(offset+n+12 <= len(data), "PNG chunk length exceeds bounds")
        typ = data[offset+4:offset+8]
        actual = zlib.crc32(data[offset+4:offset+8+n]) & 0xffffffff
        expected = struct.unpack_from(">I", data, offset+8+n)[0]
        require(actual == expected, "PNG CRC mismatch")
        if typ == b"IHDR":
            require(offset == 8 and n == 13, "invalid PNG IHDR")
            w,h,depth,color,comp,filtering,interlace = struct.unpack_from(">IIBBBBB",data,offset+8)
            ihdr = {"width":w,"height":h,"bit_depth":depth,"color_type":color}
        if typ == b"IEND":
            require(n == 0 and offset+n+12 == len(data), "invalid PNG end")
            saw_end = True
        offset += n+12
    require(ihdr is not None and saw_end, "incomplete PNG")
    return {**ihdr, "chunk_crc_validation": "passed"}


def inspect_localization(data):
    require(len(data) >= 4, "localization header truncated")
    flags, count = struct.unpack_from("<HH", data)
    require(flags == 0x2000 and 0 < count <= 4096 and 4+count*4+4 <= len(data), "not observed string table schema")
    pairs = [struct.unpack_from("<HH", data, 4+i*4) for i in range(count)]
    require(struct.unpack_from("<I", data, 4+count*4)[0] == len(data), "string table sentinel mismatch")
    require(len(set(i for i,o in pairs)) == count, "duplicate string ID")
    out = []
    for index, (identifier, start) in enumerate(pairs):
        end = pairs[index+1][1] if index+1 < count else len(data)
        require(4+count*4+4 <= start < end <= len(data), "invalid string span")
        require(data[start:start+4] == b"\x04\0\0\0" and data[end-1] == 0, "invalid string entry wrapper")
        text = data[start+4:end-1].decode("utf-8")
        require("\0" not in text, "embedded NUL in localization entry")
        out.append({"id":identifier,"offset":start,"text":text})
    return out


def inspect(input_path, output, extract=False):
    data, origin = read_input(input_path)
    groups, resources = parse_big(data)
    output.mkdir(parents=True, exist_ok=True)
    manifest = {"input":origin,"archive":{"sha256":sha256(data),"size":len(data)},
        "groups":groups,"resources":[],"summary":{}}
    all_m3g = []
    localization = []
    for entry, payload in resources:
        kind = entry["kind"]
        stem = f"{entry['index']:04d}_g{entry['group_id']:04x}_{entry['group_ordinal']:03d}"
        if kind == "m3g":
            entry["m3g"] = inspect_m3g(payload)
            if entry["m3g"]["source_path"]:
                base = entry["m3g"]["source_path"].replace("\\", "/").rsplit("/",1)[-1][:-4]
                stem += "_" + re.sub(r"[^A-Za-z0-9_.-]", "_", base)
            all_m3g.append({"member_index":entry["index"],"sha256":entry["sha256"],**entry["m3g"]})
        elif kind == "png":
            entry["png"] = inspect_png(payload)
        elif kind == "bmp":
            require(len(payload)>=26, "BMP header too short")
            declared, dib = struct.unpack_from("<I",payload,2)[0],struct.unpack_from("<I",payload,14)[0]
            require(declared == len(payload), "BMP length mismatch")
            if dib >= 40:
                w,h,planes,bpp = struct.unpack_from("<iiHH",payload,18)
                entry["bmp"] = {"width":w,"height":h,"planes":planes,"bit_depth":bpp,"declared_length_valid":True}
        elif kind == "ogg":
            marker = payload.find(b"\x01vorbis")
            require(marker >= 0 and marker+30 <= len(payload), "Ogg does not contain a Vorbis identification header")
            channels, rate = payload[marker+11],struct.unpack_from("<I",payload,marker+12)[0]
            entry["ogg"] = {"codec":"vorbis","channels":channels,"sample_rate":rate,
                            "validation_scope":"identification header only; audio decoding not performed"}
        elif entry["group_id"] == 1 and entry["group_ordinal"] == 0:
            localization = inspect_localization(payload)
            entry["localization"] = {"string_count":len(localization),"encoding":"UTF-8","validated_spans":True}
        entry["extracted_filename"] = f"{stem}.{kind}"
        if extract:
            dest = output / "extracted" / kind
            dest.mkdir(parents=True, exist_ok=True)
            (dest / entry["extracted_filename"]).write_bytes(payload)
        # Detailed graph metadata lives separately to keep the primary index useful.
        if "m3g" in entry:
            entry["m3g"] = {k:v for k,v in entry["m3g"].items() if k not in ("objects","name_table","sections")}
        manifest["resources"].append(entry)
    counts = Counter(e["kind"] for e,p in resources)
    unique = Counter()
    seen = set()
    for e,p in resources:
        if e["sha256"] not in seen:
            unique[e["kind"]] += 1
            seen.add(e["sha256"])
    manifest["summary"] = {"groups":len(groups),"members":len(resources),"types":dict(counts),
        "unique_by_sha256":dict(unique),"compression":dict(Counter(e["compression"] for e,p in resources)),
        "total_expanded_resource_bytes":sum(len(p) for e,p in resources),
        "localization_strings":len(localization),
        "m3g_object_counts":dict(sum((Counter(m["object_counts"]) for m in all_m3g),Counter())),
        "original_assets_extracted":extract,
        "gameplay_logic_status":"Separate inspect_game_data.py analysis recovers exact framing for 30 mission command streams and classifies image properties, ARM code, and data candidates. Command semantics/native gameplay are not yet recovered; see game_data_inventory.json."}
    (output/"asset_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    (output/"m3g_inventory.json").write_text(json.dumps(all_m3g,indent=2)+"\n",encoding="utf-8")
    (output/"localization.json").write_text(json.dumps(localization,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return manifest["summary"]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input",type=Path,help="Original .ipa or iphone.big")
    ap.add_argument("--output",type=Path,required=True,help="New analysis output folder")
    ap.add_argument("--extract",action="store_true",help="Also extract original resource bytes for private port work")
    args = ap.parse_args()
    try:
        print(json.dumps(inspect(args.input,args.output,args.extract),indent=2))
    except (FormatError, ValueError, UnicodeDecodeError, struct.error, zlib.error, zipfile.BadZipFile) as exc:
        ap.exit(1,f"ERROR: {exc}\n")
