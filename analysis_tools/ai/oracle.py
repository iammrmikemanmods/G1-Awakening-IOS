#!/usr/bin/env python3
"""Development-only opponent-planner oracle using unchanged original functions.

No guest execution enters the native product. Allocator, byte-memory library and
nonthrowing SjLj registration boundaries are explicit infrastructure only.
"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("combat_reference", ROOT / "analysis_tools/combat/oracle.py")
combat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(combat)

INFRASTRUCTURE = {
    0xbaa14: "malloc: bounded disjoint synthetic storage",
    0xba5dc: "free: bounded allocation retained for this single reference call",
    0xbaa5c: "memset: exact byte fill",
    0xbaa50: "memcpy: exact nonoverlapping byte copy",
    0xba210: "SjLj unregister: nonthrowing function completion",
}


class OriginalAI(combat.OriginalCombat):
    def hook(self, instance, address, size, data):
        ar = self.ar
        if address in INFRASTRUCTURE:
            self.calls[hex(address)] += 1
            r0, r1, r2 = [instance.reg_read(getattr(ar, "UC_ARM_REG_R"+str(i))) for i in range(3)]
            if address == 0xbaa14:
                instance.reg_write(ar.UC_ARM_REG_R0, self.alloc(r0))
            elif address == 0xbaa5c:
                if r2 > 0x100000:
                    raise RuntimeError("original memset size exceeds oracle bound")
                if r2:
                    instance.mem_write(r0, bytes([r1 & 255])*r2)
            elif address == 0xbaa50:
                if r2 > 0x100000 or (r2 and max(r0, r1) < min(r0+r2, r1+r2)):
                    raise RuntimeError("original memcpy exceeds bound or overlaps")
                if r2:
                    instance.mem_write(r0, bytes(instance.mem_read(r1, r2)))
            instance.reg_write(ar.UC_ARM_REG_PC, instance.reg_read(ar.UC_ARM_REG_LR))
            return
        super().hook(instance, address, size, data)

    def int_vectors(self, records):
        pointer = self.alloc(len(records)*8)
        for i, record in enumerate(records):
            self.vector(pointer+i*8, record, "i")
        return pointer

    def configure_ai(self, case):
        self.configure(case)
        self.w8(self.map+0xa8, case["current"])
        self.vector(self.map+0x98, case["controllers"], "b")
        self.vector(self.map+0xa0, case["factions"], "b")
        self.grid_columns = []
        grid = self.alloc(case["width"]*8)
        for x in range(case["width"]):
            self.grid_columns.append(self.vector(grid+x*8, [-1]*case["height"], "i"))
        self.w32(self.map+0xb4, grid)
        self.w32(self.map+0xb8, case["width"])
        points = [[x,y,0,s] for x,y,s in case.get("points", [])]
        regions = case.get("regions", [])
        self.w32(self.map+0x420, self.int_vectors(points))
        self.w32(self.map+0x424, len(points))
        self.w32(self.map+0xc, self.int_vectors(regions))
        self.w32(self.map+0x10, len(regions))
        for unit, pointer in zip(case["units"], self.units):
            self.w8(pointer+0x59, unit.get("spent", 0))
            self.w8(pointer+0x2c, unit.get("acted", 0))
            self.w32(pointer+0x40, unit.get("offset_x", 0))
            self.w32(pointer+0x44, unit.get("offset_y", 0))
        transform=[0]*23
        upgrade=[0]*23
        by_type=[0]*23
        for unit,pointer in zip(case["units"],self.units):
            transform[unit["type"]]=unit.get("transform_capability",0)
            upgrade[unit["type"]]=unit.get("upgrade_cost",0)
            by_type[unit["type"]]=pointer
        # Original unit loader 0x5a8ce..0x5a8e0 overrides map+0x14c[21]
        # with 40, independently of the raw resource scalar byte.
        upgrade[21]=40
        self.vector(self.map+0x154,transform,"B")
        self.vector(self.map+0x14c,upgrade,"B")
        self.w32(self.map+0x90,self.array(by_type))
        self.vector(self.map+0x34,case.get("upgrade_slots",[-1,-1]),"i")
        self.vector(self.map+0x58,case.get("funds",[0,0]),"i")
        self.vector(self.map+0x24c,case.get("available",[0]*23),"B")
        self.w32(self.map+0x114,self.array([0]*23))
        self.w8(self.map+0x110,0)
        capacity=2*(case["width"]+case["height"])
        for offset in (0xc8,0xd0):
            self.w32(self.map+offset,self.int_vectors([[-1,-1] for _ in range(capacity)]))
            self.w32(self.map+offset+4,capacity)
        self.vector(self.map+0x68, case["counters"], "i")
        sites = case["sites"]
        self.vector(self.map+0x3e8, [s["owner"] for s in sites], "b")
        site_xy, owners, coordinates, links = [self.alloc(len(sites)*8) for _ in range(4)]
        for s, site in enumerate(sites):
            self.vector(site_xy+s*8, site["xy"], "B")
            groups = site["groups"]
            own, coord, link = [self.alloc(len(groups)*8) for _ in range(3)]
            for g, group in enumerate(groups):
                self.vector(own+g*8, [i["owner"] for i in group], "b")
                self.vector(link+g*8, [i.get("link", 0) for i in group], "B")
                pairs = self.alloc(len(group)*8)
                for i, item in enumerate(group):
                    self.vector(pairs+i*8, item["xy"], "B")
                self.w32(coord+g*8, pairs)
                self.w32(coord+g*8+4, len(group))
            for outer, address in ((owners,own),(coordinates,coord),(links,link)):
                self.w32(outer+s*8, address)
                self.w32(outer+s*8+4, len(groups))
        for offset, address in ((0x3f0,site_xy),(0x3f8,owners),(0x400,coordinates),(0x408,links)):
            self.w32(self.map+offset, address)
            self.w32(self.map+offset+4, len(sites))
        self.vector(self.map+0x418, [0]*255, "i")
        triplets = self.int_vectors([[0]*3 for _ in range(255)])
        self.w32(self.map+0x410, triplets)
        self.w32(self.map+0x414, 255)

    def call_bounded(self,entry,args,*,count=20_000_000,timeout_us=20_000_000):
        ar=self.ar
        for i in range(13):
            self.u.reg_write(getattr(ar,"UC_ARM_REG_R"+str(i)),0)
        sp,stop=0x21ff000,0x3000000
        self.u.reg_write(ar.UC_ARM_REG_CPSR,0x30)
        self.u.reg_write(ar.UC_ARM_REG_SP,sp)
        self.u.reg_write(ar.UC_ARM_REG_LR,stop|1)
        for i,value in enumerate(args):
            if i<4:
                self.u.reg_write(getattr(ar,"UC_ARM_REG_R"+str(i)),value&0xffffffff)
            else:
                self.w32(sp+(i-4)*4,value)
        self.u.emu_start(entry|1,stop,count=count,timeout=timeout_us)
        if self.u.reg_read(ar.UC_ARM_REG_PC)!=stop or self.u.reg_read(ar.UC_ARM_REG_SP)!=sp:
            raise RuntimeError(f"bounded original {entry:#x} didnotreturn pc={self.u.reg_read(ar.UC_ARM_REG_PC):#x}")
        return self.u.reg_read(ar.UC_ARM_REG_R0)

    def field(self):
        return [combat.signed(self.r32(self.grid_columns[x]+y*4))
                for y in range(self.r8(self.map+0x16))
                for x in range(self.r8(self.map+0x15))]

    def plan(self, address):
        if address == 0:
            return None
        words = [combat.signed(self.r32(address+i*4)) for i in (0,1,2)]
        vector = self.r32(address+0xc)
        words.extend(combat.signed(self.r32(vector+i*4)) for i in range(2))
        words.extend(combat.signed(self.r32(address+i*4)) for i in (5,6,7))
        words.extend([self.r8(address+0x20),self.r8(address+0x21)])
        return words


def simple_case():
    forms = [[2,1,1,40,60,30,0,0,0,0,1,0,0,0],
             [4,0,0,0,0,40,0,0,0,0,0,0,0,0]]
    units = []
    for t,owner,x,y in ((11,0,0,0),(19,1,2,1)):
        units.append({"type":t,"owner":owner,"faction":owner,"x":x,"y":y,
                      "form":0,"level":0,"health":100,"active":1,"immune":0,
                      "flag38":0,"support":0,"timer":-1,"preset":-1,"modifiers":[0,0],
                      "forms":[f.copy() for f in forms]})
    return {"flag227":0,"width":4,"height":4,"tiles":[0]*16,"lookup":[0]*32,
            "rules":[[1,0,0]],"units":units,"current":0,"controllers":[1,1],
            "factions":[0,1],"counters":[1,1],"sites":[],"actor":0}


def varied_case(index):
    rng=random.Random(0x50ed600+index)
    case=simple_case()
    width,height=rng.randrange(3,8),rng.randrange(3,8)
    rules=[[1,0,0],[2,10,0],[4,25,0],[99,5,0],[99,20,1],[1,15,1]]
    case.update(width=width,height=height,tiles=[rng.randrange(len(rules)) for _ in range(width*height)],
                lookup=list(range(6))+[0]*26,rules=rules,flag227=index%3==0,
                factions=([0,1],[1,0],[0,0],[-1,1],[0,-1],[-1,-1])[index%6],
                controllers=([0,1],[1,1],[0,0],[-1,1])[index%4],
                counters=[rng.choice([0,1,5,17,0x7fffffff,-2147483648]),rng.choice([0,1,9,29])])
    count=rng.randrange(2,7)
    types=rng.sample(range(23),count)
    positions=rng.sample(range(width*height),count)
    units=[]
    for j,(t,xy) in enumerate(zip(types,positions)):
        forms=[]
        for f in range(2):
            lo=rng.choice([0,0,20,40,60,80])
            forms.append([rng.choice([0,1,2,3,4,6,255]),rng.choice([0,1,2]),rng.choice([0,1,2,3]),
                          lo,lo+rng.choice([0,10,20]),rng.choice([0,20,40,59,60,100]),
                          rng.choice([0,0,1,255]),0,0,0,rng.randrange(2),rng.choice([0,0,1]),0,0])
        units.append({"type":t,"owner":j%2,"faction":rng.randrange(2),"x":xy%width,"y":xy//width,
                      "form":rng.randrange(2),"level":rng.randrange(4),"health":rng.choice([0,9,49,100]),
                      "active":int(j<2 or rng.randrange(5)!=0),"immune":0,"flag38":int(rng.randrange(5)==0),
                      "support":0,"timer":-1,"preset":-1,"modifiers":[rng.choice([0,5,15,251]),rng.choice([0,10,255])],
                      "forms":forms,"spent":rng.randrange(5),"acted":rng.randrange(2),
                      "offset_x":0 if rng.randrange(8) else 3,"offset_y":0})
    actor=index%count
    units[actor]["active"]=1
    case.update(units=units,actor=actor,current=units[actor]["owner"])
    case["sites"]=[]
    for s in range(index%4):
        xy=[rng.randrange(width),rng.randrange(height)]
        if index%7==0:
            xy=[units[actor]["x"],units[actor]["y"]]
        site={"owner":rng.choice([-1,0,1]),"xy":xy,"groups":[]}
        for g in range(rng.randrange(3)):
            group=[]
            for i in range(rng.randrange(4)):
                point=[rng.randrange(width),rng.randrange(height)]
                if index%11==0:
                    point=[units[1]["x"],units[1]["y"]]
                group.append({"owner":rng.choice([-1,0,1]),"link":rng.randrange(2),"xy":point})
            site["groups"].append(group)
        case["sites"].append(site)
    case["points"]=[[rng.randrange(width),rng.randrange(height),rng.randrange(2)] for _ in range(index%3)]
    case["regions"]=[[rng.randrange(width),rng.randrange(height),rng.randrange(3),rng.randrange(3)] for _ in range(index%2)]
    return case


def original_result(image,gcc,case,index,budget_override=None):
    old=OriginalAI(image,gcc)
    old.configure_ai(case)
    actor=case["actor"]
    address=old.call(0x50ed6,[old.map,old.units[actor]])
    result={"plan":old.plan(address),"scores":[]}
    queries=[(case["units"][actor]["x"],case["units"][actor]["y"],-1,0),
             (0,0,-1,1),(case["width"]-1,case["height"]-1,1,0),
             (case["width"]//2,case["height"]//2,-1,0)]
    for x,y,excluded,alternate in queries:
        value=old.call(0x4e8f4,[old.map,old.units[actor],x,y,
                                old.units[excluded] if excluded>=0 else 0,alternate])
        result["scores"].append([x,y,excluded,alternate,combat.signed(value)])
        for unit,pointer in zip(case["units"],old.units):
            if old.r8(pointer+0x3b)!=unit["x"] or old.r8(pointer+0x3c)!=unit["y"]:
                raise RuntimeError("original score failed to restore unit coordinates")
    budget=(-2147483648,-1,0,1,2,4,99,127,128,255,256,511)[index%12]
    if budget_override is not None:
        budget=budget_override
    old.call(0x49b16,[old.map])
    a=case["units"][actor]
    old.call(0x4a29c,[old.map,old.units[actor],a["x"],a["y"],budget,-1,1,1])
    vacant=old.call(0x49b5a,[old.map,a["x"],a["y"]])
    result["explicit_budget"]=[budget,int(vacant!=0),*old.field()]
    old.check_text()
    return result,old.calls


def write_fixture(path,cases):
    rows=["G1_AI_ATTACK_V1"]
    def row(tag,values):
        rows.append(tag+" "+" ".join(map(str,values)))
    for index,(case,result) in enumerate(cases):
        row("C",[index,case["width"],case["height"],case["actor"],case["current"],int(case["flag227"]),
                 *case["factions"],*case["controllers"],*case["counters"],len(case["units"]),len(case["sites"])])
        row("G",case["tiles"])
        row("L",case["lookup"])
        row("T",[len(case["rules"]),*[v for rule in case["rules"] for v in rule]])
        for u in case["units"]:
            row("U",[u[k] for k in ("type","owner","faction","form","level","health","active","immune","flag38",
                                    "support","timer","preset","x","y")]+
                    [u.get(k,0) for k in ("spent","acted","offset_x","offset_y")]+
                    u["modifiers"]+[v for f in u["forms"] for v in f])
        for site in case["sites"]:
            row("S",[site["owner"],*site["xy"],len(site["groups"])])
            for group in site["groups"]:
                row("I",[len(group),*[v for i in group for v in (i["owner"],i.get("link",0),*i["xy"])]])
        row("P",[len(case.get("points",[])),*[v for point in case.get("points",[]) for v in point]])
        row("R",[len(case.get("regions",[])),*[v for region in case.get("regions",[]) for v in region]])
        if "fallback" in result or "admission" in result:
            values=[*case["funds"],*case["upgrade_slots"]]
            for owner in range(2):
                slots=[u["type"] for u in sorted(case["units"],key=lambda u:u["type"]) if u["owner"]==owner]
                values.extend([len(slots),*slots])
            for unit in case["units"]:
                values.extend([unit.get("upgrade_cost",0),unit.get("transform_capability",0)])
            row("M",values)
        if "admission" in result:
            row("W",case["available"])
        row("A",[0] if result["plan"] is None else [1,*result["plan"]])
        row("Q",[len(result["scores"]),*[v for q in result["scores"] for v in q]])
        row("B",result["explicit_budget"])
        if "fallback" in result:
            for tag,key in (("F","fallback"),("J","decision")):
                value=result[key]
                row(tag,[value["form_after"],*value["stats_after"],int(value["plan"] is not None),
                         *(value["plan"] or [])])
        if "admission" in result:
            row("D",[case["cursor"],*result["admission"]])
            if result["admission"][0]==1 and "production_destination" in result:
                target=result["production_destination"]
                row("X",[result["admission"][1],int(target is not None),*(target or [])])
    rows.append("END")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text("\n".join(rows)+"\n")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--binary",type=Path,required=True)
    p.add_argument("--libgcc",type=Path,required=True)
    p.add_argument("--unicorn-dir",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--fixture",type=Path)
    p.add_argument("--count",type=int,default=192)
    p.add_argument("--archive",type=Path)
    p.add_argument("--source-fixture",type=Path)
    args = p.parse_args()
    if bool(args.archive)!=bool(args.source_fixture):
        p.error("--archive and --source-fixture must be supplied together")
    sys.path.insert(0,str(args.unicorn_dir))
    image,gcc = args.binary.read_bytes(),args.libgcc.read_bytes()
    if combat.sha(image) != combat.IMAGE_SHA or combat.sha(gcc) != combat.LIBGCC_SHA:
        raise ValueError("wrong original input")
    if not 1<=args.count<=512:
        p.error("--count must be1..512")
    cases=[]
    calls=Counter()
    for index in range(args.count):
        case=simple_case() if index==0 else varied_case(index)
        result,used=original_result(image,gcc,case,index)
        cases.append((case,result))
        calls.update(used)
    result={"original_sha256":combat.sha(image),"libgcc_sha256":combat.sha(gcc),
            "oracle_sha256":combat.sha(Path(__file__).read_bytes()),
            "combat_oracle_sha256":combat.sha((ROOT/"analysis_tools/combat/oracle.py").read_bytes()),
            "original_text_unchanged":True,"original_game_function_replacements":0,
            "infrastructure_boundaries":{hex(k):v for k,v in INFRASTRUCTURE.items()},
            "case_count":len(cases),"cases":[{"input":c,"output":r} for c,r in cases],"calls":dict(calls)}
    if args.fixture:
        write_fixture(args.fixture,cases)
        result["fixture_sha256"]=combat.sha(args.fixture.read_bytes())
    if args.archive:
        archive=args.archive.read_bytes()
        if combat.sha(archive)!=combat.ARCHIVE_SHA:
            raise ValueError("wrong original archive")
        source,provenance=combat.source_cases(image,archive)
        source_results=[]
        for index,case in enumerate(source):
            case.update(actor=0,current=0,controllers=[1,1],factions=[0,1],
                        counters=[1,1],sites=[])
            output,used=original_result(image,gcc,case,index,budget_override=2)
            source_results.append((case,output))
            calls.update(used)
        write_fixture(args.source_fixture,source_results)
        result["source_data"]={"provenance":provenance,"case_count":len(source_results),
            "nonempty_plans":sum(r["plan"] is not None for _,r in source_results),
            "fixture_sha256":combat.sha(args.source_fixture.read_bytes()),
            "original_payload_fixture_excluded_from_git":True,
            "scope":"actual23definitions/twoforms/firstmap withsyntheticadjacentplacements; notliveAIturn"}
        result["calls"]=dict(calls)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"case_count":result["case_count"],"nonempty_plans":sum(r["plan"] is not None for _,r in cases),
                      "calls":result["calls"]}))


if __name__ == "__main__":
    main()
