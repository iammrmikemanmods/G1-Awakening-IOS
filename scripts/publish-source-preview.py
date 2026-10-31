#!/usr/bin/env python3
"""Publish a pinned source/code preview; never upload owner game resources.

Only the repository's GITHUB_TOKEN is used. No credential leaves api.github.com
or uploads.github.com. The historical code artifact is downloaded without
forwarding authorization to its signed redirect. Existing assets are never
silently replaced. No branch, visibility, gameplay or save mutation occurs.
"""
from __future__ import annotations
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import plistlib
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import zipfile

REPO = 'iammrmikemanmods/G1-Awakening-IOS'
SOURCE = 'be203a911bc26313615ea450758413e5c9cf6462'
TAG = 'v0.17.0-dev1'
ARTIFACT = 12792373727
ARTIFACT_SHA = '445617609b17d14a996c81d8d7f3b15511f3ec558a77374081f2443b163846e7'
EXE_SHA = '2b0b140201e8a7f700f04a7a9c1e7845f2aa576a9620db06cdf4b98100e5741d'
MAX_ARCHIVE = 32 * 1024 * 1024


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_zip(data: bytes) -> list[str]:
    if len(data) > MAX_ARCHIVE:
        raise ValueError('Archive exceeds publication limit')
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = z.namelist()
        if len(set(names)) != len(names):
            raise ValueError('Duplicate archive members')
        total = 0
        for info in z.infolist():
            p = PurePosixPath(info.filename)
            if p.is_absolute() or '..' in p.parts or '\\' in info.filename or ':' in info.filename:
                raise ValueError('Unsafe archive path')
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Symlink rejected')
            if p.suffix.lower() in {'.ipa', '.big', '.mp4', '.ttf', '.otf', '.woff', '.woff2', '.eot', '.ttc', '.dfont', '.p12', '.mobileprovision'}:
                raise ValueError('Private/original-media/font/signing payload excluded')
            total += info.file_size
        if total > 96 * 1024 * 1024:
            raise ValueError('Expanded archive exceeds limit')
        if z.testzip() is not None:
            raise ValueError('Archive CRC failure')
    return names


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def api(method: str, path: str, data: dict | bytes | None = None, content_type: str = 'application/json'):
    url = path if path.startswith('https://') else 'https://api.github.com' + path
    if urllib.parse.urlparse(url).hostname not in {'api.github.com', 'uploads.github.com'}:
        raise ValueError('Refusing credential forwarding')
    body = json.dumps(data).encode() if isinstance(data, dict) else data
    request = urllib.request.Request(url, data=body, method=method, headers={
        'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
        'Accept': 'application/vnd.github+json', 'Content-Type': content_type,
        'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'G1-source-release-publisher',
    })
    with urllib.request.build_opener(NoRedirect).open(request, timeout=90) as response:
        return json.load(response)


def maybe_get(path: str):
    try:
        return api('GET', path)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def download_artifact() -> bytes:
    prefix = f'/repos/{REPO}/actions/artifacts/{ARTIFACT}'
    meta = api('GET', prefix)
    if meta.get('expired') or meta.get('digest') != 'sha256:' + ARTIFACT_SHA:
        raise ValueError('Historical artifact is expired or has the wrong identity')
    req = urllib.request.Request('https://api.github.com' + prefix + '/zip', headers={
        'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
        'Accept': 'application/vnd.github+json', 'User-Agent': 'G1-source-release-publisher',
    })
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=90) as r:
            data = r.read(MAX_ARCHIVE + 1)
    except urllib.error.HTTPError as e:
        if e.code not in (301, 302, 303, 307, 308):
            raise
        location = e.headers.get('Location', '')
        if not location.startswith('https://'):
            raise ValueError('Unsafe artifact redirect') from None
        # No authorization header on the external, expiring artifact URL.
        with urllib.request.urlopen(location, timeout=90) as r:
            data = r.read(MAX_ARCHIVE + 1)
    if sha(data) != ARTIFACT_SHA:
        raise ValueError('Downloaded code artifact SHA-256 mismatch')
    names = validate_zip(data)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        plists = [n for n in names if n.endswith('G1AwakeningNative.app/Info.plist')]
        exes = [n for n in names if n.endswith('G1AwakeningNative.app/G1AwakeningNative')]
        if len(plists) != 1 or len(exes) != 1:
            raise ValueError('Unexpected code artifact layout')
        info = plistlib.loads(z.read(plists[0]))
        if info.get('G1SourceCommit') != SOURCE or info.get('CFBundleVersion') != '17':
            raise ValueError('Code/source version mismatch')
        if sha(z.read(exes[0])) != EXE_SHA:
            raise ValueError('Executable identity mismatch')
    return data


