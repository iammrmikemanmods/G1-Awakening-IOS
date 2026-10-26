#!/usr/bin/env python3
"""Summarize observed original SetTimer registers; never infer rate from FPS.

Input is an existing development-only CPU observation log. This script does
not run or modify an emulator or the original executable. A gameplay frame
must first be independently viewed; its number is supplied explicitly.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import struct


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("probe", type=Path)
    ap.add_argument("--first-gameplay-frame", type=int, required=True)
    ap.add_argument("--last-gameplay-frame", type=int, required=True)
    ap.add_argument("--original-executable", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    if args.first_gameplay_frame >= args.last_gameplay_frame:
        ap.error("a positive interval between two viewed gameplay captures is required")
    text = (args.probe / "runtime.log").read_text()
    original = args.original_executable.read_bytes()
    captures, samples, observed_opcodes = [], [], {}
    latest_frame = None
    pointer = loaded_byte = load_line = None
    for line_number, line in enumerate(text.splitlines(), 1):
        match = re.match(r"G1_CAPTURE: presentation (\d+) viewport", line)
        if match:
            latest_frame = int(match[1])
            captures.append({"frame": latest_frame, "log_line": line_number})
        if not line.startswith("G1_CPU_TRACE "):
            continue
        match = re.search(r"regs=\[([^]]+)\]", line)
        if not match:
            raise ValueError("trace line missing registers")
        regs = [int(value, 16) for value in match[1].split(", ")]
        if len(regs) != 16:
            raise ValueError("wrong register count")
        before = re.search(r"before pc=(0x[0-9a-f]+).* opcode=(0x[0-9a-f]+)", line)
        if before:
            address, opcode = int(before[1], 16), int(before[2], 16)
            expected = int.from_bytes(original[address - 0x1000:address - 0x1000 + 2], "little")
            if opcode != expected:
                raise ValueError(f"observed instruction prefix differs from original at {address:#x}")
            observed_opcodes[f"0x{address:08x}"] = f"0x{opcode:04x}"
            if address == 0x28f54:
                pointer, loaded_byte, load_line = regs[3], None, line_number
            elif address == 0x28f7a:
                if loaded_byte is None:
                    raise ValueError("timer call has no preceding observed flag load")
                bits = (regs[3] << 32) | regs[2]
                interval = struct.unpack("<d", struct.pack("<Q", bits))[0]
                expected_bits = 0x3F9EB851E0000000 if loaded_byte == 0 else 0x3F847AE140000000
                if bits != expected_bits:
                    raise ValueError("observed interval does not match the original branch")
                samples.append({"log_line": line_number, "flag_load_log_line": load_line,
                                "preceding_capture_frame": latest_frame,
                                "core_pointer": f"0x{pointer:08x}", "core_byte_plus8": loaded_byte,
                                "r0": f"0x{regs[0]:08x}", "r1": f"0x{regs[1]:08x}",
                                "r2": f"0x{regs[2]:08x}", "r3": f"0x{regs[3]:08x}",
                                "double_bits": f"0x{bits:016x}", "interval_seconds": interval})
        elif "after original_pc=0x00028f54 " in line:
            loaded_byte = regs[3]
            if not 0 <= loaded_byte <= 255:
                raise ValueError("LDRB result is not a byte")
    capture_lines = {item["frame"]: item["log_line"] for item in captures}
    first = capture_lines[args.first_gameplay_frame]
    last = capture_lines[args.last_gameplay_frame]
    gameplay = [sample for sample in samples if first < sample["log_line"] < last]
    if not gameplay:
        raise ValueError("no timer samples between the viewed gameplay captures")
    frames = []
    for number in [args.first_gameplay_frame, args.last_gameplay_frame]:
        png = args.probe / "frames" / f"frame_{number:06d}.png"
        ppm = png.with_suffix(".ppm")
        frames.append({"frame": number, "log_line": capture_lines[number],
                       "png_sha256": sha(png), "ppm_sha256": sha(ppm)})
    result = {
        "kind": "observed original guest timer arguments in a development-only runtime",
        "native_product_includes_compatibility_runtime": False,
        "probe": str(args.probe), "log_sha256": sha(args.probe / "runtime.log"),
        "original_executable_sha256": sha(args.original_executable),
        "observed_instruction_prefixes_match_original": observed_opcodes,
        "instruction_scope": "Original Thumb prefixes fetched at the four traced addresses; not a hash of all live relocated memory",
        "all_timer_argument_samples": len(samples),
        "all_interval_bit_counts": dict(Counter(sample["double_bits"] for sample in samples)),
        "viewed_gameplay_frames": frames,
        "gameplay_timer_argument_samples": len(gameplay),
        "gameplay_interval_bit_counts": dict(Counter(sample["double_bits"] for sample in gameplay)),
        "gameplay_flag_counts": dict(Counter(sample["core_byte_plus8"] for sample in gameplay)),
        "first_gameplay_sample": gameplay[0], "last_gameplay_sample": gameplay[-1],
        "limits": [
            "Observed timer request argument, not measured wall-clock delivery or fixed simulation frequency.",
            "Diagnostic trace single-steps the CPU and changes host timing; no FPS inference is valid.",
            "One copied-save first-mission state on Linux, not every game mode or physical historical iPhone.",
            "The original callback re-arms after work; 30ms requests do not imply exactly 33.333 updates/s.",
            "No native app/device performance or campaign completion is established.",
        ],
    }
    (args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
