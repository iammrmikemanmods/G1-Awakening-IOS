#!/usr/bin/env python3
"""Development-only unchanged original battle pass/solid-background recorder.

Records 0x3cc9c at explicit public scene/transform/graphics boundaries, and runs
0xb5fe8 + 0xb4cb4 with no-image backgrounds through actual ARM libgcc arithmetic.
GL calls are recorded, never sent to a GPU. No original instruction is patched.
"""
import argparse
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import struct
import sys


def digest(value):
    return hashlib.sha256(value).hexdigest()


def signed(value):
    return struct.unpack("<i", struct.pack("<I", value & 0xffffffff))[0]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ("binary", "libgcc", "unicorn-dir", "output"):
        ap.add_argument("--"+name, type=Path, required=True)
    ap.add_argument("--base-oracle", type=Path, default=
                    Path(__file__).resolve().parents[1]/"sprite"/"render_oracle.py")
    args = ap.parse_args()
    sys.path.insert(0, str(args.unicorn_dir.resolve()))
    import unicorn
    spec = importlib.util.spec_from_file_location("battle_pass_base", args.base_oracle)
    base = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(base)
    base.MATH[0xba228] = "___addsf3vfp"
    image, gcc = args.binary.read_bytes(), args.libgcc.read_bytes()
    if digest(image) != base.IMAGE_SHA or digest(gcc) != base.LIBGCC_SHA:
        raise ValueError("original input differs from audited image")

    class Original(base.OriginalRenderer):
        GL = {0xba690: ("glClear", 1), 0xba69c: ("glClearColorx", 4),
              0xba6e4: ("glColorMask", 4), 0xba744: ("glDepthMask", 1),
              0xba75c: ("glDisable", 1), 0xba78c: ("glEnable", 1)}

        def __init__(self):
            self.events, self.info = [], {}
            super().__init__(image, gcc)
            self.cine = self.alloc(0x120)
            self.transform = self.object({})
            self.engine = self.object({0x10: "factory", 0x1c: "identity"})
            self.word(self.app+8, self.engine)
            self.graphics = self.object({0x58: "render_node", 0x5c: "render_world", 0x64: "set_camera"})
            self.graphics_owner = self.alloc(0x20)
            self.word(self.graphics_owner+4, self.graphics)
            self.word(self.graphics_owner+8, 1)
            self.word(self.app+0xc, self.graphics_owner)
            self.target = self.object({})
            self.target_owner = self.object({0x10: "get_target"})
            self.context_owner = self.object({0x1c: "begin_context", 0x18: "end_context"})
            self.scene = self.node("scene", {0xd0: "get_camera"})
            self.camera = self.node("camera")
            self.models = [self.node("model_a"), self.node("model_b")]
            self.effects = [self.node("effect_"+str(i)) for i in range(4)]
            self.death = self.node("death_effect")
            self.array = self.alloc(16)
            self.renderer = self.alloc(0x250)
            self.graphics_context = self.alloc(0x120)
            self.background = self.alloc(0x48)

        def node(self, name, extra=None):
            obj = self.object({0x8c: "get_enabled", 0x90: "set_enabled", 0xa4: "transform_to", **(extra or {})})
            self.info[obj] = {"name": name, "enabled": True}
            return obj

        def name(self, pointer):
            return self.info[pointer]["name"]

        def hook(self, instance, address, size, user):
            ar = self.ar
            regs = [instance.reg_read(getattr(ar, "UC_ARM_REG_R"+str(i))) for i in range(4)]
            r0, r1, r2, r3 = regs
            sp = instance.reg_read(ar.UC_ARM_REG_SP)
            name = self.handlers.get(address)
            handled = True
            if address in self.GL:
                gl_name, count = self.GL[address]
                self.events.append({"operation": gl_name, "arguments": regs[:count]})
            elif address == 0x12cf4:
                instance.reg_write(ar.UC_ARM_REG_R0, self.target_owner)
            elif address == 0x14dd8:
                instance.reg_write(ar.UC_ARM_REG_R0, self.context_owner)
            elif address == 0x271d0:
                if (r0, r1) != (self.graphics_owner, self.target):
                    raise RuntimeError("unexpected graphics target")
                self.events.append({"operation": "begin_target", "argument3": r3,
                                    "argument4": self.read_word(sp)})
            elif address == 0x2708e:
                self.events.append({"operation": "finish_target"})
            elif name == "get_target":
                instance.reg_write(ar.UC_ARM_REG_R0, self.target)
            elif name in ("begin_context", "end_context"):
                self.events.append({"operation": name})
            elif name == "factory":
                if r0 != 0x1a:
                    raise RuntimeError("unexpected original factory request")
                self.word(r1, self.transform)
                self.events.append({"operation": "create_transform"})
            elif name == "get_enabled":
                value = self.info[r0]["enabled"]
                instance.mem_write(r1, bytes([int(value)]))
                self.events.append({"operation": name, "target": self.name(r0), "enabled": value})
            elif name == "set_enabled":
                value = bool(r1 & 255)
                self.info[r0]["enabled"] = value
                self.events.append({"operation": name, "target": self.name(r0), "enabled": value})
            elif name == "get_camera":
                self.word(r1, self.camera)
                self.events.append({"operation": name})
            elif name == "transform_to":
                if r2 != self.transform:
                    raise RuntimeError("unexpected transform output object")
                instance.mem_write(r3, b"\x01")
                self.events.append({"operation": name, "target": self.name(r0), "relative_to": self.name(r1)})
            elif name == "set_camera":
                if r2 != self.transform:
                    raise RuntimeError("unexpected camera transform")
                self.events.append({"operation": name, "target": self.name(r1)})
            elif name in ("render_world", "render_node"):
                entry = {"operation": name, "target": self.name(r1)}
                if name == "render_world":
                    entry["enabled_snapshot"] = {x["name"]: x["enabled"] for x in self.info.values()
                                                   if x["name"] not in ("scene", "camera")}
                else:
                    if r2 != self.transform:
                        raise RuntimeError("unexpected individual render transform")
                    entry["enabled"] = self.info[r1]["enabled"]
                self.events.append(entry)
            elif address in (0x8e49a, 0xb611a):
                raise RuntimeError("out-of-scope dirty graphics or textured background path")
            else:
                handled = False
            if handled:
                instance.reg_write(ar.UC_ARM_REG_PC, instance.reg_read(ar.UC_ARM_REG_LR))
            else:
                super().hook(instance, address, size, user)

        def pass_case(self, flags, missing=()):
            self.u.mem_write(self.cine, bytes(0x120))
            nodes = self.models+self.effects+[self.death]
            for obj, enabled in zip(nodes, flags):
                self.info[obj]["enabled"] = bool(enabled)
            self.word(self.cine+0x60, self.scene)
            self.word(self.cine+0x84, self.models[0])
            self.word(self.cine+0x88, 0 if "model_b" in missing else self.models[1])
            self.word(self.cine+0xac, 0 if "death_effect" in missing else self.death)
            for i, effect in enumerate(self.effects):
                self.word(self.array+4*i, 0 if "effect_"+str(i) in missing else effect)
            self.word(self.cine+0xa0, 0 if "effect_array" in missing else self.array)
            self.events = []
            self.call(0x3cc9c, [self.cine])
            for obj, enabled in zip(nodes, flags):
                if self.info[obj]["enabled"] != bool(enabled):
                    raise RuntimeError("original pass did not restore visibility")
            return {"flags": flags, "missing": list(missing), "events": self.events[:]}

        def clear_case(self, rgba, color, depth, alpha, scissor, null=False, ready=True):
            self.u.mem_write(self.renderer, bytes(0x250))
            self.u.mem_write(self.graphics_context, bytes(0x120))
            self.u.mem_write(self.background, bytes(0x48))
            self.word(self.renderer+4, self.graphics_context)
            self.word(self.renderer+0x228, scissor)
            self.u.mem_write(self.graphics_context+0x61, bytes([int(ready), int(alpha)]))
            packed = (rgba[3] << 24) | (rgba[0] << 16) | (rgba[1] << 8) | rgba[2]
            self.word(self.background+0x20, packed)
            self.u.mem_write(self.background+0x40, bytes([int(color), int(depth)]))
            self.events = []
            self.call(0xb5fe8, [self.renderer, 0 if null else self.background, 0])
            return {"rgba8": rgba, "color_clear": color, "depth_clear": depth, "alpha_write": alpha,
                    "scissor_state": scissor, "null_background": null, "context_ready": ready,
                    "events": self.events[:], "scissor_state_after": self.read_word(self.renderer+0x228)}

    original = Original()
    pass_cases = [original.pass_case([False]*7), original.pass_case([True]*7),
                  original.pass_case([True, False, True, False, True, False, True])]
    for i in range(7):
        flags = [False]*7
        flags[i] = True
        pass_cases.append(original.pass_case(flags))
    for missing in (("model_b",), ("death_effect",), ("effect_0", "effect_2"), ("effect_array",)):
        pass_cases.append(original.pass_case([True]*7, missing))
    clear_cases = []
    for color, depth, alpha, scissor in itertools.product((False, True), (False, True), (False, True), (0, 1, 4, 5)):
        clear_cases.append(original.clear_case([1, 127, 254, 33], color, depth, alpha, scissor))
    for alpha, scissor in itertools.product((False, True), (0, 5)):
        clear_cases.append(original.clear_case([31, 47, 83, 99], False, False, alpha, scissor, null=True))
    for resource_id, rgba in ((486, [96, 156, 255, 255]), (534, [168, 0, 216, 255]), (1212, [96, 156, 255, 255])):
        for alpha in (False, True):
            case = original.clear_case(rgba, True, True, alpha, 0)
            case["actual_scene_resource"] = resource_id
            clear_cases.append(case)
    clear_cases.append(original.clear_case([0, 255, 128, 0], True, True, True, 0))
    clear_cases.append(original.clear_case([10, 20, 30, 40], True, True, True, 0, ready=False))
    result = {
        "schema": 1, "kind": "unchanged original battle submission order and no-image clear",
        "original_image_sha256": base.IMAGE_SHA, "original_libgcc_sha256": base.LIBGCC_SHA,
        "runner_sha256": digest(Path(__file__).read_bytes()), "base_oracle_sha256": digest(args.base_oracle.read_bytes()),
        "unicorn_version": unicorn.__version__, "instruction_patches": 0,
        "original_text_readonly_unchanged": True, "original_libgcc_readonly_unchanged": True,
        "pass_function": "0x3cc9c", "clear_functions": ["0xb5fe8", "0xb4cb4"],
        "pass_case_count": len(pass_cases), "clear_case_count": len(clear_cases),
        "scope": {"synthetic_state": True, "actual_asset_loader": False, "gpu_execution": False,
                  "background_image_supported": False, "ordinary_no_secondary_viewport": True,
                  "transform_calculation_executed": False, "public_submission_order_executed": True,
                  "original_float_clear_conversion_executed": True},
        "recording_boundaries": ["public retain/release/identity/factory", "public enabled state",
                                 "public transform-to returns success without calculating matrix", "public camera query",
                                 "public Graphics renderWorld/renderNode/setCamera", "target begin/end helpers",
                                 "graphics target/context acquisition", "GL clear/color-mask/depth-mask/scissor calls"],
        "visibility_order": ["model_a", "model_b", "effect_0", "effect_1", "effect_2", "effect_3", "death_effect"],
        "pass_cases": pass_cases, "clear_cases": clear_cases,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps({key: result[key] for key in ("pass_case_count", "clear_case_count", "original_text_readonly_unchanged")}))


if __name__ == "__main__":
    main()
