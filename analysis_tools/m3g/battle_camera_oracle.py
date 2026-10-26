#!/usr/bin/env python3
"""Record unchanged battle camera selection and propagation at public graph boundaries.

Development only. Executes 3d9d0, 3d51e, hashes and smart-pointer wrappers.
Public graph queries, ownership, animation and translation are explicit recorded
callbacks over a supplied synthetic graph; no original M3G renderer is claimed.
"""
import argparse
from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path
import struct
import sys


SCENE_NAMES = [
    'cam_auto_takehit', 'cam_auto_car', 'cam_auto_shoot', 'cam_auto_death',
    'cam_decpt_takehit', 'cam_decpt_shoot', 'cam_decpt_death', 'Stat_Camera',
    'd_Stat_Camera', 'cam_rot', 'cam_auto_setup', 'cam_decpt_setup',
    'cam_auto_zoom', 'cam_decpt_zoom',
]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def name_hash(name):
    value = 0
    for byte in reversed(name.encode('ascii')):
        value = (value * 0x19660d + 0x3c6ef35f + byte) & 0xffffffff
    if value & 0x80000000:
        value = (-value) & 0xffffffff
    return value & 0x3fffffff


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('binary', 'libgcc', 'unicorn-dir', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.unicorn_dir))
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'sprite'))
    import render_oracle as base
    import unicorn
    image, gcc = args.binary.read_bytes(), args.libgcc.read_bytes()
    if sha(image) != base.IMAGE_SHA or sha(gcc) != base.LIBGCC_SHA:
        raise ValueError('private original input identity differs')

    class OriginalCamera(base.OriginalRenderer):
        def __init__(self):
            super().__init__(image, gcc)
            self.nodes, self.labels, self.events = {}, {}, []
            self.world = self.node('scene_world', 22)
            self.scene_parent = self.node('scene_camera_parent', 9, self.world)
            self.scene_find = {}
            for name in SCENE_NAMES:
                camera = self.node('scene:' + name, 5, self.scene_parent)
                self.scene_find[name_hash(name)] = camera
            self.models, self.model_find = [], []
            for side in ('a', 'b'):
                root = self.node('model_' + side, 9)
                mapping = {}
                for name in ('roboCAM', 'vehiCAM'):
                    outer = self.node(side + ':' + name + 'Transform', 9, root)
                    inner = self.node(side + ':' + name + ':inner', 9, outer)
                    camera = self.node(side + ':' + name + ':camera', 5, inner)
                    mapping[name_hash(name + 'Transform')] = outer
                self.models.append(root)
                self.model_find.append(mapping)
            self.old_root = self.node('old_camera_grandparent', 9)
            self.old_parent = self.node('old_camera_parent', 9, self.old_root)
            self.old_camera = self.node('old_camera', 5, self.old_parent)
            self.controller = self.alloc(0x90)
            self.units = [self.alloc(0x60), self.alloc(0x60)]
            self.cinematic = self.alloc(0xb0)
            self.word(self.controller + 0x4c, self.units[0])
            self.word(self.controller + 0x50, self.units[1])
            self.word(self.cinematic + 0x48, self.controller)
            self.word(self.cinematic + 0x60, self.world)
            self.word(self.cinematic + 0x84, self.models[0])
            self.word(self.cinematic + 0x88, self.models[1])
            self.word(self.cinematic + 0x90, 1777)
            self.word(self.cinematic + 0x94, 3888)

        def node(self, label, kind, parent=0):
            obj = self.object({8: 'query', 0x24: 'animate', 0x28: 'find',
                               0x64: 'translation', 0x80: 'parent',
                               0xbc: 'child', 0xd0: 'get_camera', 0xd4: 'set_camera'})
            self.nodes[obj] = {'label': label, 'type': kind, 'parent': parent,
                               'children': []}
            self.labels[label] = obj
            if parent:
                self.nodes[parent]['children'].append(obj)
            return obj

        def label(self, pointer):
            return None if pointer == 0 else self.nodes[pointer]['label']

        def cstring(self, address):
            data = bytearray()
            for i in range(4096):
                byte = bytes(self.u.mem_read(address + i, 1))
                if byte == b'\0':
                    return bytes(data)
                data += byte
            raise RuntimeError('bounded original string is not terminated')

        def hook(self, instance, address, size, user):
            ar = self.ar
            r0, r1, r2, r3 = [instance.reg_read(reg) for reg in
                (ar.UC_ARM_REG_R0, ar.UC_ARM_REG_R1, ar.UC_ARM_REG_R2, ar.UC_ARM_REG_R3)]
            if address == 0x3d51e:
                self.events.append({'operation': 'propagate_entry',
                    'time': struct.unpack('<i', struct.pack('<I', r1))[0],
                    'adjustment_byte': r2 & 0xff})
            if address in (0xbabac, 0xbaba0, 0xbab7c):
                if address == 0xbabac:
                    result = len(self.cstring(r0)); name = 'strlen'
                else:
                    data = self.cstring(r1) + b'\0'
                    offset = len(self.cstring(r0)) if address == 0xbab7c else 0
                    instance.mem_write(r0 + offset, data)
                    result, name = r0, 'strcat' if offset else 'strcpy'
                self.calls[name] += 1
                instance.reg_write(ar.UC_ARM_REG_R0, result)
                instance.reg_write(ar.UC_ARM_REG_PC, instance.reg_read(ar.UC_ARM_REG_LR))
                return
            name = self.handlers.get(address)
            if name in ('query', 'animate', 'find', 'translation', 'parent',
                        'child', 'get_camera', 'set_camera'):
                obj = self.nodes[r0]
                event = {'operation': name, 'object': obj['label']}
                if name == 'query':
                    accepted = (r1 == obj['type'] or r1 == 9 and obj['type'] == 22)
                    self.word(r2, r0 if accepted else 0)
                    event.update(interface=r1, accepted=accepted)
                elif name == 'find':
                    if r0 == self.world:
                        if r1 not in self.scene_find:
                            raise RuntimeError('unexpected scene-camera hash ' + hex(r1))
                        result = self.scene_find[r1]
                    else:
                        side = self.models.index(r0)
                        if r1 not in self.model_find[side]:
                            raise RuntimeError('unexpected model-camera hash ' + hex(r1))
                        result = self.model_find[side][r1] if self.available[side] else 0
                    self.word(r2, result)
                    event.update(user_id=r1, result=self.label(result))
                elif name == 'animate':
                    self.word(r2, 0)
                    event['time'] = struct.unpack('<i', struct.pack('<I', r1))[0]
                elif name == 'translation':
                    event['bits'] = list(struct.unpack('<III', instance.mem_read(r1, 12)))
                elif name == 'parent':
                    self.word(r1, obj['parent']);event['result'] = self.label(obj['parent'])
                elif name == 'child':
                    if r1 >= len(obj['children']):
                        raise RuntimeError('original requested unavailable synthetic child')
                    child = obj['children'][r1]
                    self.word(r2, child);event.update(index=r1, result=self.label(child))
                elif name == 'get_camera':
                    self.word(r1, self.active_camera);event['result'] = self.label(self.active_camera)
                elif name == 'set_camera':
                    self.active_camera = r1;event['camera'] = self.label(r1)
                self.events.append(event);self.calls['public_' + name] += 1
                instance.reg_write(ar.UC_ARM_REG_R0, 0)
                instance.reg_write(ar.UC_ARM_REG_PC, instance.reg_read(ar.UC_ARM_REG_LR))
                return
            if 0xba000 <= address < 0xbb000 and address not in self.math and address not in (0xba1f8, 0xba210, 0xba204):
                raise RuntimeError('unexpected original import ' + hex(address))
            super().hook(instance, address, size, user)

        def run(self, case):
            self.events = []
            self.available = case['model_camera_available']
            self.active_camera = self.old_camera if case['old_active_camera'] else 0
            self.word(self.cinematic + 0x88, self.models[1] if case['model_b_present'] else 0)
            self.nodes[self.old_camera]['parent'] = self.old_parent if case['old_parent_depth'] else 0
            self.nodes[self.old_parent]['parent'] = self.old_root if case['old_parent_depth'] > 1 else 0
            for address, value in ((self.units[0] + 0xc, case['forms'][0]),
                                   (self.units[1] + 0xc, case['forms'][1]),
                                   (self.cinematic + 0x6c, case['adjustment_flags'][0]),
                                   (self.cinematic + 0x6d, case['adjustment_flags'][1]),
                                   (self.cinematic + 0x9c, case['old_side_a'])):
                self.u.mem_write(address, bytes([int(value)]))
            self.word(self.cinematic + 0x8c, self.old_camera if case['old_model_camera'] else 0)
            self.call(0x3d9d0, [self.cinematic, case['camera_id']])
            return {**case, 'selected_camera': self.label(self.active_camera),
                    'stored_model_camera': self.label(self.read_word(self.cinematic + 0x8c)),
                    'side_a_after': bool(bytes(self.u.mem_read(self.cinematic + 0x9c, 1))[0]),
                    'events': list(self.events)}

    runner = OriginalCamera()
    cases = []
    for camera_id, form_a, form_b, available_a, available_b in itertools.product(
            range(13), (0, 1), (0, 1), (False, True), (False, True)):
        serial = len(cases)
        case = {'camera_id': camera_id, 'forms': [form_a, form_b],
                'model_camera_available': [available_a, available_b],
                'adjustment_flags': [serial & 1, (serial >> 1) & 1],
                'old_model_camera': bool(serial & 1), 'old_side_a': bool(serial & 2),
                'old_parent_depth': serial % 3, 'old_active_camera': True,
                'model_b_present': True}
        cases.append(runner.run(case))
    for camera_id in range(13):
        cases.append(runner.run({'camera_id': camera_id, 'forms': [0, 1],
            'model_camera_available': [True, True], 'model_b_present': False,
            'adjustment_flags': [7, 255], 'old_model_camera': False,
            'old_side_a': False, 'old_parent_depth': 2, 'old_active_camera': False}))
    report = {
        'schema': 1,
        'scope': 'Original camera selection/propagation with explicit recorded public synthetic graph boundaries; not M3G execution, loaded scene identity or GPU output',
        'original_image_sha256': base.IMAGE_SHA, 'original_libgcc_sha256': base.LIBGCC_SHA,
        'runner_sha256': sha(Path(__file__).read_bytes()),
        'loader_sha256': sha(Path(base.__file__).read_bytes()),
        'unicorn_version': unicorn.__version__,
        'functions': ['0x3d9d0', '0x3d51e', '0x26b4c', '0x26b94', '0x2701c'],
        'host_boundaries': ['bounded allocator/free and C string functions',
                            'public graph find/query/child/parent and camera storage',
                            'record-only animate and additive Translate', 'retain/release and identity'],
        'instruction_patches': [], 'original_main_and_libgcc_unchanged': True,
        'cases': cases, 'summary': {'cases': len(cases),
            'public_events': sum(e['operation'] != 'propagate_entry' for c in cases for e in c['events']),
            'propagation_entries': sum(e['operation'] == 'propagate_entry' for c in cases for e in c['events'])},
        'calls': dict(runner.calls),
    }
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report['summary']))


if __name__ == '__main__':
    main()
