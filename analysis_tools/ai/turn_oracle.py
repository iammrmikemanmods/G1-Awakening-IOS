#!/usr/bin/env python3
"""Original AI idle driver oracle, stopping before external action/turn dispatch.

Production candidates, affordability, adjacency and owner ordering execute in
the unchanged original. Ordinary cases deliberately have no attack/capture or
enemy-approach plan; the real 58158/512e6 returns and the driver increments its
cursor. Production/end-turn stop at their natural called-function boundary.
"""
import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path
import random
import sys

spec=importlib.util.spec_from_file_location("ai_reference",Path(__file__).with_name("oracle.py"))
ai=importlib.util.module_from_spec(spec);spec.loader.exec_module(ai)


def make_case(index):
    rng=random.Random(0x58dcc00+index)
    c=ai.simple_case()
    c.update(width=7,height=6,tiles=[rng.choice([0,0,0,1]) for _ in range(42)],
             lookup=[0,1]+[0]*30,rules=[[1,0,0],[99,0,0],[1,0,0],[1,0,0],[1,0,0]],
             units=[],current=index%2,controllers=[1,1],factions=[0,1],
             funds=[rng.choice([0,1,3,7,15,30]),rng.choice([0,2,5,10,25])],
             upgrade_slots=[-1,-1],available=[rng.randrange(2) for _ in range(23)],cursor=index%24)
    positions=rng.sample(range(42),23)
    for t,point in enumerate(positions):
        owner=t%2
        active=int(owner==c["current"] and rng.randrange(3)!=0)
        f0=[2,0,0,0,0,30,0,0,rng.randrange(2),0,0,0,0,0]
        f1=f0.copy()
        if index%5:
            f0[12]=int(rng.randrange(4)==0)
            f0[9]=int(rng.randrange(4)==0)
            f1[12]=int(rng.randrange(3)==0)
            f1[9]=int(rng.randrange(3)==0)
        f0[6]=rng.choice([0,0,1]);f1[6]=rng.choice([0,1])
        c["units"].append({"type":t,"owner":owner,"faction":owner,"x":point%7,"y":point//7,
            "form":rng.randrange(2),"level":0,"health":100,"active":active,"immune":0,"flag38":0,
            "support":0,"timer":-1,"preset":-1,"modifiers":[0,0],"forms":[f0,f1],
            "spent":0,"acted":rng.randrange(2),"offset_x":3 if index%11==0 else 0,"offset_y":0,
            "upgrade_cost":rng.choice([0,1,2,5,8,12,127,255]),"transform_capability":0})
    c["actor"]=0
    c["points"]=[[2,2,1],[3,2,1]] if index%7==0 else []
    c["regions"]=[[0,0,7,6]] if index%13==0 else []
    return c


def effective_cost_cases():
    rows=[]
    for raw in (0,5,255):
        for funds in (39,40,41):
            case=make_case(1)
            case.update(actor=1,current=1,cursor=0,tiles=[0]*42,
                        rules=[[1,0,0] for _ in range(5)],funds=[0,funds],
                        available=[int(t==21) for t in range(23)],points=[],regions=[])
            for unit in case['units']:unit.update(active=0,acted=0)
            producer=case['units'][1]
            producer.update(active=1,form=0,x=2,y=2)
            for form in producer['forms']:form[12]=1
            target=case['units'][21]
            target['upgrade_cost']=raw
            for form in target['forms']:form[8]=0
            rows.append(case)
    return rows


