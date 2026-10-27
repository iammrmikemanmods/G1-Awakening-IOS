#!/usr/bin/env python3
"""Read-only G1 1.1.3 original HUD/dialogue/battle asset provenance check.

This script never exports or rewrites copyrighted source images, and verifies
original FGIB members used by the native iPhone XR Build014 UI changes.
"""
import argparse
import hashlib
import json
import struct
import zipfile
import zlib

SOURCE_SHA = '663d2888982093ce66b7811ccb7a6ad3acd37fc02ffa85144775b88c39e83cb4'
PNG = {
    # Complete original 480x320 tech specs background images for each faction,
    # verified against screenshots supplied by the owner.
    1224: (480,320,'9a124f219b854a957c2f9aa95ba471f90ab6b45af3fa394c1eb5e7536f1d9812'),
    417: (480,320,'bb27c30c5894af2d9bf6209a116a5d215eb8bfefdd53dbc467543e227cd8651b'),
    657: (52,49,'e98fc1c9be033c4686e14c1def7e700fa2e7ec927423d1ae31af5c929226ff19'),
    514: (480,62,'ee83f54f96a08df966558d2116906af0cf4fced85dbed37611a351efb13d867d'),
    874: (128,63,'f0d0f0d5accf7210ed410b5e7f2a0493f648f85864d54ddb045e06f02056d15c'),
    799: (128,63,'d27f3e12779c2056faff69ec32a992f69909a6e1553aabfaf3d1b27bdfcff46a'),  # compared via descriptor and original source SHA
    709: (51,54,'f6356f1e24285dfb2f2e08b4928770447998644e23cd7dd78bbfa218e15dd735'),
    1034:(480,93,'bcb21e991868503d4a986fa007f60d6496e3603aef32596c2a385ba74f9da312'),
    1038:(156,58,'0a2eabdc0965540843b84d32c118144424307fc78103b1e8acd0b3d21ca06b60'),
    721:(52,49,'7fb785f36c5d974c6345f3c174358a1b97503f58092e68dac3d74a4921b93c6f'),
    1118:(52,49,'6abdf383748fc4ab119dd1031a54a43500f97b873d2390333da27737424848bf'),
    919:(52,49,'a2b984932b89b64cf7b055ed51493c4e6bde648ce5da2ce805b42c87777d1bf6'),
    633:(52,49,'d8c428f2f7dcb7afffedfcdbb5552390503241180d9b1d486a86d5769e2f3e27'),
    904:(52,49,'3533f21b54e11be138143b868828486ede28dcefaba7c596c57eb74f02cc1c38'),
    433:(52,49,'ae75db54d12acd5c1441103325a5c5b9386e2baa1094c9b085852e5d358b8224'),
    660:(52,49,'b8f612f72093cfd51321e9a960a7a8d66783cdb85aa8331fb58114498708b963'),
    850:(52,49,'a41ef3955c319a6551a0cdd4049223b7c0275f2bb899f70f01f49394f8402ae2'),
    669:(52,49,'e0a5157f65f529cacf6275771e6a99c54ac29b35e61a68a4561243bc057968c3'),
    726:(52,49,'a5c1f635661a582aebf50cc6d60983e0740f046f4d1322248e53601b5fb7e5bc'),
    454:(52,49,'8921f40a030cfe1d50e52731b9fa0de2269798b7e1deff320e362c1974a22ce5'),
    442:(52,49,'f695283eb60c4992d7280f07ccd9db41dd0dac30e6151fbda2c52f773d641432'),
    548:(52,49,'e4171558e1290e8f8ea9285c13bdf3762371454c81166fad86d8e05a7b4b64b3'),
    793:(52,49,'9354af28b9a3c65b5bb0fec4ca6cc8fd56d73ad20fc42e70aa2947fcd033fa2e'),
    1076:(52,49,'ae4c1338304071dfe2efac5a6a5666b5c41a54635495e26003f62c28ce46d9fd'),
    591:(52,49,'8142d15e2ec1b13e2c1380afb27534df82bb3ba25adc116e65d5c5e34353fecc'),
    1191:(52,49,'1036a620300a2c8eecb6d76bd920bade1e52501bf26212bff136c798ebaa449e'),
    905:(60,49,'47aa4c8441acf215ff82b8a22df600c018f697d310dc03acc4a22c7270c2fd34'),
    719:(60,49,'64b7cba7b9e226ebd5a1f02374c1b072212fba319381b5b9fc6c042f4f3eb502'),
}
BMP = {
    646: (48,51,'5c71ba42af5b8be3bd3c66eb6e8e9d3bc03116fe16e82c2e3294aadebaff078c'),
    731: (54,50,'dcf4ca21049346044c78ae435e8c34bc7a9fd6ff46fccfbb639dbbedf898989e'),
    396: (70,66,'a79fb2a89411ff68ea2a86e69e159fc95b2ad6162f712c2b9d1944f3d0988ff2'),
    878: (73,70,'cba97ef5edb70a8f1b55e6e04923efdabcce7c8753f7729369821d0f3a0acb91'),
    670: (54,51,'f0707e0cb803ab93854989995cc47d053a0ccdebf29284c6b3818461e96116a7'),
    1295: (77,66,'fa3f28b4cf5a664b683e4f18ed1545a119c27e09717b3163e1a0975df0581e85'),
    1156: (76,68,'3a8c916a0e7ec5ffc1cff2d518418a39054bc5ccfce028115cb9fbe71b92c173'),
}


