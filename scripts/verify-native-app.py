#!/usr/bin/env python3
"""Inspect the actual app executable; compilation is not a device launch test."""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import re
import struct


def inspect_executable(data):
    if len(data) < 32:
        raise ValueError('truncated native executable')
    magic, cpu, subtype, kind, count, command_bytes, flags, _ = struct.unpack_from('<8I', data)
    if (magic, cpu, subtype, kind) != (0xfeedfacf, 0x0100000c, 0, 2):
        raise ValueError('expected a thin ARM64 Mach-O executable')
    if command_bytes > len(data) - 32 or count > command_bytes // 8:
        raise ValueError('invalid Mach-O command bounds')
    cursor, end = 32, 32 + command_bytes
    target, entry = None, False
    dependencies = []
    for _ in range(count):
        if cursor + 8 > end:
            raise ValueError('truncated Mach-O command')
        command, size = struct.unpack_from('<II', data, cursor)
        if size < 8 or size % 8 or cursor + size > end:
            raise ValueError('invalid Mach-O command length')
        if command == 0x32:
            if target is not None or size < 24:
                raise ValueError('invalid/repeated build target')
            platform, minimum, sdk, tools = struct.unpack_from('<4I', data, cursor + 8)
            if platform != 2 or minimum != 0x00110500 or tools > (size - 24) // 8:
                raise ValueError('expected iPhoneOS minimum 17.5')
            target = {'platform': 'iPhoneOS', 'minimum_os': '17.5', 'sdk_encoded': sdk}
        elif command in (0xc, 0x80000018, 0x8000001f, 0x80000023):
            if size < 24:
                raise ValueError('invalid linked-library command')
            start = struct.unpack_from('<I', data, cursor + 8)[0]
            if start < 24 or start >= size:
                raise ValueError('invalid linked-library name offset')
            raw = data[cursor + start:cursor + size]
            if b'\0' not in raw:
                raise ValueError('unterminated linked-library name')
            name = raw.split(b'\0', 1)[0].decode('utf-8')
            if not name.startswith(('/System/Library/Frameworks/', '/usr/lib/')):
                raise ValueError('unexpected non-system runtime dependency: ' + name)
            dependencies.append(name)
        elif command == 0x80000028:
            if size != 24:
                raise ValueError('invalid native entry command')
            offset = struct.unpack_from('<Q', data, cursor + 8)[0]
            if offset >= len(data):
                raise ValueError('native entry point exceeds executable')
            entry = True
        elif command in (0x21, 0x2c):
            if size < 20 or struct.unpack_from('<I', data, cursor + 16)[0] != 0:
                raise ValueError('encrypted executable is unsupported')
        cursor += size
    if cursor != end or target is None or not entry:
        raise ValueError('missing native entry or iPhoneOS build target')
    return {'architecture': 'arm64', 'executable_sha256': hashlib.sha256(data).hexdigest(),
            'executable_bytes': len(data), 'system_dependencies': dependencies, **target}


def inspect_app(app):
    with (app / 'Info.plist').open('rb') as source:
        info = plistlib.load(source)
    if info.get('CFBundleExecutable') != 'G1AwakeningNative':
        raise ValueError('unexpected native executable name')
    if info.get('CFBundleIdentifier') != 'org.g1awakening.native.test':
        raise ValueError('unexpected test app identity')
    if info.get('MinimumOSVersion') != '17.5' or info.get('UIDeviceFamily') != [1]:
        raise ValueError('unexpected deployment target or device family')
    commit = info.get('G1SourceCommit', '')
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('source commit is not recorded in the app')
    result = inspect_executable((app / info['CFBundleExecutable']).read_bytes())
    result.update({'source_commit': commit, 'bundle_identifier': info['CFBundleIdentifier'],
                   'version': info['CFBundleShortVersionString'],
                   'artifact_kind': info.get('G1ArtifactKind', 'native test app'),
                   'feature_scope': info.get('G1FeatureScope', 'See source-specific validation'),
                   'original_assets_bundled': (app / 'GameData' / 'iphone.big').is_file(),
                   'device_execution_verified': False, 'full_playthrough_verified': False})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('app', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    report = json.dumps(inspect_app(args.app), indent=2) + '\n'
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report)
    print(report, end='')


if __name__ == '__main__':
    main()