def execute(image,gcc,case):
    import unicorn
    old=ai.OriginalAI(image,gcc);old.configure_ai(case)
    ar=old.ar
    old.w8(old.map+0x130,23)
    old.call(0x496e4,[old.map])
    old.w32(old.map+0x3d0,-1);old.w32(old.map+0x2c,case["cursor"])
    ordinary=[];boundaries=[]
    def observe(u,address,size,data):
        if address==0x58158:
            ordinary.append((u.reg_read(ar.UC_ARM_REG_R1),old.r32(old.map+0x2c)))
        elif address in (0x5494c,0x55d50):
            boundaries.append((address,[u.reg_read(getattr(ar,"UC_ARM_REG_R"+str(i))) for i in range(4)]))
            u.emu_stop()
    handle=old.u.hook_add(unicorn.UC_HOOK_CODE,observe)
    try:
        old.call_bounded(0x58dcc,[old.map,30])
    except RuntimeError:
        if len(boundaries)!=1:raise
    finally:
        old.u.hook_del(handle)
    if boundaries:
        if ordinary:raise RuntimeError("ordinary test unexpectedly dispatched an action")
        entry,registers=boundaries[0]
        if entry==0x5494c:
            if registers[1]!=0:raise RuntimeError("unexpected production phase")
            result=[1,old.r8(registers[2]+9),old.r32(old.map+0x120),old.r32(old.map+0x2c)]
        else:
            result=[2,-1,-1,old.r32(old.map+0x2c)]
    else:
        if len(ordinary)!=1:raise RuntimeError("ordinary driver did not dispatch exactlyone unit")
        result=[0,old.r8(ordinary[0][0]+9),-1,old.r32(old.map+0x2c)]
    destination=None
    if result[0]==1:
        producer=registers[2]
        old.call_bounded(0x4a678,[old.map,producer])
        old.vector(old.map+0x3d8,[old.r8(producer+0x3b),old.r8(producer+0x3c)],"B")
        old.w32(old.map+0x3d0,0);old.w32(old.map+0xac,0)
        spawn=[]
        def observe_spawn(u,address,size,data):
            if address==0x54016:
                spawn.append([u.reg_read(ar.UC_ARM_REG_R3),
                              old.r32(u.reg_read(ar.UC_ARM_REG_SP))])
                u.emu_stop()
        handle=old.u.hook_add(unicorn.UC_HOOK_CODE,observe_spawn)
        try:
            old.call_bounded(0x58dcc,[old.map,101])
        except RuntimeError:
            if len(spawn)!=1:raise
        finally:
            old.u.hook_del(handle)
        if len(spawn)>1:raise RuntimeError("multiple production destinations")
        destination=spawn[0] if spawn else None
    old.check_text()
    return result,destination,old.calls


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--binary",type=Path,required=True);p.add_argument("--libgcc",type=Path,required=True)
    p.add_argument("--unicorn-dir",type=Path,required=True);p.add_argument("--output",type=Path,required=True)
    p.add_argument("--fixture",type=Path,required=True);p.add_argument("--count",type=int,default=192)
    a=p.parse_args()
    if not 1<=a.count<=256:p.error("count must be1..256")
    sys.path.insert(0,str(a.unicorn_dir))
    image,gcc=a.binary.read_bytes(),a.libgcc.read_bytes()
    if ai.combat.sha(image)!=ai.combat.IMAGE_SHA or ai.combat.sha(gcc)!=ai.combat.LIBGCC_SHA:
        raise ValueError("wrong original inputs")
    cases=[];calls=Counter()
    all_cases=[make_case(i) for i in range(a.count)]+effective_cost_cases()
    for index,c in enumerate(all_cases):
        r,used=ai.original_result(image,gcc,c,index,budget_override=2);calls.update(used)
        r["admission"],r["production_destination"],used=execute(image,gcc,c);calls.update(used)
        cases.append((c,r))
    ai.write_fixture(a.fixture,cases)
    report={"original_sha256":ai.combat.sha(image),"libgcc_sha256":ai.combat.sha(gcc),
            "case_count":len(cases),"ordinary":sum(r["admission"][0]==0 for _,r in cases),
            "production":sum(r["admission"][0]==1 for _,r in cases),
            "finish":sum(r["admission"][0]==2 for _,r in cases),
            "production_destinations":sum(r["production_destination"] is not None for _,r in cases),
            "original_text_unchanged":True,"gameplay_function_replacements":0,
            "whole_or_prefix_entry":"0x58dcc","external_dispatch_stops":["0x5494c","0x55d50","0x54016"],
            "fixture_sha256":ai.combat.sha(a.fixture.read_bytes()),
            "oracle_sha256":ai.combat.sha(Path(__file__).read_bytes()),
            "shared_oracle_sha256":ai.combat.sha(Path(__file__).with_name("oracle.py").read_bytes()),
            "type21_boundary_cases":{"start_index":a.count,"count":9,
                "raw_costs":[0,5,255],"funds":[39,40,41],"effective_cost":40},
            "calls":dict(calls),"cases":[{"input":c,"output":r} for c,r in cases]}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:report[k] for k in ("case_count","ordinary","production","finish")}))


if __name__=="__main__":main()
