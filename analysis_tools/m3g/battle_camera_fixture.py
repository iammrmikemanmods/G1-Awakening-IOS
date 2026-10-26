#!/usr/bin/env python3
"""Convert recorded original camera boundary events to native test expectations."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raw = args.input.read_bytes();reference = json.loads(raw)
    cases = reference['cases']
    if len(cases) != 221 or reference['instruction_patches']:
        raise ValueError('unexpected original reference scope')
    labels = sorted({value for c in cases for e in c['events']
                     for key, value in e.items()
                     if key in ('object', 'result', 'camera') and isinstance(value, str)})
    labels = sorted(set(labels) | {'old_camera', 'old_camera_parent', 'old_camera_grandparent'})
    refs = {name: (1 if name.startswith('a:') else 2 if name.startswith('b:') else 0, i + 1)
            for i, name in enumerate(labels)}
    def node(name):
        return '{%d,%d}' % refs[name]
    def optional(name):
        return 'g1::M3GBattleCameraNode' + node(name) if name else 'std::nullopt'
    def ancestry(camera, events):
        parents = {e['object']: e['result'] for e in events if e['operation'] == 'parent'}
        parent = parents.get(camera)
        grandparent = parents.get(parent) if parent else None
        return '{' + ','.join(optional(n) for n in (camera, parent, grandparent)) + '}'
    def boolean(value):
        return 'true' if value else 'false'
    routes = {}
    for case in cases:
        key = (case['camera_id'], tuple(case['forms']))
        found = [e for e in case['events'] if e['operation'] == 'find']
        route = routes.setdefault(key, {})
        for e in found:
            if e['object'] == 'scene_world':
                route['name'] = e['result'][len('scene:'):]
                route['scene_key'] = e['user_id']
            elif e['object'] in ('model_a', 'model_b'):
                route['model_key'] = e['user_id']
    out = ['// Generated from unchanged-original camera boundary reference.\n',
           '// SHA256 ' + hashlib.sha256(raw).hexdigest() + '\n',
           '#pragma once\n#include "g1/M3GBattleCamera.hpp"\n\nnamespace g1_camera_test {\n',
           'struct Row { g1::M3GBattleCameraRequest request; g1::M3GBattleCameraState previous; bool model_found;\n',
           'g1::M3GBattleCameraAncestry current,selected; bool side_a; std::string_view scene_name;\n',
           'std::uint32_t scene_key,model_key; std::uint8_t adjustment; std::int32_t before,after;\n',
           'std::vector<g1::M3GBattleCameraEffect> effects; };\n',
           'inline const std::vector<Row> rows{\n']
    for c in cases:
        events = c['events'];split = next(i for i, e in enumerate(events) if e['operation'] == 'set_camera')
        before, after = events[:split], events[split+1:]
        calls = [e for e in events if e['operation'] == 'propagate_entry']
        if len(calls) != 2 or calls[0]['adjustment_byte'] != calls[1]['adjustment_byte']:
            raise ValueError('unexpected original propagation sequence')
        effects = []
        for e in events:
            kind = e['operation']
            if kind == 'animate':
                effects.append('{g1::M3GBattleCameraEffectKind::animate,' + node(e['object']) + ',' + str(e['time']) + ',{}}')
            elif kind == 'set_camera':
                effects.append('{g1::M3GBattleCameraEffectKind::set_active_camera,' + node(e['camera']) + ',0,{}}')
            elif kind == 'translation':
                if e['bits'] != [0, 0, 0x40000000]:
                    raise ValueError('unexpected original translation; preserve its exact bytes')
                effects.append('{g1::M3GBattleCameraEffectKind::translate,' + node(e['object']) + ',0,{{0,0,2}}}')
        route = routes[(c['camera_id'], tuple(c['forms']))]
        request = '{' + str(c['camera_id']) + ',{{' + ','.join(map(str, c['forms'])) + '}},{{' + ','.join(map(str, c['adjustment_flags'])) + '}}}'
        row = [request, '{' + boolean(c['old_model_camera']) + ',' + boolean(c['old_side_a']) + '}',
               boolean(c['stored_model_camera'] is not None),
               ancestry('old_camera' if c['old_active_camera'] else None, before),
               ancestry(c['selected_camera'], after), boolean(c['side_a_after']),
               json.dumps(route['name']), str(route['scene_key']) + 'U', str(route.get('model_key', 0)) + 'U',
               str(calls[0]['adjustment_byte']), str(calls[0]['time']), str(calls[1]['time']),
               '{' + ','.join(effects) + '}']
        out.append('{' + ','.join(row) + '},\n')
    out.append('};\n} // namespace g1_camera_test\n')
    args.output.write_text(''.join(out))
    print(json.dumps({'original_cases': len(cases), 'effects': sum(
        e['operation'] in ('animate', 'set_camera', 'translation') for c in cases for e in c['events']),
        'fixture_bytes': args.output.stat().st_size}))


if __name__ == '__main__':
    main()
