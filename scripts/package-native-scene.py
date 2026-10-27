#!/usr/bin/env python3
"""Package actual cloud-built ARM64 code with locally verified original data.

This makes an unsigned native test IPA with its source-specific feature scope.
No original executable is copied into the output. The user signs with Sideloadly.
"""
import argparse
import hashlib
import importlib.util
import json
from io import BytesIO
from pathlib import Path, PurePosixPath
import plistlib
import stat
import tempfile
import zipfile


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_code_artifact(path):
    allowed = {'Info.plist', 'G1AwakeningNative', 'PkgInfo',
               'Licenses/Native-Port-MPL-2.0.txt', 'Licenses/LodePNG-Zlib.txt',
               'Licenses/STB-MIT-Public-Domain.txt'}
    prefix = 'G1AwakeningNative.app/'
    files, seen = {}, set()
    with zipfile.ZipFile(path) as source:
        entries = source.infolist()
        if len(entries) > 1000 or sum(entry.file_size for entry in entries) > 64 * 1024 * 1024:
            raise ValueError('native code artifact exceeds packaging bounds')
        for entry in entries:
            posix = PurePosixPath(entry.filename)
            if (entry.filename in seen or posix.is_absolute() or '..' in posix.parts or
                    '\\' in entry.filename or '\x00' in entry.filename):
                raise ValueError('unsafe or repeated artifact entry')
            seen.add(entry.filename)
            mode = (entry.external_attr >> 16) & 0xffff
            if stat.S_ISLNK(mode) or entry.flag_bits & 1:
                raise ValueError('symlink/encrypted artifact entries are unsupported')
            if entry.is_dir():
                continue
            if entry.file_size > 32 * 1024 * 1024:
                raise ValueError('artifact entry exceeds file-size limit')
            if entry.filename.startswith(prefix):
                relative = entry.filename[len(prefix):]
                if relative not in allowed:
                    raise ValueError('unexpected native app member: ' + relative)
                files[relative] = source.read(entry)
        validation = json.loads(source.read('native-app-validation.json'))
        policy = source.read('README_MEMORY_ZIP_POLICY.md')
    required = allowed - {'PkgInfo'}
    if not required.issubset(files):
        raise ValueError('code artifact is missing app metadata, code or licenses')
    return files, validation, policy


ORIGINAL_ICON_SHA256 = "21503f76f7c3aefdf5d23c5be7229bd43134b2cbf2b08af155982e2543a837f8"
# Exactly the 23.0s 1792x828/60fps stereo user-supplied replacement movie.
OPENING_XR_SHA256 = "86a1a9a559843e2ab13e8f513617c8c63e29ef6cd56fe0f6a0446fab7e3911d6"
OPENING_FILENAME = "G1OpeningXR.mp4"

# Pillow is an explicit local packaging dependency (not linked into the app).
# iPhone XR uses the 120x120 retina variant. Include the 180x180 Retina HD
# variant too for current iPhones and the 40pt Spotlight icons.
ORIGINAL_ICON_SIZES = {
    "Icon-60": 60, "Icon-60@2x": 120, "Icon-60@3x": 180,
    "Icon-Small-40": 40, "Icon-Small-40@2x": 80, "Icon-Small-40@3x": 120,
}


