#!/usr/bin/env python3
"""Recover empirically validated game-data framing without inventing runtime semantics.

Reads original IPA or FGIB through inspect_assets.py. Output is research metadata,
not runnable gameplay. The command schema was derived from 30 resource streams;
its byte consumption/counts are validated. Opcode 7 was subsequently corrected
from the original parser at 0x48698..0x487ac: its third site word is a group
count, and each group contains an independently counted list of pairs. This
tool does not execute the recovered command semantics.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import struct

from inspect_assets import FormatError, parse_big, read_input, require, sha256

FIXED_ARGUMENT_COUNTS = {0:0,1:0,2:0,3:2,4:3,5:1,6:5,8:1,9:2,10:1,
                         13:0,14:0,16:1,18:2,19:2,20:2}
HYPOTHESES = {3:"dialogue: first field resembles speaker/unit, second text index",
              4:"camera focus: two coordinates and a mode",
              5:"delay: observed values include 200, 500, 1000",
              6:"place unit: unit/index sentinel, x, y, two flags",
              7:"site coordinates with independently counted groups of coordinate pairs",
              9:"load map/grid and terrain/style",
              10:"mission completion/transition parameter",
              12:"mission objective or blocking condition",
              15:"available unit roster",
              16:"mission title text index"}


def decode_mission(data):
    require(len(data)>=2 and data[0]==1 and (len(data)-2)%2==0, "mission framing header invalid")
    count=data[1]
    words=list(struct.unpack(">"+"H"*((len(data)-2)//2),data[2:]))
    pos=0
    commands=[]

    def take(n):
        nonlocal pos
        require(0<=n<=len(words)-pos, "mission argument exceeds resource bounds")
        result=words[pos:pos+n]
        pos+=n
        return result

    for index in range(count):
        start=pos
        opcode=take(1)[0]
        args=[]
        if opcode in FIXED_ARGUMENT_COUNTS:
            args=take(FIXED_ARGUMENT_COUNTS[opcode])
        elif opcode in (15,17,21):
            n=take(1)[0]
            args=[n]+take(n*{15:1,17:3,21:4}[opcode])
        elif opcode==12:
            subtype=take(1)[0]
            sizes={0:4,1:6,2:3,3:5}
            require(subtype in sizes, "unknown objective-layout subtype")
            args=[subtype]+take(sizes[subtype]-1)
        elif opcode==7:
            n=take(1)[0]
            args=[n]
            require(n<=(len(words)-pos)//3, "site list exceeds resource bounds")
            for _ in range(n):
                triple=take(3)
                args+=triple
                groups=triple[2]
                require(groups<=len(words)-pos, "site groups exceed resource bounds")
                for _ in range(groups):
                    extra=take(1)[0]
                    args.append(extra)
                    require(extra<=(len(words)-pos)//2, "site pairs exceed resource bounds")
                    args+=take(extra*2)
        else:
            raise FormatError(f"unknown mission opcode {opcode} at word {start}")
        commands.append({"instruction_index":index,"byte_offset":2+2*start,
                         "opcode":opcode,"argument_words_u16":args})
    require(pos==len(words), "mission command count did not consume the whole stream")
    return {"version":1,"declared_instruction_count":count,"commands":commands,
            "exact_framing_validated":True,
            "semantic_status":"framing only; bounded native bootstrap evidence is documented separately in WORLD_BOOTSTRAP.md"}


def inspect(path, output):
    raw, origin=read_input(path)
    groups, resources=parse_big(raw)
    by_id={e["resource_id"]:(e,d) for e,d in resources}
    result={"input":origin,"archive_sha256":sha256(raw),"roles":[],"mission_streams":[],"grids":[],
            "mission_opcode_meaning_hypotheses":{str(k):v for k,v in HYPOTHESES.items()},
            "evidence_limits":["This tool validates mission framing, including the opcode7 group loop recovered from original 0x48698..0x487ac; it does not execute dispatch behavior.",
                               "Grid byte layouts are exact; tile meaning, orientation and mission-to-grid mapping are not proven.",
                               "ARM resources contain executable instructions; shader role is supported by texture/color operations but loader tracing remains necessary.",
                               "No known script VM signature is present at the start of any resource. Custom mission command streams are present."]}
    for e,d in resources:
        if e["kind"]!="bin": continue
        role="unclassified_binary"
        note={"member_index":e["index"],"resource_id":e["resource_id"],"sha256":e["sha256"],"size":len(d)}
        if e["resource_id"]==1:
            role="localization_table"
        elif e["key_hex"]=="0xe179f4be":
            pairs=list(struct.iter_unpack("<II",d))
            require(len(pairs) in (3,4) and pairs[0]==(6,0xffffffff), "image property layout differs")
            require(pairs[-1][0]==14 and pairs[-1][1]>>24==2, "image reference field differs")
            target=pairs[-1][1]&0xffffff
            require(target in by_id and by_id[target][0]["kind"] in ("png","bmp"), "image property references missing/non-image resource")
            require(all(op in (6,9,14,16) for op,value in pairs), "unknown image property opcode")
            role="image_property_commands"
            note.update(words=[{"opcode":op,"value":value} for op,value in pairs],
                        target_resource_id=target,target_member_index=by_id[target][0]["index"],
                        validation="all 161 targets resolve exactly to PNG/BMP resources")
        elif len(d)==2960 and d[4:8]==bytes.fromhex("f05f2de9"):
            count=struct.unpack_from("<I",d)[0]
            require(0<count<179 and all(x==0 for x in d[4+count*4:0x2d0]), "embedded ARM instruction count/padding differs")
            code=d[4:4+count*4]
            require(bytes.fromhex("1eff2fe1") in code, "ARM return instruction absent")
            role="arm32_shader_candidate"
            note.update(instruction_count=count,code_offset=4,code_bytes=len(code),
                        code_sha256=sha256(code),padding_end=0x2d0,
                        validation="Instruction count/padding and ARM entry/return match the observed schema. Original sample routines were independently inspected with Capstone; texture sampling and color blending were observed there.")
        elif 310<=e["resource_id"]<=339:
            role="mission_command_stream"
            mission={**note,**decode_mission(d)}
            result["mission_streams"].append(mission)
            note.update(instruction_count=mission["declared_instruction_count"])
        elif 258<=e["resource_id"]<=279:
            require(len(d)>=2 and d[0]*d[1]+2==len(d), "grid byte layout differs")
            role="tile_grid_candidate"
            w,h=d[:2]
            result["grids"].append({**note,"width":w,"height":h,
                "rows":[list(d[2+y*w:2+(y+1)*w]) for y in range(h)],
                "semantic_status":"row-major view is provisional; tile semantics and actual world coordinates unverified"})
            note.update(width=w,height=h)
        elif 283<=e["resource_id"]<=305:
            require(len(d) in (54,56), "unit definition candidate length differs")
            role="unit_definition_candidate"
            note.update(validation="23 adjacent compact records; semantics still unknown")
        else:
            magic={b"\x1bLua":"Lua",b"\x7fELF":"ELF",b"\xca\xfe\xba\xbe":"Java class/fat MachO",
                   b"dex\n":"DEX",b"\0asm":"WebAssembly",b"BSJB":".NET metadata"}
            note["known_vm_magic"]=next((v for k,v in magic.items() if d.startswith(k)),None)
        note["role"]=role
        result["roles"].append(note)
    result["summary"]={"binary_roles":dict(Counter(e["role"] for e in result["roles"])),
        "mission_stream_count":len(result["mission_streams"]),
        "mission_instruction_count":sum(x["declared_instruction_count"] for x in result["mission_streams"]),
        "all_mission_counts_and_lengths_match":True,
        "opcode_counts":dict(Counter(c["opcode"] for m in result["mission_streams"] for c in m["commands"]))}
    output.mkdir(parents=True,exist_ok=True)
    (output/"game_data_inventory.json").write_text(json.dumps(result,indent=2)+"\n")
    return result["summary"]


if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input",type=Path)
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    try: print(json.dumps(inspect(args.input,args.output),indent=2))
    except (ValueError,struct.error) as exc: ap.exit(1,f"ERROR: {exc}\n")
