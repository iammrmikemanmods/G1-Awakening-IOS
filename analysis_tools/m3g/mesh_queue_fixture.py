#!/usr/bin/env python3
"""Emit synthetic numeric classification vectors captured from original code."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raw = args.input.read_bytes()
    data = json.loads(raw)
    lines = ['#pragma once', '#include <cstdint>', '#include <vector>',
             '// Original fixture SHA256 ' + hashlib.sha256(raw).hexdigest(),
             'namespace g1_queue_test {',
             'struct Case { const char* name; std::uint8_t blend; '
             'std::uint32_t parent,node,effective; int material; std::uint8_t colors,default_alpha; '
             'int texture0,texture1; bool transparent; std::int32_t serial,grouping; };',
             'inline const std::vector<Case> cases = {']
    count = 0
    for case in data['cases']:
        out = case['original']
        if out is None:
            continue
        inp = case['input']
        # The native Scene already resolves a missing CompositingMode to its
        # original REPLACE default. The seeded original blend byte is ignored
        # when that pointer is absent; do not turn it into a live native mode.
        resolved_blend = inp['blend'] if inp.get('compositing_present', True) else 68
        values = [json.dumps(case['name']), str(resolved_blend),
                  f"0x{inp['parent_alpha_bits']:08x}U", f"0x{inp['node_alpha_bits']:08x}U",
                  f"0x{out['effective_alpha_bits']:08x}U",
                  str(inp['material_diffuse_alpha'] if inp['material_diffuse_alpha'] is not None else -1),
                  str(inp['color_components'] or 0), str(inp['default_alpha'])]
        values += [str(value if value is not None else -1) for value in inp['texture_formats']]
        values += [str(out['transparent']).lower(), str(inp.get('serial', 37)), str(out['grouping_key'])]
        lines.append('    {' + ','.join(values) + '},')
        count += 1
    lines += ['};', '} // namespace g1_queue_test', '']
    args.output.write_text('\n'.join(lines))
    print(json.dumps({'classification_cases': count, 'skipped_no_queue_cases': len(data['cases']) - count,
                      'sha256': hashlib.sha256(args.output.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
