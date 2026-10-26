#!/usr/bin/env python3
"""Generate a native test fixture from the synthetic original spline record.

This generated data contains synthetic inputs and observed scalar results only;
no original executable, proprietary model, or CPU runtime is included.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct


def bits(value):
    return struct.unpack('<I', struct.pack('<f', value))[0]


def values(items):
    return '{' + ','.join(f'0x{x:08x}U' for x in items) + '}'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--reference',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    raw=args.reference.read_bytes(); reference=json.loads(raw)
    lines=['#pragma once', '', '#include "g1/M3GAnimation.hpp"', '#include <cstring>', '#include <initializer_list>', '#include <string>', '#include <utility>', '',
           'namespace g1_spline_test {',
           f'// Synthetic original-function record SHA-256: {hashlib.sha256(raw).hexdigest()}',
           'inline float scalar(std::uint32_t bits) { float v;std::memcpy(&v,&bits,4);return v; }',
           'inline std::vector<float> scalars(std::initializer_list<std::uint32_t> bits) {',
           '    std::vector<float> result;for(const auto b:bits)result.push_back(scalar(b));return result;', '}',
           'struct Prepared { std::size_t index;std::vector<std::uint32_t> value,outgoing,incoming; };',
           'struct Sample { std::int32_t time;std::uint32_t weight;std::vector<std::uint32_t> initial,expected; };',
           'struct Case { std::string name;g1::M3GSequence sequence;std::vector<Prepared> prepared;std::vector<Sample> samples; };',
           'inline std::vector<Case> cases() {', '    std::vector<Case> result;']
    for entry in reference['cases']:
        source=entry['input']
        lines += ['    {',f'        Case c;c.name={json.dumps(source["name"])};',
                  f'        c.sequence.interpolation={source["interpolation"]};c.sequence.repeat_mode={source["repeat_mode"]};',
                  f'        c.sequence.duration={source["duration"]};c.sequence.first={source["first"]};c.sequence.last={source["last"]};',
                  f'        c.sequence.components={source["components"]};']
        for time,vector in source['keyframes']:
            lines.append(f'        c.sequence.keyframes.push_back({{{time},scalars({values([bits(x) for x in vector])})}});')
        for prepared in entry['prepared']:
            arrays=','.join(values(prepared[field]['bits']) for field in ('value','outgoing','incoming'))
            lines.append(f'        c.prepared.push_back({{{prepared["index"]},{arrays}}});')
        for sample in entry['samples']:
            lines.append(f'        c.samples.push_back({{{sample["world_time"]},0x{sample["weight_bits"]:08x}U,{values(sample["initial_bits"])},{values(sample["result"]["bits"])}}});')
        lines += ['        result.push_back(std::move(c));','    }']
    lines += ['    return result;','}', '} // namespace g1_spline_test','']
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text('\n'.join(lines))
    print(json.dumps({'cases':len(reference['cases']),'samples':sum(len(x['samples']) for x in reference['cases']),
                      'output_sha256':hashlib.sha256(args.output.read_bytes()).hexdigest()}))


if __name__=='__main__':main()
