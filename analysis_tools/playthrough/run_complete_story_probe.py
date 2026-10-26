#!/usr/bin/env python3
"""Reproduce the bounded native Story pilot and record its exact evidence scope."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def identity(path):
    path = path.resolve()
    data = path.read_bytes()
    return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--terrain-tables", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=120)
    parser.add_argument("--human-turns", type=int, default=150)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Output directory must not already exist")
    inputs = {"pilot": identity(args.pilot), "archive": identity(args.archive),
              "terrain_tables": identity(args.terrain_tables)}
    command = [str(args.pilot.resolve()), "--archive", str(args.archive.resolve()),
               "--terrain-tables", str(args.terrain_tables.resolve()),
               "--output", str(args.output.resolve()),
               "--strategy", "native-planner-tactical", "--followup-policy", "aggressive",
               "--group", "0", "--start-mission", "0", "--seed", "0x4741",
               "--max-missions", "17", "--max-ticks", "200000",
               "--max-human-turns", str(args.human_turns), "--max-seconds", str(args.seconds)]
    run = subprocess.run(command, capture_output=True, text=True, timeout=args.seconds + 30)
    result_path = args.output / "result.json"
    result = json.loads(result_path.read_text()) if result_path.exists() else {}
    handoffs = result.get("native_handoffs", [])
    completed = (run.returncode == 0 and result.get("outcome") == "native_campaign_ending"
                 and result.get("error") == "" and result.get("start_mode") == "fresh_campaign"
                 and result.get("start_mission") == 0 and result.get("resume_input") == ""
                 and result.get("gameplay_state_forced") is False
                 and len(handoffs) == 17
                 and all(h.get("group") == 0 and h.get("index") == i
                         and h.get("handoff") == ("campaign_ending" if i == 16 else "next_mission")
                         and h.get("profile_written") is True for i, h in enumerate(handoffs))
                 and result.get("persisted_profile", {}).get("completed", [False])[0] is True)
    record = {"schema": 1, "command": command, "inputs": inputs,
              "returncode": run.returncode, "stdout": run.stdout, "stderr": run.stderr,
              "native_gameplay_core_used": True, "original_executable_executed": False,
              "gameplay_state_forced": False,
              "presentation_feedback": "synthetic; no rendered/GPU/audio/device validation",
              "result": identity(result_path) if result_path.exists() else None,
              "events": identity(args.output / "events.jsonl") if (args.output / "events.jsonl").exists() else None,
              "observed": {"outcome": result.get("outcome"), "error": result.get("error"),
                           "continuous_story_indices": [h.get("index") for h in handoffs],
                           "profile_file_writes": result.get("profile_writes"),
                           "checkpoint_file_writes": result.get("checkpoint_writes"),
                           "in_memory_checkpoint_matches": result.get("escape_search", {}).get("live_replay_checkpoint_matches"),
                           "full_story_headless_completed": completed,
                           "full_device_playthrough_verified": False}}
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "reproduction.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record["observed"], indent=2))
    return 0 if completed else 1


if __name__ == "__main__":
    raise SystemExit(main())
