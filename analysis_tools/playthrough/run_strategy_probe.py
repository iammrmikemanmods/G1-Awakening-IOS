#!/usr/bin/env python3
"""Run the native public-command pilot; never edit a checkpoint or game data.

This is a development tool, not linked into the iOS application. The caller
supplies its locally rebuilt native pilot and original archive/table data.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def file_record(path):
    data = path.read_bytes()
    return {"path": str(path), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--terrain-tables", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=60)
    parser.add_argument("--human-turns", type=int, default=150)
    args = parser.parse_args()
    pilot, archive, tables = [p.resolve(strict=True) for p in
                              (args.pilot, args.archive, args.terrain_tables)]
    output = args.output.resolve()
    if output.exists():
        parser.error("--output must be a new directory; earlier results are preserved")
    records = {"pilot": file_record(pilot), "archive": file_record(archive),
               "terrain_tables": file_record(tables)}
    expected = {
        "archive": "663d2888982093ce66b7811ccb7a6ad3acd37fc02ffa85144775b88c39e83cb4",
        "terrain_tables": "b870e3d74244741003c8068178e7f58bb5fbe35599599c918e024227463725a8",
    }
    for key, digest in expected.items():
        if records[key]["sha256"] != digest:
            parser.error(f"{key} differs from the documented original-data reference")
    command = [str(pilot), "--archive", str(archive), "--terrain-tables", str(tables),
               "--output", str(output), "--strategy", "native-planner-tactical",
               "--group", "0", "--start-mission", "0", "--seed", "0x4741",
               "--max-missions", "17", "--max-ticks", "200000",
               "--max-human-turns", str(args.human_turns),
               "--max-seconds", str(args.seconds)]
    completed = subprocess.run(command, check=False, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    evidence = {"schema": 1, "command": command, "inputs": records,
                "returncode": completed.returncode, "stdout": completed.stdout,
                "stderr": completed.stderr, "native_gameplay_core_used": True,
                "original_executable_executed": False,
                "presentation_feedback": "synthetic; not rendered/device validation",
                "gameplay_state_forced": False}
    if not output.is_dir():
        print(json.dumps(evidence, indent=2), file=sys.stderr)
        return completed.returncode or 1
    result_path = output / "result.json"
    if result_path.is_file():
        result = json.loads(result_path.read_text())
        handoffs = result.get("native_handoffs", [])
        successes = [x["index"] for x in handoffs if x["handoff"] == "next_mission"]
        evidence["result"] = file_record(result_path)
        evidence["observed"] = {
            "outcome": result["outcome"], "error": result["error"],
            "successful_story_indices": successes,
            "continuous_prefix": successes == list(range(len(successes))),
            "final_mission": result["final"]["mission"],
            "profile_writes": result["profile_writes"],
            "live_checkpoint_matches": result["escape_search"]["live_replay_checkpoint_matches"],
            "full_story_completed": result["outcome"] == "native_campaign_ending"
                and bool(result["persisted_profile"]["completed"][0]),
        }
        if result["gameplay_state_forced"] or result["device_or_rendered_playthrough"]:
            raise RuntimeError("pilot result conflicts with the declared validation scope")
    (output / "reproduction.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(completed.stdout, end="")
    print(completed.stderr, end="", file=sys.stderr)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