def make_source(source_dir: Path, policy: str) -> bytes:
    actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source_dir, text=True).strip()
    if actual != SOURCE:
        raise ValueError('Source checkout differs from the pinned commit')
    raw = subprocess.check_output(['git', 'archive', '--format=zip', SOURCE], cwd=source_dir)
    validate_zip(raw)
    prefix = 'G1-Awakening-IOS-Build017/'
    files: dict[str, bytes] = {}
    modes: dict[str, int] = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        for i in z.infolist():
            if not i.is_dir():
                files[prefix + i.filename] = z.read(i.filename)
                modes[prefix + i.filename] = i.external_attr
    policy_path = prefix + 'README_MEMORY_ZIP_POLICY.md'
    if policy_path in files:
        raise ValueError('Release policy would overwrite canonical source')
    files[policy_path] = policy.encode()
    files[prefix + 'PUBLICATION_IDENTITY.json'] = (json.dumps({
        'source_commit': SOURCE, 'canonical_files_are_unchanged': True,
        'extra_files': ['README_MEMORY_ZIP_POLICY.md', 'PUBLICATION_IDENTITY.json', 'PUBLICATION_SHA256.json'],
        'original_game_resources_included': False, 'full_ipa_included': False,
        'new_compilation_performed': False,
    }, indent=2) + '\n').encode()
    manifest = {name: sha(b) for name, b in sorted(files.items())}
    files[prefix + 'PUBLICATION_SHA256.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2026, 10, 31, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = modes.get(name, 0o100644 << 16)
            z.writestr(info, data)
    result = buf.getvalue()
    validate_zip(result)
    with zipfile.ZipFile(io.BytesIO(result)) as z:
        if any(sha(z.read(n)) != h for n, h in manifest.items()):
            raise ValueError('Export manifest mismatch')
    return result


def main() -> None:
    if os.environ.get('GITHUB_REPOSITORY') != REPO:
        raise ValueError('Publisher is locked to the requested repository')
    root = Path(__file__).resolve().parents[1]
    source_dir = root.parent / 'source'
    policy = (root / 'README_MEMORY_ZIP_POLICY.md').read_text()
    assets = {
        'G1-Awakening-Build017-Source.zip': make_source(source_dir, policy),
        'G1-Awakening-Build017-Native-Code-Only.zip': download_artifact(),
    }
    assets['SHA256SUMS.txt'] = ''.join(f'{sha(data)}  {name}\n' for name, data in assets.items()).encode()
    base = f'/repos/{REPO}'
    ref = maybe_get(base + '/git/ref/tags/' + TAG)
    if ref is not None and (ref['object']['type'] != 'commit' or ref['object']['sha'] != SOURCE):
        raise ValueError('Existing tag does not match source; refusing to move it')
    release = maybe_get(base + '/releases/tags/' + TAG)
    notes = (root / 'docs/releases/build017-source.md').read_text()
    if release is None:
        release = api('POST', base + '/releases', {
            'tag_name': TAG, 'target_commitish': SOURCE,
            'name': 'Build 017 — Native source and code preview',
            'body': notes, 'draft': True, 'prerelease': True, 'make_latest': 'false',
        })
    elif not release.get('prerelease'):
        raise ValueError('Existing release is not a prerelease; refusing to change scope')
    existing = {a['name']: a for a in api('GET', base + f"/releases/{release['id']}/assets?per_page=100")}
    for name, data in assets.items():
        if name in existing:
            item = existing[name]
            if item.get('digest') != 'sha256:' + sha(data) or item['size'] != len(data):
                raise ValueError('Existing asset differs; refusing silent replacement: ' + name)
            continue
        if not release.get('draft'):
            raise ValueError('Refusing to append assets silently to a published release')
        url = release['upload_url'].split('{')[0] + '?name=' + urllib.parse.quote(name)
        uploaded = api('POST', url, data, 'application/zip' if name.endswith('.zip') else 'text/plain')
        if uploaded['size'] != len(data) or uploaded.get('digest') != 'sha256:' + sha(data):
            raise ValueError('Server upload identity mismatch')
    if release.get('draft'):
        release = api('PATCH', base + f"/releases/{release['id']}", {
            'draft': False, 'prerelease': True, 'make_latest': 'false',
        })
    print(json.dumps({'release_url': release['html_url'], 'source_commit': SOURCE,
                      'full_ipa_uploaded': False, 'repository_visibility_changed': False,
                      'assets': {n: {'sha256': sha(b), 'bytes': len(b)} for n, b in assets.items()}}, indent=2))


if __name__ == '__main__':
    main()
