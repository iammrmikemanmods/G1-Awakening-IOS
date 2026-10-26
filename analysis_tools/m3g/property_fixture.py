#!/usr/bin/env python3
"""Compile captured original scalar-property observations into C++ test data.

The input is numeric development-only oracle output; no original code or asset
payload is emitted. Nonfinite/negative-controller diagnostics remain marked as
native rejection cases instead of being misreported as accepted-state parity.
"""
import argparse
import hashlib
import json
import math
import struct
from pathlib import Path


def finite(bits):
    return math.isfinite(struct.unpack('<f', struct.pack('<I', bits))[0])


def u(bits):
    return f'0x{bits:08x}U'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raw = args.input.read_bytes()
    data = json.loads(raw)
    lines = [
        '#pragma once', '#include <cstdint>', '#include <vector>',
        '// Original numeric fixture SHA256 ' + hashlib.sha256(raw).hexdigest(),
        'namespace g1_property_test {',
        'struct Direct { std::uint32_t property,value; std::uint8_t mode; bool visible,finite; '
        'std::uint32_t alpha; bool enabled; std::uint32_t field; };',
        'inline const std::vector<Direct> direct = {'
    ]
    accepted_direct = 0
    for case in data['direct']:
        mode = case['camera_mode'] or 0
        after = case['after']
        is_finite = finite(case['value_bits'])
        accepted_direct += is_finite
        values = [u(case['property']), u(case['value_bits']), str(mode),
                  str(case['visible_before']).lower(), str(is_finite).lower(),
                  u(after['alpha_bits']), str(bool(after['node_flags'] & 1)).lower(),
                  u(after['parallel_height_bits' if mode == 49 else 'fov_bits'])]
        lines.append('    {' + ','.join(values) + '},')
    lines += ['};',
              'struct Track { std::uint32_t property,value,weight; std::int32_t start,end; bool null_controller; };',
              'struct Sample { std::uint32_t property,value; };',
              'struct Dispatch { const char* name; std::uint8_t mode; bool visible,accepted; '
              'std::int32_t time; std::vector<Track> tracks; std::vector<Sample> samples; '
              'std::uint32_t alpha; bool enabled; std::uint32_t field; };',
              'inline const std::vector<Dispatch> dispatch = {']
    accepted_dispatch = 0
    for case in data['dispatch']:
        tracks = [item for group in case['track_groups'] for item in group]
        accepted = all(finite(t['weight_bits']) and not (t['weight_bits'] & 0x80000000)
                       for t in tracks)
        accepted_dispatch += accepted
        rendered_tracks = []
        for track in tracks:
            rendered_tracks.append('{' + ','.join([
                u(track['property']), u(track['value_bits']), u(track['weight_bits']),
                str(track.get('active_start', 0)), str(track.get('active_end', 0)),
                str(track.get('null_controller', False)).lower()]) + '}')
        rendered_samples = ['{' + u(e['property']) + ',' + u(e['value_bits']) + '}'
                            for e in case['events'] if e['entry'] == '0x8c0f2']
        mode = case['camera_mode']
        after = case['after']
        values = [json.dumps(case['name']), str(mode), str(case['visible_before']).lower(),
                  str(accepted).lower(), str(case['world_time']),
                  '{' + ','.join(rendered_tracks) + '}', '{' + ','.join(rendered_samples) + '}',
                  u(after['alpha_bits']), str(bool(after['node_flags'] & 1)).lower(),
                  u(after['parallel_height_bits' if mode == 49 else 'fov_bits'])]
        lines.append('    {' + ','.join(values) + '},')
    lines += ['};', '} // namespace g1_property_test', '']
    args.output.write_text('\n'.join(lines))
    print(json.dumps({'direct': len(data['direct']), 'finite_direct': accepted_direct,
                      'dispatch': len(data['dispatch']), 'accepted_dispatch': accepted_dispatch,
                      'output_sha256': hashlib.sha256(args.output.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
