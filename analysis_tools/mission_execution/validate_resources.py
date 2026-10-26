#!/usr/bin/env python3
"""Independent local archive/text comparison and explicit control-flow fixture.

No original game payload is embedded. The probe's renderer/capture observations
are deliberately synthetic and do not demonstrate capture, UI or a playthrough.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import zlib

ARCHIVE_SHA = "663d2888982093ce66b7811ccb7a6ad3acd37fc02ffa85144775b88c39e83cb4"
TEXT_SHA = "8c189a68d0d31b53d08b88438fa0df06c88196bf446a43801ae332039c4f452a"
MISSION_SHA = "7ecc54a292717325b9e6e2c44c3c166e44be296b2e408c42b76cc49b6d10346a"


def sha(data): return hashlib.sha256(data).hexdigest()


def resource(archive, wanted, wanted_key):
    start, groups, members, count = struct.unpack_from("<4I", archive, 8)
    matches = []
    for ordinal in range(groups):
        base, length, first = struct.unpack_from("<IHH", archive, start + ordinal * 8)
        if not base <= wanted < base + length: continue
        index = first + wanted - base
        if index >= count: raise RuntimeError("bad source member index")
        key, offset = struct.unpack_from("<II", archive, members + index * 8)
        end = struct.unpack_from("<I", archive, members + (index + 1) * 8 + 4)[0]
        if key != wanted_key: continue
        flags = struct.unpack_from("<I", archive, offset)[0]
        if flags == 4: payload = archive[offset + 4:end]
        elif flags == 0x800004:
            expanded, compressed = struct.unpack_from("<II", archive, offset + 4)
            if compressed != end - offset - 12: raise RuntimeError("bad compressed span")
            payload = zlib.decompress(archive[offset + 12:end])
            if len(payload) != expanded: raise RuntimeError("bad expanded span")
        else: raise RuntimeError("unsupported source member flags")
        matches.append(payload)
    if len(matches) != 1: raise RuntimeError("source member missing or ambiguous")
    return matches[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--probe", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    archive = args.archive.read_bytes()
    if sha(archive) != ARCHIVE_SHA: raise SystemExit("original archive SHA256 mismatch")
    text = resource(archive, 1, 0x69e4c505)
    mission = resource(archive, 315, 0xf4e02223)
    if sha(text) != TEXT_SHA or sha(mission) != MISSION_SHA:
        raise SystemExit("source text/mission member SHA256 mismatch")
    flags, count = struct.unpack_from("<HH", text)
    assert flags == 0x2000 and count == 511
    assert struct.unpack_from("<I", text, 4 + 4 * count)[0] == len(text)
    entries = []
    for index in range(count):
        identity, offset = struct.unpack_from("<HH", text, 4 + 4 * index)
        end = len(text) if index + 1 == count else struct.unpack_from("<H", text, 10 + 4 * index)[0]
        raw = text[offset:end]
        assert raw[:4] == b"\x04\0\0\0" and raw[-1] == 0 and b"\0" not in raw[4:-1]
        raw[4:-1].decode("utf-8", "strict")
        entries.append({"id": identity, "offset": offset, "utf8_hex": raw[4:-1].hex()})
    run = subprocess.run([str(args.probe.resolve()), str(args.archive.resolve())], check=True,
                         capture_output=True, text=True, timeout=30)
    actual = json.loads(run.stdout)
    assert actual["text_entries"] == entries
    assert actual["control_flow_reference_only"] and actual["not_a_playthrough"]
    assert actual["renderer_and_capture_observations_are_synthetic"] and not actual["effects_applied"]
    assert actual["mission_resource_id"] == 315 and actual["mission_command_count"] == 29
    flow = actual["command_entries"]
    assert [row["index"] for row in flow] == list(range(9, 27))
    expected_dialogue = [(9, 11, 280), (10, 1, 281), (11, 11, 282), (12, 1, 283),
                        (14, 1, 284), (16, 11, 285), (17, 1, 286), (20, 1, 287),
                        (21, 11, 288), (22, 1, 289), (23, 1, 290)]
    dialogues = [row for row in flow if row["opcode"] == 3]
    assert [(row["index"], row["speaker_type"], row["text_index"]) for row in dialogues] == expected_dialogue
    assert all(row["heading_text_id"] == (0x01a0 if row["speaker_type"] == 11 else 0x02a7) for row in dialogues)
    goal = next(row for row in flow if row["index"] == 18)
    assert goal["objective_indices"] == [0, 0, 0, 0] and goal["text_id"] == 619
    assert goal["mode"] == 0 and goal["phase"] == 99
    assert actual["capture_target"] == [5, 7] and not actual["initial_capture_satisfied"]
    assert actual["stop_index"] == 26 and not actual["opcode_8_consumed"]
    args.output.mkdir(parents=True, exist_ok=True)
    # The full text-bearing probe output remains local; committed report contains
    # only hashes, IDs and branch observations, not the game's string payloads.
    (args.output / "native_resource_probe.json").write_text(run.stdout)
    report = {
        "archive_sha256": sha(archive), "text_resource_sha256": sha(text),
        "mission_resource_sha256": sha(mission), "native_probe_sha256": sha(args.probe.read_bytes()),
        "validator_source_sha256": sha(Path(__file__).read_bytes()),
        "localization_entries_compared_byte_for_byte": len(entries),
        "source_text_payload_bytes": len(text), "full_probe_output_sha256": sha(run.stdout.encode()),
        "mission_resource_id": 315, "mission_command_count": 29,
        "control_flow_command_entries": flow, "capture_target": [5, 7],
        "initial_capture_satisfied": False, "final_stop_index": 26,
        "final_stop": "completion_presentation_required", "opcode_8_consumed": False,
        "synthetic_renderer_and_capture_observations": True, "effects_applied": False,
        "is_playthrough_evidence": False,
        "limits": ["Native font layout, UI, camera motion and capture actions were not exercised.",
                   "Synthetic observations only test control-flow continuation using original script data.",
                   "Completion presentation, save, campaign handoff and device validation remain unimplemented/unverified."]}
    (args.output / "native_mission_execution_validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"localization_entries": len(entries), "control_flow_entries": len(flow),
                      "stop_index": 26, "is_playthrough_evidence": False}))


if __name__ == "__main__": main()
