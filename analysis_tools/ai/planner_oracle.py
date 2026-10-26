#!/usr/bin/env python3
"""Whole original 0x4ec72 fallback and 0x512e6 opponent-planner comparisons.

Imports the explicit infrastructure-only original AI reference harness. All
planner, movement, transform, score and capture helpers execute unchanged.
"""
import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path
import random
import sys

spec=importlib.util.spec_from_file_location("ai_reference",Path(__file__).with_name("oracle.py"))
ai=importlib.util.module_from_spec(spec)
spec.loader.exec_module(ai)


def make_case(index):
    rng=random.Random(0x4ec720+index)
    case=ai.varied_case(index+1)
    if index%2==0:
        case["tiles"]=[0]*(case["width"]*case["height"])
        case["points"]=[];case["regions"]=[]
    case["funds"]=[rng.choice([0,3,10,50]),rng.choice([0,5,25])]
    for unit in case["units"]:
        unit["transform_capability"]=rng.choice([0,1,1,255])
        unit["upgrade_cost"]=rng.choice([0,2,5,10,255])
        # Keep all synthetic movement costs positive to avoid an original
        # zero-cost recursive gradient cycle, a separate unsupported boundary.
        for form in unit["forms"]:
            if form[0]==255:form[0]=3
            form[12]=1 if index%13==0 else 0
    a=case["units"][case["actor"]]
    actor_slots=[u["type"] for u in sorted(case["units"],key=lambda u:u["type"]) if u["owner"]==a["owner"]]
    case["upgrade_slots"]=[-1,-1]
    if index%3:
        case["upgrade_slots"][case["current"]]=actor_slots.index(a["type"])
    return case


def execute(image,gcc,case,entry):
    old=ai.OriginalAI(image,gcc)
    old.configure_ai(case)
    actor=old.units[case["actor"]]
    address=old.call_bounded(entry,[old.map,actor])
    value={"plan":old.plan(address),"form_after":old.r8(actor+12),"stats_after":old.unit_result(actor)[:3]}
    old.check_text()
    return value,old.calls


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--binary",type=Path,required=True)
    p.add_argument("--libgcc",type=Path,required=True)
    p.add_argument("--unicorn-dir",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--fixture",type=Path,required=True)
    p.add_argument("--count",type=int,default=128)
    a=p.parse_args()
    if not 1<=a.count<=256:p.error("count must be1..256")
    sys.path.insert(0,str(a.unicorn_dir))
    image,gcc=a.binary.read_bytes(),a.libgcc.read_bytes()
    if ai.combat.sha(image)!=ai.combat.IMAGE_SHA or ai.combat.sha(gcc)!=ai.combat.LIBGCC_SHA:
        raise ValueError("original inputs differ")
    rows=[];calls=Counter()
    for index in range(a.count):
        case=make_case(index)
        result,used=ai.original_result(image,gcc,case,index,budget_override=2)
        calls.update(used)
        for key,entry in (("fallback",0x4ec72),("decision",0x512e6)):
            value,used=execute(image,gcc,case,entry)
            result[key]=value;calls.update(used)
        rows.append((case,result))
    ai.write_fixture(a.fixture,rows)
    report={"original_sha256":ai.combat.sha(image),"libgcc_sha256":ai.combat.sha(gcc),
            "case_count":len(rows),"original_text_unchanged":True,
            "whole_original_functions":["0x4ec72","0x512e6"],
            "gameplay_function_replacements":0,"rng_substitutions":0,
            "infrastructure_boundaries":{hex(k):v for k,v in ai.INFRASTRUCTURE.items()},
            "fixture_sha256":ai.combat.sha(a.fixture.read_bytes()),
            "oracle_sha256":ai.combat.sha(Path(__file__).read_bytes()),
            "shared_oracle_sha256":ai.combat.sha(Path(__file__).with_name("oracle.py").read_bytes()),
            "calls":dict(calls),"cases":[{"input":c,"output":r} for c,r in rows]}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"cases":len(rows),"fallback_plans":sum(r["fallback"]["plan"] is not None for _,r in rows),
        "decision_plans":sum(r["decision"]["plan"] is not None for _,r in rows),
        "fallback_form_changes":sum(r["fallback"]["form_after"]!=c["units"][c["actor"]]["form"] for c,r in rows)}))


if __name__=="__main__":main()
