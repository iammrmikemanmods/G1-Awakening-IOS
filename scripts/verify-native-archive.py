#!/usr/bin/env python3
"""Check every object in a native iPhoneOS static archive; this is not an app test."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct


def members(data: bytes):
    if not data.startswith(b'!<arch>\n'):
        raise ValueError('expected a regular ar archive')
    offset = 8
    while offset < len(data):
        if len(data) - offset < 60:
            raise ValueError('truncated archive header')
        header = data[offset:offset + 60]
        if header[58:60] != b'`\n':
            raise ValueError('invalid archive header marker')
        try:
            size = int(header[48:58].decode('ascii').strip())
            name = header[:16].decode('ascii').rstrip()
        except (UnicodeDecodeError, ValueError) as error:
            raise ValueError('invalid archive member metadata') from error
        if size < 0 or offset + 60 + size > len(data):
            raise ValueError('archive member exceeds input bounds')
        body = data[offset + 60:offset + 60 + size]
        if name.startswith('#1/'):
            name_length = int(name[3:])
            if name_length < 1 or name_length > len(body):
                raise ValueError('invalid BSD extended member name')
            name = body[:name_length].rstrip(b'\0').decode('utf-8')
            body = body[name_length:]
        else:
            name = name.rstrip('/')
        if not (name.startswith('__.SYMDEF') or name in ('', '/')):
            yield name, body
        offset += 60 + size
        if size % 2:
            if offset >= len(data) or data[offset:offset + 1] != b'\n':
                raise ValueError('missing archive alignment byte')
            offset += 1


def inspect_object(name: str, data: bytes):
    if len(data) < 32:
        raise ValueError(f'{name}: truncated Mach-O header')
    magic, cpu, subtype, kind, count, command_bytes, _flags, _reserved = \
        struct.unpack_from('<8I', data)
    if magic != 0xfeedfacf or cpu != 0x0100000c or subtype != 0 or kind != 1:
        raise ValueError(f'{name}: expected ordinary ARM64 Mach-O object code')
    if command_bytes > len(data) - 32 or count > command_bytes // 8:
        raise ValueError(f'{name}: invalid Mach-O load command bounds')
    cursor = 32
    target = None
    end = 32 + command_bytes
    for _ in range(count):
        if cursor + 8 > end:
            raise ValueError(f'{name}: truncated load command')
        command, size = struct.unpack_from('<II', data, cursor)
        if size < 8 or size % 8 or cursor + size > end:
            raise ValueError(f'{name}: invalid load command length')
        if command == 0x32:  # LC_BUILD_VERSION
            if target is not None or size < 24:
                raise ValueError(f'{name}: invalid or repeated build target')
            platform, minimum, sdk, tool_count = struct.unpack_from('<4I', data, cursor + 8)
            if tool_count > (size - 24) // 8:
                raise ValueError(f'{name}: invalid build tool list')
            if platform != 2 or minimum != ((17 << 16) | (5 << 8)):
                raise ValueError(f'{name}: expected iPhoneOS 17.5 target')
            target = {'platform': 'iPhoneOS', 'minimum_os': '17.5',
                      'sdk_encoded': sdk}
        cursor += size
    if cursor != end or target is None:
        raise ValueError(f'{name}: missing or malformed target metadata')
    return {'member': name, 'sha256': hashlib.sha256(data).hexdigest(),
            'architecture': 'arm64', **target}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    args = parser.parse_args()
    data = args.archive.read_bytes()
    objects = [inspect_object(name, body) for name, body in members(data)]
    if not objects:
        raise ValueError('archive contains no native objects')
    print(json.dumps({'archive': str(args.archive),
                      'sha256': hashlib.sha256(data).hexdigest(),
                      'object_count': len(objects), 'objects': objects,
                      'playable_app': False, 'device_execution_verified': False}, indent=2))


if __name__ == '__main__':
    main()
