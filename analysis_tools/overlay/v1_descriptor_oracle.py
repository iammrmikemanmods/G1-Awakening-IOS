#!/usr/bin/env python3
"""Compare a strict native v1 overlay decoder with the unchanged original parser.

The parser body 0x5ecfe..0x5f7f6 executes from read-only original text. Only
memory allocation, byte fill/free, raw stream reads and an independently
resolved image's dimensions are substituted. Original endian/sign handling,
vector allocation logic and crop/variant constructors execute unchanged.
No resource, executable or image pixels are embedded in this tool.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

IMAGE_SHA = '0d510516fe3676ee4a0f4dff60ba64e1c5bf79a0c9800f420b1bbdb1c12febfd'
LIBGCC_SHA = 'd758fbf1ac952532955d62866bd02df55315c0599f64bdd978ff941fccbdcf83'
DESCRIPTOR_SHA = 'dc520143e30346dad8ed479089fcb78783b97922b7e1bda0eef0e5c1f28a50bb'
BMP_SHA = '9ca143bb91d5bb8f8bfc2dce2244cb3df334e5ebf059931ba827990fb36069cb'
PROPERTY_SHA = 'e6522b4147b7553cde18e15b1be0febfa7143ec57a23ecc430c682e0416bd382'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def original_class(base):
    class OriginalDescriptor(base.OriginalCombat):
        def __init__(self, binary, gcc, data):
            super().__init__(binary, gcc)
            self.data = data
            self.cursor = 0
            self.texture = self.alloc(0x18)
            self.w32(self.texture + 8, 69)
            self.w32(self.texture + 12, 63)
            self.stream = self.alloc(0x40)
            self.owner = self.alloc(0xa8)
            self.read_trace = []
            self.image_ids = []
            self.variant_inputs = []
            self.variant_definitions = []

        def ret(self, result=None):
            if result is not None:
                self.u.reg_write(self.ar.UC_ARM_REG_R0, result)
            self.u.reg_write(self.ar.UC_ARM_REG_PC, self.u.reg_read(self.ar.UC_ARM_REG_LR))

        def hook(self, instance, address, size, user):
            ar = self.ar
            r = [instance.reg_read(getattr(ar, 'UC_ARM_REG_R' + str(i))) for i in range(3)]
            if address == 0x7672:
                if r[0] != self.stream + 8 or r[2] not in (1, 2, 4):
                    raise RuntimeError(f'unexpected read {r}')
                end = self.cursor + r[2]
                if end > len(self.data):
                    raise RuntimeError('original parser read past input')
                self.read_trace.append([self.cursor, r[2]])
                instance.mem_write(r[1], self.data[self.cursor:end])
                self.cursor = end
                self.calls['raw_stream_read'] += 1
                self.ret()
            elif address == 0x1f540:
                if r[0] > 65536:
                    raise RuntimeError('unexpected allocation')
                self.calls['allocate'] += 1
                self.ret(self.alloc(r[0]))
            elif address in (0x1f512, 0xba210):
                self.calls[hex(address)] += 1
                self.ret()
            elif address in (0x1f4e0, 0xbaa5c):
                if r[2] > 65536:
                    raise RuntimeError('unexpected fill')
                instance.mem_write(r[0], bytes([r[1] & 255]) * r[2])
                self.calls['byte_fill'] += 1
                self.ret()
            elif address == 0x61f9e:
                self.image_ids.append(r[1])
                if r[1:] != [1000, 0]:
                    raise RuntimeError('unexpected image lookup')
                self.calls['image_lookup'] += 1
                self.ret(self.texture)
            else:
                if address == 0x2ae20:
                    self.variant_inputs.append(r[0])
                elif address == 0x2ae14:
                    rectangles = self.values(self.owner + 4, 'I')
                    self.variant_definitions.append([rectangles.index(r[1]), self.variant_inputs[-1]])
                super().hook(instance, address, size, user)

        def values(self, address, fmt):
            count, pointer = self.r32(address + 4), self.r32(address)
            if count > 32767:
                raise RuntimeError('unexpected vector size')
            return list(struct.unpack('<' + fmt * count,
                                    self.u.mem_read(pointer, count * struct.calcsize(fmt)))) if count else []

        def nested(self, address, fmt):
            count, pointer = self.r32(address + 4), self.r32(address)
            return [self.values(pointer + i * 8, fmt) for i in range(count)]

        def run(self):
            sp = 0x21ff000
            for offset, value in [(0x108, self.stream), (0x40, self.owner),
                                  (0x34, self.owner), (0x3c, 1000), (0x30, 0)]:
                self.w32(sp + offset, value)
            self.call(0x5ecfe, [], 0x5f7f6)
            self.check_text()
            if self.cursor != len(self.data):
                raise RuntimeError('unconsumed source')
            rectangles = []
            for pointer in self.values(self.owner + 4, 'I'):
                rectangles.append([base.signed(self.r32(pointer + offset))
                                   for offset in (0x1c, 0x20, 0x14, 0x18)])
            variants = []
            for pointer in self.values(self.owner + 0x28, 'I'):
                variants.append([base.signed(self.r32(pointer + offset))
                                 for offset in (0x1c, 0x20, 0x14, 0x18, 8)])
            parts = self.nested(self.owner + 0x30, 'h')
            xs = self.nested(self.owner + 0x38, 'h')
            ys = self.nested(self.owner + 0x40, 'h')
            frames = [list(map(list, zip(a, b, c))) for a, b, c in zip(parts, xs, ys)]
            animations = [list(map(list, zip(a, b))) for a, b in
                          zip(self.nested(self.owner + 0x48, 'B'), self.nested(self.owner + 0x50, 'H'))]
            return dict(rectangles=rectangles, variants=variants, frames=frames,
                        extra_points=list(map(list, zip(self.values(self.owner + 0x98, 'h'),
                                                        self.values(self.owner + 0xa0, 'h')))),
                        animations=animations, consumed=self.cursor,
                        initial_animation=self.values(self.owner + 0x5c, 'B'),
                        overall_bounds=self.values(self.owner + 0x88, 'h'),
                        frame_bounds=self.nested(self.owner + 0x80, 'h'),
                        image_ids=self.image_ids, variant_inputs=self.variant_inputs,
                        variant_definitions=self.variant_definitions,
                        boundaries=dict(self.calls))


    return OriginalDescriptor


def synthetic(rectangles, variants, frames, animations):
    out = bytearray([1, 0])
    out += struct.pack('>H', len(rectangles)) + bytes([0])
    for rectangle in rectangles:
        out += bytes(rectangle)
    out += struct.pack('>H', len(variants))
    for variant in variants:
        out += bytes(variant)
    out += struct.pack('>H', len(frames))
    for frame in frames:
        out.append(len(frame))
        for variant, x, y in frame:
            out += struct.pack('Bbb', variant, x, y)
        out.append(0)
    out += bytes([0, len(animations)])
    for animation in animations:
        out.append(len(animation))
        for frame, duration in animation:
            out += struct.pack('>BH', frame, duration)
    return bytes(out)


def scalars(value):
    return sum(map(scalars, value)) if isinstance(value, list) else 1


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('binary', 'libgcc', 'unicorn-dir', 'base-oracle', 'descriptor',
                 'image-properties', 'bmp', 'native-probe', 'native-header',
                 'native-source', 'native-probe-source', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--decoded-output', type=Path,
                   help='Optional private decoded fixture for the separate 2D clock oracle; do not publish game payloads')
    args = p.parse_args()
    image, gcc, descriptor = args.binary.read_bytes(), args.libgcc.read_bytes(), args.descriptor.read_bytes()
    properties, bmp = args.image_properties.read_bytes(), args.bmp.read_bytes()
    for data, expected, name in ((image, IMAGE_SHA, 'original executable'), (gcc, LIBGCC_SHA, 'original libgcc'),
                                  (descriptor, DESCRIPTOR_SHA, 'descriptor 256'), (bmp, BMP_SHA, 'BMP 997'),
                                  (properties, PROPERTY_SHA, 'image properties 1000')):
        if sha(data) != expected:
            raise ValueError(name + ' differs from pinned input')
    pairs = list(struct.iter_unpack('<II', properties))
    if pairs != [(6, 0xffffffff), (9, 0x00ff00ff), (14, 0x020003e5)]:
        raise ValueError('unexpected image property record')
    if bmp[:2] != b'BM' or struct.unpack_from('<iiHH', bmp, 18) != (69, 63, 1, 8):
        raise ValueError('unexpected source image dimensions or palette format')
    sys.path.insert(0, str(args.unicorn_dir))
    import unicorn
    spec = importlib.util.spec_from_file_location('v1_descriptor_combat_base', args.base_oracle)
    base = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(base)
    original_type = original_class(base)
    fields = ('rectangles', 'variants', 'frames', 'animations')
    cases = [('resource256', descriptor),
             ('synthetic-empty-frame', synthetic([[0, 0, 1, 1]], [[0, 0]],
                                                  [[[0, 0, 0]], []], [[[0, 100], [1, 1]]])),
             ('synthetic-signed-offsets-and-endian-duration',
              synthetic([[0, 0, 1, 1], [68, 62, 1, 1]], [[1, 0], [0, 0]],
                        [[[0, -128, 127], [1, 127, -128]], []], [[[0, 32767], [1, 1]]]))]
    results = []
    rejection_count = 0
    with tempfile.TemporaryDirectory(prefix='g1-overlay-oracle-') as temporary:
        path = Path(temporary) / 'descriptor.bin'
        for name, data in cases:
            path.write_bytes(data)
            run = subprocess.run([str(args.native_probe.resolve()), str(path), '69', '63'],
                                 capture_output=True, text=True, check=True, timeout=10)
            decoded = json.loads(run.stdout)
            original = original_type(image, gcc, data)
            reference = original.run()
            for field in fields:
                if decoded[field] != reference[field]:
                    raise RuntimeError(f'{name}: native/original mismatch for {field}')
            if reference['image_ids'] != [1000] or reference['extra_points']:
                raise RuntimeError('unexpected parser image/point branch')
            if any(reference['variant_inputs']):
                raise RuntimeError('unsupported transformed variant entered comparison')
            if reference['initial_animation'] != [step[0] for step in reference['animations'][0]]:
                raise RuntimeError('unexpected initial sequence')
            results.append({'case': name, 'source_sha256': sha(data), 'consumed_bytes': reference['consumed'],
                            'rectangles': len(decoded['rectangles']), 'variants': len(decoded['variants']),
                            'frames': len(decoded['frames']), 'animations': len(decoded['animations']),
                            'scalar_comparisons': sum(scalars(decoded[field]) for field in fields),
                            'metadata_sha256': sha(json.dumps(decoded, sort_keys=True).encode()),
                            'original_overall_bounds': reference['overall_bounds'],
                            'original_image_lookup_ids': reference['image_ids'],
                            'boundary_calls': reference['boundaries'], 'passed': True})
            if name == 'resource256' and args.decoded_output is not None:
                fixture = {'source_sha256': DESCRIPTOR_SHA, 'bytes_consumed': reference['consumed'],
                           'version': 1, 'wide_coordinates': False, 'extra_images': 0,
                           'rectangles': decoded['rectangles'], 'variants': reference['variant_definitions'],
                           'frames': [{'parts': frame, 'explicit_bounds': None} for frame in decoded['frames']],
                           'extra_points': [], 'animations': decoded['animations']}
                args.decoded_output.parent.mkdir(parents=True, exist_ok=True)
                args.decoded_output.write_text(json.dumps(fixture, indent=2) + '\n')
        # Safe-input rejection is native-only. The original is intentionally
        # not executed on malformed input or unsupported feature branches.
        bad_inputs = [descriptor[:cut] for cut in range(len(descriptor))]
        bad_inputs += [descriptor + b'\0']
        for offset, value in ((0, 2), (1, 1), (4, 1), (59, 255), (60, 1), (65, 255)):
            bad = bytearray(descriptor)
            bad[offset] = value
            bad_inputs.append(bytes(bad))
        for data in bad_inputs:
            path.write_bytes(data)
            run = subprocess.run([str(args.native_probe.resolve()), str(path), '69', '63'],
                                 capture_output=True, text=True, timeout=10)
            if run.returncode != 1:
                raise RuntimeError('native decoder accepted a malformed/unsupported descriptor')
            rejection_count += 1
    report = {
        'schema': 1, 'scope': 'Strict version-1 resource-256 metadata decoder versus original parser body',
        'original_image_sha256': IMAGE_SHA, 'original_libgcc_sha256': LIBGCC_SHA,
        'descriptor_resource': 256, 'descriptor_sha256': DESCRIPTOR_SHA,
        'image_properties_resource': 1000, 'image_properties_sha256': PROPERTY_SHA,
        'source_image_resource': 997, 'source_image_sha256': BMP_SHA,
        'source_image_dimensions': [69, 63], 'source_image_format': 'uncompressed 8-bit paletted BMP',
        'original_parser_range': ['0x5ecfe', '0x5f7f6'],
        'original_parser_parent': '0x5eb30',
        'original_helpers': ['0x7632', '0x7650', '0x7758', '0x7782', '0x2b1bc', '0x2adb6', '0x2ae20', '0x2ae14'],
        'instruction_patches': 0, 'original_code_readonly_and_unchanged': True,
        'boundaries': {'0x7672': 'raw stream byte-copy; endian/sign and field interpretation execute unchanged',
                       '0x61f9e': 'resolved image dimensions from pinned BMP; image property/palette loading excluded',
                       '0x1f540': 'bounded allocation', '0x1f512': 'free in a monotonic temporary arena',
                       '0x1f4e0': 'exact byte fill'},
        'oracle_sha256': sha(Path(__file__).read_bytes()),
        'base_oracle_sha256': sha(args.base_oracle.read_bytes()),
        'native_header_sha256': sha(args.native_header.read_bytes()),
        'native_source_sha256': sha(args.native_source.read_bytes()),
        'native_probe_source_sha256': sha(args.native_probe_source.read_bytes()),
        'native_probe_binary_sha256': sha(args.native_probe.read_bytes()),
        'unicorn_version': unicorn.__version__, 'case_count': len(results),
        'scalar_comparisons': sum(case['scalar_comparisons'] for case in results),
        'native_only_rejected_inputs': rejection_count, 'cases': results,
        'limitations': ['Only the observed narrow-coordinate, identity-variant, single-image v1 profile is supported',
                        'No archive selection, image property loader or BMP pixel decoder executes in this parser comparison',
                        'Overall/frame collision bounds are not part of the native metadata interface',
                        'No clock, projection, viewport mapping, clipping, draw submission, Metal or device execution',
                        'Malformed-input rejections are safe native policy, not a claim of original failure parity'],
        'passed': True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ('case_count', 'scalar_comparisons',
                                                  'native_only_rejected_inputs', 'passed')}))


if __name__ == '__main__':
    main()