def original_icon_files(source_zip, info):
    primary = info.get("CFBundleIcons", {}).get("CFBundlePrimaryIcon", {})
    listed = primary.get("CFBundleIconFiles")
    if listed is None:
        return {}, None
    if (not isinstance(listed, list) or set(listed) != set(ORIGINAL_ICON_SIZES) or
            len(listed) != len(ORIGINAL_ICON_SIZES)):
        raise ValueError("compiled Info.plist does not list exactly the original icon sizes")
    if primary.get("CFBundleIconName"):
        raise ValueError("a non-existent asset-catalog icon may not override bundled PNG icons")
    if primary.get("UIPrerenderedIcon") is not True:
        raise ValueError("original G1 icon must not receive legacy gloss")
    try:
        from PIL import Image
    except ImportError as error:
        raise RuntimeError("Original iOS icon conversion needs Pillow: pip install Pillow") from error

    originals = [entry for entry in source_zip.infolist() if entry.filename == "iTunesArtwork"]
    if len(originals) != 1 or originals[0].file_size > 2*1024*1024:
        raise ValueError("pinned original IPA must contain exactly one bounded iTunesArtwork")
    artwork = source_zip.read(originals[0])
    if sha(artwork) != ORIGINAL_ICON_SHA256:
        raise ValueError("source game's original iTunes icon artwork checksum differs")
    with Image.open(BytesIO(artwork)) as decoded:
        decoded.load()
        if decoded.size != (512, 512) or decoded.format != "JPEG":
            raise ValueError("source game's original icon must decode as its 512x512 JPEG")
        rgb = decoded.convert("RGB")
    produced = {}
    for name, size in ORIGINAL_ICON_SIZES.items():
        # Preserve the 1980s original image, no AI redraw or new text.
        icon = rgb.resize((size, size), Image.Resampling.LANCZOS)
        output = BytesIO()
        icon.save(output, format="PNG", optimize=True)
        payload = output.getvalue()
        with Image.open(BytesIO(payload)) as verification:
            verification.load()
            if verification.size != (size, size) or verification.mode != "RGB":
                raise ValueError("resized original icon failed exact dimensions")
        produced[f"{name}.png"] = payload
    record = {
        "source_resource": "iTunesArtwork", "source_sha256": sha(artwork),
        "source_dimensions": [512, 512], "original_art_preserved": True,
        "method": "Pillow LANCZOS lossless PNG output; no AI artwork",
        "icons": {name: {"pixels": ORIGINAL_ICON_SIZES[name], "sha256": sha(produced[name+".png"])}
                  for name in sorted(ORIGINAL_ICON_SIZES)}
    }
    return produced, record


