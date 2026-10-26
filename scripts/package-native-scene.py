#!/usr/bin/env python3
"""Package actual cloud-built ARM64 code with locally verified original data.

This makes an unsigned first-mission scene-test IPA, not a completed native game.
No original executable is copied into the output. The user signs with Sideloadly.
"""
import argparse
import hashlib
import importlib.util
import json
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
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    extractor = load_module('g1_tables', root / 'native/tools/extract_terrain_tables.py')
    verifier = load_module('g1_app_verifier', Path(__file__).with_name('verify-native-app.py'))
    paths = [p.resolve() for p in (args.code_artifact, args.source_ipa, args.out, args.report)]
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
    tables, table_record = extractor.extract_tables_from_ipa(args.source_ipa)
    if sha(tables) != 'b870e3d74244741003c8068178e7f58bb5fbe35599599c918e024227463725a8':
        raise ValueError('terrain tables differ from the reviewed data')
    with zipfile.ZipFile(args.source_ipa) as source:
        archive = source.read('Payload/G1awakening.app/iphone.big')
    if sha(archive) != '663d2888982093ce66b7811ccb7a6ad3acd37fc02ffa85144775b88c39e83cb4':
        raise ValueError('game archive differs from the reviewed data')
    data_record = {'schema': 1, 'original_ipa_sha256': extractor.EXPECTED_IPA_SHA256,
                   'archive_sha256': sha(archive), 'terrain_tables_sha256': sha(tables),
                   'terrain_extraction': table_record, 'contains_original_executable': False}
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
        report = {'schema': 1, 'artifact_kind': 'native first-mission scene test',
                  'source_commit': info['G1SourceCommit'], 'ipa_sha256': sha(staged.read_bytes()),
                  'ipa_bytes': staged.stat().st_size, 'code_artifact_sha256': sha(args.code_artifact.read_bytes()),
                  'native_executable': native, 'data': data_record,
                  'files': [{'path': output_prefix + name, 'bytes': len(data), 'sha256': sha(data)}
                            for name, data in sorted(files.items())],
                  'signed': False, 'requires_sideloadly_signing': True,
                  'contains_original_executable': False, 'contains_compatibility_runtime': False,
                  'device_installation_verified': False, 'device_execution_verified': False,
                  'full_gameplay_implemented': False, 'full_playthrough_verified': False,
                  'sustained_60fps_verified': False,
                  'scope': 'Recovered first terrain, initial sprites, native animation and range preview only'}
        staged.replace(args.out)
        args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('artifact_kind','source_commit','ipa_sha256','ipa_bytes',
                                            'signed','full_playthrough_verified')}))


if __name__ == '__main__':
    main()
