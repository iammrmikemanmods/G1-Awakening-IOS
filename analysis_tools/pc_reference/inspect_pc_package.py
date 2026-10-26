#!/usr/bin/env python3
"""Read-only PE/embedded-ZIP audit; never executes or extracts a payload.

Usage: python3 inspect_pc_package.py --exe G1Awakening.exe --ipa original.ipa
          --source-checkout /optional/touchHLE --output audit.json
Uses only Python's standard library. The original inputs are opened read-only.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import struct
import zipfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def pe_metadata(data):
    def unpack(fmt, off):
        return struct.unpack_from('<' + fmt, data, off)

    if data[:2] != b'MZ':
        raise ValueError('Missing MZ header')
    pe = unpack('I', 0x3c)[0]
    if data[pe:pe+4] != b'PE\0\0':
        raise ValueError('Missing PE header')
    machine, count, timestamp, symptr, symcount, optsize, flags = unpack('HHIIIHH', pe+4)
    opt = pe + 24
    if unpack('H', opt)[0] != 0x20b:
        raise ValueError('This audit expects PE32+')
    sections = []
    for i in range(count):
        off = opt + optsize + i*40
        name = data[off:off+8].split(b'\0')[0].decode('ascii')
        vsize, va, size, raw = unpack('IIII', off+8)
        if raw+size > len(data):
            raise ValueError('Truncated section')
        sections.append(dict(name=name, virtual_size=vsize, virtual_address=va,
                             raw_size=size, raw_offset=raw))

    def rva(addr, size=1):
        for s in sections:
            delta = addr-s['virtual_address']
            if delta >= 0 and delta+size <= s['raw_size']:
                return s['raw_offset']+delta
        raise ValueError('Unbacked RVA ' + hex(addr))

    def cstr(addr):
        off = rva(addr)
        end = data.find(b'\0', off, min(off+4096, len(data)))
        if end < 0:
            raise ValueError('Unterminated PE string')
        return data[off:end].decode('ascii')

    ndirs = unpack('I', opt+108)[0]
    dirs = [unpack('II', opt+112+i*8) for i in range(min(ndirs, 16))]
    imports = []
    if dirs[1][0]:
        off = rva(dirs[1][0], 20)
        for _ in range(1024):
            orig, stamp, forward, name, first = unpack('IIIII', off)
            off += 20
            if not any((orig, stamp, forward, name, first)):
                break
            entries = []
            thunk = rva(orig or first, 8)
            for j in range(16384):
                val = unpack('Q', thunk+j*8)[0]
                if not val:
                    break
                entries.append({'ordinal': val & 0xffff} if val >> 63 else cstr(val+2))
            imports.append({'dll': cstr(name), 'functions': entries})
        else:
            raise ValueError('Unbounded import list')

    resources = []
    if dirs[2][0]:
        root = rva(dirs[2][0], dirs[2][1])
        seen = set()

        def resource_name(value):
            if not value >> 31:
                return value
            off = root+(value & 0x7fffffff)
            length = unpack('H', off)[0]
            return data[off+2:off+2+2*length].decode('utf-16le')

        def visit(relative, path):
            if relative in seen or len(path) > 5:
                raise ValueError('Invalid resource tree')
            seen.add(relative)
            off = root+relative
            named, ids = unpack('HH', off+12)
            if named+ids > 4096:
                raise ValueError('Oversized resource list')
            for i in range(named+ids):
                name, target = unpack('II', off+16+i*8)
                node = path+[resource_name(name)]
                if target >> 31:
                    visit(target & 0x7fffffff, node)
                else:
                    va, size, page, reserved = unpack('IIII', root+target)
                    at = rva(va, size)
                    blob = data[at:at+size]
                    resources.append({'path': node, 'file_offset': at, 'bytes': size,
                                      'codepage': page, 'sha256': sha(blob),
                                      'utf8_text': blob.decode('utf-8', errors='replace')
                                      if node[0] == 24 else None})
        visit(0, [])
    raw_end = max(s['raw_offset']+s['raw_size'] for s in sections)
    return {'machine': hex(machine), 'architecture': 'x86_64' if machine == 0x8664 else 'other',
            'format': 'PE32+', 'subsystem': unpack('H', opt+68)[0],
            'image_base': hex(unpack('Q', opt+24)[0]),
            'entry_rva': hex(unpack('I', opt+16)[0]),
            'sections': sections, 'section_raw_end': raw_end,
            'bytes_after_sections': len(data)-raw_end,
            'clr_directory': list(dirs[14]), 'certificate_directory': list(dirs[4]),
            'imports': imports, 'resources': resources}


def embedded_zip(data):
    matches = []
    for match in re.finditer(b'PK\x05\x06', data):
        off = match.start()
        if off+22 > len(data):
            continue
        disk, start_disk, disk_count, count, cdsize, cdoff, comment = struct.unpack_from('<4H2IH', data, off+4)
        start = off-cdsize-cdoff
        end = off+22+comment
        if disk or start_disk or disk_count != count or not 0 < count <= 1024:
            continue
        if start < 0 or end > len(data) or data[start:start+4] != b'PK\x03\x04':
            continue
        with zipfile.ZipFile(io.BytesIO(data[start:end])) as z:
            if len(z.infolist()) == count:
                matches.append((start, end))
    if len(matches) != 1:
        raise ValueError(f'Expected one ZIP, found {len(matches)}')
    return matches[0]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--exe', type=Path, required=True)
    ap.add_argument('--ipa', type=Path, required=True)
    ap.add_argument('--source-checkout', type=Path)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    data = args.exe.read_bytes()
    start, end = embedded_zip(data)
    z = zipfile.ZipFile(io.BytesIO(data[start:end]))
    if sum(e.file_size for e in z.infolist()) > 256*1024*1024 or any(e.file_size > 64*1024*1024 for e in z.infolist()):
        raise ValueError('Payload exceeds this bounded audit')
    members = {}
    for e in z.infolist():
        blob = z.read(e)  # zipfile verifies CRC while reading every entry.
        members[e.filename] = {'path': e.filename, 'bytes': len(blob), 'compressed_bytes': e.compress_size,
                               'zip_crc32': f'{e.CRC:08x}', 'sha256': sha(blob)}
    provenance = json.loads(z.read('build_provenance.json'))
    original_claim = json.loads(z.read('SOURCE_PROVENANCE.json'))
    game_binary = z.read('game/G1awakening.app/G1awakening')
    magic, cpu, subtype, kind, commands, command_bytes, flags = struct.unpack_from('<7I', game_binary)
    if (magic, cpu, subtype, kind) != (0xfeedface, 12, 6, 2):
        raise ValueError('Expected original thin ARMv6 Mach-O executable')
    originals = []
    with zipfile.ZipFile(args.ipa) as ipa:
        for entry in original_claim['files']:
            actual = z.read(entry['path'])
            reference = ipa.read(entry['source_member'])
            originals.append({'path': entry['path'], 'source_member': entry['source_member'],
                              'bytes': len(actual), 'sha256': sha(actual),
                              'byte_identical_to_original_ipa': actual == reference})
    manifest_checks = []
    for manifest_name in ('runtime_file_hashes.json', 'DIAGNOSTIC_PAYLOAD.json'):
        claims = json.loads(z.read(manifest_name))['files']
        failures = []
        for entry in claims:
            name = entry.get('path', entry.get('file'))
            actual = members.get(name)
            if actual is None or actual['sha256'] != entry['sha256'] or actual['bytes'] != entry['bytes']:
                failures.append(name)
        manifest_checks.append({'manifest': manifest_name, 'entries_checked': len(claims), 'failures': failures})
    source_matches = []
    if args.source_checkout:
        base = args.source_checkout.resolve()
        for entry in provenance['patched_source_files']:
            rel = PurePosixPath(entry['file'])
            if rel.is_absolute() or '..' in rel.parts:
                raise ValueError('Unsafe source provenance path')
            path = (base / str(rel)).resolve()
            path.relative_to(base)
            actual = sha(path.read_bytes()) if path.is_file() else None
            source_matches.append({'file': str(path), 'recorded_sha256': entry['sha256'],
                                   'actual_sha256': actual, 'matches': actual == entry['sha256']})
    outer = data[:start]+data[end:]
    launch_strings = []
    for m in re.finditer(rb'[\x20-\x7e]{6,}', outer):
        text = m.group().decode('ascii')
        if any(k in text.lower() for k in ('touchhle', 'fps', 'scale-hack', 'widescreen', 'g1awakening', 'createprocess')):
            launch_strings.append(text)
    result = {'scope': 'Read-only static audit; no Windows executable run; no payload extracted or modified.',
              'input': {'path': str(args.exe.resolve()), 'bytes': len(data), 'sha256': sha(data)},
              'original_ipa': {'path': str(args.ipa.resolve()), 'sha256': sha(args.ipa.read_bytes())},
              'launcher_pe': pe_metadata(data),
              'embedded_zip': {'file_offset': start, 'end_exclusive': end, 'bytes': end-start,
                               'sha256': sha(data[start:end]), 'entries': len(members), 'all_entry_crc_checks_passed': True},
              'members': list(members.values()), 'original_app_comparison': originals,
              'payload_manifest_comparison': manifest_checks,
              'runtime_pe': pe_metadata(z.read('touchHLE.exe')),
              'original_game_macho': {'magic': hex(magic), 'cpu_type': cpu,
                                     'cpu_subtype': subtype, 'architecture': 'ARMv6',
                                     'format': 'Mach-O 32-bit little endian', 'file_type': kind,
                                     'load_commands': commands, 'load_command_bytes': command_bytes,
                                     'sha256': sha(game_binary)},
              'recorded_build_provenance': provenance, 'source_checkout_comparison': source_matches,
              'outer_launcher_relevant_strings': launch_strings,
              'interpretation': {'gameplay_source': 'Original ARMv6 executable hosted by touchHLE/Dynarmic',
                                 'native_windows_components': ['launcher', 'compatibility runtime'],
                                 'native_recovered_gameplay_found': False,
                                 'windows_playability_tested_by_this_audit': False,
                                 'package_metadata_can_predate_user_report': True}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'exe_sha256': sha(data),
                      'zip_entries_verified': len(members),
                      'original_app_byte_matches': sum(e['byte_identical_to_original_ipa'] for e in originals),
                      'original_app_files': len(originals),
                      'patched_sources_match': sum(e['matches'] for e in source_matches),
                      'patched_sources_checked': len(source_matches),
                      'payload_manifest_failures': sum(len(e['failures']) for e in manifest_checks)}))


if __name__ == '__main__':
    main()
