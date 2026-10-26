#!/usr/bin/env python3
"""Unchanged-original development reference for capture planning and income.

Imports the shared bounded ARM oracle. No guest code or original executable is
part of the native app. Reference fixtures contain synthetic game state only.
"""
import argparse
from collections import Counter
import copy
import importlib.util
import json
from pathlib import Path
import random
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("ai_reference", HERE / "oracle.py")
ai = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ai)


def case_for(index):
    if index < 192:
        case = ai.simple_case() if index == 0 else ai.varied_case(index)
        if index % 9 == 0:
            case["current"] ^= 1  # Original actor-owner baseline/current-player distinction.
        return case
    rng = random.Random(0x508a200 + index)
    case = ai.simple_case()
    actor = case["units"][0]
    actor["forms"][0][0] = 4
    actor["forms"][0][10] = [0, 1, 255][index % 3]
    actor["forms"][1][10] = [0, 1, 255][(index // 3) % 3]
    actor["form"] = index % 2
    actor["spent"] = [0, 1, 3, 4, 5, 255][index % 6]
    case["current"] = (index // 2) % 2
    case["factions"] = ([0, 1], [1, 0], [0, 0], [-1, -1])[index % 4]
    case["counters"] = [[0, 0], [1, 1], [7, 19], [2147483647, -2147483648]][index % 4]
    for u in case["units"]:
        u["offset_x"] = 3 if index % 7 == 0 else 0
    case["sites"] = []
    for s in range(3):
        coordinates = ([0, 0], [1, 0], [2, 1], [128, 0], [255, 255], [3, 3])
        site = {"owner": rng.choice([-1, 0, 1]), "xy": list(coordinates[(index+s) % 6]), "groups": []}
        for g in range(2):
            group = []
            for i in range(3):
                group.append({"owner": rng.choice([-1, 0, 1]), "link": rng.randrange(2),
                              "xy": list(coordinates[(index+s+g+i) % 6])})
            site["groups"].append(group)
        case["sites"].append(site)
    return case


def network_state(old, case):
    counters = old.r32(old.map + 0x68)
    result = [old.r32(counters), old.r32(counters+4)]
    site_owners = old.r32(old.map+0x3e8)
    item_owners = old.r32(old.map+0x3f8)
    item_links = old.r32(old.map+0x408)
    for s, site in enumerate(case["sites"]):
        result.append(old.r8(site_owners+s))
        groups = old.r32(item_owners+s*8)
        links = old.r32(item_links+s*8)
        for g, group in enumerate(site["groups"]):
            owners = old.r32(groups+g*8)
            connected = old.r32(links+g*8)
            for i in range(len(group)):
                result.extend([old.r8(owners+i), old.r8(connected+i)])
    for pointer in old.units:
        result.extend(old.u.mem_read(pointer, 0x60))
    return result


def original_result(image, gcc, case, index):
    old = ai.OriginalAI(image, gcc)
    old.configure_ai(case)
    before = network_state(old, case)
    pointer = old.call(0x508a2, [old.map, old.units[case["actor"]]])
    result = {"plan": old.plan(pointer), "income_queries": []}
    if network_state(old, case) != before:
        raise RuntimeError("original capture planner changed network or unit state")
    # Explicit stale/overflow baselines are intentional: helpers do not obtain
    # these from recomputed income, and callers pass already stored counters.
    for s, site in enumerate(case["sites"]):
        targets = [(0, s, 0, 0)]
        for g, group in enumerate(site["groups"]):
            targets.extend((1, s, g, i) for i in range(len(group)))
        for k, s, g, i in targets:
            owner = (index+s+g+i) % 2
            own, other = case["counters"]
            args = [old.map, owner, own, other, s]
            if k:
                args.extend([g, i])
            value = ai.combat.signed(old.call(0x4b452 if k else 0x4b56c, args))
            result["income_queries"].append([k, s, g, i, owner, own, other, value])
            if network_state(old, case) != before:
                raise RuntimeError("original income helper failed to restore network or units")
    old.check_text()
    return result, old.calls


def write_fixture(path, cases):
    # This dedicated schema is independent of the attack/turn fixture writer.
    # Only synthetic inputs and unchanged-original results are serialized.
    rows = ["G1_AI_SITE_V1"]
    def row(tag, values):
        rows.append(tag + " " + " ".join(map(str, values)))
    for index, (case, result) in enumerate(cases):
        row("C", [index, case["width"], case["height"], case["actor"], case["current"],
                  int(case["flag227"]), *case["factions"], *case["controllers"],
                  *case["counters"], len(case["units"]), len(case["sites"])])
        row("G", case["tiles"])
        row("L", case["lookup"])
        row("T", [len(case["rules"]), *[v for rule in case["rules"] for v in rule]])
        for u in case["units"]:
            row("U", [u[k] for k in ("type", "owner", "faction", "form", "level", "health", "active",
                                     "immune", "flag38", "support", "timer", "preset", "x", "y")] +
                     [u.get(k, 0) for k in ("spent", "acted", "offset_x", "offset_y")] +
                     u["modifiers"] + [v for form in u["forms"] for v in form])
        for site in case["sites"]:
            row("S", [site["owner"], *site["xy"], len(site["groups"])])
            for group in site["groups"]:
                row("I", [len(group), *[v for item in group for v in
                         (item["owner"], item.get("link", 0), *item["xy"])]])
        row("P", [len(case.get("points", [])), *[v for point in case.get("points", []) for v in point]])
        row("R", [len(case.get("regions", [])), *[v for region in case.get("regions", []) for v in region]])
        row("A", [0] if result["plan"] is None else [1, *result["plan"]])
        row("I", [len(result["income_queries"]), *[v for query in result["income_queries"] for v in query]])
    rows.append("END")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--libgcc", type=Path, required=True)
    parser.add_argument("--unicorn-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--count", type=int, default=256)
    args = parser.parse_args()
    sys.path.insert(0, str(args.unicorn_dir))
    image, gcc = args.binary.read_bytes(), args.libgcc.read_bytes()
    if ai.combat.sha(image) != ai.combat.IMAGE_SHA or ai.combat.sha(gcc) != ai.combat.LIBGCC_SHA:
        raise ValueError("wrong original input")
    if not 1 <= args.count <= 512:
        parser.error("count must be1..512")
    cases, calls = [], Counter()
    for index in range(args.count):
        case = case_for(index)
        result, used = original_result(image, gcc, case, index)
        cases.append((copy.deepcopy(case), result))
        calls.update(used)
    args.fixture.parent.mkdir(parents=True, exist_ok=True)
    write_fixture(args.fixture, cases)
    result = {"schema":"g1.native.ai-site-original.v1", "original_sha256":ai.combat.sha(image),
              "libgcc_sha256":ai.combat.sha(gcc), "oracle_sha256":ai.combat.sha(Path(__file__).read_bytes()),
              "shared_oracle_sha256":ai.combat.sha((HERE/"oracle.py").read_bytes()),
              "combat_oracle_sha256":ai.combat.sha((HERE.parent/"combat/oracle.py").read_bytes()),
              "original_text_unchanged":True, "original_game_function_replacements":0,
              "infrastructure_boundaries":{hex(k):v for k,v in ai.INFRASTRUCTURE.items()},
              "case_count":len(cases), "network_and_unit_state_restored":True,
              "income_query_count":sum(len(r["income_queries"]) for _,r in cases),
              "calls":dict(calls), "fixture_sha256":ai.combat.sha(args.fixture.read_bytes()),
              "cases":[{"input":c,"output":r} for c,r in cases]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps({"cases":len(cases), "viable_capture_plans":sum(r["plan"] is not None for _,r in cases),
                      "income_queries":result["income_query_count"], "calls":dict(calls)}))


if __name__ == "__main__":
    main()
