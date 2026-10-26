#!/usr/bin/env python3
"""Original/native terrain sprite placement, playback and shared-RNG comparison.

Only synthetic input/result vectors are written to the portable fixture.
Actual game inputs remain local; their records contain hashes and counts only.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import struct
import subprocess
import sys

from sprite_decorations_oracle import OriginalSpriteDecorations, read_actual_inputs
from animated_map_oracle import decode_config, CONFIG_SHA, TABLES_SHA
from geometry_oracle import IMAGE_SHA, LIBGCC_SHA, digest, float_bits
from matrix_oracle import OriginalMatrix

DESCRIPTORS = (638, 825, 581, 1095, 1132, 982)
STEPS = [0, 249, 1, 250, 1000, 0, 1, 249] + [250] * 9


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def encode_config(tables):
    out = bytearray()
    for table in tables:
        out.append(len(table))
        for row in table:
            out.append(len(row))
            out += bytes(row)
    return bytes(out)


def synthetic(index):
    style = 0 if index % 2 == 0 else 2
    width, height = 5 + index % 4, 3 + index % 3
    cells = [(x * 7 + y * 11 + index * 3) % 32 for y in range(height) for x in range(width)]
    if index % 4 in (0, 1):
        for at in range(len(cells)):
            if at % 3 != 0: cells[at] = 13 if style == 0 else (18 if at % 2 else 23)
    if index % 6 == 0:
        cells[-width:] = [13] * width  # Counted bottom padding, never registered.
    lookup = [(i + index) % 4 for i in range(32)]
    # Give the left/right early-rejection and special branches varied inputs.
    tables = bytearray(480)
    for s in range(3):
        for tile in range(32):
            tables[s * 160 + tile * 5:s * 160 + tile * 5 + 5] = bytes(
                [tile % 32, (tile + 1) % 32, (tile + 2) % 32, (tile + 3) % 32, ((tile + index) % 4 - 2) & 255])
    config = [[[20, 14], [4, 21], [18, 23]], [], [], []]
    if index % 6 in (2, 3): config[0][style] = []
    rng = random.Random(0x69812 + index)
    bank = []
    for count in (1, 5, 3, 4, 8, 3):
        bank.append([[[rng.randrange(256), rng.randrange(1, 501)]
                      for _ in range(rng.randrange(1, 5))] for _ in range(count)])
    return {'name': f'synthetic_{index:02d}', 'style': style,
            'grid': bytes([width, height, *cells]), 'tables': bytes(tables),
            'config': encode_config(config), 'lookup': lookup, 'bank': bank,
            'seed': (0, 1, 0x47413133, 0xffffffff)[index % 4], 'steps': STEPS}


def input_words(case, magic=True):
    words = ['G1_TERRAIN_SPRITE_INPUT_V1'] if magic else []
    words += [case['seed'], case['style']]
    for data in (case['grid'], case['tables'], case['config'], case['lookup']):
        words += [len(data), *data]
    for animations in case['bank']:
        words.append(len(animations))
        for steps in animations:
            words += [len(steps), *(value for step in steps for value in step)]
    words += [len(case['steps']), *case['steps']]
    return words


def flatten_snapshot(state):
    words = [state['accumulated_ms'], state['phase'], state['random_index'], state['random_draws'],
             len(state['candidate_records']), *state['candidate_records'],
             len(state['slot_phases']), *state['slot_phases'], len(state['sprites'])]
    for sprite in state['sprites']:
        words += [sprite['index'], sprite['selector'], sprite['animation'], sprite['visible'],
                  sprite['enabled'], sprite['parent'], sprite['attachment_order'], sprite['position'] is not None]
        if sprite['position'] is not None: words += sprite['position']
        words += sprite['playback']
    return [int(x) for x in words]


def fixture_case(case, layout, states, final_words, draws):
    out = [f"CASE {case['name']}", 'INPUT ' + ' '.join(map(str, input_words(case, False)))]
    layout_words = [layout['candidate_capacity'], layout['registered_candidates'],
                    layout['slot_count'], layout['fixed_sprite_capacity'], layout['original_sprite_count']]
    out.append('LAYOUT ' + ' '.join(map(str, layout_words)))
    out.append('STATES ' + str(len(states)))
    for state in states:
        words = flatten_snapshot(state)
        out.append('STATE ' + ' '.join(map(str, [len(words), *words])))
    out.append('RNG ' + ' '.join(map(str, final_words)))
    out.append('DRAWS ' + str(len(draws)))
    for d in draws:
        out.append('DRAW ' + ' '.join(map(str, [d['index'], d['descriptor'], d['image'], d['key'],
                    d['frame'], d['parent'], d['attachment_order'], *d['model_bits']])))
    out.append('END')
    return '\n'.join(out)


def original_draws(original, matrix, cache):
    draws = []
    for sprite in original.snapshot()['sprites']:
        data = original.instances[sprite['index']]
        if not sprite['visible'] or not sprite['parent']: continue
        operations = data['operations']
        if [x[0] for x in operations] != ['transform_identity',
                                         'transform_translation', 'transform_rotation']:
            raise RuntimeError(f"original terrain placement transform sequence differs at{sprite['index']}: {operations}")
        # Original727a4 skips setScale when its argument equals1. Run exactly
        # identity -> translation -> quaternion rotation in the original core.
        translation, angle, axis = operations[1][1], operations[2][1][0], operations[2][1][1:]
        components = [sprite['position'], translation, angle, axis]
        key = canonical(components)
        if key not in cache:
            matrix.call(0xa6848, [matrix.transform_core])
            matrix.u.mem_write(matrix.vector, struct.pack('<3I', *translation))
            matrix.call(0xa6766, [matrix.transform_core, matrix.vector])
            matrix.call(0xba390, [angle, 0x3c8efa35])
            radians = matrix.u.reg_read(matrix.ar.UC_ARM_REG_R0)
            matrix.u.mem_write(matrix.vector, struct.pack('<3I', *axis))
            matrix.call(0x9fbd4, [matrix.quaternion, radians, matrix.vector])
            matrix.call(0xa69b0, [matrix.transform_core, matrix.quaternion])
            cache[key] = matrix.matrix_bits()
        draws.append({'index': sprite['index'], 'descriptor': data['descriptor'], 'image': 961,
                      'key': 0xf4e02223, 'frame': sprite['playback'][1], 'parent': sprite['parent'],
                      'attachment_order': sprite['attachment_order'],
                      'model_bits': cache[key]})
    return sorted(draws, key=lambda draw: draw['attachment_order'])


def check_case(case, image, gcc, native_probe, matrix, matrix_cache, fixture):
    original = OriginalSpriteDecorations(image, gcc)
    bank = dict(zip(DESCRIPTORS, case['bank']))
    layout = original.setup_pool(case['grid'], decode_config(case['config']), case['tables'],
                                 case['style'], case['lookup'], bank, case['seed'], [0] * 207)
    states = [original.snapshot()] + [original.advance(delta) for delta in case['steps']]
    native_result = subprocess.run([str(native_probe.resolve())],
        input=' '.join(map(str, input_words(case))), text=True, capture_output=True, timeout=15)
    if native_result.returncode:
        raise RuntimeError(f"{case['name']} native probe failed: {native_result.stderr}")
    native = json.loads(native_result.stdout)
    for key, value in native['layout'].items():
        if value != layout[key]:
            raise RuntimeError(f"{case['name']} layout{key}: native{value} original{layout[key]}")
    if len(native['snapshots']) != len(states):
        raise RuntimeError('native snapshot count differs')
    comparisons = 0
    for i, (expected, actual) in enumerate(zip(states, native['snapshots'])):
        words = actual.pop('random_words')
        actual['random_words_sha256'] = digest(struct.pack('<624I', *words))
        if actual != expected:
            for key, value in expected.items():
                if actual.get(key) != value:
                    if key == 'sprites':
                        for j, (a, e) in enumerate(zip(actual[key], value)):
                            if a != e:
                                raise RuntimeError(json.dumps({'case': case['name'], 'snapshot': i,
                                    'sprite': j + 4, 'native': a, 'original': e}))
                    raise RuntimeError(json.dumps({'case': case['name'], 'snapshot': i, 'field': key,
                                                   'native': actual.get(key), 'original': value}))
        comparisons += len(flatten_snapshot(expected)) + 624
    expected_draws = original_draws(original, matrix, matrix_cache)
    if native['draws'] != expected_draws:
        for actual, expected in zip(native['draws'], expected_draws):
            if actual != expected:
                raise RuntimeError(json.dumps({'case': case['name'], 'native_draw': actual, 'original_draw': expected}))
        raise RuntimeError('native/original attached draw count differs')
    comparisons += len(expected_draws) * 23
    final_words = list(struct.unpack('<624I', original.u.mem_read(original.rng + 0x14, 624 * 4)))
    if fixture is not None: fixture.append(fixture_case(case, layout, states, final_words, expected_draws))
    original.check_text()
    summary = {'name': case['name'], 'style': case['style'], 'seed': case['seed'],
               'grid_sha256': digest(case['grid']), 'grid_dimensions': list(case['grid'][:2]),
               'lookup_sha256': digest(bytes(case['lookup'])),
               **{k: v for k, v in layout.items() if k != 'initial_candidate_records'},
               'snapshots': len(states), 'final_draws': original.draws,
               'final_visible_attached_sprites': len(expected_draws),
               'source_and_native_state_sha256': digest(canonical(states)),
               'source_and_native_draws_sha256': digest(canonical(expected_draws)),
               'random_words_sha256': states[-1]['random_words_sha256'],
               'scalar_comparisons': comparisons, 'passed': True}
    if 'resource' in case: summary['grid_resource_id'] = case['resource']
    print(json.dumps({k: summary[k] for k in ('name', 'slot_count', 'initial_pool_draws',
                      'stage2_draws', 'snapshots', 'final_visible_attached_sprites', 'passed')}), flush=True)
    return summary, original.calls


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for option in ('binary', 'libgcc', 'unicorn-dir', 'manifest', 'tables', 'native-probe',
                   'atlas-decoder', 'catalog', 'fixture', 'output'):
        ap.add_argument('--' + option, type=Path, required=True)
    ap.add_argument('--synthetic-count', type=int, default=12)
    ap.add_argument('--only-synthetic', action='store_true')
    args = ap.parse_args()
    sys.path.insert(0, str(args.unicorn_dir))
    import unicorn
    image, gcc, tables = args.binary.read_bytes(), args.libgcc.read_bytes(), args.tables.read_bytes()
    if (digest(image), digest(gcc), digest(tables)) != (IMAGE_SHA, LIBGCC_SHA, TABLES_SHA):
        raise ValueError('original image/libgcc/visual tables differ from audited inputs')
    spec = importlib.util.spec_from_file_location('atlas_reference', args.atlas_decoder)
    decoder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(decoder)
    resource = read_actual_inputs(args.manifest)
    if digest(resource(307)) != CONFIG_SHA: raise ValueError('resource307 differs from audited input')
    matrix, cache, fixture, reports, calls = OriginalMatrix(image, gcc), {}, [], [], {}
    cases = [synthetic(i) for i in range(args.synthetic_count)]
    synthetic_count = len(cases)
    if not args.only_synthetic:
        bank = [decoder.decode(resource(rid))['animations'] for rid in DESCRIPTORS]
        catalog = json.loads(args.catalog.read_text())['catalog']['map_style_pairs']
        for entry in catalog:
            style, rid = entry['style'], entry['resource']
            if style not in (0, 2): continue
            lookup = list(resource(282 if style == 0 else 281)[1:])
            if style == 0:
                lookup = [0] * 32
                for i in (1, 2, 3, 4, 5, 26, 27): lookup[i] = 1
                for i in (6, 12, 13): lookup[i] = 3
            else:
                for i, v in ((8, 1), (19, 0), (30, 1), (31, 1)): lookup[i] = v
            cases.append({'name': f'resource{rid}_style{style}', 'resource': rid, 'style': style,
                          'seed': 0x47413133, 'grid': resource(rid), 'tables': tables,
                          'config': resource(307), 'lookup': lookup, 'bank': bank, 'steps': STEPS})
    for i, case in enumerate(cases):
        report, boundaries = check_case(case, image, gcc, args.native_probe, matrix, cache,
                                         fixture if i < synthetic_count else None)
        reports.append(report)
        for name, count in boundaries.items(): calls[name] = calls.get(name, 0) + count
    args.fixture.parent.mkdir(parents=True, exist_ok=True)
    args.fixture.write_text('G1_TERRAIN_SPRITE_ORACLE_V1 ' + str(synthetic_count) + '\n' + '\n'.join(fixture) + '\n')
    output = {'scope': 'Bounded style0/2 terrain sprite construction, updates and model matrices versus unchanged original instructions',
        'original_sha256': IMAGE_SHA, 'libgcc_sha256': LIBGCC_SHA, 'visual_tables_sha256': TABLES_SHA,
        'config_resource_id': 307, 'config_sha256': CONFIG_SHA, 'unicorn_version': unicorn.__version__,
        'original_code_readonly_and_unchanged': True, 'instruction_patches': 0,
        'original_blocks': ['0x6a3cc..0x6a782', '0x6b1e8..0x6b28c', '0x6b606..0x6b660',
                            '0x693d0..0x694ee', '0x6980c..0x6993a', '0x6994c..0x6a1e8', '0x6d656..0x6d758/0x6d82a'],
        'original_functions': ['0x474a0', '0x45a5e', '0x64e64', '0x64ebc', '0x7acc', '0x7b26', '0x2b43c',
                               '0x66d58', '0x70dd4', '0x652e4', '0x5d17a', '0x72d80', '0x72cc0', '0x727a4', '0x6526c'],
        'substitutions': ['bounded allocation/free and exact memset/animation-byte initialization',
                          'decoded descriptor data and M3G object construction at7315c',
                          'geometry-refresh observer at728f0; its quad math is validated separately',
                          'M3G ownership/enable/parent/transform recording boundaries',
                          'shared singleton, nonthrowing unwind registration',
                          'original ARMv6 libgcc import redirection',
                          'matrix external memcpy and host sinf/cosf, not historical iOS libm'],
        'entry_profile': 'Actual source-grid dimensions, zero camera padding, one terrain batch; stage2 original front/side rows retained',
        'animation_lookup_entry': '207-byte vector, out-of-range selectors73..78 return0 through unchanged5d17a',
        'synthetic_cases': synthetic_count, 'actual_map_style_pairs': len(cases) - synthetic_count,
        'cases': reports, 'snapshots': sum(r['snapshots'] for r in reports),
        'scalar_comparisons': sum(r['scalar_comparisons'] for r in reports),
        'unique_original_matrix_core_executions': len(cache), 'boundary_calls': calls,
        'fixture_sha256': digest(args.fixture.read_bytes()), 'native_probe_sha256': digest(args.native_probe.read_bytes()),
        'oracle_sha256': digest(Path(__file__).read_bytes()),
        'sprite_oracle_sha256': digest((Path(__file__).parent / 'sprite_decorations_oracle.py').read_bytes()),
        'all_passed': True, 'native_gpu_or_device_test': False,
        'not_established': ['camera-dependent terrain padding and other original scene objects',
                            'complete live timed call order relative to all mission/AI/combat updates',
                            'historical seed identity', 'GPU pixel fidelity', 'full campaign playthrough']}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({k: output[k] for k in ('all_passed', 'synthetic_cases', 'actual_map_style_pairs',
                      'snapshots', 'scalar_comparisons', 'unique_original_matrix_core_executions')}))


if __name__ == '__main__':
    main()
