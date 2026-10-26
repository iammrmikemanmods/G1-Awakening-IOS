#!/usr/bin/env python3
"""Original AI comparisons using previously verified first-world source data.

The saved world probe input is hash-recorded and contains the independently
validated first grid/definitions/sites. AI turn, funds and listed scenario
changes are explicit test seeds, not observations of a live campaign turn.
The resulting fixture contains original data and must remain outside Git.
"""
import argparse
from collections import Counter
import copy
import importlib.util
import json
from pathlib import Path
import sys

spec=importlib.util.spec_from_file_location("planner_reference",Path(__file__).with_name("planner_oracle.py"))
planner=importlib.util.module_from_spec(spec);spec.loader.exec_module(planner)
ai=planner.ai


def seed(source):
    live={u["type"]:u for u in source["units"]}
    c={"width":source["width"],"height":source["height"],"tiles":source["tiles"],
       "lookup":source["effective_lookup"],"rules":source["terrain_rules"],"units":[],
       "current":1,"controllers":[0,1],"factions":source["player_factions"],
       "flag227":0,"counters":[1,1],"funds":[0,0],"upgrade_slots":[-1,-1],
       "available":[int(t in source["available_types"]) for t in range(23)],"sites":[],"actor":19}
    for d in source["definitions"]:
        t=d["type"];u=live.get(t)
        faction=d["scalar_fields"][0]
        c["units"].append({"type":t,"owner":c["factions"].index(faction),"faction":faction,
            "x":u["x"] if u else 0,"y":u["y"] if u else 0,"form":u["form"] if u else 0,
            "level":0,"health":100,"active":int(u is not None),"immune":0,"flag38":0,
            "support":0,"timer":-1,"preset":-1,"spent":0,"acted":0,"offset_x":0,"offset_y":0,
            "modifiers":d["scalar_fields"][3:5],"upgrade_cost":d["scalar_fields"][1],
            "transform_capability":d["scalar_fields"][2],"forms":d["forms"]})
    for s in source["sites"]:
        c["sites"].append({"owner":s["state"],"xy":[s["x"],s["y"]],
            "groups":[[{"owner":-1,"link":0,"xy":point} for point in g] for g in s["coordinate_groups"]]})
    return c


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("binary","libgcc","unicorn-dir","world-json","output","fixture"):
        p.add_argument("--"+name,type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.unicorn_dir))
    image,gcc=a.binary.read_bytes(),a.libgcc.read_bytes()
    if ai.combat.sha(image)!=ai.combat.IMAGE_SHA or ai.combat.sha(gcc)!=ai.combat.LIBGCC_SHA:
        raise ValueError("wrong original input")
    source=json.loads(a.world_json.read_text())
    if (source["mission_resource_id"],source["grid_resource_id"],len(source["definitions"]))!=(315,268,23):
        raise ValueError("unexpected first-world source metadata")
    base=seed(source);cases=[];calls=Counter();descriptions=[]
    for i in range(8):
        c=copy.deepcopy(base)
        notes=["AI player1 and income counters1/1 are explicit seeds"]
        if i&1:
            c["units"][11]["x"],c["units"][11]["y"]=3,7
            notes.append("Bumblebee relocatedadjacent to type19")
        if i&2:
            for site in c["sites"]:
                site["owner"]=1
                for group in site["groups"]:
                    for item in group:item["owner"]=1
            notes.append("all initial sites/items seeded owner1")
        if i&4:
            c["funds"][1]=25
            slots=[u["type"] for u in c["units"] if u["owner"]==1]
            c["upgrade_slots"][1]=slots.index(19)
            notes.append("funds25 and upgrade slotfor type19")
        result,used=ai.original_result(image,gcc,c,i,budget_override=2);calls.update(used)
        for key,entry in (("fallback",0x4ec72),("decision",0x512e6)):
            result[key],used=planner.execute(image,gcc,c,entry);calls.update(used)
        cases.append((c,result));descriptions.append(notes)
    ai.write_fixture(a.fixture,cases)
    report={"original_sha256":ai.combat.sha(image),"libgcc_sha256":ai.combat.sha(gcc),
        "source_world_json_sha256":ai.combat.sha(a.world_json.read_bytes()),
        "source_world_input":"research/binary/native_world/native_world_actual.json",
        "mission_resource_id":315,"grid_resource_id":268,"definitions":23,
        "case_count":len(cases),"native_expected_values_from_original_execution":True,
        "source_data_fixture_excluded_from_git":True,"live_campaign_turn_observed":False,
        "original_text_unchanged":True,"original_gameplay_function_replacements":0,
        "fixture_sha256":ai.combat.sha(a.fixture.read_bytes()),"calls":dict(calls),
        "scenarios":[{"changes":notes,"result":r} for notes,(_,r) in zip(descriptions,cases)],
        "oracle_sha256":ai.combat.sha(Path(__file__).read_bytes()),
        "shared_oracle_sha256":ai.combat.sha(Path(__file__).with_name("oracle.py").read_bytes())}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"cases":len(cases),"plans":[r["decision"]["plan"] for _,r in cases]}))


if __name__=="__main__":main()
