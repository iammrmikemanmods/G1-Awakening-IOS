#!/usr/bin/env python3
"""Run a native mode through actual saved-profile admission and record its scope."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import zlib


def identity(path):
    path = path.resolve()
    data = path.read_bytes()
    return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def profile(path):
    data = path.read_bytes()
    if len(data) != 330 or data[:8] != b"G1NPROF\0":
        raise ValueError("Invalid native profile signature/size")
    if struct.unpack_from("<II", data, 8) != (1, 330):
        raise ValueError("Invalid native profile version/declared size")
    if zlib.adler32(data[:-4]) != struct.unpack_from("<I", data, 326)[0]:
        raise ValueError("Native profile checksum mismatch")
    if any(x not in (0, 1) for x in data[16:18]):
        raise ValueError("Invalid native profile flag")
    return {"completed": [bool(x) for x in data[16:18]],
            "highest_unlocked": list(struct.unpack_from("<ii", data, 18)),
            "records": [list(struct.unpack_from("<iii", data, 26 + i*12)) for i in range(25)]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--terrain-tables", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--group", type=int, choices=(1, 2), required=True)
    parser.add_argument("--mission", type=int, default=0)
    parser.add_argument("--faction", type=int, choices=(0, 1), default=0)
    parser.add_argument("--opponent", type=int, choices=(0, 1), default=1)
    parser.add_argument("--strategy", default="tactical-search")
    parser.add_argument("--policy", default="aggressive")
    parser.add_argument("--seconds", type=float, default=90)
    parser.add_argument("--human-turns", type=int, default=180)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Output directory must not already exist")
    initial = profile(args.profile)
    if not initial["completed"][args.group - 1]:
        raise SystemExit("Mode is not unlocked in the actual supplied profile")
    inputs = {"pilot": identity(args.pilot), "archive": identity(args.archive),
              "terrain_tables": identity(args.terrain_tables), "profile": identity(args.profile)}
    command = [str(args.pilot.resolve()), "--archive", str(args.archive.resolve()),
               "--terrain-tables", str(args.terrain_tables.resolve()),
               "--initial-profile", str(args.profile.resolve()),
               "--output", str(args.output.resolve()),
               "--strategy", args.strategy, "--followup-policy", args.policy,
               "--group", str(args.group), "--start-mission", str(args.mission),
               "--arena-faction", str(args.faction), "--arena-opponent", str(args.opponent),
               "--seed", "0x4741", "--max-missions", "8" if args.group == 1 else "1",
               "--max-ticks", "200000", "--max-human-turns", str(args.human_turns),
               "--max-seconds", str(args.seconds)]
    run = subprocess.run(command, capture_output=True, text=True, timeout=args.seconds + 30)
    result_path = args.output / "result.json"
    result = json.loads(result_path.read_text()) if result_path.exists() else {}
    final_path = args.output / "campaign.g1native"
    final_profile = profile(final_path) if final_path.exists() else None
    story_preserved = bool(final_profile and initial["completed"][0] == final_profile["completed"][0]
        and initial["highest_unlocked"][0] == final_profile["highest_unlocked"][0]
        and initial["records"][:17] == final_profile["records"][:17])
    hands = result.get("native_handoffs", [])
    showdown_completed = (args.group == 1 and args.mission == 0 and len(hands) == 8
        and all(h["group"] == 1 and h["index"] == i and h["profile_written"]
                and h["handoff"] == ("campaign_ending" if i == 7 else "next_mission")
                for i, h in enumerate(hands))
        and result.get("outcome") == "native_campaign_ending"
        and final_profile and final_profile["completed"][1] and story_preserved)
    arena_finished = (args.group == 2 and len(hands) == 1 and hands[0]["group"] == 2
        and hands[0]["index"] == args.mission and hands[0]["handoff"] == "campaign_menu"
        and hands[0]["profile_written"] and result.get("outcome") == "native_arena_finished"
        and final_profile == initial)
    observed = {"outcome": result.get("outcome"), "error": result.get("error"),
                "handoffs": hands, "initial_profile": initial, "final_profile": final_profile,
                "story_records_preserved": story_preserved,
                "complete_showdown_headless": bool(showdown_completed),
                "arena_headless_finished": bool(arena_finished),
                "device_playthrough_verified": False}
    record = {"schema": 1, "command": command, "inputs": inputs,
              "returncode": run.returncode, "stdout": run.stdout, "stderr": run.stderr,
              "presentation_feedback": "synthetic; not GPU/audio/device validation",
              "native_gameplay_core_used": True, "original_executable_executed": False,
              "gameplay_state_forced": False, "unlock_flags_forced": False,
              "result": identity(result_path) if result_path.exists() else None,
              "events": identity(args.output / "events.jsonl") if (args.output / "events.jsonl").exists() else None,
              "observed": observed}
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "reproduction.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({k:v for k,v in observed.items() if k not in ("initial_profile", "final_profile", "handoffs")}, indent=2))
    return 0 if run.returncode == 0 and (showdown_completed or arena_finished) else 1


if __name__ == "__main__":
    raise SystemExit(main())
