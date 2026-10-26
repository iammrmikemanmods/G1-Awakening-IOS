#!/usr/bin/env python3
"""Development-only style0/2 terrain sprite constructor and update oracle.

Runs unchanged candidate-count/register/select instructions, original sprite
selector/start logic, complete placement/RNG/playback routines and the intact
stage2 placement loop. The descriptor loader boundary receives independently
decoded local asset data; M3G ownership/transform calls are recorded. There is
no replacement of random generation, selection, position or playback math.
Original binaries/assets are local inputs, never product dependencies.
"""
from collections import Counter
import json
from pathlib import Path
import struct
import sys

from animated_map_oracle import OriginalAnimatedMap, decode_config
from decorations_oracle import OriginalDecorations
from geometry_oracle import IMAGE_SHA, LIBGCC_SHA, digest, float_bits
import render_oracle as rendering

rendering.MATH.update({0xba228: "___addsf3vfp", 0xba3b4: "___subsf3vfp"})


def signed(value):
    return value if value < 0x80000000 else value - 0x100000000


class OriginalSpriteDecorations(OriginalAnimatedMap):
    call = OriginalDecorations.call

    def __init__(self, image, gcc):
        self.draws, self.generated = 0, []
        self.instances, self.mesh_indices, self.transform_indices = {}, {}, {}
        self.group_ids, self.sprite_indices = {}, {}
        self.placements, self.starts = [], []
        self.loader_requests = []
        self.attachment_order = 0
        self.stage2 = False
        super().__init__(image, gcc)
        self.rng = self.alloc(0x9d4)
        self.word(self.rng + 0xc, 0)
        self.word(self.rng + 0x10, 0x9908b0df)

    def block(self, start, stop, frame=0x21fe000, extra_registers=()):
        ar = self.ar
        self.active_endpoint = stop
        try:
            for i in range(13):
                self.u.reg_write(getattr(ar, "UC_ARM_REG_R" + str(i)), 0)
            self.u.reg_write(ar.UC_ARM_REG_CPSR, 0x30)
            self.u.reg_write(ar.UC_ARM_REG_SP, frame)
            self.u.reg_write(ar.UC_ARM_REG_LR, 0x3000001)
            for register, value in extra_registers:
                self.u.reg_write(register, value)
            self.u.emu_start(start | 1, stop, count=5_000_000, timeout=15_000_000)
            if self.u.reg_read(ar.UC_ARM_REG_PC) != stop or self.u.reg_read(ar.UC_ARM_REG_SP) != frame:
                raise RuntimeError(f"original sprite block{start:#x} did not reach{stop:#x}; PC={self.u.reg_read(ar.UC_ARM_REG_PC):#x}")
        finally:
            self.active_endpoint = None
        self.check_text()

    def seed_descriptor(self, sprite, descriptor, selector, index):
        animations = self.bank[descriptor]
        frames_outer = self.alloc(len(animations) * 8)
        durations_outer = self.alloc(len(animations) * 8)
        self.word(sprite + 0x48, frames_outer)
        self.word(sprite + 0x4c, len(animations))
        self.word(sprite + 0x50, durations_outer)
        self.word(sprite + 0x54, len(animations))
        for i, steps in enumerate(animations):
            frames, durations = self.alloc(len(steps)), self.alloc(len(steps) * 2)
            self.u.mem_write(frames, bytes(s[0] for s in steps))
            self.u.mem_write(durations, struct.pack('<' + 'h' * len(steps), *(s[1] for s in steps)))
            for pointer, data in ((frames_outer, frames), (durations_outer, durations)):
                self.word(pointer + i * 8, data)
                self.word(pointer + i * 8 + 4, len(steps))
        mesh = self.object({0x90: 'node_enable', 0x7c: 'mesh_set_transform'})
        transform = self.object({0x1c: 'transform_identity', 0x28: 'transform_rotation',
                                 0x30: 'transform_scale', 0x34: 'transform_translation'})
        self.word(sprite + 0xb0, mesh)
        self.word(sprite + 0xdc, transform)
        self.mesh_indices[mesh], self.transform_indices[transform] = index, index
        self.sprite_indices[sprite] = index
        self.instances[index] = {'pointer': sprite, 'selector': selector,
                                'descriptor': descriptor, 'enabled': False,
                                'parent': 0, 'attachment_order': 0, 'position': None, 'operations': []}

    def hook(self, instance, address, size, user):
        ar = self.ar
        if address == getattr(self, 'active_endpoint', None):
            instance.emu_stop()
            return
        r0, r1, r2, r3 = [instance.reg_read(getattr(ar, 'UC_ARM_REG_R' + str(i))) for i in range(4)]
        sp = instance.reg_read(ar.UC_ARM_REG_SP)
        if address == 0x2b46c:
            self.calls['shared_random_singleton'] += 1
            instance.reg_write(ar.UC_ARM_REG_R0, self.rng)
            instance.reg_write(ar.UC_ARM_REG_PC, instance.reg_read(ar.UC_ARM_REG_LR))
            return
        if address == 0x1adc4:
            raise RuntimeError('explicitly seeded oracle attempted wall-clock seeding')
        if address == 0x7b26:
            self.draws += 1
        if address == 0x7c0a:
            self.generated.append(r0)
        if address == 0x66d58:
            self.construct_selector = r0
        if address == 0x7315c:
            if r0 != 0x030003c1 or r1 & 0xff000000 != 0x03000000:
                raise RuntimeError('original sprite loader binding differs')
            index = self.next_sprite_index
            self.next_sprite_index += 1
            self.loader_requests.append([index, self.construct_selector, r1 & 0xffffff])
            self.seed_descriptor(r2, r1 & 0xffffff, self.construct_selector, index)
            self.calls['independently_decoded_descriptor_and_M3G_objects'] += 1
            instance.reg_write(ar.UC_ARM_REG_PC, instance.reg_read(ar.UC_ARM_REG_LR))
            return
        if address == 0x728f0:
            self.calls['geometry_refresh_observer'] += 1
            instance.reg_write(ar.UC_ARM_REG_PC, instance.reg_read(ar.UC_ARM_REG_LR))
            return
        if address == 0x1f4e0:
            if r2 > 255 or not 0x1000000 <= r0 <= 0x1400000 - r2:
                raise RuntimeError('animation byte initialization escaped bound')
            instance.mem_write(r0, bytes([r1 & 255]) * r2)
            self.calls['animation_byte_buffer_initialization'] += 1
            instance.reg_write(ar.UC_ARM_REG_PC, instance.reg_read(ar.UC_ARM_REG_LR))
            return
        if address == 0x727a4:
            index = self.sprite_indices[r0]
            values = [signed(r1), signed(r2), signed(r3), signed(self.read_word(sp)), self.read_word(sp + 4)]
            self.instances[index]['position'] = values[:3]
            self.instances[index]['operations'] = []
            if values[3:] != [-45, float_bits(1.0)]:
                raise RuntimeError('terrain sprite uses an unexpected orientation or scale')
            self.placements.append([index, *values])
        if address == 0x72d80:
            self.starts.append([self.sprite_indices[r0], r1, signed(r2), r3])
        name = self.handlers.get(address)
        if name == 'node_enable':
            if r1 not in (0, 1):
                raise RuntimeError('original M3G visibility argument is not boolean')
            self.instances[self.mesh_indices[r0]]['enabled'] = bool(r1)
        elif name == 'add_child':
            self.instances[self.mesh_indices[r1]]['parent'] = self.group_ids[r0]
            self.attachment_order += 1
            self.instances[self.mesh_indices[r1]]['attachment_order'] = self.attachment_order
        elif name and name.startswith('transform_'):
            index = self.transform_indices[r0]
            count = 0 if name == 'transform_identity' else (4 if name == 'transform_rotation' else 3)
            values = list(struct.unpack('<' + 'I' * count, instance.mem_read(r1, count * 4))) if count else []
            self.instances[index]['operations'].append([name, values])
        super().hook(instance, address, size, user)

    def setup_pool(self, grid, config, tables, style, lookup, bank, seed, animation_config):
        self.setup(grid, config)
        self.style, self.bank = style, bank
        if style not in (0, 2):
            raise ValueError('sprite oracle requires style0 or2')
        self.word(self.map_object + 0x22c, style)
        self.u.mem_write(self.map_object + 0x15, bytes([self.width, self.height]))
        self.word(self.map_object + 0x18, self.grid_data)
        self.word(self.map_object + 0x1c, len(self.grid))
        lookup_data = self.alloc(32)
        self.u.mem_write(lookup_data, bytes(lookup))
        self.word(self.map_object + 0x20, lookup_data)
        self.word(self.map_object + 0x24, 32)
        visual_address = (0xd9084, 0xd8f38, 0xd8fe2)[style]
        self.u.mem_write(visual_address, tables[style * 160:(style + 1) * 160])
        self.word(0xd95bc, visual_address)
        self.capacity, self.slots = self.first_pass()
        self.candidate_pointer = self.alloc(self.capacity * 3)
        self.u.mem_write(self.candidate_pointer, bytes([127]) * self.capacity * 3)
        self.word(0xd8e18, self.candidate_pointer)
        self.word(0xd8dfc, self.alloc(self.capacity * 4))
        frame, offset = 0x21fe000, 0
        for y in range(self.height):
            for x in range(self.width):
                self.u.mem_write(frame, bytes(0x300))
                for at, value in ((0x150, self.grid[y*self.width+x]), (0x1e0, x),
                                  (0x204, y), (0x140, x), (0x128, 0), (0xec, offset)):
                    self.word(frame + at, value)
                self.block(0x6b1e8, 0x6b28c, frame)
                offset = self.read_word(frame + 0xec)
        if offset > self.capacity * 3 or offset % 3:
            raise RuntimeError('original candidate registration exceeds its counted capacity')
        self.registered = offset // 3
        self.initial_records = list(self.u.mem_read(self.candidate_pointer, self.capacity * 3))
        app = self.alloc(0x400)
        self.word(self.controller + 0xe4, app)
        self.word(app + 0x3e8, self.rng)
        self.word(0xd8e24, 8)
        self.word(0xd8e08, self.alloc(24))
        self.call(0x7acc, [self.rng, seed])
        self.u.mem_write(frame, bytes(0x300))
        self.block(0x6b606, 0x6b660, frame)
        self.initial_pool_draws = self.draws

        # The original second-stage count and allocation-index calculations.
        self.u.mem_write(frame, bytes(0x300))
        self.block(0x693d0, 0x694ee, frame)
        self.fixed_capacity = self.read_word(0xd8e10)
        self.sprite_count = self.read_word(0xd8e84)
        if self.sprite_count > 2048 or self.read_word(0xd8e88) != 7:
            raise RuntimeError('original sprite allocation exceeds bounded profile')
        sprite_table = self.alloc(self.sprite_count * 4)
        self.u.mem_write(sprite_table, bytes(self.sprite_count * 4))
        self.word(0xd8e90, sprite_table)
        group_table = self.alloc(10 * 4)
        self.word(0xd8e98, group_table)
        for i, group_id in ((0, 1), (9, 2)):
            group = self.object({0xc0: 'add_child'})
            self.word(group_table + i * 4, group)
            self.group_ids[group] = group_id
        group = self.object({0xc0: 'add_child'})
        self.word(0xd95ec, group)
        self.group_ids[group] = 3
        owner, animation_object = self.alloc(0x80), self.alloc(0x28)
        self.word(0xd8dd4, owner)
        self.word(owner + 0x7c, animation_object)
        animation_bytes = self.alloc(len(animation_config))
        self.u.mem_write(animation_bytes, bytes(animation_config))
        self.word(animation_object + 0x20, animation_bytes)
        self.word(animation_object + 0x24, len(animation_config))
        self.next_sprite_index = 4
        self.u.mem_write(frame, bytes(0x300))
        self.block(0x6980c, 0x6993a, frame)
        if self.next_sprite_index != self.sprite_count:
            raise RuntimeError('original construction skipped an expected sprite index')
        self.u.mem_write(frame, bytes(0x300))
        self.block(0x6994c, 0x6a1e8, frame)
        self.stage2_draws = self.draws - self.initial_pool_draws
        self.check_text()
        return {'candidate_capacity': self.capacity, 'registered_candidates': self.registered,
                'slot_count': self.slots, 'fixed_sprite_capacity': self.fixed_capacity,
                'original_sprite_count': self.sprite_count,
                'initial_candidate_records': self.initial_records,
                'initial_pool_draws': self.initial_pool_draws,
                'stage2_draws': self.stage2_draws}

    def snapshot(self):
        instances = []
        for index, data in sorted(self.instances.items()):
            p = data['pointer']
            step = self.read_word(p + 0x64)
            frames, count = self.read_word(p + 0x5c), self.read_word(p + 0x60)
            if not 0 <= step < count:
                raise RuntimeError('original animation escaped its independently decoded sequence')
            instances.append({'index': index, 'selector': data['selector'],
                'animation': self.read_word(p + 0x58),
                'visible': self.u.mem_read(p + 0x74, 1)[0],
                'enabled': int(data['enabled']), 'parent': data['parent'],
                'attachment_order': data['attachment_order'],
                'position': data['position'],
                'playback': [step, self.u.mem_read(frames + step, 1)[0],
                    signed(self.read_word(p + 0x78)), signed(self.read_word(p + 0x70)),
                    self.u.mem_read(p + 0xc4, 1)[0], self.u.mem_read(p + 0x75, 1)[0]]})
        phases = self.read_word(0xd8e14)
        return {'candidate_records': list(self.u.mem_read(self.candidate_pointer, self.capacity * 3)),
                'slot_phases': list(struct.unpack('<' + 'I' * self.slots,
                    self.u.mem_read(phases, self.slots * 4))),
                'sprites': instances,
                'accumulated_ms': self.read_word(0xd8e20), 'phase': self.read_word(0xd8e28),
                'random_index': self.read_word(self.rng + 8), 'random_draws': self.draws,
                'random_words_sha256': digest(bytes(self.u.mem_read(self.rng + 0x14, 624 * 4)))}

    def advance(self, delta):
        before = self.read_word(0xd8e20)
        frame = 0x21fe000
        self.u.mem_write(frame, bytes(0x300))
        self.word(frame + 0xc, delta)
        stop = 0x6d758 if before + delta >= 250 else 0x6d82a
        self.block(0x6d656, stop, frame)
        # The caller5d5bc reaches6526c after the transient update. This visits
        # only indices below7 and advances those whose byte74 is nonzero.
        self.call(0x6526c, [delta])
        return self.snapshot()


