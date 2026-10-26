#!/usr/bin/env python3
"""Create synthetic reference inputs and export original ARM outputs as native fixtures."""
import argparse
import json
from pathlib import Path
import random


def basic(name, width=5, height=5, budget=3, cost=1):
    x, y = width // 2, height // 2
    owners = [None] * (width * height)
    owners[y * width + x] = 0
    return {"name": name, "width": width, "height": height,
            "terrain": [[cost, 0] for _ in owners], "active_owners": owners,
            "points": [], "rectangles": [],
            "unit": {"x": x, "y": y, "type": 0, "owner": 0, "form": 0,
                     "base_budget": budget, "spent_budget": 0, "field6": 0}}


def cases():
    result = []
    for name, w, h, budget, cost in [
        ("open_diamond", 5, 5, 2, 1), ("single_occupied", 1, 1, 4, 1),
        ("zero_budget", 3, 3, 0, 1), ("zero_cost_connected", 4, 3, 0, 0),
        ("costly_first_step", 5, 1, 2, 7), ("raw_terrain99_origin", 3, 3, 4, 99),
        ("budget127", 3, 1, 127, 1), ("budget128", 3, 1, 128, 1),
        ("budget255", 4, 2, 255, 4), ("cost255_budget2", 3, 3, 2, 255),
        ("signed_base128_cost255", 3, 3, 128, 255)]:
        result.append(basic(name, w, h, budget, cost))
    c = basic("spent_prevents_first_step", 3, 1, 2, 7)
    c["unit"]["spent_budget"] = 1
    result.append(c)
    c = basic("spent_byte_wrap", 3, 2, 2, 100)
    c["unit"]["spent_budget"] = 3
    result.append(c)
    c = basic("unoccupied_origin_zero_budget", 3, 3, 0)
    c["active_owners"] = [None] * 9
    result.append(c)
    c = basic("friendly_and_enemy", 5, 3, 4)
    c["active_owners"][6], c["active_owners"][8] = 0, 1
    result.append(c)
    for special in [-128, -1, 0, 1, 127]:
        c = basic(f"field6_{special}", 5, 3, 3)
        c["unit"]["field6"] = special
        c["active_owners"][8] = 1
        c["terrain"][8] = [99, 0]
        c["terrain"][6] = [7, 1]
        result.append(c)
    for special in [0, 1]:
        c = basic(f"type11_field6_{special}", 5, 3, 3, 7)
        c["unit"]["type"], c["unit"]["field6"] = 11, special
        c["terrain"][8], c["terrain"][6] = [99, 1], [99, 0]
        c["active_owners"][2] = 1
        result.append(c)
    for state in [-1, 0, 1, 2]:
        c = basic(f"point_state_{state}", 5, 1, 3)
        c["points"] = [[3, 0, state], [1, 0, state]]
        result.append(c)
    for special in [0, 1]:
        c = basic(f"region_field6_{special}", 5, 5, 3)
        c["rectangles"] = [[0, 0, 2, 2], [3, 0, 2, 5]]
        c["unit"]["field6"] = special
        result.append(c)
    c = basic("region99_large_budget", 5, 1, 255)
    c["rectangles"] = [[3, 0, 1, 1]]
    result.append(c)
    c = basic("region_empty_and_negative", 5, 3, 3)
    c["rectangles"] = [[1, 1, 0, 3], [4, 0, -2, 2], [-1, -1, 2, 2]]
    result.append(c)
    c = basic("alternate_route_improves_budget", 5, 5, 7)
    c["terrain"] = [[v, 0] for v in
                    [1, 1, 1, 1, 1, 1, 7, 7, 7, 1, 1, 1, 1, 7, 1,
                     1, 7, 7, 7, 1, 1, 1, 1, 1, 1]]
    result.append(c)

    rng = random.Random(0x473141)
    for number in range(225):
        w, h = rng.randint(1, 7), rng.randint(1, 7)
        c = basic(f"seeded_{number:03d}", w, h, rng.randint(0, 9))
        p = c["unit"]
        p["x"], p["y"] = rng.randrange(w), rng.randrange(h)
        p["type"], p["owner"], p["form"] = rng.choice([0, 5, 11, 17]), rng.randrange(2), rng.randrange(2)
        p["field6"] = rng.choice([-1, 0, 0, 0, 1, 2])
        p["spent_budget"] = rng.randint(0, p["base_budget"])
        c["terrain"] = [[rng.choice([0, 1, 1, 1, 2, 3, 7, 99]), rng.randrange(2)]
                        for _ in range(w * h)]
        c["active_owners"] = [rng.choice([None, None, None, None, 0, 1]) for _ in range(w * h)]
        c["active_owners"][p["y"] * w + p["x"]] = p["owner"]
        c["points"] = [[rng.randrange(w), rng.randrange(h), rng.choice([0, 1, -1])]
                       for _ in range(rng.randint(0, 2))]
        c["rectangles"] = [[rng.randrange(w), rng.randrange(h), rng.randint(0, 3), rng.randint(0, 3)]
                           for _ in range(rng.randint(0, 2))]
        result.append(c)
    return result


def export_fixtures(source, oracle, output):
    results = {r["name"]: r for r in oracle["results"]}
    lines = ["G1_MOVEMENT_ORACLE_V1", str(len(source["cases"]))]
    for case in source["cases"]:
        p, result = case["unit"], results[case["name"]]
        lines.append(case["name"])
        lines.append(" ".join(map(str, [case["width"], case["height"], p["x"], p["y"],
                     p["type"], p["owner"], p["base_budget"], p["spent_budget"], p["field6"], p["form"]])))
        for terrain, owner in zip(case["terrain"], case["active_owners"]):
            lines.append(f"{terrain[0]} {terrain[1]} {-1 if owner is None else owner}")
        lines.append(str(len(case["points"])))
        lines.extend(" ".join(map(str, record)) for record in case["points"])
        lines.append(str(len(case["rectangles"])))
        lines.extend(" ".join(map(str, record)) for record in case["rectangles"])
        lines.append(f"{result['remaining_budget']} {int(result['has_unoccupied_destination'])}")
        for key in ["remaining", "entry_costs", "out_of_bounds_costs"]:
            lines.append(" ".join(map(str, result[key])))
    output.write_text("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--oracle", type=Path)
    parser.add_argument("--fixture", type=Path)
    args = parser.parse_args()
    if args.oracle:
        export_fixtures(json.loads(args.cases.read_text()), json.loads(args.oracle.read_text()), args.fixture)
    else:
        args.cases.parent.mkdir(parents=True, exist_ok=True)
        args.cases.write_text(json.dumps({"seed": "0x473141", "cases": cases()}, indent=2) + "\n")


if __name__ == "__main__":
    main()
