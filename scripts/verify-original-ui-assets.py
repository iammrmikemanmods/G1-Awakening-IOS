#!/usr/bin/env python3
"""Verify recovered original G1 UI image identities against the user-supplied 1.1.3 IPA.

Read only. Never extracts executables, alters the IPA, generates artwork, or
claims original ARM32 UI dispatcher parity. The hashes are source-image hashes
from the independently checked Build 011 asset provenance report.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zipfile
import zlib

ARCHIVE_SHA256 = '663d2888982093ce66b7811ccb7a6ad3acd37fc02ffa85144775b88c39e83cb4'
UI_KEY = 0xB7178678
# resource ID : (width, height, source PNG SHA256)
IMAGES = {
    1002: (480, 320, '47f5a6c38db8c69f0b585d3430a274ceb27152d232dd0758b4b2e2efc3c9f691'),
    1004: (298, 62, 'f9bb98ff886cfcc8f1d0217e06138d1579a26e8a89abb3c4fefe3e937b69ec0d'),
    1034: (480, 93, 'bcb21e991868503d4a986fa007f60d6496e3603aef32596c2a385ba74f9da312'),
    721: (52, 49, '7fb785f36c5d974c6345f3c174358a1b97503f58092e68dac3d74a4921b93c6f'),
    639: (52, 49, '55d05575eb2cfc8e50a3cadfaa8a8ebb5c73cb013d732de2eb57fddfd66a0800'),
    793: (52, 49, '9354af28b9a3c65b5bb0fec4ca6cc8fd56d73ad20fc42e70aa2947fcd033fa2e'),
    660: (52, 49, 'b8f612f72093cfd51321e9a960a7a8d66783cdb85aa8331fb58114498708b963'),
    726: (52, 49, 'a5c1f635661a582aebf50cc6d60983e0740f046f4d1322248e53601b5fb7e5bc'),
    1118: (52, 49, '6abdf383748fc4ab119dd1031a54a43500f97b873d2390333da27737424848bf'),
    719: (60, 49, '64b7cba7b9e226ebd5a1f02374c1b072212fba319381b5b9fc6c042f4f3eb502'),
    454: (52, 49, '8921f40a030cfe1d50e52731b9fa0de2269798b7e1deff320e362c1974a22ce5'),
    919: (52, 49, 'a2b984932b89b64cf7b055ed51493c4e6bde648ce5da2ce805b42c87777d1bf6'),
    1076: (52, 49, 'ae4c1338304071dfe2efac5a6a5666b5c41a54635495e26003f62c28ce46d9fd'),
    905: (60, 49, '47aa4c8441acf215ff82b8a22df600c018f697d310dc03acc4a22c7270c2fd34'),
}


def u32(data, at):
    if at < 0 or at + 4 > len(data):
        raise ValueError('FGIB 32-bit field outside archive')
    return struct.unpack_from('<I', data, at)[0]


def verify_ui(ipa):
    with zipfile.ZipFile(ipa) as container:
        member = 'Payload/G1awakening.app/iphone.big'
        if member not in container.namelist():
            raise ValueError('Original 1.1.3 FGIB member is missing')
        if container.getinfo(member).file_size > 8_000_000:
            raise ValueError('Original FGIB exceeds its expected upper bound')
        archive = container.read(member)
    digest = hashlib.sha256(archive).hexdigest()
    if digest != ARCHIVE_SHA256:
        raise ValueError('Source iphone.big SHA256 differs from the frozen original')
    if len(archive) < 32 or archive[:8] != b'FGIB\x01\x00\x80\x00':
        raise ValueError('Invalid FGIB magic/version')
    group_offset, group_count, member_offset, member_count, body_offset, body_size = struct.unpack_from('<6I', archive, 8)
    if group_offset != 32 or group_offset + group_count*8 != member_offset or \
            member_offset + (member_count+1)*8 != body_offset or \
            body_offset + body_size != len(archive):
        raise ValueError('Unexpected FGIB group/member/body geometry')
    members = {}
    for g in range(group_count):
        base, count, first = struct.unpack_from('<IHH', archive, group_offset + 8*g)
        for i in range(count):
            identity = base+i
            if identity in IMAGES:
                if identity in members or first+i >= member_count:
                    raise ValueError(f'Ambiguous/invalid original UI resource {identity}')
                members[identity] = first+i
    if set(members) != set(IMAGES):
        raise ValueError(f'Missing original UI IDs: {sorted(set(IMAGES)-set(members))}')
    for identity, index in members.items():
        key, at = struct.unpack_from('<II', archive, member_offset + 8*index)
        stop = u32(archive, member_offset + 8*(index+1)+4)
        if key != UI_KEY or at < body_offset or at+4 > stop or stop > len(archive):
            raise ValueError(f'Source UI image {identity} key/offset differs')
        flags = u32(archive,at)
        if flags == 4:
            png = archive[at+4:stop]
        elif flags == 0x00800004:
            if u32(archive,at+8) != stop-at-12:
                raise ValueError(f'Compressed byte count differs for UI {identity}')
            png = zlib.decompress(archive[at+12:stop])
            if len(png) != u32(archive,at+4):
                raise ValueError(f'Decompressed PNG size differs for UI {identity}')
        else:
            raise ValueError(f'Unsupported original UI resource flags for {identity}')
        if not png.startswith(b'\x89PNG\r\n\x1a\n') or png[12:16] != b'IHDR':
            raise ValueError(f'Original UI {identity} is not a PNG')
        dimensions = struct.unpack_from('>II',png,16)
        width,height,expected = IMAGES[identity]
        if dimensions != (width,height) or hashlib.sha256(png).hexdigest() != expected:
            raise ValueError(f'Original UI image {identity} dimensions or SHA256 differ')
    return {'source_sha256':digest,'identity_key':f'0x{UI_KEY:08x}',
            'original_png_assets_checked':len(IMAGES),'all_png_sha256_and_dimensions_verified':True,
            'original_app_rewritten':False,'native_ui_touch_regions_verified':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_ipa',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    result=json.dumps(verify_ui(args.source_ipa),indent=2)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(result)
    print(result,end='')


if __name__=='__main__':
    main()
