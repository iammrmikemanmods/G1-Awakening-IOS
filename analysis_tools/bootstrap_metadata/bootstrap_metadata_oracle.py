#!/usr/bin/env python3
"""Original loader/debit fragments; development reference, never an app CPU."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

IMAGE_SHA256 = "0d510516fe3676ee4a0f4dff60ba64e1c5bf79a0c9800f420b1bbdb1c12febfd"
SUPPORT_SHA256 = "f0505848b34b88b6653cbb8ebe5f74fa8fd5394f4e1727fa93f0b3f2c18374ad"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--support", type=Path, required=True,
                        help="unchanged mission_progression/oracle.py")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    image = args.image.read_bytes()
    if digest(image) != IMAGE_SHA256:
        raise SystemExit("original executable hash mismatch")
    if digest(args.support.read_bytes()) != SUPPORT_SHA256:
        raise SystemExit("reference support hash mismatch")
    spec = importlib.util.spec_from_file_location("original_support", args.support)
    support = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(support)
    ref = support.Reference(image)
    ar = ref.ar
    cost_data = ref.array([0] * 23, "B")
    ref.vector(ref.map + 0x14c, cost_data, 23)
    funds_data = ref.array([0, 0], "i")
    ref.vector(ref.map + 0x58, funds_data, 2)
    rows = []
    for unit_type in range(23):
        for raw in (0, 127, 128, 255):
            ref.w8(cost_data + unit_type, raw)
            ref.w32(ref.sp + 0xf0, unit_type)
            ref.w32(ref.sp + 0x4c, ref.map + 0x14c)
            ref.run(0x5a8ce, stop=0x5a8e0)
            cost = ref.r8(cost_data + unit_type)
            cost = cost if cost < 128 else cost - 256
            for funds in (-2147483648, -1, 0, 1, 50, 2147483647):
                owner = unit_type % 2
                ref.w32(funds_data + owner * 4, funds)
                ref.w32(funds_data + (1 - owner) * 4, 123456)
                def seed():
                    ref.u.reg_write(ar.UC_ARM_REG_R5, ref.map)
                    ref.u.reg_write(ar.UC_ARM_REG_R10, owner)
                    ref.u.reg_write(ar.UC_ARM_REG_R11, unit_type)
                ref.run(0x54094, stop=0x540ca, seed=seed)
                assert ref.r32(funds_data + (1 - owner) * 4) == 123456
                rows.append([unit_type, raw, funds, cost,
                             support.s32(ref.r32(funds_data + owner * 4))])
    if ref.boundaries:
        raise RuntimeError("unexpected external-call replacement")
    args.output.mkdir(parents=True, exist_ok=True)
    fixture = "".join(" ".join(map(str, row)) + "\n" for row in rows).encode()
    (args.output / "world_funds_original_vectors.txt").write_bytes(fixture)
    result = {
        "status": "passed", "cases": len(rows),
        "original_sha256": IMAGE_SHA256, "support_sha256": SUPPORT_SHA256,
        "oracle_sha256": digest(Path(__file__).read_bytes()),
        "fixture_sha256": digest(fixture),
        "original_fragments": ["0x5a8ce..0x5a8e0", "0x54094..0x540ca"],
        "executed_helpers": ["0x2aa78", "0x2b460"],
        "replaced_external_calls": {},
        "limits": ["Original loader and spawn function-body fragments, not full game startup.",
                   "Synthetic type/cost/funds inputs; no proprietary data payload in fixture.",
                   "Turn credit/order and site snapshot separately established by dispatcher callsites.",
                   "No native session, Apple device, or campaign playthrough claim."]}
    (args.output / "original_bootstrap_metadata_reference.json").write_text(
        json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
