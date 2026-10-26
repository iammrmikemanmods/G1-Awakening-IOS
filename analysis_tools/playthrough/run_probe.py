#!/usr/bin/env python3
"""Run the development-only native gameplay input pilot and record provenance.

This runner does not build an app, use the original CPU, alter a saved game,
change gameplay state, or upload anything. Its child probe uses public native
GameSession commands. Presentation feedback is explicitly synthetic.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys


ARCHIVE_SHA256 = "663d2888982093ce66b7811ccb7a6ad3acd37fc02ffa85144775b88c39e83cb4"
STRATEGIES = (
    "direct", "economy", "coordinated", "coordinated-economy",
    "native-planner", "native-planner-search",
)


def digest(path: Path) -> dict[str, int | str]:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def source_files(root: Path) -> dict[str, dict[str, int | str]]:
    result = {}
    for directory in ("include", "src", "tools", "third_party"):
        for path in sorted((root / directory).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                result[str(path.relative_to(root))] = digest(path)
    cmake = root / "CMakeLists.txt"
    if cmake.is_file():
        result["CMakeLists.txt"] = digest(cmake)
    if "tools/session_playthrough_probe.cpp" not in result:
        raise ValueError("--native-source must contain tools/session_playthrough_probe.cpp")
    return result


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", required=True, type=Path, help="Already-built native host executable")
    parser.add_argument("--native-source", required=True, type=Path, help="Matching native source directory")
    parser.add_argument("--archive", required=True, type=Path, help="Local audited iphone.big; never uploaded")
    parser.add_argument("--terrain-tables", required=True, type=Path, help="Local 480-byte visual table data")
    parser.add_argument("--output", required=True, type=Path, help="Must be a new directory")
    parser.add_argument("--strategy", choices=STRATEGIES, default="native-planner-search")
    parser.add_argument("--matrix", action="store_true", help="30 isolated starts, not a completed campaign")
    parser.add_argument("--group", type=int, choices=(0, 1, 2), default=0)
    parser.add_argument("--start-mission", type=int, default=0)
    parser.add_argument("--seed", default="0x4741")
    parser.add_argument("--max-missions", type=int, default=17)
    parser.add_argument("--max-ticks", type=int, default=200000)
    parser.add_argument("--max-human-turns", type=int, default=500)
    parser.add_argument("--max-seconds", type=float, default=90)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    for name in ("probe", "native_source", "archive", "terrain_tables", "output"):
        setattr(args, name, getattr(args, name).resolve())
    if digest(args.archive)["sha256"] != ARCHIVE_SHA256:
        raise ValueError("Archive does not match the audited 1.1.3 resource set")
    if args.terrain_tables.stat().st_size != 480:
        raise ValueError("Terrain table input must be exactly 480 bytes")
    if min(args.max_missions, args.max_ticks, args.max_human_turns, args.max_seconds) <= 0:
        raise ValueError("All run bounds must be positive")
    source_before = source_files(args.native_source)
    binary_before = digest(args.probe)
    inputs = {
        "archive": {"path": str(args.archive), **digest(args.archive)},
        "terrain_tables": {"path": str(args.terrain_tables), **digest(args.terrain_tables)},
    }
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = {
        "scope": "native headless gameplay command integration; not a rendered/device playthrough",
        "presentation_feedback": "synthetic",
        "gameplay_state_forced": False,
        "source_hashes": source_before,
        "probe": {"path": str(args.probe), **binary_before},
        "inputs": inputs,
        "build_attestation": "Executable hash is authoritative; build separately from the recorded sources.",
        "matrix": args.matrix,
    }
    write_json(args.output / "provenance.json", manifest)
    if args.matrix:
        entries = [(group, index) for group, count in enumerate((17, 8, 5)) for index in range(count)]
    else:
        entries = [(args.group, args.start_mission)]
    runs = []
    for group, index in entries:
        output = args.output / (f"g{group}_m{index:02d}" if args.matrix else "continuous")
        command = [
            str(args.probe), "--archive", str(args.archive),
            "--terrain-tables", str(args.terrain_tables), "--output", str(output),
            "--strategy", args.strategy, "--group", str(group), "--start-mission", str(index),
            "--seed", args.seed, "--max-missions", "1" if args.matrix else str(args.max_missions),
            "--max-ticks", str(args.max_ticks), "--max-human-turns", str(args.max_human_turns),
            "--max-seconds", str(args.max_seconds),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=args.max_seconds + 20)
        row = {
            "group": group, "start_mission": index, "command": command,
            "returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr,
        }
        result_path = output / "result.json"
        if result_path.is_file():
            row["result"] = json.loads(result_path.read_text(encoding="utf-8"))
            row["result_file"] = digest(result_path)
            row["events_file"] = digest(output / "events.jsonl")
        runs.append(row)
        write_json(args.output / "results.json", {
            "scope": "30 isolated starts, not a completed campaign" if args.matrix else "continuous native campaign attempt",
            "runs": runs,
        })
        result = row.get("result", {})
        print(f"group={group} mission={index} outcome={result.get('outcome', 'no_result')}", flush=True)
    unchanged = source_before == source_files(args.native_source) and binary_before == digest(args.probe)
    errors = [row for row in runs if row["returncode"] or "result" not in row]
    summary = {
        "run_count": len(runs), "source_and_executable_unchanged": unchanged,
        "outcomes": dict(Counter(row.get("result", {}).get("outcome", "no_result") for row in runs)),
        "process_or_core_errors": len(errors), "presentation_feedback": "synthetic",
        "complete_rendered_campaign_verified": False, "iphone_xr_verified": False,
    }
    write_json(args.output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0 if unchanged and not errors else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"run_probe.py: {error}", file=sys.stderr)
        raise SystemExit(2)
