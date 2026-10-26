#!/usr/bin/env python3
"""Development-only upgrade/repair and owner-slot reference from original ARM.

Gameplay helpers execute unchanged. Only explicit renderer, UI-string and audio
presentation boundaries are recorded. Original code is never shipped natively.
"""
import argparse
from collections import Counter
import copy
import importlib.util
import json
from pathlib import Path
import random
import sys

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location("ai_reference",ROOT/"analysis_tools/ai/oracle.py")
ai=importlib.util.module_from_spec(spec);spec.loader.exec_module(ai)

PRESENTATION={
    0x5ca2c:"renderer unit effect request: record type/mode",
    0x60800:"UI string assignment: record, no gameplay value returned",
    0x60b70:"UI integer string append: record, no gameplay value returned",
    0x2ad12:"audio request: record group/event",
}


class OriginalActions(ai.OriginalAI):
    def __init__(self,image,gcc):
        self.effects=[];self.audio=[];self.heal_amounts=[]
        super().__init__(image,gcc)

    def hook(self,u,address,size,data):
        if address==0x431be:
            self.heal_amounts.append(ai.combat.signed(u.reg_read(self.ar.UC_ARM_REG_R1)))
        if address in PRESENTATION:
            self.calls[hex(address)]+=1
            r=[u.reg_read(getattr(self.ar,"UC_ARM_REG_R"+str(i))) for i in range(3)]
            if address==0x5ca2c:self.effects.append(r[1:3])
            if address==0x2ad12:self.audio.append(r[1:3])
            u.reg_write(self.ar.UC_ARM_REG_PC,u.reg_read(self.ar.UC_ARM_REG_LR))
            return
        super().hook(u,address,size,data)

    def configure_actions(self,case):
        self.configure_ai(case)
        self.w32(self.map+0x60,self.alloc(16));self.w32(self.map+0x64,2)
        self.w32(self.map+0x3cc,self.units[case["actor"]])
        self.w32(self.map+0x29c,self.alloc(0x100))

    def signed_vector(self,offset,count=2):
        return [ai.combat.signed(self.r32(self.r32(self.map+offset)+i*4)) for i in range(count)]

    def target_types(self):
        return [self.r8(self.r32(self.r32(self.map+0xf4)+i*4)+9)
                for i in range(self.r8(self.map+0xf0))]

    def upgraded(self,pointer):
        return [self.r8(pointer+0x1a),*self.unit_result(pointer)[:3],
                self.r8(pointer+0x2c),self.r8(pointer+0x5a),
                ai.combat.signed(self.r32(pointer+0x30)),ai.combat.signed(self.r32(pointer+0x34))]


def make_case(index):
    rng=random.Random(0x556a800+index)
    c=ai.simple_case()
    c.update(width=7,height=7,tiles=[0]*49,lookup=[0]*32,
             rules=[[1,0,0] for _ in range(5)],units=[],funds=[rng.choice([-5,0,1,2,5,10,50,0x7fffffff]) for _ in range(2)],
             upgrade_slots=[-1,-1],available=[0]*23)
    places=rng.sample(range(49),23)
    for t,p in enumerate(places):
        forms=[]
        for f in range(2):
            forms.append([2+f,1,1,20,40,30,0,rng.choice([0,1,1,2,255]),0,0,0,0,
                          rng.choice([0,0,1,2,255]),0])
        c["units"].append({"type":t,"owner":t%2,"faction":t%2,"x":p%7,"y":p//7,
          "form":rng.randrange(2),"level":rng.choice([0,1,12,24,25,255]),
          "health":rng.choice([0,1,9,10,49,50,90,91,99,100,101,255]),
          "active":int(rng.randrange(4)!=0),"immune":rng.randrange(2),"flag38":0,
          "support":0,"timer":rng.choice([-1,0,1200]),"preset":rng.choice([-1,5000]),
          "modifiers":[0,0],"forms":forms,"spent":0,"acted":rng.randrange(2),
          "offset_x":rng.choice([0,3]),"offset_y":0,
          "upgrade_cost":rng.choice([0,1,2,5,127,128,255]),"transform_capability":0})
    c["actor"]=index%23
    a=c["units"][c["actor"]];c["current"]=a["owner"]
    if index%3==0:
        a.update(active=1,acted=0,level=index%25)
        a["forms"][0][12]=0;a["forms"][a["form"]][7]=1
        a["upgrade_cost"]=index%7;c["funds"][a["owner"]]=index%12
    edges={3:(90,10),6:(80,10),9:(1,3),12:(100,10),15:(255,10),
           18:(99,0),21:(0,11),24:(9,0x7fffffff),27:(91,0x7fffffff)}
    if index in edges:
        a["health"],c["funds"][a["owner"]]=edges[index]
        c["heal_target_self"]=True
    if index==27:a["upgrade_cost"]=255
    if index%19==0:
        for u in c["units"]:u["active"]=0
    for owner in range(2):
        slots=[u["type"] for u in c["units"] if u["owner"]==owner]
        c["upgrade_slots"][owner]=rng.choice([-1,*range(len(slots))])
    if index%2==0:
        slots=[u["type"] for u in c["units"] if u["owner"]==a["owner"]]
        c["upgrade_slots"][a["owner"]]=slots.index(a["type"])
    return c


