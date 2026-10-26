#!/usr/bin/env python3
"""Native Sprite3D comparison against the frozen original-execution recorder.

Expected values come only from that independent original JSON, never from the
native implementation. The text fixture and metadata contain no game payload.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess

REFERENCE_SHA = '027532e072019b84008ace8b566fb7a370fa8070bb4803f233208d12f4b66722'
def sha(data): return hashlib.sha256(data).hexdigest()
def bits(v): return struct.unpack('<I', struct.pack('<f', v))[0]
def identity(): return [float(i % 5 == 0) for i in range(16)]


def make_fixture(reference):
    lines = [f'G1SPRITE3D1 {len(reference["cases"])} {len(reference["shared_queue_cases"])}']
    def line(tag, values): lines.append(tag + ' ' + ' '.join(str(x) for x in values))
    for result in reference['cases']:
        c = result['case']; lines.append('CASE ' + c['name'])
        line('I', [c['projection_type'], int(c.get('scaled', True)), int(c.get('appearance', True)),
                   *c.get('viewport', [480,320]), *c.get('image_size', [64,128])])
        for tag, values in [('C', c.get('crop', [0,0,64,128])), ('M', c['world']), ('V', c.get('view', identity()))]:
            line(tag, map(bits, values))
        line('P', result['projection_bits'])
        line('E', [int(bool(result['gl_draws']))])
        if result['gl_draws']:
            draw = result['draws'][0]; arrays = result['gl_draws'][0]
            translate = next(x for x in result['selected_gl_calls'] if x['name'] == '_glTranslatef')
            line('O', translate['arguments_raw'][:3]);line('R', draw['rectangle_fixed16'])
            line('B', draw['crop_bounds_fixed16']);line('F', [int(draw['mirror_x']), int(draw['mirror_y'])])
            line('XY', arrays['positions_fixed16']);line('UV', arrays['uv_fixed16'])
    for queue in reference['shared_queue_cases']:
        lines.append(f'QUEUE {queue["name"]} {len(queue["entries"])}')
        line('CAM', map(bits, queue['camera_world_position']))
        objects = {}
        for row in queue['entries']:
            c = row['entry']; objects.setdefault(c['object'], len(objects) + 1)
            line('D', [objects[c['object']], c['layer'], int(c['transparent']), c.get('material_key', 0),
                       *map(bits, c.get('position', [0,0,0]))])
            line('K', [row['key_signed']])
        line('ORDER', [x-1 for x in queue['draw_order_indices']])
    lines.append('END')
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--probe', type=Path, required=True)
    parser.add_argument('--fixture', type=Path)
    parser.add_argument('--native-test', type=Path)
    parser.add_argument('--ubsan-test', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args();root = args.root.resolve()
    reference_path = root / 'native/research/m3g_validation/sprite3d_original_projected_draws.json'
    raw = reference_path.read_bytes()
    if sha(raw) != REFERENCE_SHA: raise ValueError('frozen original Sprite3D reference changed')
    reference = json.loads(raw)
    fixture_path = args.fixture or root / 'native/tests/m3g_sprite3d_cases.txt'
    fixture_path.parent.mkdir(parents=True, exist_ok=True)
    fixture_path.write_text(make_fixture(reference))
    fixture_provenance = {'schema': 1, 'format': 'G1SPRITE3D1',
                          'fixture_sha256': sha(fixture_path.read_bytes()),
                          'expected_values_source': 'Frozen unchanged-original renderer/queue execution, not native output',
                          'reference_path': str(reference_path.relative_to(root)), 'reference_sha256': REFERENCE_SHA,
                          'original_executable_sha256': reference['original_sha256'],
                          'libgcc_sha256': reference['libgcc_sha256'],
                          'original_recorder_sha256': reference['runner_sha256'],
                          'generator_sha256': sha(Path(__file__).read_bytes()),
                          'renderer_cases': 142, 'drawn_cases': 47, 'original_numeric_boolean_values': 1557,
                          'authored_nodes': 54, 'authored_camera_seeds': 2, 'queue_sequences': 4,
                          'original_game_payloads_embedded': False}
    provenance_path = fixture_path.with_name(fixture_path.stem + '_provenance.json')
    provenance_path.write_text(json.dumps(fixture_provenance, indent=2) + '\n')
    run = subprocess.run([str(args.probe.resolve()), str(fixture_path.resolve())], check=True,
                         capture_output=True, text=True, timeout=30)
    actual = json.loads(run.stdout)
    differences, comparisons = [], 0
    def equal(name, field, actual, expected):
        nonlocal comparisons
        comparisons += len(expected) if isinstance(expected, list) else 1
        if actual != expected: differences.append({'case': name, 'field': field, 'actual': actual, 'expected': expected})
    equal('corpus', 'case_count', len(actual['cases']), len(reference['cases']))
    for expected, got in zip(reference['cases'], actual['cases']):
        name = expected['case']['name'];equal(name, 'name', got['name'], name)
        drawn = bool(expected['gl_draws']);equal(name, 'drawn', got['drawn'], drawn)
        if not drawn or not got['drawn']: continue
        center = next(x for x in expected['selected_gl_calls'] if x['name'] == '_glTranslatef')['arguments_raw'][:3]
        equal(name, 'center_bits', got['center_bits'], center)
        for field in ('rectangle_fixed16', 'crop_bounds_fixed16', 'mirror_x', 'mirror_y'):
            equal(name, field, got[field], expected['draws'][0][field])
        for field in ('positions_fixed16', 'uv_fixed16'):
            equal(name, field, got[field], expected['gl_draws'][0][field])
    equal('corpus', 'queue_count', len(actual['queues']), len(reference['shared_queue_cases']))
    for expected, got in zip(reference['shared_queue_cases'], actual['queues']):
        name = expected['name'];equal(name, 'name', got['name'], name)
        equal(name, 'keys', got['keys'], [x['key_signed'] for x in expected['entries']])
        equal(name, 'order', got['order'], [x-1 for x in expected['draw_order_indices']])
    contracts = {}
    for name, path in [('optimized', args.native_test), ('undefined_behavior_sanitizer', args.ubsan_test)]:
        if path is None: continue
        tested = subprocess.run([str(path.resolve()), str(fixture_path.resolve())], check=True,
                                capture_output=True, text=True, timeout=30)
        observed = json.loads(tested.stdout)
        if (not observed.get('passed') or observed.get('original_value_checks') != 1557 or
                observed.get('contract_checks') != 30 or tested.stderr):
            raise ValueError('focused native Sprite3D contract run differed')
        contracts[name] = {'result': observed, 'executable_sha256': sha(path.read_bytes()),
                           'exit_code': tested.returncode, 'stderr': tested.stderr}
    report = {'schema': 1, 'scope': 'Native Sprite3D arithmetic versus frozen unchanged-original GL recording',
              'reference_sha256': REFERENCE_SHA, 'original_executable_sha256': reference['original_sha256'],
              'libgcc_sha256': reference['libgcc_sha256'], 'fixture_sha256': sha(fixture_path.read_bytes()),
              'probe_sha256': sha(args.probe.read_bytes()), 'comparisons': comparisons,
              'original_numeric_boolean_comparisons': 1557, 'binary32_origin_values_compared_exactly': 141,
              'fixed16_values_compared_exactly': 1128, 'contracts': contracts,
              'cases': len(reference['cases']), 'draws': sum(bool(x['gl_draws']) for x in reference['cases']),
              'queue_sequences': len(reference['shared_queue_cases']), 'differences': differences,
              'passed': not differences, 'gpu_tested': False, 'iphone_tested': False,
              'reference_limits': reference['boundaries'],
              'source_sha256': {str(p.relative_to(root)): sha(p.read_bytes()) for p in
                               [Path(__file__), root / 'native/include/g1/M3GSprite3D.hpp',
                                root / 'native/src/M3GSprite3D.cpp', root / 'native/tools/m3g_sprite3d_probe.cpp',
                                root / 'native/tests/m3g_sprite3d_fixture.hpp', root / 'native/tests/m3g_sprite3d_test.cpp']}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'comparisons': comparisons, 'differences': len(differences), 'first_differences': differences[:8],
                      'output': str(args.output)}, indent=2))
    if differences: raise SystemExit(1)


if __name__ == '__main__': main()
