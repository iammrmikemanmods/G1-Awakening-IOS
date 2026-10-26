#!/usr/bin/env python3
"""Development-only original ordinary battle-controller recorder.

Executes unchanged 0x413e8 and its original timeline/libgcc helpers. Public
objects, camera routing, text formatting, audio and effect placement are
explicit recording boundaries. This is a phase/effect-order reference, not
an original M3G loader, renderer, game combat resolver or native product.
"""
import argparse
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import struct
import sys

IMAGE_SHA = "0d510516fe3676ee4a0f4dff60ba64e1c5bf79a0c9800f420b1bbdb1c12febfd"
LIBGCC_SHA = "d758fbf1ac952532955d62866bd02df55315c0599f64bdd978ff941fccbdcf83"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def signed(value):
    return struct.unpack("<i", struct.pack("<I", value & 0xffffffff))[0]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--libgcc", type=Path, required=True)
    parser.add_argument("--unicorn-dir", type=Path, required=True)
    parser.add_argument("--base-oracle", type=Path, default=
                        Path(__file__).resolve().parents[1] / "sprite" / "render_oracle.py")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.unicorn_dir.resolve()))
    import unicorn
    image, gcc = args.binary.read_bytes(), args.libgcc.read_bytes()
    if sha(image) != IMAGE_SHA or sha(gcc) != LIBGCC_SHA:
        raise ValueError("original image or libgcc differs from audited input")
    base = load_module("g1_controller_base", args.base_oracle)
    base.MATH.update({0xba228: "___addsf3vfp", 0xba330: "___gesf2vfp"})

    class Recorder(base.OriginalRenderer):
        def __init__(self):
            self.events = []
            self.labels = {}
            self.text_values = {}
            self.embedded = [False, False]
            self.render_enabled = {}
            super().__init__(image, gcc)
            self.cine = self.alloc(0x120)
            self.controller = self.alloc(0x100)
            self.world = self.alloc(0x400)
            self.game_app = self.alloc(0x500)
            self.input_state = self.alloc(0x40)
            self.word(self.input_state+0x10, 320)
            self.word(self.input_state+0x14, 480)
            self.units = [self.alloc(0x80), self.alloc(0x80)]
            self.models = [self.named_object("model_a"), self.named_object("model_b")]
            self.effects = [self.named_object("effect_" + str(i)) for i in range(4)]
            self.death = self.named_object("death_effect")
            self.camera = self.named_object("embedded_camera")
            self.effect_array = self.alloc(16)
            for i, value in enumerate(self.effects):
                self.word(self.effect_array + 4*i, value)

        def named_object(self, label):
            obj = self.object({0x24: "animate", 0x90: "set_render_enabled"})
            self.labels[obj] = label
            self.render_enabled[label] = True
            return obj

        def byte(self, address, value):
            self.u.mem_write(address, bytes([value & 255]))

        def read_byte(self, address):
            return self.u.mem_read(address, 1)[0]

        def clock_label(self, address):
            return {self.cine+0x90: "a", self.cine+0x94: "b"}.get(address, hex(address))

        def hook(self, instance, address, size, user):
            ar = self.ar
            r0, r1, r2, r3 = [instance.reg_read(getattr(ar, "UC_ARM_REG_R" + str(i))) for i in range(4)]
            sp = instance.reg_read(ar.UC_ARM_REG_SP)
            name = self.handlers.get(address)
            handled = True
            if name == "animate":
                self.events.append({"kind": "animate", "target": self.labels[r0], "time": signed(r1)})
                self.word(r2, 0)
            elif name == "set_render_enabled":
                label = self.labels[r0]
                self.render_enabled[label] = bool(r1 & 255)
                self.events.append({"kind": "set_render_enabled", "target": label, "enabled": bool(r1 & 255)})
            elif address == 0x3c23a:
                self.events.append({"kind": "start_clip", "target": self.labels[self.read_word(r1)],
                                    "clip": r2, "clock": self.clock_label(r3)})
                handled = False
            elif address == 0x3c950:
                clock = self.read_word(sp+4)
                self.events.append({"kind": "tick_clip", "target": self.labels[self.read_word(r1)],
                                    "clip": r3, "delta": signed(r2),
                                    "restart": bool(self.read_word(sp)), "clock": self.clock_label(clock)})
                handled = False
            elif address == 0x3d9d0:
                self.events.append({"kind": "select_camera", "id": r1})
                # Explicit graph callback: the separately recorded real camera
                # route determines side, and supplied graph presence controls
                # only the non-null test that this phase helper consumes.
                side_a = r1 in (0, 1, 2, 6, 7, 9, 11)
                self.byte(self.cine+0x9c, side_a)
                embedded = r1 != 8 and self.embedded[0 if side_a else 1]
                self.word(self.cine+0x8c, self.camera if embedded else 0)
            elif address == 0x3d51e:
                self.events.append({"kind": "propagate_camera", "time": signed(r1), "adjust": r2 & 255})
            elif address == 0x3c74a:
                self.events.append({"kind": "place_effect", "side_a": bool(r1 & 255), "hit": bool(r2 & 255)})
            elif address == 0x60800:
                self.text_values[r0] = ""
                self.events.append({"kind": "clear_text", "field": hex(r0-self.cine)})
            elif address == 0x60b70:
                self.text_values[r0] = str(signed(r1))
                self.events.append({"kind": "set_integer_text", "field": hex(r0-self.cine), "value": signed(r1)})
            elif address == 0x2ad12:
                self.events.append({"kind": "audio", "category": signed(r1), "event": signed(r2)})
            elif address == 0x62d1c:
                instance.reg_write(ar.UC_ARM_REG_R0, self.game_app)
            elif address == 0x62d0c:
                instance.reg_write(ar.UC_ARM_REG_R0, self.input_state)
            elif address == 0x3cc9c:
                self.events.append({"kind": "render_scene_and_participants", "enabled": self.render_enabled.copy()})
            elif address == 0x3c1fe:
                self.events.append({"kind": "draw_battle_hud", "slide_fixed16": signed(self.read_word(self.cine+0x40))})
            elif address == 0x606f6:
                self.text_values[r0] = self.text_values.get(r1, "")
            elif address == 0x604b4:
                pass
            elif address == 0x42a88:
                self.events.append({"kind": "draw_damage_text", "font_id": r0,
                                    "x": signed(r3), "y": signed(self.read_word(sp)),
                                    "flags": self.read_word(sp+4)})
            elif address == 0x2ad6c:
                self.events.append({"kind": "audio_status", "category": signed(r1)})
                instance.reg_write(ar.UC_ARM_REG_R0, 1)
            elif address in (0x3fadc, 0x4e7b8, 0x2b9c2, 0x3c14e):
                raise RuntimeError(f"unexpected out-of-scope original boundary {address:#x}")
            else:
                handled = False
            if handled:
                instance.reg_write(ar.UC_ARM_REG_PC, instance.reg_read(ar.UC_ARM_REG_LR))
            else:
                super().hook(instance, address, size, user)

        def initialize(self, inputs):
            self.u.mem_write(self.cine, bytes(0x120))
            self.u.mem_write(self.controller, bytes(0x100))
            self.u.mem_write(self.world, bytes(0x400))
            self.u.mem_write(self.game_app, bytes(0x500))
            for i, unit in enumerate(self.units):
                self.u.mem_write(unit, bytes(0x80))
                self.byte(unit+0xc, inputs.get("form_a" if i == 0 else "form_b", 0))
                self.byte(unit+0x19, inputs.get("immune_a" if i == 0 else "immune_b", False))
                self.byte(unit+0xb, inputs.get("faction_a" if i == 0 else "faction_b", i))
            self.word(self.cine+0x48, self.controller)
            self.word(self.cine+0x4c, self.world)
            self.word(self.world+0x29c, self.game_app)
            self.word(self.controller+0x4c, self.units[0])
            self.word(self.controller+0x50, self.units[1])
            for offset, key, default in ((0x54, "counter", False), (0x55, "a_first", True),
                                         (0x60, "death_a", False), (0x61, "death_b", False)):
                self.byte(self.controller+offset, inputs.get(key, default))
            for offset, key, default in ((0x58, "damage_a", 17), (0x5c, "damage_b", 31)):
                self.word(self.controller+offset, inputs.get(key, default))
            self.embedded = [bool(inputs.get("embedded_a", False)), bool(inputs.get("embedded_b", False))]
            for offset, value in ((0x84, self.models[0]), (0x88, self.models[1]),
                                  (0xa0, self.effect_array), (0xac, self.death),
                                  (0x90, inputs.get("clock_a", 1666)), (0x94, inputs.get("clock_b", 1666)),
                                  (0x44, 640), (0x40, -41943040),
                                  (0x18, inputs.get("final_a", 83)), (0x1c, inputs.get("final_b", 69)),
                                  (0x30, inputs.get("before_a", 100)), (0x34, inputs.get("before_b", 100)),
                                  (4, inputs.get("elapsed", 0))):
                self.word(self.cine+offset, value)
            for offset, value in ((0, inputs.get("phase", 0)), (0xc, inputs.get("complete", False)),
                                  (0xa4, inputs.get("intro", False)), (0x6c, inputs.get("adjust_a", 1)),
                                  (0x6d, inputs.get("adjust_b", 0)), (0x9c, inputs.get("camera_side_a", True))):
                self.byte(self.cine+offset, value)
            self.word(self.cine+0x8c, self.camera if inputs.get("embedded_current", False) else 0)
            self.text_values = {}
            self.events = []
            self.render_enabled = {label: True for label in self.labels.values()}

        def state(self):
            fields = {"phase": self.read_byte(self.cine), "complete": bool(self.read_byte(self.cine+0xc)),
                      "camera_side_a": bool(self.read_byte(self.cine+0x9c)),
                      "embedded_current": bool(self.read_word(self.cine+0x8c))}
            for key, offset in (("elapsed", 4), ("slide_fixed16", 0x40), ("clock_a", 0x90), ("clock_b", 0x94),
                                ("display_health_a", 0x30), ("display_health_b", 0x34)):
                fields[key] = signed(self.read_word(self.cine+offset))
            return fields

        def step(self, delta):
            self.events = []
            self.call(0x413e8, [self.cine, delta])
            return {"state": self.state(), "events": self.events[:]}

        def draw(self, refresh):
            self.events = []
            before = self.state()
            self.call(0x40f0c, [self.cine, 0, int(refresh)])
            if self.state() != before:
                raise RuntimeError("recorded ordinary draw changed phase/time state")
            return {"events": self.events[:], "render_enabled": self.render_enabled.copy()}

    original = Recorder()
    cases = []
    thresholds = {0: 999, 1: 1332, 2: 731, 3: 2999, 4: 1332, 5: 731,
                  6: 2999, 7: 999, 8: 3599, 9: 1332, 10: 1332, 11: 998, 12: 998}
    for phase, limit in thresholds.items():
        for embedded in (False, True):
            for elapsed, delta in ((0, 33), (limit-1, 1), (limit, 1), (limit, 2), (limit+1, 0), (limit-1, 10000)):
                inputs = {"phase": phase, "elapsed": elapsed,
                          "embedded_current": embedded, "embedded_a": embedded, "embedded_b": embedded}
                original.initialize(inputs)
                cases.append({"name": f"phase_{phase}_embedded_{int(embedded)}_at_{elapsed}_delta_{delta}",
                              "input": inputs, "delta": delta, "before": original.state(),
                              **original.step(delta)})
    for phase in (0, 2, 5, 9, 10, 11, 12):
        for a_first, counter, form_a, form_b in itertools.product((False, True), repeat=4):
            inputs = {"phase": phase, "elapsed": thresholds[phase], "intro": True,
                      "a_first": a_first, "counter": counter, "form_a": int(form_a), "form_b": int(form_b)}
            original.initialize(inputs)
            cases.append({"name": f"transition_{phase}_{int(a_first)}{int(counter)}{int(form_a)}{int(form_b)}",
                          "input": inputs, "delta": 2, "before": original.state(), **original.step(2)})
    for phase in (1, 4):
        for elapsed, delta in ((465, 1), (465, 2), (466, 1), (400, 100), (467, 33)):
            inputs = {"phase": phase, "elapsed": elapsed}
            original.initialize(inputs)
            cases.append({"name": f"shot_audio_{phase}_{elapsed}_{delta}", "input": inputs,
                          "delta": delta, "before": original.state(), **original.step(delta)})
    for phase in (2, 5):
        for elapsed, delta in ((332, 2), (332, 4), (333, 2), (300, 100), (334, 33)):
            inputs = {"phase": phase, "elapsed": elapsed}
            original.initialize(inputs)
            cases.append({"name": f"hit_audio_{phase}_{elapsed}_{delta}", "input": inputs,
                          "delta": delta, "before": original.state(), **original.step(delta)})
        for death in (False, True):
            inputs = {"phase": phase, "elapsed": thresholds[phase], "counter": True,
                      "a_first": phase == 2, "death_a": death, "death_b": death}
            original.initialize(inputs)
            cases.append({"name": f"death_gate_{phase}_{int(death)}", "input": inputs,
                          "delta": 2, "before": original.state(), **original.step(2)})
    for phase in (1, 4):
        inputs = {"phase": phase, "elapsed": thresholds[phase], "immune_a": True, "immune_b": True}
        original.initialize(inputs)
        cases.append({"name": f"immune_text_{phase}", "input": inputs,
                      "delta": 1, "before": original.state(), **original.step(1)})
    inputs = {"phase": 7, "elapsed": 1100, "complete": True}
    original.initialize(inputs)
    cases.append({"name": "completed_noop", "input": inputs, "delta": 100,
                  "before": original.state(), **original.step(100)})

    sequences = []
    for a_first, counter, intro in itertools.product((False, True), repeat=3):
        inputs = {"a_first": a_first, "counter": counter, "intro": intro,
                  "before_a": 100 if intro else 99,
                  "embedded_a": True, "embedded_b": False}
        original.initialize(inputs)
        frames = []
        for step in range(300):
            before = original.state()
            result = original.step(100)
            frames.append({"before": before, **result})
            if result["state"]["complete"]:
                break
        else:
            raise RuntimeError("ordinary sequence did not reach original completion byte")
        phases = []
        for frame in frames:
            for phase in (frame["before"]["phase"], frame["state"]["phase"]):
                if not phases or phases[-1] != phase:
                    phases.append(phase)
        sequences.append({"name": f"sequence_{int(a_first)}{int(counter)}{int(intro)}", "input": inputs,
                          "delta": 100, "phase_order": phases, "step_count": len(frames), "steps": frames})
    for a_first in (False, True):
        inputs = {"a_first": a_first, "death_a": not a_first, "death_b": a_first,
                  "counter": False, "form_a": 1, "form_b": 1}
        original.initialize(inputs)
        frames = []
        for _ in range(200):
            before = original.state()
            result = original.step(100)
            frames.append({"before": before, **result})
            if result["state"]["complete"]:
                break
        else:
            raise RuntimeError("death sequence did not complete")
        sequences.append({"name": f"death_sequence_{int(a_first)}", "input": inputs,
                          "delta": 100, "step_count": len(frames), "steps": frames})
    draw_cases = []
    for phase, side, form_a in itertools.product(range(13), (False, True), (0, 1)):
        for elapsed in (0, 466, 467):
            inputs = {"phase": phase, "elapsed": elapsed, "camera_side_a": side, "form_a": form_a}
            original.initialize(inputs)
            draw_cases.append({"name": f"draw_{phase}_{int(side)}_{form_a}_{elapsed}",
                               "input": inputs, "refresh": True, **original.draw(True)})
    for phase in (0, 1, 7):
        inputs = {"phase": phase, "elapsed": 500}
        original.initialize(inputs)
        draw_cases.append({"name": f"draw_{phase}_no_refresh", "input": inputs,
                           "refresh": False, **original.draw(False)})
    report = {
        "schema": 1, "kind": "unchanged original ordinary battle phase controller",
        "original_image_sha256": IMAGE_SHA, "original_libgcc_sha256": LIBGCC_SHA,
        "unicorn_version": unicorn.__version__, "runner_sha256": sha(Path(__file__).read_bytes()),
        "base_oracle_sha256": sha(args.base_oracle.read_bytes()),
        "function": "0x413e8", "draw_function": "0x40f0c",
        "original_helpers": ["0x3c23a", "0x3c950", "0x42b44", "original ARMv6 libgcc"],
        "instruction_patches": 0, "original_text_readonly_unchanged": True,
        "original_libgcc_readonly_unchanged": True,
        "case_count": len(cases), "sequence_count": len(sequences),
        "draw_case_count": len(draw_cases),
        "sequence_step_count": sum(x["step_count"] for x in sequences),
        "recording_boundaries": ["public retain/release/identity", "public animate: signed requested time only",
                                 "camera select: record ID and supply separately proven route side plus synthetic graph presence",
                                 "camera propagation: record signed time and adjustment byte only",
                                 "effect placement: record side and hit arguments only", "text formatting", "audio request", "app singleton",
                                 "public render-enable setter", "scene/participants rendering helper: record current enable states",
                                 "battle HUD and damage text drawing"],
        "scope": {"synthetic_state": True, "original_complete_phase_function": True,
                  "actual_combat_resolver": False, "actual_asset_loader": False,
                  "gpu_rendering": False, "unit_viewer_phase13": False,
                  "transition_inputs_include_synthetic_boundary_combinations": True},
        "thresholds_strict_greater_than": thresholds, "cases": cases, "sequences": sequences, "draw_cases": draw_cases,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ("case_count", "sequence_count", "sequence_step_count", "draw_case_count",
                                                  "original_text_readonly_unchanged")}))


if __name__ == "__main__":
    main()