def zip_write(archive, name, data, executable=False):
    entry = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
    entry.create_system = 3
    entry.external_attr = (stat.S_IFREG | (0o755 if executable else 0o644)) << 16
    entry.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(entry, data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--code-artifact', required=True, type=Path)
    parser.add_argument('--source-ipa', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--expected-commit')
    parser.add_argument('--startup-video', type=Path,
                        help='Original user-supplied 1792x828, 60Hz G1 replacement opening MP4')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    extractor = load_module('g1_tables', root / 'native/tools/extract_terrain_tables.py')
    verifier = load_module('g1_app_verifier', Path(__file__).with_name('verify-native-app.py'))
    paths = [p.resolve() for p in (args.code_artifact, args.source_ipa, args.out, args.report)]
    if args.startup_video:
        paths.append(args.startup_video.resolve())
    if len(set(paths)) != len(paths):
        raise ValueError('all input/output paths must be distinct')
    if args.out.exists() or args.report.exists():
        raise ValueError('output already exists; choose a new test-build filename')
    files, build, policy = read_code_artifact(args.code_artifact)
    info = plistlib.loads(files['Info.plist'])
    native = verifier.inspect_executable(files['G1AwakeningNative'])
    if info.get('CFBundleExecutable') != 'G1AwakeningNative' or \
            info.get('CFBundleIdentifier') != 'org.g1awakening.native.test' or \
            info.get('MinimumOSVersion') != '17.5' or info.get('UIDeviceFamily') != [1]:
        raise ValueError('unexpected app identity or deployment settings')
    if info.get('G1SourceCommit') != build.get('source_commit') or \
            native['executable_sha256'] != build.get('executable_sha256'):
        raise ValueError('app bytes do not match cloud validation metadata')
    if args.expected_commit and info['G1SourceCommit'] != args.expected_commit:
        raise ValueError('cloud artifact is from a different source commit')
    if info.get('CFBundleVersion') == '10' and \
            set(info.get('CFBundleIcons', {}).get('CFBundlePrimaryIcon', {}).get('CFBundleIconFiles', [])) != set(ORIGINAL_ICON_SIZES):
        raise ValueError('Build 010 requires every original icon variant')
    tables, table_record = extractor.extract_tables_from_ipa(args.source_ipa)
    if sha(tables) != 'b870e3d74244741003c8068178e7f58bb5fbe35599599c918e024227463725a8':
        raise ValueError('terrain tables differ from the reviewed data')
    with zipfile.ZipFile(args.source_ipa) as source:
        archive = source.read('Payload/G1awakening.app/iphone.big')
        icon_files, icon_record = original_icon_files(source, info)
    if sha(archive) != '663d2888982093ce66b7811ccb7a6ad3acd37fc02ffa85144775b88c39e83cb4':
        raise ValueError('game archive differs from the reviewed data')
    data_record = {'schema': 1, 'original_ipa_sha256': extractor.EXPECTED_IPA_SHA256,
                   'archive_sha256': sha(archive), 'terrain_tables_sha256': sha(tables),
                   'terrain_extraction': table_record, 'contains_original_executable': False}
    if icon_record:
        if any(name in files for name in icon_files):
            raise ValueError("icon name collision with compiled app artifact")
        files.update(icon_files)
        data_record["original_application_icon"] = icon_record
    video_record = None
    if int(info.get('CFBundleVersion', '0')) >= 11 and not args.startup_video:
        raise ValueError('native Build011+ requires the new source user opening MP4')
    if args.startup_video:
        if args.startup_video.stat().st_size > 64*1024*1024:
            raise ValueError('replacement startup MP4 exceeds 64MiB input bound')
        movie = args.startup_video.read_bytes()
        if sha(movie) != OPENING_XR_SHA256 or len(movie) < 1024 or movie[4:8] != b'ftyp':
            raise ValueError('replacement opening is not the exact reviewed XR 60Hz MP4')
        if OPENING_FILENAME in files:
            raise ValueError('replacement opening collides with compiled app file')
        files[OPENING_FILENAME] = movie
        video_record = {'member':OPENING_FILENAME,'sha256':sha(movie),
                        'bytes':len(movie),'width':1792,'height':828,
                        'fps':60,'duration_seconds':23,
                        'audio':'AAC stereo 48kHz','verified_by':'pinned source hash and MP4 signature'}
    files['GameData/iphone.big'] = archive
    files['GameData/terrain-tables.bin'] = tables
    files['GameData/provenance.json'] = (json.dumps(data_record, indent=2) + '\n').encode()
    output_prefix = 'Payload/G1AwakeningNative.app/'
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='g1-ipa-', dir=args.out.parent) as tmp:
        staged = Path(tmp) / 'unsigned.ipa'
        with zipfile.ZipFile(staged, 'w') as output:
            for name, data in sorted(files.items()):
                zip_write(output, output_prefix + name, data, name == 'G1AwakeningNative')
            zip_write(output, 'README_MEMORY_ZIP_POLICY.md', policy)
        with zipfile.ZipFile(staged) as verification:
            if verification.testzip() is not None:
                raise ValueError('packaged ZIP failed its CRC check')
            expected = {output_prefix + name for name in files} | {'README_MEMORY_ZIP_POLICY.md'}
            if set(verification.namelist()) != expected:
                raise ValueError('IPA file inventory changed during packaging')
            for name, data in files.items():
                if verification.read(output_prefix + name) != data:
                    raise ValueError('packaged bytes differ from verified input')
        report = {'schema': 1, 'artifact_kind': info.get('G1ArtifactKind', 'native test app'),
                  'source_commit': info['G1SourceCommit'], 'ipa_sha256': sha(staged.read_bytes()),
                  'ipa_bytes': staged.stat().st_size, 'code_artifact_sha256': sha(args.code_artifact.read_bytes()),
                  'native_executable': native, 'data': data_record,
                  'original_icon': icon_record, 'native_replacement_opening': video_record,
                  'files': [{'path': output_prefix + name, 'bytes': len(data), 'sha256': sha(data)}
                            for name, data in sorted(files.items())],
                  'signed': False, 'requires_sideloadly_signing': True,
                  'contains_original_executable': False, 'contains_compatibility_runtime': False,
                  'device_installation_verified': False, 'device_execution_verified': False,
                  'full_gameplay_implemented': True, 'full_playthrough_verified': False,
                  'sustained_60fps_verified': False,
                  'scope': info.get('G1FeatureScope', 'Recovered first terrain, initial sprites, native animation and range preview only')}
        staged.replace(args.out)
        args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('artifact_kind','source_commit','ipa_sha256','ipa_bytes',
                                            'signed','full_playthrough_verified')}))


if __name__ == '__main__':
    main()
