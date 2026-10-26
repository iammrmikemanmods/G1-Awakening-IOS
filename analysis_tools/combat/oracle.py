#!/usr/bin/env python3
"""Development-only original ARM combat reference; never part of native product.

Executes original stat/HP/RNG/world-modifier/target/support/damage functions.
The battle setup and exchange are stopped at explicit pre-presentation edges.
No formula, random word, attack result or target decision is supplied by a hook.
Synthetic fixtures contain no original code or game-resource payloads.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import struct
import sys
import zlib

IMAGE_SHA = "0d510516fe3676ee4a0f4dff60ba64e1c5bf79a0c9800f420b1bbdb1c12febfd"
LIBGCC_SHA = "d758fbf1ac952532955d62866bd02df55315c0599f64bdd978ff941fccbdcf83"
ARCHIVE_SHA = "663d2888982093ce66b7811ccb7a6ad3acd37fc02ffa85144775b88c39e83cb4"
MATH = {0xba288: "___divsi3", 0xba36c: "___modsi3", 0xba384: "___muldi3"}
BOUNDARIES = {
    0x2b46c: "shared RNG service lookup returns the explicit seeded original RNG object",
    0xba1f8: "SjLj unwind registration for a bounded nonthrowing function prefix",
    0x5c9b2: "renderer removes a destroyed unit presentation; record only",
    0x60918: "UI string clear for destroyed unit; record only",
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def signed(value):
    return value if value < 0x80000000 else value - 0x100000000


def load_libgcc(data):
    magic, count = struct.unpack_from(">II", data)
    if magic != 0xcafebabe:
        raise ValueError("expected pinned original universal libgcc")
    slices = [struct.unpack_from(">5I", data, 8 + i*20) for i in range(count)]
    _, _, offset, size, _ = next(x for x in slices if x[0] == 12 and x[1] == 6)
    thin = data[offset:offset+size]
    count, = struct.unpack_from("<I", thin, 16)
    cursor, segments = 28, []
    for _ in range(count):
        command, length = struct.unpack_from("<II", thin, cursor)
        if command == 1:
            segments.append(struct.unpack_from("<4I", thin, cursor+24))
        elif command == 2:
            symbols, symbol_count, strings, _ = struct.unpack_from("<4I", thin, cursor+8)
        cursor += length
    exports = {}
    for i in range(symbol_count):
        name_offset, _, _, description, value = struct.unpack_from("<IBBHI", thin, symbols+i*12)
        start = strings+name_offset
        name = thin[start:thin.index(b"\0", start)].decode()
        if name in MATH.values():
            exports[name] = value | (1 if description & 8 else 0)
    if set(exports) != set(MATH.values()):
        raise ValueError("original ARMv6 libgcc exports missing")
    return thin, segments, exports


class OriginalCombat:
    def __init__(self, image, gcc):
        import unicorn as uc
        from unicorn import arm_const as ar
        self.uc, self.ar = uc, ar
        self.u = uc.Uc(uc.UC_ARCH_ARM, uc.UC_MODE_THUMB)
        self.u.mem_map(0x1000, 0xf0000)
        self.u.mem_write(0x1000, image)
        self.text = image[:0xd1000]
        self.u.mem_protect(0x1000, 0xd1000, uc.UC_PROT_READ | uc.UC_PROT_EXEC)
        self.u.mem_map(0x1000000, 0x400000)
        self.u.mem_map(0x2000000, 0x200000)
        self.u.mem_map(0x3000000, 0x1000)
        self.u.mem_map(0x40000000, 0x10000)
        self.thin, segments, exports = load_libgcc(gcc)
        for vm, _, offset, size in segments:
            self.u.mem_write(0x40000000+vm, self.thin[offset:offset+size])
        self.u.mem_protect(0x40000000, 0x9000, uc.UC_PROT_READ | uc.UC_PROT_EXEC)
        self.math = {pc: 0x40000000+exports[name] for pc, name in MATH.items()}
        self.u.reg_write(ar.UC_ARM_REG_C1_C0_2, 0x00f00000)
        self.u.reg_write(ar.UC_ARM_REG_FPEXC, 0x40000000)
        self.next = 0x1000000
        self.calls = Counter()
        self.draws = 0
        self.generated_words = []
        self.strikes = []
        self.support_calls = []
        self.battle_mode = False
        self.map = self.alloc(0x600)
        self.app = self.alloc(0x500)
        slot, singleton = self.alloc(4), self.alloc(0x60)
        self.w32(0xd2038, slot)
        self.w32(slot, singleton)
        self.w32(singleton+0x58, self.app)
        self.w32(self.app+0x3e4, self.map)
        self.rng = self.alloc(0x9d4)
        self.w32(self.rng+0xc, 0)
        self.w32(self.rng+0x10, 0x9908b0df)
        self.w32(self.app+0x3e8, self.rng)
        self.u.hook_add(uc.UC_HOOK_CODE, self.hook)

    def alloc(self, size):
        pointer = self.next
        self.next += (max(size, 8)+7) & ~7
        if self.next > 0x1400000:
            raise RuntimeError("synthetic heap bound exceeded")
        return pointer

    def w32(self, address, value):
        self.u.mem_write(address, struct.pack("<I", value & 0xffffffff))

    def w8(self, address, value):
        self.u.mem_write(address, bytes([value & 255]))

    def r32(self, address):
        return struct.unpack("<I", self.u.mem_read(address, 4))[0]

    def r8(self, address):
        return self.u.mem_read(address, 1)[0]

    def array(self, values, fmt="I"):
        pointer = self.alloc(len(values)*struct.calcsize(fmt))
        if values:
            self.u.mem_write(pointer, struct.pack("<"+fmt*len(values), *values))
        return pointer

    def vector(self, address, values, fmt="I"):
        pointer = self.array(values, fmt)
        self.w32(address, pointer)
        self.w32(address+4, len(values))
        return pointer

    def hook(self, instance, address, size, _):
        ar = self.ar
        if address in self.math:
            self.calls[MATH[address]] += 1
            instance.reg_write(ar.UC_ARM_REG_PC, self.math[address])
            return
        if address == 0x7b26:
            self.draws += 1
        elif address == 0x7c0a:
            self.generated_words.append(instance.reg_read(ar.UC_ARM_REG_R0))
        elif address == 0x43c9a and self.battle_mode:
            self.support_calls.append(instance.reg_read(ar.UC_ARM_REG_R0))
        elif address == 0x43bea and self.battle_mode:
            defender = instance.reg_read(ar.UC_ARM_REG_R1)
            self.strikes.append({"defender": defender, "before": self.r8(defender+0x5a),
                                 "immune": int(self.r8(defender+0x19) != 0),
                                 "draw_start": self.draws, "evaded": 0})
        elif address == 0x43c86 and self.battle_mode:
            self.strikes[-1]["evaded"] = 1
        elif address == 0x43c90 and self.battle_mode:
            record = self.strikes[-1]
            record.update(damage=signed(instance.reg_read(ar.UC_ARM_REG_R4)),
                          after=self.r8(record["defender"]+0x5a),
                          draws=self.draws-record["draw_start"])
        if address in BOUNDARIES:
            self.calls[hex(address)] += 1
            if address == 0x2b46c:
                instance.reg_write(ar.UC_ARM_REG_R0, self.rng)
            instance.reg_write(ar.UC_ARM_REG_PC, instance.reg_read(ar.UC_ARM_REG_LR))
        elif address == 0x1adc4:
            raise RuntimeError("unseeded original generator unexpectedly requested wall-clock seed")
        elif 0xba1e0 <= address < 0xbaaa0:
            raise RuntimeError(f"unimplemented original import {address:#x}")

    def call(self, entry, args, stop=None):
        ar = self.ar
        registers = [getattr(ar, "UC_ARM_REG_R"+str(i)) for i in range(13)]
        for register in registers:
            self.u.reg_write(register, 0)
        initial_sp, returned = 0x21ff000, 0x3000000
        self.u.reg_write(ar.UC_ARM_REG_CPSR, 0x30)
        self.u.reg_write(ar.UC_ARM_REG_SP, initial_sp)
        self.u.reg_write(ar.UC_ARM_REG_LR, returned | 1)
        for i, value in enumerate(args):
            if i < 4:
                self.u.reg_write(registers[i], value & 0xffffffff)
            else:
                self.w32(initial_sp+(i-4)*4, value)
        target = returned if stop is None else stop
        self.u.emu_start(entry | 1, target, count=2_000_000, timeout=3_000_000)
        pc = self.u.reg_read(ar.UC_ARM_REG_PC)
        if pc != target or (stop is None and self.u.reg_read(ar.UC_ARM_REG_SP) != initial_sp):
            raise RuntimeError(f"original {entry:#x} did not reach exact stop {target:#x}; pc={pc:#x}")
        return self.u.reg_read(ar.UC_ARM_REG_R0)

    def check_text(self):
        if bytes(self.u.mem_read(0x1000, 0xd1000)) != self.text:
            raise RuntimeError("original main code changed")
        if bytes(self.u.mem_read(0x40000000, 0x9000)) != self.thin[:0x9000]:
            raise RuntimeError("original ARMv6 libgcc changed")

    def seed(self, seed):
        self.call(0x7acc, [self.rng, seed])
        self.draws = 0

    def next_word(self):
        return self.call(0x7b26, [self.rng])

    def configure(self, case):
        self.w8(self.map+0x15, case["width"])
        self.w8(self.map+0x16, case["height"])
        self.vector(self.map+0x18, case["tiles"], "B")
        self.vector(self.map+0x20, case["lookup"], "B")
        rows = self.alloc(len(case["rules"])*8)
        for i, row in enumerate(case["rules"]):
            self.vector(rows+i*8, row, "B")
        rule_vector = self.alloc(8)
        self.w32(rule_vector, rows)
        self.w32(rule_vector+4, len(case["rules"]))
        self.w32(self.map+0x294, rule_vector)
        types, modifiers = self.alloc(23*8), [[0]*23, [0]*23]
        self.units, self.by_type = [], {}
        for unit in case["units"]:
            pointer = self.alloc(0x80)
            self.units.append(pointer)
            self.by_type[unit["type"]] = pointer
            for field, offset in (("type",9),("owner",10),("faction",11),("form",12),
                                  ("active",13),("immune",0x19),("flag38",0x38),
                                  ("x",0x3b),("y",0x3c),("health",0x5a)):
                self.w8(pointer+offset, unit[field])
            self.w32(pointer+0x5c, unit["support"])
            self.w32(pointer+0x30, unit["timer"])
            self.w32(pointer+0x34, unit["preset"])
            self.w32(pointer+0x24, 0x12345678)
            self.w32(pointer+0x28, 0xabcdef01)
            forms = self.alloc(16)
            for form, values in enumerate(unit["forms"]):
                self.vector(forms+form*8, values, "B")
            self.w32(types+unit["type"]*8, forms)
            self.w32(types+unit["type"]*8+4, 2)
            for i in range(2):
                modifiers[i][unit["type"]] = unit["modifiers"][i]
        self.w32(self.map+0x174, types)
        self.w32(self.map+0x178, 23)
        self.vector(self.map+0x15c, modifiers[0], "B")
        self.vector(self.map+0x164, modifiers[1], "B")
        owners = []
        for owner in range(2):
            addresses = [pointer for unit_type,pointer in sorted(self.by_type.items())
                         if self.r8(pointer+0xa) == owner]
            owners.append(self.array(addresses+[0]*(23-len(addresses))))
        self.w32(self.map+0x54, 23)
        self.w32(self.map+0x84, self.array(owners))
        self.vector(self.map+0x34, [-1, -1], "i")
        self.vector(self.map+0x7c,
                    [sum(u["active"] != 0 and u["owner"] == owner for u in case["units"])
                     for owner in range(2)], "B")
        self.vector(self.map+0x98, [0,1], "B")
        self.w8(self.map+0x227, case["flag227"])
        self.w32(self.map+0xf4, self.array([0]*23))
        self.w32(self.map+0x104, self.array([0]*23))
        self.w32(self.map+0x3c, self.array([0]*6))
        deaths = self.alloc(16)
        for i in range(2):
            self.vector(deaths+i*8, [0]*4, "i")
        self.w32(self.map+0x70, deaths)
        self.w32(self.map+0x74, 2)
        self.vector(self.map+0x1a4, [99]*23)
        self.w32(self.map+0x1ac, self.alloc(23*8))
        self.w32(self.map+0x298, self.alloc(8))
        for unit,pointer in zip(case["units"],self.units):
            self.call(0x4328a, [pointer,unit["level"]])

    def unit_result(self, pointer):
        return [*struct.unpack("<3h", self.u.mem_read(pointer+0x1c,6)),
                self.r8(pointer+0x5a), self.r8(pointer+0xd), signed(self.r32(pointer+0x5c)),
                signed(self.r32(pointer+0x30)), signed(self.r32(pointer+0x34))]

    def battle(self, case):
        self.configure(case)
        a,d = [self.units[case[key]] for key in ("attacker","defender")]
        eligibility = [self.call(0x52fdc,[self.map,a,d]),self.call(0x52fdc,[self.map,d,a])]
        bonuses = [signed(self.call(0x438c2,[a,d])),signed(self.call(0x4383a,[d,a])),
                   signed(self.call(0x438c2,[d,a])),signed(self.call(0x4383a,[a,d]))]
        self.seed(case["seed"])
        self.battle_mode = True
        self.call(0x585c4,[self.map,a,d],stop=0x586aa)
        counter = int(self.support_calls == [a,d])
        if self.support_calls not in ([a],[a,d]):
            raise RuntimeError("unexpected original support-call order")
        support_count = self.r32(self.map+0x44)
        if support_count > 6:
            raise RuntimeError("fixture exceeded original support storage")
        support = [self.r8(self.r32(self.r32(self.map+0x3c)+i*4)+9)
                   for i in range(support_count)]
        self.call(0x58172,[self.map],stop=0x582ec)
        self.battle_mode = False
        if len(self.strikes) not in (1,2):
            raise RuntimeError("unexpected original strike count")
        dead_count = self.r32(self.map+0x78)
        deaths = []
        for i in range(dead_count):
            pointer = self.r32(self.r32(self.map+0x70)+i*8)
            deaths.append(list(struct.unpack("<4i",self.u.mem_read(pointer,16))))
        result = {"eligibility":eligibility,"bonuses":bonuses,"counter_before":counter,
                  "support":support,"strikes":[{k:s[k] for k in
                      ("damage","before","after","immune","evaded","draws")}
                      for s in self.strikes],
                  "deaths":deaths,"units":[self.unit_result(p) for p in self.units],
                  "draws":self.draws,"rng_index":self.r32(self.rng+8),
                  "owner_active":[self.r8(self.r32(self.map+0x7c)+i) for i in range(2)],
                  "death_counters":[self.r32(self.map+0x278),self.r32(self.map+0x27c)],
                  "original_rng_state_sha256":sha(bytes(self.u.mem_read(self.rng+8,4))+
                                                      bytes(self.u.mem_read(self.rng+0x14,624*4)))}
        result["next_words"] = [self.next_word() for _ in range(8)]
        self.check_text()
        return result

    def direct_strike(self, case, words):
        self.configure(case)
        a,d=self.units
        for pointer,offset,value in ((a,0x1c,case["low"]),(a,0x1e,case["high"]),
                                      (d,0x20,case["defense"])):
            self.u.mem_write(pointer+offset,struct.pack("<h",value))
        self.u.mem_write(self.rng+0x14,struct.pack("<624I",*(words+[0]*(624-len(words)))))
        self.w32(self.rng+8,0)
        self.draws=0
        self.battle_mode=True
        self.call(0x43bea,[a,d])
        self.battle_mode=False
        self.check_text()
        strike=self.strikes[0]
        result=[strike[k] for k in ("damage","before","after","immune","evaded","draws")]
        result += [signed(self.r32(d+0x30)),signed(self.r32(d+0x34)),self.r32(self.rng+8)]
        return result


def synthetic_case(i):
    chooser = random.Random(0x47414300+i)
    forms = []
    for f in range(2):
        low = chooser.randrange(15,101)
        forms.append([3,1,1,low,low+chooser.randrange(0,20),chooser.randrange(0,81),
                      chooser.choice([0,1,2]),0,0,0,0,0,0,0])
    units = []
    count = 2+i%5
    for j in range(count):
        own_forms = [row.copy() for row in forms]
        for row in own_forms:
            row[3] = chooser.randrange(10,111)
            row[4] = row[3]+chooser.randrange(0,17)
            row[5] = chooser.randrange(0,111)
        if i%7 == 0:
            own_forms[0][4] = own_forms[0][3]
            own_forms[1][4] = own_forms[1][3]
        if i%11 == 0 and j == 1:
            own_forms[0][3] = own_forms[1][3] = 0
        if i%13 == 0 and j >= 2:
            own_forms[0][11] = own_forms[1][11] = 1
        if i%5 == 0:
            own_forms[0][2] = own_forms[1][2] = 3
        unit_type = j if not (j == 1 and i%3 == 0) else 10
        owner = 0 if j == 0 or j%2 == 0 else 1
        locations = [(3,3),(4,3),(4,2),(3,2),(4,4),(3,4)]
        x,y = locations[j]
        if j == 1 and i%5 == 0:
            x = 6
        units.append({"type":unit_type,"owner":owner,"faction":owner,"form":i%2,
                      "x":x,"y":y,"level":chooser.randrange(0,4),
                      "health":chooser.choice([1,5,9,10,24,25,49,50,74,75,100]),
                      "active":1 if j < 2 else int(i%9 != 0),
                      "immune":int((i%17 == 0 and j == 1) or (i%19 == 0 and j == 0)),
                      "flag38":int(i%23 == 0 and j == 1),
                      "support":-7-j,"timer":1234+j,"preset":4321+j,
                      "modifiers":[chooser.randrange(-20,21)&255,chooser.randrange(-20,21)&255],
                      "forms":own_forms})
    tiles = [0]*64
    for j,u in enumerate(units):
        tiles[u["y"]*8+u["x"]] = j%3
    return {"seed":(0x4d540001+i*0x10203)&0xffffffff,"flag227":int(i%29 == 0),
            "width":8,"height":8,"tiles":tiles,"lookup":[j%3 for j in range(32)],
            "rules":[[1,0,0],[1,15,0],[1,30,0]],"units":units,"attacker":0,"defender":1}


def unit_line(unit):
    fields = ("type","owner","faction","form","x","y","level","health",
              "active","immune","flag38","support","timer","preset")
    return [*[unit[k] for k in fields],*unit["modifiers"],*unit["forms"][0],*unit["forms"][1]]


def write_fixture(path, rng, stats, health, direct, battles):
    lines = ["G1_COMBAT_ORACLE_V1"]
    def row(kind, values):
        lines.append(kind+" "+" ".join(map(str,values)))
    for case in rng:
        row("R",[case["seed"],len(case["words"]),*case["words"],case["index"],*case["state"]])
    for case in stats:
        row("S",case["input"]+case["output"])
    for case in health:
        row("H",case["input"]+case["output"])
    for case in direct:
        row("X",case["input"]+case["output"])
    for case,result in battles:
        row("B",[case["seed"],case["flag227"],case["width"],case["height"],len(case["units"]),
                  case["attacker"],case["defender"]])
        row("G",case["tiles"])
        row("L",case["lookup"])
        row("T",[len(case["rules"]),*[v for r in case["rules"] for v in r]])
        for unit in case["units"]:
            row("U",unit_line(unit))
        row("E",[*result["eligibility"],*result["bonuses"],result["counter_before"],
                  result["draws"],result["rng_index"],len(result["support"]),*result["support"],
                  len(result["strikes"]),len(result["deaths"])])
        for strike in result["strikes"]:
            row("A",[strike[k] for k in ("damage","before","after","immune","evaded","draws")])
        for death in result["deaths"]:
            row("D",death)
        for unit in result["units"]:
            row("V",unit)
        row("N",result["next_words"])
    lines.append("END")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text("\n".join(lines)+"\n")


def resource(archive,wanted):
    """Independent bounded extraction for the exact hash-pinned local source."""
    group_start,group_count,member_start,member_count=struct.unpack_from("<4I",archive,8)
    found=[]
    for group in range(group_count):
        base,count,first=struct.unpack_from("<IHH",archive,group_start+group*8)
        if not base<=wanted<base+count:
            continue
        index=first+wanted-base
        if index>=member_count:
            raise ValueError("source resource member outside table")
        key,begin=struct.unpack_from("<II",archive,member_start+index*8)
        end=struct.unpack_from("<I",archive,member_start+(index+1)*8+4)[0]
        if key==0xf4e02223:
            found.append((begin,end))
    if len(found)!=1:
        raise ValueError("source resource absent/ambiguous")
    begin,end=found[0]
    if not 0<=begin<end<=len(archive):
        raise ValueError("source resource span invalid")
    flags,=struct.unpack_from("<I",archive,begin)
    if flags==4:
        return archive[begin+4:end]
    if flags!=0x800004:
        raise ValueError("source resource flags unsupported")
    expanded,stored=struct.unpack_from("<II",archive,begin+4)
    if expanded>16*1024*1024 or stored!=end-begin-12:
        raise ValueError("source resource compressed lengths invalid")
    decoder=zlib.decompressobj()
    raw=decoder.decompress(archive[begin+12:end],expanded+1)
    if len(raw)!=expanded or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise ValueError("source resource decompression span mismatch")
    return raw


def source_cases(image,archive):
    tags=struct.unpack_from("<23I",image,0xcecc0-0x1000)
    definitions=[]
    provenance=[]
    for unit_type,tag in enumerate(tags):
        if tag>>24!=3:
            raise ValueError("original unit definition tag changed")
        raw=resource(archive,tag&0xffffff)
        cursor=5+raw[4]*2
        scalar=list(raw[cursor:cursor+5]);cursor+=5
        cursor+=1+raw[cursor]
        count=raw[cursor];cursor+=1
        forms=[]
        for _ in range(count):
            length=raw[cursor];cursor+=1
            forms.append(list(raw[cursor:cursor+length]));cursor+=length
        if cursor!=len(raw) or len(scalar)!=5 or len(forms)!=2 or any(len(f)!=14 for f in forms):
            raise ValueError("source definition framing differs from original reader")
        definitions.append((scalar,forms))
        provenance.append({"type":unit_type,"resource_id":tag&0xffffff,"sha256":sha(raw)})
    grid=resource(archive,268)
    width,height=grid[:2]
    if len(grid)!=2+width*height:
        raise ValueError("source first grid framing differs")
    raw_rules=resource(archive,306)
    rows=[];cursor=1
    for _ in range(raw_rules[0]):
        n=raw_rules[cursor];cursor+=1
        rows.append(list(raw_rules[cursor:cursor+n]));cursor+=n
    if cursor!=len(raw_rules) or any(len(row)!=3 for row in rows):
        raise ValueError("source terrain rule framing differs")
    lookup=[0]*32
    for i in (1,2,3,4,5,26,27):lookup[i]=1
    for i in (6,12,13):lookup[i]=3
    cases=[]
    for i in range(92):
        case=synthetic_case(1)
        case.update(seed=0x47616d65+i,flag227=0,width=width,height=height,tiles=list(grid[2:]),
                    lookup=lookup,rules=rows)
        case["units"]=case["units"][:2]
        attacker=i//4
        types=[attacker,19 if attacker==11 else 11]
        for j,(u,t) in enumerate(zip(case["units"],types)):
            scalar,forms=definitions[t]
            u.update(type=t,owner=j,faction=scalar[0],form=(i//2)%2 if j==0 else 0,
                     x=1+j,y=2,level=(i%2)*3 if j==0 else 1,health=100 if i%2==0 else 49,
                     active=1,immune=0,flag38=0,support=0,timer=-1,preset=-1,
                     modifiers=scalar[3:5],forms=forms)
        cases.append(case)
    return cases,{"archive_sha256":sha(archive),"definition_table_va":"0xcecc0",
                  "definition_resources":provenance,"grid_resource_id":268,"grid_sha256":sha(grid),
                  "terrain_resource_id":306,"terrain_sha256":sha(raw_rules),
                  "placement_scope":"synthetic adjacent placement and two levels using actual source definitions, first grid/style0/rules",
                  "phase_scope":"flag227=0; not a full live battle or mission playthrough"}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--binary",type=Path,required=True)
    ap.add_argument("--libgcc",type=Path,required=True)
    ap.add_argument("--unicorn-dir",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--fixture",type=Path,required=True)
    ap.add_argument("--battle-count",type=int,default=192)
    ap.add_argument("--archive",type=Path)
    ap.add_argument("--source-fixture",type=Path)
    args=ap.parse_args()
    if bool(args.archive)!=bool(args.source_fixture):
        ap.error("--archive and --source-fixture must be supplied together")
    if not 1 <= args.battle_count <= 512:
        ap.error("battle count must be1..512")
    sys.path.insert(0,str(args.unicorn_dir))
    import unicorn
    image,gcc=args.binary.read_bytes(),args.libgcc.read_bytes()
    if sha(image)!=IMAGE_SHA or sha(gcc)!=LIBGCC_SHA:
        raise ValueError("original binary/libgcc differs from audited input")
    total_calls=Counter()
    rng=[]
    for seed in (0,1,5489,0x7fffffff,0x80000000,0xffffffff):
        o=OriginalCombat(image,gcc)
        o.seed(seed)
        words=[o.next_word() for _ in range(1250)]
        rng.append({"seed":seed,"words":words,"index":o.r32(o.rng+8),
                    "state":list(struct.unpack("<624I",o.u.mem_read(o.rng+0x14,624*4)))})
        o.check_text()
        total_calls.update(o.calls)
    stats=[]
    for low,high,defense in ((-128,-127,-6),(-5,-1,0),(0,1,4),(5,9,10),(50,75,95),(126,127,100)):
        for level in (0,1,2,5,31,255):
            case=synthetic_case(1)
            case["units"]=case["units"][:2]
            case["units"][0]["form"]=0
            case["units"][0]["level"]=level
            case["units"][0]["forms"][0][3:6]=[v&255 for v in (low,high,defense)]
            o=OriginalCombat(image,gcc)
            o.configure(case)
            stats.append({"input":[low,high,defense,level],"output":o.unit_result(o.units[0])[:3]})
            o.check_text()
            total_calls.update(o.calls)
    health=[]
    for mode in (0,1):
        for value in (-2147483648,-1,0,1,9,10,24,25,49,50,74,75,100,255,256,2147483647):
            for immune in (0,1):
                o=OriginalCombat(image,gcc)
                pointer=o.alloc(0x80)
                o.w8(pointer+0x5a,74)
                o.w8(pointer+0x19,immune)
                o.w32(pointer+0x30,123)
                o.w32(pointer+0x34,456)
                o.call(0x43184 if mode==0 else 0x43198,[pointer,value])
                health.append({"input":[74,immune,123,456,mode,value],
                               "output":[o.r8(pointer+0x5a),signed(o.r32(pointer+0x30)),
                                         signed(o.r32(pointer+0x34))]})
                o.check_text()
    direct=[]
    # Untempering is input construction only: outputs still come from original
    # generator instructions. These states make rare INT_MIN/sign cases exact.
    def untemper(value):
        y=value^(value>>18)
        y=y^((y<<15)&0xefc60000)
        z=y
        for _ in range(5):z=y^((z<<7)&0x9d2c5680)
        y=z
        for _ in range(3):z=y^(z>>11)
        return z&0xffffffff
    patterns=[[-32768,-32767,-2147483648,255,32767],
              [32767,32766,2147483647,255,-32768],
              [50,75,0,100,30],[50,50,0,0,127]]
    for i in range(16):
        low,high,support,hp,defense=patterns[i%4]
        case=synthetic_case(1);case["units"]=case["units"][:2]
        case.update(low=low,high=high,defense=defense,tiles=[0]*64,
                    lookup=[0]*32,rules=[[1,0,0]])
        for u in case["units"]:u.update(modifiers=[0,0],form=0,immune=0)
        case["units"][0].update(support=support,health=hp)
        case["units"][1].update(type=10 if i//4%2==0 else 19,health=100,immune=i//8)
        target=[0x80000000,0xffffffff,0x7fffffff,0][i//4]
        words=[untemper(target),untemper(0x80000000),untemper(0xffffffff),0]
        o=OriginalCombat(image,gcc)
        result=o.direct_strike(case,words)
        if o.generated_words and o.generated_words[0] != target:
            raise RuntimeError("original generator did not produce the intended signed edge input")
        total_calls.update(o.calls)
        direct.append({"input":[low,high,support,hp,defense,case["units"][1]["type"],100,
                                case["units"][1]["immune"],case["units"][1]["timer"],
                                case["units"][1]["preset"],*words],"output":result,
                       "original_generated_words":o.generated_words})
    battles=[]
    for i in range(args.battle_count):
        case=synthetic_case(i)
        o=OriginalCombat(image,gcc)
        result=o.battle(case)
        total_calls.update(o.calls)
        battles.append((case,result))
    write_fixture(args.fixture,rng,stats,health,direct,battles)
    report={"scope":"Unchanged original stat/HP/RNG/modifier/support/attack/counter/death prefix execution",
            "binary_sha256":IMAGE_SHA,"libgcc_sha256":LIBGCC_SHA,
            "libgcc_armv6_slice_sha256":sha(load_libgcc(gcc)[0]),
            "oracle_source_sha256":sha(Path(__file__).read_bytes()),
            "fixture_sha256":sha(args.fixture.read_bytes()),"fixture_original_assets":False,
            "unicorn_version":unicorn.__version__,"code_readonly_unchanged":True,
            "instruction_patches":0,"rng_formula_hooks":0,"damage_formula_hooks":0,
            "math_imports":MATH,"boundaries":BOUNDARIES,"boundary_calls":dict(total_calls),
            "rng_seeds":len(rng),"rng_words":sum(len(r["words"]) for r in rng),
            "rng_full_states":len(rng),"stat_cases":len(stats),"health_cases":len(health),
            "direct_strike_edge_cases":len(direct),
            "direct_strike_edge_results":direct,
            "battle_cases":len(battles),"battle_results":[r for _,r in battles],
            "battle_setup_stop":"0x585c4 entry to0x586aa before support presentation branch",
            "battle_resolution_stop":"0x58172 entry to0x582ec after HP/death, before cinematic ordering",
            "seeded_death_selection":"owner turn-selection indices=-1; selected-unit cycling branch is outside scope",
            "device_tested":False,"playable_complete_game":False,
            "native_comparison":"fixture is generated from original execution; native test runs separately"}
    if args.archive:
        archive=args.archive.read_bytes()
        if sha(archive)!=ARCHIVE_SHA:
            raise ValueError("source archive differs from audited input")
        cases,provenance=source_cases(image,archive)
        source_battles=[]
        for case in cases:
            o=OriginalCombat(image,gcc)
            result=o.battle(case)
            total_calls.update(o.calls)
            source_battles.append((case,result))
        write_fixture(args.source_fixture,rng,stats,health,direct,source_battles)
        report["source_data"]={**provenance,"cases":len(source_battles),
                               "fixture_sha256":sha(args.source_fixture.read_bytes()),
                               "fixture_must_not_be_committed":True,
                               "results":[r for _,r in source_battles]}
        report["boundary_calls"]=dict(total_calls)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:report[k] for k in ("rng_seeds","rng_words","stat_cases","health_cases","battle_cases",
                                          "fixture_sha256","code_readonly_unchanged")},indent=2))


if __name__=="__main__":
    main()