def effective_cost_cases():
    """Independent raw bytes around the actual type21 funds boundary."""
    rows=[]
    for raw in (0,5,255):
        for funds in (39,40,41):
            c=make_case(1)
            for unit in c['units']:unit.update(active=0,acted=0)
            c['actor']=21;c['current']=1;c['funds']=[0,funds]
            c['upgrade_slots']=[-1,10]
            actor=c['units'][21]
            actor.update(active=1,acted=0,level=0,form=0,health=100,
                         x=1,y=1,upgrade_cost=raw)
            actor['forms'][0][12]=0;actor['forms'][0][7]=0
            # An ordinary next owner slot lets the unchanged post-upgrade
            # selection loop terminate through its real candidate predicate.
            next_unit=c['units'][1]
            next_unit.update(active=1,acted=0,x=2,y=1)
            next_unit['forms'][0][12]=0
            rows.append(c)
    return rows


def verify_effective_cost_loader(image,gcc):
    """Execute the original loader override, preserving arbitrary raw bytes."""
    old=ai.OriginalAI(image,gcc);old.configure_ai(ai.simple_case())
    table=old.r32(old.map+0x14c)
    old.w32(0x21ff000+0x4c,old.map+0x14c)
    results=[]
    for unit_type in range(23):
        for raw in (0,1,5,40,127,128,255):
            old.w8(table+unit_type,raw)
            old.w32(0x21ff000+0xf0,unit_type)
            old.call(0x5a8ce,[],stop=0x5a8e0)
            actual=old.r8(table+unit_type)
            if actual!=(40 if unit_type==21 else raw):
                raise RuntimeError('Original effective cost loader differs')
            results.append([unit_type,raw,actual])
    old.check_text()
    return {'original_block':'0x5a8ce..0x5a8e0','cases':results,
            'case_count':len(results),'original_text_unchanged':True,
            'gameplay_replacements':0,'all_matched':True}


