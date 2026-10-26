#!/usr/bin/env python3
"""Preserve ordinary controller/draw recordings as a native test protocol.

Development only. Reads the frozen original JSON; no original executable,
graphics, random generator or runtime instruction translation is included.
"""
import argparse
import hashlib
import json
from pathlib import Path

KINDS = ['animate', 'start_clip', 'tick_clip', 'select_camera',
         'propagate_camera', 'place_effect', 'clear_text', 'set_integer_text', 'audio']
TARGETS = ['model_a', 'model_b', 'effect_0', 'effect_1', 'effect_2', 'effect_3', 'death_effect']
SIDES_A = {0, 1, 2, 6, 7, 9, 11}
PIN = '2a0d24678c03d9a88942e021a8cf8eeafb0577e9dc2c8923c2ac9d368e35cca2'


def config(inp):
    embedded = sum(1 << i for i in range(13) if i != 8 and
                   inp.get('embedded_a' if i in SIDES_A else 'embedded_b', False))
    fields = [('a_first', True), ('counter', False), ('intro', False),
              ('form_a', 0), ('form_b', 0), ('faction_a', 0), ('faction_b', 1),
              ('adjust_a', 1), ('adjust_b', 0), ('immune_a', False), ('immune_b', False),
              ('death_a', False), ('death_b', False), ('damage_a', 17), ('damage_b', 31),
              ('final_a', 83), ('final_b', 69)]
    return [int(inp.get(key, default)) for key, default in fields] + [320, 480, embedded]


def state(row):
    return [int(row[k]) for k in ['phase', 'complete', 'camera_side_a', 'embedded_current',
        'elapsed', 'slide_fixed16', 'clock_a', 'clock_b', 'display_health_a', 'display_health_b']]


def event(e):
    return [KINDS.index(e['kind']), TARGETS.index(e.get('target', 'model_a')),
        e.get('time', 0), e.get('clip', 0), {'a': 0, 'b': 1}[e.get('clock', 'a')],
        e.get('delta', 0), e.get('id', 0), e.get('adjust', 0), int(e.get('field', '0'), 0),
        e.get('value', 0), e.get('category', 0), e.get('event', 0), int(e.get('restart', False)),
        int(e.get('side_a', False)), int(e.get('hit', False))]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('reference', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    raw = a.reference.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PIN:
        raise ValueError('reference differs from the frozen original execution')
    data = json.loads(raw)
    steps = [(row['name'], row['input'], row['before'], row['delta'], row) for row in data['cases']]
    for sequence in data['sequences']:
        steps.extend((sequence['name'] + '_' + str(i), sequence['input'], row['before'],
                      sequence['delta'], row) for i, row in enumerate(sequence['steps']))
    lines = ['G1_BATTLE_CONTROLLER_1', str(len(steps))]
    def values(v): lines.append(' '.join(str(x) for x in v))
    for name, inp, before, delta, row in steps:
        lines.append(name); values(config(inp)); values(state(before)); lines.append(str(delta))
        values(state(row['state'])); lines.append(str(len(row['events'])))
        for e in row['events']: values(event(e))
    lines.append(str(len(data['draw_cases'])))
    for row in data['draw_cases']:
        inp = row['input']
        lines.append(row['name']); values(config(inp))
        values([inp.get('phase', 0), 0, int(inp.get('camera_side_a', True)), 0,
                inp.get('elapsed', 0), -41943040, 1666, 1666, 100, 100])
        lines.append(str(int(row['refresh'])))
        render = next((e for e in row['events'] if e['kind'] == 'render_scene_and_participants'), None)
        damage = next((e for e in row['events'] if e['kind'] == 'draw_damage_text'), None)
        values([int(render is not None)] +
               [int(render['enabled'][name]) if render else 0 for name in TARGETS] +
               [int(damage is not None), damage['x'] if damage else 0,
                damage['y'] if damage else 0, -41943040])
    a.output.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'steps': len(steps), 'draws': len(data['draw_cases']),
                      'bytes': a.output.stat().st_size,
                      'sha256': hashlib.sha256(a.output.read_bytes()).hexdigest()}))


if __name__ == '__main__': main()
