#!/usr/bin/env python3
"""Check the selected Cargo features and the packaged iOS host.

This Source Code Form is subject to the Mozilla Public License, v. 2.0.
See the LICENSE file or https://mozilla.org/MPL/2.0/.
"""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import re
import struct
import subprocess
import tempfile
import zipfile

KIT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((KIT / "build-manifest.json").read_text())


def command(args):
    return subprocess.run([str(x) for x in args], check=True, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout


def features(path):
    metadata = json.loads(path.read_text())
    packages = {p["id"]: p["name"] for p in metadata["packages"]}
    found = {}
    for node in metadata["resolve"]["nodes"]:
        name = packages[node["id"]]
        if name in ("touchHLE", "touchhle-ios-entry"):
            found[name] = node["features"]
    for name in ("touchHLE", "touchhle-ios-entry"):
        for feature in ("cpu-interpreter", "compact-memory"):
            if feature not in found.get(name, []):
                raise ValueError(f"{name} is missing required feature {feature}")
        if "cpu-dynarmic" in found[name]:
            raise ValueError(f"Unexpected JIT backend feature selected in {name}")
    if "dynamic-sdl" not in found["touchHLE"]:
        raise ValueError("Core must share the host SDL library")
    if "static" in found["touchHLE"]:
        raise ValueError("Private static SDL was selected alongside the shared host SDL")
    return found


def capability_code(data):
    """Resolve the exported symbol in a thin ARM64 Mach-O, without executing it."""
    magic, cpu, _subtype, _kind, ncmds, _size, _flags, _reserved = struct.unpack_from("<IiiIIIII", data)
    if magic != 0xfeedfacf or cpu != 0x0100000c:
        raise ValueError("Core is not a thin ARM64 Mach-O")
    offset, segments, symtab = 32, [], None
    for _ in range(ncmds):
        cmd, size = struct.unpack_from("<II", data, offset)
        if size < 8 or offset + size > len(data):
            raise ValueError("Malformed Mach-O load command")
        if cmd == 0x19:
            _name, vmaddr, _vmsize, fileoff, filesize = struct.unpack_from("<16sQQQQ", data, offset + 8)
            segments.append((vmaddr, fileoff, filesize))
        elif cmd == 2:
            symtab = struct.unpack_from("<IIII", data, offset + 8)
        offset += size
    if not symtab:
        raise ValueError("Core symbol table is missing")
    symoff, count, stroff, strsize = symtab
    if symoff + count * 16 > len(data) or stroff + strsize > len(data):
        raise ValueError("Malformed Mach-O symbol table")
    address = None
    for index in range(count):
        string_index, symbol_type, _section, _desc, value = struct.unpack_from("<IBBHQ", data, symoff + index * 16)
        if string_index >= strsize:
            continue
        start = stroff + string_index
        name = data[start:data.find(b"\0", start, stroff + strsize)]
        if name == b"_touchhle_ios_requires_jit" and symbol_type & 1:
            address = value
            break
    if address is None:
        raise ValueError("Export touchhle_ios_requires_jit is missing")
    location = next((fileoff + address - vmaddr for vmaddr, fileoff, size in segments
                     if vmaddr <= address < vmaddr + size), None)
    if location is None or location + 16 > len(data):
        raise ValueError("No file-backed code found for JIT capability export")
    words = list(struct.unpack_from("<IIII", data, location))
    instructions = words[:]
    # Optional BTI landing pad or NOP, followed by MOV of zero and ordinary RET.
    while instructions and instructions[0] in (0xd503245f, 0xd503201f):
        instructions.pop(0)
    zero_moves = (0x52800000, 0xd2800000, 0x2a1f03e0, 0xaa1f03e0)
    zero_return = len(instructions) >= 2 and instructions[0] in zero_moves and instructions[1] == 0xd65f03c0
    if not zero_return:
        raise ValueError("JIT capability code is not a recognized constant-zero ARM64 return; "
                         f"inspect before distributing: {[hex(w) for w in words]}")
    return {"symbol": "_touchhle_ios_requires_jit", "address": hex(address),
            "first_instruction_words": [hex(w) for w in words],
            "constant_zero_return_verified_statically": True,
            "executed_on_ios": False}


def verify_ipa(path):
    config = MANIFEST["artifact"]
    app = config["app_path"]
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if any(name.startswith("/") or ".." in Path(name).parts for name in names):
            raise ValueError("Unexpected archive paths")
        guest_files = [name for name in names if name.startswith(app + "/touchHLE_apps/")
                       and not name.endswith("/") and not name.endswith("/README.txt")]
        if guest_files:
            raise ValueError(f"Game payloads must be imported after install: {guest_files}")
        if any(name.lower().endswith((".ipa", ".mobileprovision", ".p12", ".cer", ".mobiledevicepairing"))
               or "/_CodeSignature/" in name for name in names):
            raise ValueError("IPA contains a nested package or signing material")
        info = plistlib.loads(archive.read(app + "/Info.plist"))
        if info["CFBundleIdentifier"] != config["bundle_id"]:
            raise ValueError("Unexpected bundle identifier")
        if info["CFBundleExecutable"] != config["executable"]:
            raise ValueError("Unexpected host executable")
        if info.get("MinimumOSVersion") != MANIFEST["toolchain"]["deployment_target"]:
            raise ValueError("Unexpected app minimum iOS version")
        if "iPhoneOS" not in info.get("CFBundleSupportedPlatforms", []):
            raise ValueError("Artifact is not an iPhoneOS device build")
        libraries = sorted(Path(name).name for name in names if name.startswith(app + "/Frameworks/")
                           and name.endswith(".dylib"))
        if libraries != sorted(config["frameworks"]):
            raise ValueError(f"Expected exactly the patched core and shared SDL; found {libraries}")
        binaries = [config["executable"]] + ["Frameworks/" + x for x in config["frameworks"]]
        checks = []
        with tempfile.TemporaryDirectory(prefix="g1-ipa-check-") as temp:
            for relative in binaries:
                data = archive.read(app + "/" + relative)
                binary = Path(temp) / Path(relative).name
                binary.write_bytes(data)
                architecture = command(["xcrun", "lipo", "-archs", binary]).strip()
                if architecture != "arm64":
                    raise ValueError(f"Unexpected architecture for {relative}: {architecture}")
                build = command(["xcrun", "vtool", "-show-build", binary])
                if not re.search(r"\bplatform\s+IOS\s", build):
                    raise ValueError(f"Non-device platform for {relative}: {build}")
                minimum = re.search(r"\bminos\s+([0-9.]+)", build)
                if not minimum or minimum.group(1) != MANIFEST["toolchain"]["deployment_target"]:
                    raise ValueError(f"Unexpected minimum OS for {relative}: {build}")
                item = {"path": relative, "sha256": hashlib.sha256(data).hexdigest(),
                        "architecture": architecture, "build_commands": build,
                        "linked_libraries": command(["xcrun", "otool", "-L", binary])}
                if Path(relative).name == config["core"]:
                    item["jit_capability"] = capability_code(data)
                checks.append(item)
    return {"ipa": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size, "bundle_id": config["bundle_id"],
            "minimum_ios": info["MinimumOSVersion"], "binaries": checks,
            "game_payload_present": False, "signing_credentials_used": False,
            "device_execution_verified": False, "xr_60fps_verified": False,
            "full_playthrough_verified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", required=True, type=Path)
    parser.add_argument("--ipa", type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    report = {"selected_features": features(args.features)}
    if args.ipa:
        report["packaged_ipa"] = verify_ipa(args.ipa)
    report["status"] = "passed"
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