def check(ipa):
    with zipfile.ZipFile(ipa) as z:
        archive=z.read('Payload/G1awakening.app/iphone.big')
    if hashlib.sha256(archive).hexdigest()!=SOURCE_SHA:
        raise ValueError('Original game source archive is not the frozen 1.1.3 version')
    go,gc,mo,mc,body,_=struct.unpack_from('<6I',archive,8)
    if archive[:8]!=b'FGIB\x01\x00\x80\x00' or go!=32 or go+gc*8!=mo or mo+(mc+1)*8!=body:
        raise ValueError('Invalid original FGIB indexing')
    ids={}
    for g in range(gc):
        base,count,first=struct.unpack_from('<IHH',archive,go+g*8)
        for i in range(count):
            rid=base+i
            if rid in PNG or rid in BMP:
                if rid in ids or first+i>=mc:raise ValueError('Original FGIB ID collision')
                ids[rid]=first+i
    if set(ids)!=(set(PNG)|set(BMP)):
        raise ValueError(f'Missing original art: {(set(PNG)|set(BMP))-set(ids)}')
    for rid,j in ids.items():
        key,offset=struct.unpack_from('<II',archive,mo+j*8)
        end=struct.unpack_from('<I',archive,mo+(j+1)*8+4)[0]
        if offset<body or not offset+4<=end<=len(archive):raise ValueError(f'{rid} offset out of bounds')
        flag=struct.unpack_from('<I',archive,offset)[0]
        if flag==4:raw=archive[offset+4:end]
        elif flag==0x800004:
            raw=zlib.decompress(archive[offset+12:end]);expected=struct.unpack_from('<I',archive,offset+4)[0]
            if len(raw)!=expected:raise ValueError(f'{rid} invalid compressed length')
        else:raise ValueError(f'{rid} bad FGIB compression')
        if rid in PNG:
            width,height,wanted=PNG[rid]
            if key!=0xb7178678 or raw[:8]!=b'\x89PNG\r\n\x1a\n' or raw[12:16]!=b'IHDR':
                raise ValueError(f'{rid} not original PNG')
            dimensions=struct.unpack_from('>II',raw,16)
        else:
            width,height,wanted=BMP[rid]
            if key!=0xb717945f or raw[:2]!=b'BM' or len(raw)<54:
                raise ValueError(f'{rid} not original BMP')
            dimensions=struct.unpack_from('<II',raw,18)
        if dimensions!=(width,height) or (wanted and hashlib.sha256(raw).hexdigest()!=wanted):
            raise ValueError(f'{rid} original dimensions or checksum failed')
    # Same source ID and dimensions consumed at runtime. Catch regressions
    # where a port changes hardcoded BMP size without updating source data.
    from pathlib import Path
    runtime=(Path(__file__).resolve().parents[1]/'native/platform/apple/NativeSourceArt.hpp').read_text()
    hud=(Path(__file__).resolve().parents[1]/'native/platform/apple/NativeTacticalHUD.hpp').read_text()
    for ident in (731,396,878,670,1295,1156):
        w,h,_=BMP[ident]
        expected=f'{{{ident},{w},{h}}}'
        if expected not in runtime or (ident in (731,396,878,670) and expected not in hud):
            raise ValueError(f'{ident} runtime BMP declaration diverges from original archive')
    tech_source=(Path(__file__).resolve().parents[1]/'native/platform/apple/NativeTechSpecs.hpp').read_text()
    for ident,w,h in ((1224,480,320),(417,480,320),(709,51,54),
                      (442,52,49),(904,52,49),(657,52,49)):
        if f'archive,{ident},{w},{h}' not in tech_source:
            raise ValueError(f'{ident} tech specs runtime source contract changed')
    if '{646,48,51}' not in (Path(__file__).resolve().parents[1]/'native/platform/apple/NativeApp.mm').read_text():
        raise ValueError('Original Frenzy portrait 646 native runtime dimensions diverged')
    return {'source_sha256':SOURCE_SHA,'source_png_contracts':len(PNG),
            'source_bmp_portrait_contracts':len(BMP),'all_checked':True,
            'on_device_render_validation':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('original_ipa');p.add_argument('--out');args=p.parse_args()
    result=check(args.original_ipa)
    data=json.dumps(result,indent=2)+'\n'
    if args.out:
        from pathlib import Path
        Path(args.out).write_text(data)
    print(data,end='')
