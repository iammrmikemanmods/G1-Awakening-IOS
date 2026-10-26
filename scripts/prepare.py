#!/usr/bin/env python3
"""Verify the kit, obtain the pinned source and apply the exact checked patches.

This Source Code Form is subject to the Mozilla Public License, v. 2.0.
See the LICENSE file or https://mozilla.org/MPL/2.0/.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

KIT = Path(__file__).resolve().parents[1]
MANIFEST = KIT / "build-manifest.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args, cwd=None, capture=False):
    print("+ " + " ".join(str(a) for a in args), flush=True)
    result = subprocess.run([str(a) for a in args], cwd=cwd, check=True,
                            text=True, stdout=subprocess.PIPE if capture else None)
    return result.stdout.strip() if capture else None


def safe_relative(value):
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unexpected nonrelative path: {value}")
    return path


def verify_kit():
    manifest = json.loads(MANIFEST.read_text())
    if len(manifest["patches"]) != 7:
        raise ValueError("Expected the seven checked implementation patches")
    for item in manifest["patches"]:
        path = KIT / safe_relative(item["file"])
        if digest(path) != item["sha256"] or path.stat().st_size != item["bytes"]:
            raise ValueError(f"Patch bytes differ from the checkpoint: {item['file']}")
    if any(KIT.rglob("*.ipa")):
        # A completed local build may be in artifacts; it is not part of a clean kit.
        unexpected = [str(p) for p in KIT.rglob("*.ipa") if "artifacts" not in p.relative_to(KIT).parts]
        if unexpected:
            raise ValueError(f"Do not place game or other IPA files in this repository: {unexpected}")
    return manifest


def check_snapshot(repo, manifest):
    checks = []
    for item in manifest["expected_source_files"]:
        path = repo / safe_relative(item["file"])
        actual = digest(path)
        if actual != item["sha256"]:
            raise ValueError(f"Prepared source differs from reviewed snapshot: {item['file']}")
        checks.append({"file": item["file"], "sha256": actual})
    if digest(repo / "Cargo.lock") != manifest["cargo_lock_sha256"]:
        raise ValueError("Cargo.lock differs from the pinned/tested lockfile")
    games = [p.relative_to(repo).as_posix() for p in (repo / "touchHLE_apps").rglob("*")
             if p.is_file() and p.name != "README.txt"]
    if games:
        raise ValueError(f"The host source contains game payloads: {games}")
    return checks


def verify_existing(repo, manifest, need_submodules):
    record_path = repo / ".g1-preparation.json"
    record = json.loads(record_path.read_text())
    head = run(["git", "rev-parse", "HEAD"], cwd=repo, capture=True)
    if head != manifest["upstream"]["commit"]:
        raise ValueError("Prepared checkout no longer has the pinned base commit")
    if record["manifest_sha256"] != digest(MANIFEST):
        raise ValueError("Preparation record belongs to a different manifest")
    check_snapshot(repo, manifest)
    for item in record["patched_source_files"]:
        if digest(repo / safe_relative(item["file"])) != item["sha256"]:
            raise ValueError(f"Prepared source changed: {item['file']}")
    if need_submodules:
        if not record["submodules_initialized"]:
            raise ValueError("Preparation skipped submodules; this is not a build-ready checkout")
        status = run(["git", "submodule", "status", "--recursive"], cwd=repo, capture=True)
        if any(line and line[0] in "-+U" for line in status.splitlines()):
            raise ValueError("A submodule is missing or differs from its pinned gitlink")
    return record


def prepare(args, manifest):
    repo = args.destination.resolve()
    if repo.exists():
        raise ValueError(f"Destination already exists; choose a fresh directory: {repo}")
    repo.parent.mkdir(parents=True, exist_ok=True)
    if args.local_source:
        # Local validation only. This reads the existing object store and never
        # checks out, cleans, resets or patches the original source tree.
        run(["git", "clone", "--shared", "--no-checkout", args.local_source.resolve(), repo])
    else:
        run(["git", "init", repo])
        run(["git", "remote", "add", "origin", manifest["upstream"]["url"]], cwd=repo)
        run(["git", "fetch", "--depth", "1", "origin", manifest["upstream"]["commit"]], cwd=repo)
    run(["git", "config", "core.autocrlf", "false"], cwd=repo)
    run(["git", "checkout", "--detach", manifest["upstream"]["commit"]], cwd=repo)
    head = run(["git", "rev-parse", "HEAD"], cwd=repo, capture=True)
    if head != manifest["upstream"]["commit"]:
        raise ValueError("Checkout commit mismatch")
    submodules = "Not initialized: source-preparation-only local check"
    if not args.skip_submodules:
        run(["git", "submodule", "sync", "--recursive"], cwd=repo)
        run(["git", "submodule", "update", "--init", "--recursive", "--depth", "1"], cwd=repo)
        submodules = run(["git", "submodule", "status", "--recursive"], cwd=repo, capture=True)
        if any(line and line[0] in "-+U" for line in submodules.splitlines()):
            raise ValueError("Submodule initialization did not reach all pinned revisions")
    for item in manifest["patches"]:
        patch = KIT / item["file"]
        run(["git", "apply", "--check", "--index", patch], cwd=repo)
        run(["git", "apply", "--index", patch], cwd=repo)
    checks = check_snapshot(repo, manifest)
    changed = run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"], cwd=repo, capture=True)
    files = [{"file": x, "sha256": digest(repo / safe_relative(x))}
             for x in changed.splitlines() if x]
    record = {
        "base_commit": head, "manifest_sha256": digest(MANIFEST),
        "patch_count": len(manifest["patches"]), "patches": manifest["patches"],
        "submodules_initialized": not args.skip_submodules,
        "submodule_revisions": submodules.splitlines(),
        "reviewed_snapshot_checks": checks, "patched_source_files": files,
        "cargo_lock_sha256": digest(repo / "Cargo.lock"),
        "source_only_validation": bool(args.skip_submodules),
        "apple_sdk_build_performed_by_preparation": False,
        "game_payload_present": False,
    }
    (repo / ".g1-preparation.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--verify-kit", action="store_true")
    action.add_argument("--destination", type=Path)
    action.add_argument("--verify-existing", type=Path)
    parser.add_argument("--local-source", type=Path)
    parser.add_argument("--skip-submodules", action="store_true",
                        help="Source-preparation check only; build script refuses this state")
    parser.add_argument("--require-submodules", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    manifest = verify_kit()
    if args.verify_kit:
        record = {"patch_count": len(manifest["patches"]), "all_patch_hashes_match": True,
                  "manifest_sha256": digest(MANIFEST), "apple_sdk_build_performed": False}
    elif args.verify_existing:
        record = verify_existing(args.verify_existing.resolve(), manifest, args.require_submodules)
    else:
        record = prepare(args, manifest)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"status": "passed", "patch_count": record["patch_count"],
                      "apple_sdk_build_performed_by_preparation": False}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"Preparation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