def read_actual_inputs(manifest_path):
    manifest = json.loads(Path(manifest_path).read_text())
    resources = {r['resource_id']: r for r in manifest['resources'] if r['key_hex'] == '0xf4e02223'}
    def resource(rid):
        item = resources[rid]
        data = (Path(manifest_path).parent / 'extracted' / item['kind'] / item['extracted_filename']).read_bytes()
        if digest(data) != item['sha256']:
            raise ValueError(f'local resource{rid} differs from audited input')
        return data
    return resource


if __name__ == '__main__':
    # Bounded diagnostic only. Formal native parity/fixture generation is in
    # validate_sprite_decorations.py once the native API is complete.
    sys.path.insert(0, '/tmp/g1-movement-oracle-tools/python')
    sys.path.insert(0, str(Path('native/tests').resolve()))
    import generate_atlas_reference as decoder
    resource = read_actual_inputs('research/assets/results/asset_manifest.json')
    bank = {rid: decoder.decode(resource(rid))['animations'] for rid in (638, 825, 581, 1095, 1132, 982)}
    image = Path('research/binary/G1awakening.armv6').read_bytes()
    gcc = Path('../.tools/g1_runtime/Applesauce/touchHLE_dylibs/libgcc_s.1.dylib').read_bytes()
    if (digest(image), digest(gcc)) != (IMAGE_SHA, LIBGCC_SHA):
        raise ValueError('original image or libgcc differs from audited input')
    style = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    rid = int(sys.argv[2]) if len(sys.argv) > 2 else (268 if style == 0 else 272)
    lookup = list(resource(282 if style == 0 else 281)[1:])
    if style == 0:
        lookup = [0] * 32
        for i in (1, 2, 3, 4, 5, 26, 27): lookup[i] = 1
        for i in (6, 12, 13): lookup[i] = 3
    else:
        for i, value in ((8, 1), (19, 0), (30, 1), (31, 1)): lookup[i] = value
    original = OriginalSpriteDecorations(image, gcc)
    layout = original.setup_pool(resource(rid), decode_config(resource(307)),
        Path('research/native_terrain/terrain_visual_tables.bin').read_bytes(), style, lookup,
        bank, 0x47413133, list(resource(309)[1:]))
    states = [original.snapshot()] + [original.advance(d) for d in (0, 249, 1, 250, 1000, 0, 250, 250, 250, 250)]
    report = {'style': style, 'grid_resource_id': rid, 'layout': layout,
              'snapshots': states, 'loader_requests': original.loader_requests,
              'placements': original.placements, 'starts': original.starts,
              'boundary_calls': dict(original.calls)}
    out = Path(f'research/native_terrain/sprite_decorations_diagnostic_{style}_{rid}.json')
    out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'output': str(out), 'layout': {k:v for k,v in layout.items() if k != 'initial_candidate_records'},
                      'snapshots': len(states), 'final_draws': original.draws}))