def execute(image,gcc,c):
    used=Counter()
    def original():
        o=OriginalActions(image,gcc);o.configure_actions(c);return o
    old=original();actor=old.units[c["actor"]]
    upgrade=old.call(0x4ec0e,[old.map,actor])
    command=old.call_bounded(0x5300e,[old.map,actor])
    raw_heal=old.call(0x4a73c,[old.map,actor])
    targets=old.target_types() if raw_heal else None
    if bool(upgrade)!=bool(command&512):raise RuntimeError("original upgrade outer gate differs")
    old.check_text();used.update(old.calls)
    result={"upgrade_allowed":upgrade,"heal_allowed":int(bool(command&16)),"targets":targets}
    if upgrade:
        old=original();actor=old.units[c["actor"]]
        old.call(0x556a8,[old.map,actor],stop=0x557aa)
        result["upgrade"]={"unit":old.upgraded(actor),"funds":old.signed_vector(0x58),
                           "slots":old.signed_vector(0x34),"effects":old.effects}
        old.check_text();used.update(old.calls)
    if command&16:
        # Confirm one target actually selected by original list ordering.
        target_type=c["units"][c["actor"]]["type"] if c.get("heal_target_self") else targets[c["actor"]%len(targets)]
        target_index=next(i for i,u in enumerate(c["units"]) if u["type"]==target_type)
        old=original();target=old.units[target_index];actor=old.units[c["actor"]]
        old.w32(old.map+0xfc,0);old.w32(old.r32(old.map+0xf4),target)
        boundaries=[]
        def stop(u,address,size,data):
            if address in (0x589f4,0x58aa6,0x58ae4):
                boundaries.append(address);u.emu_stop()
        handle=old.u.hook_add(old.uc.UC_HOOK_CODE,stop)
        try:
            old.call_bounded(0x588e0,[old.map])
        except RuntimeError:
            if len(boundaries)!=1:raise
        finally:old.u.hook_del(handle)
        if len(boundaries)!=1:raise RuntimeError("heal did not reach one core boundary")
        boundary=boundaries[0]
        result["heal"]={"target":target_index,"stop":hex(boundary),
          "health":old.r8(target+0x5a),"timer":ai.combat.signed(old.r32(target+0x30)),
          "preset":ai.combat.signed(old.r32(target+0x34)),"acted":old.r8(actor+0x2c),
          "funds":old.signed_vector(0x58),"audio":old.audio,"effects":old.effects,
          "requested_health":old.heal_amounts[0] if old.heal_amounts else 0}
        old.check_text();used.update(old.calls)
    first=[]
    for owner in range(2):
        old=original()
        old.w32(0x21ff000+0x7c,old.map);old.w32(0x21ff000+0x11c,owner)
        old.call(0x567f6,[],stop=0x5686c)
        first.append(old.signed_vector(0x34)[owner])
        old.check_text();used.update(old.calls)
    result["first_slots"]=first
    old=original();actor=old.units[c["actor"]]
    old.call_bounded(0x43ac8,[actor,1])
    result["removal_slots"]=old.signed_vector(0x34)
    result["removal_auxiliary"]=[old.r8(actor+0xd),old.r32(actor+0x24),old.r32(actor+0x28)]
    old.check_text();used.update(old.calls)
    old=original();old.call_bounded(0x5077a,[old.map])
    result["reset_slots"]=old.signed_vector(0x34)
    old.check_text();used.update(old.calls)
    return result,used


def write_fixture(path,rows):
    lines=["G1_ACTIONS_V1"]
    def row(tag,values):lines.append(tag+" "+" ".join(str(int(x)) for x in values))
    for index,(c,r) in enumerate(rows):
        row("C",[index,c["actor"],c["current"],*c["funds"],*c["upgrade_slots"],len(c["units"])])
        for u in c["units"]:
            row("U",[u[k] for k in ('type','owner','faction','form','level','health','active','immune',
                'x','y','acted','timer','preset','upgrade_cost')]+[v for f in u['forms'] for v in f])
        row("G",[r["upgrade_allowed"],r["heal_allowed"]])
        row("T",[-1] if r["targets"] is None else [len(r["targets"]),*r["targets"]])
        if "upgrade" in r:
            v=r["upgrade"]
            row("A",[*v["unit"],*v["funds"],*v["slots"]])
        if "heal" in r:
            v=r["heal"]
            outcome={"0x589f4":0,"0x58aa6":1,"0x58ae4":2}[v["stop"]]
            row("H",[v["target"],outcome,v["health"],v["timer"],v["preset"],v["acted"],
                     *v["funds"],v["requested_health"],len(v["audio"]),*[x for pair in v["audio"] for x in pair]])
        row("S",[*r["first_slots"],*r["removal_slots"],*r["reset_slots"]])
    lines.append("END")
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text("\n".join(lines)+"\n")


def source_cases(path):
    source=json.loads(path.read_text())
    if (source['mission_resource_id'],source['grid_resource_id'],len(source['definitions']))!=(315,268,23):
        raise ValueError('unexpected independently decoded first-world source')
    spec=importlib.util.spec_from_file_location('source_ai',ROOT/'analysis_tools/ai/source_oracle.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    base=m.seed(source);rows=[]
    for t in range(23):
        for form in range(2):
            for level in (0,24):
                c=copy.deepcopy(base);c['actor']=t;c['heal_target_self']=bool(level)
                for u in c['units']:u.update(active=0,acted=0,x=0,y=0)
                a=c['units'][t];a.update(active=1,form=form,level=level,x=1,y=2,health=90 if level else 9)
                c['current']=a['owner'];c['funds']=[20,20]
                friends=[u for u in c['units'] if u['type']!=t and u['owner']==a['owner'] and u['forms'][0][12]!=1]
                if friends:friends[0].update(active=1,x=2,y=2,health=45)
                enemies=[u for u in c['units'] if u['owner']!=a['owner']]
                if enemies:enemies[0].update(active=1,x=4,y=7)
                slots=[u['type'] for u in c['units'] if u['owner']==a['owner']]
                c['upgrade_slots'][a['owner']]=slots.index(t)
                rows.append(c)
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--binary",type=Path,required=True);p.add_argument("--libgcc",type=Path,required=True)
    p.add_argument("--unicorn-dir",type=Path,required=True);p.add_argument("--output",type=Path,required=True)
    p.add_argument("--fixture",type=Path,required=True);p.add_argument("--count",type=int,default=192)
    p.add_argument("--world-json",type=Path);p.add_argument("--source-fixture",type=Path)
    a=p.parse_args()
    if not 1<=a.count<=256:p.error("count must be1..256")
    if bool(a.world_json)!=bool(a.source_fixture):p.error('supply both world-json and source-fixture')
    sys.path.insert(0,str(a.unicorn_dir))
    image,gcc=a.binary.read_bytes(),a.libgcc.read_bytes()
    if ai.combat.sha(image)!=ai.combat.IMAGE_SHA or ai.combat.sha(gcc)!=ai.combat.LIBGCC_SHA:
        raise ValueError("wrong pinned original inputs")
    loader=verify_effective_cost_loader(image,gcc)
    rows=[];calls=Counter()
    all_cases=[make_case(i) for i in range(a.count)]+effective_cost_cases()
    for index,c in enumerate(all_cases):
        try:r,used=execute(image,gcc,c)
        except Exception as error:raise RuntimeError(f"original action case{index} failed") from error
        rows.append((c,r));calls.update(used)
    write_fixture(a.fixture,rows)
    report={"original_sha256":ai.combat.sha(image),"libgcc_sha256":ai.combat.sha(gcc),
      "case_count":len(rows),"upgrade_executions":sum('upgrade' in r for _,r in rows),
      "heal_executions":sum('heal' in r for _,r in rows),
      "original_text_unchanged":True,"gameplay_function_replacements":0,
      "presentation_boundaries":{hex(k):v for k,v in PRESENTATION.items()},
      "infrastructure_boundaries":{hex(k):v for k,v in ai.INFRASTRUCTURE.items()},
      "calls":dict(calls),"fixture_sha256":ai.combat.sha(a.fixture.read_bytes()),
      "oracle_sha256":ai.combat.sha(Path(__file__).read_bytes()),
      "shared_oracle_sha256":ai.combat.sha((ROOT/'analysis_tools/ai/oracle.py').read_bytes()),
      "effective_cost_loader":loader,
      "type21_boundary_cases":{"start_index":a.count,"count":9,
          "raw_costs":[0,5,255],"funds":[39,40,41],"effective_cost":40},
      "cases":[{"input":c,"output":r} for c,r in rows]}
    if a.world_json:
        source=[];source_calls=Counter()
        for index,c in enumerate(source_cases(a.world_json)):
            try:r,used=execute(image,gcc,c)
            except Exception as error:raise RuntimeError(f'original source action case{index} failed') from error
            source.append((c,r));source_calls.update(used)
        write_fixture(a.source_fixture,source)
        report['source_data']={'world_json_sha256':ai.combat.sha(a.world_json.read_bytes()),
          'grid_resource_id':268,'definition_count':23,'forms_per_type':2,'levels':[0,24],
          'case_count':len(source),'upgrade_executions':sum('upgrade' in r for _,r in source),
          'heal_executions':sum('heal' in r for _,r in source),'calls':dict(source_calls),
          'fixture_sha256':ai.combat.sha(a.source_fixture.read_bytes()),
          'source_fixture_excluded_from_git':True,
          'scope':'actual definitions/first grid with explicit synthetic active units, positions, HP, funds and slots; not live gameplay'}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:report[k] for k in ('case_count','upgrade_executions','heal_executions')}))


if __name__=="__main__":main()
