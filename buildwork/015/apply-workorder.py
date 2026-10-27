#!/usr/bin/env python3
"""Apply the user's hash-pinned source-only Build015 change on its isolated branch.

No game assets, original executable, secrets, force-push, main-branch modification
or arbitrary downloaded program is involved. The patch is reviewed repository
source; every old/new file hash is checked before/after git apply.
"""
from pathlib import Path, PurePosixPath
import base64, hashlib, json, os, subprocess, zlib

ROOT=Path(__file__).resolve().parents[2]
MANIFEST=ROOT/'buildwork/015/manifest.json'
BRANCH='feature/adaptive-presentation-015'
BASE='0ea4a23fec90d4a66830b4686d15c72f4ec2e97c'

def git(*args: str) -> str:
    return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def load():
    m=json.loads(MANIFEST.read_text())
    if (m['repository'],m['branch'],m['base'],m['build']) != (
        'iammrmikemanmods/G1-Awakening-IOS',BRANCH,BASE,15):
        raise ValueError('Unexpected build/work branch identity')
    subprocess.run(['git','merge-base','--is-ancestor',BASE,'HEAD'],cwd=ROOT,check=True)
    names=[]
    for f in m['files']:
        name=f['path'];p=PurePosixPath(name)
        if p.is_absolute() or '..' in p.parts or name in names or '\\' in name:
            raise ValueError('Unsafe or duplicate source path')
        if not (name.startswith(('native/','scripts/','docs/')) or name=='.github/workflows/native-core.yml'):
            raise ValueError('Path is outside the agreed source scopes')
        if (ROOT/name).is_symlink(): raise ValueError('Symlinks not allowed')
        names.append(name)
    return m

def verify(m, after: bool):
    for f in m['files']:
        p=ROOT/f['path'];expected=f['after' if after else 'before']
        if expected is None:
            if p.exists():raise ValueError('New source file already exists: '+f['path'])
        elif not p.is_file() or digest(p.read_bytes())!=expected:
            raise ValueError('Source hash mismatch: '+f['path'])
        if after and p.stat().st_size!=f['bytes']:
            raise ValueError('Source byte length mismatch')

if __name__=='__main__':
    import sys
    if len(sys.argv)!=2 or sys.argv[1] not in ('apply','publish'):
        raise SystemExit('Usage: apply-workorder.py apply|publish')
    m=load()
    if sys.argv[1]=='apply':
        verify(m,False)
        n=m['patch_parts']
        if not 1<=n<=16:raise ValueError('Unexpected patch part count')
        data=''.join((MANIFEST.parent/f'patch.{i:02}.b64').read_text().strip() for i in range(n))
        if len(data)>524288:raise ValueError('Patch payload exceeds limit')
        packed=base64.b64decode(data,validate=True)
        decoder=zlib.decompressobj(16+zlib.MAX_WBITS)
        patch=decoder.decompress(packed,1048577)
        if not decoder.eof or decoder.unused_data or len(patch)>1048576:
            raise ValueError('Malformed or oversized source patch')
        if len(patch)!=m['patch_bytes'] or digest(patch)!=m['patch_sha256']:
            raise ValueError('Source patch identity mismatch')
        subprocess.run(['git','apply','--check','--unidiff-zero','-'],input=patch,cwd=ROOT,check=True)
        subprocess.run(['git','apply','--unidiff-zero','-'],input=patch,cwd=ROOT,check=True)
        verify(m,True)
        print(json.dumps({'applied_files':len(m['files']),'patch_sha256':m['patch_sha256']}))
    else:
        verify(m,True)
        prior=git('rev-parse','HEAD')
        remote=git('ls-remote','origin','refs/heads/'+BRANCH).split()[0]
        if remote!=prior:raise ValueError('Branch advanced during validation; refusing overwrite')
        subprocess.run(['git','add','--',*[f['path'] for f in m['files']]],cwd=ROOT,check=True)
        names=set(git('diff','--cached','--name-only').splitlines())
        if names!={f['path'] for f in m['files']}:raise ValueError('Unexpected staged paths')
        subprocess.run(['git','-c','user.name=G1 Build Validation','-c',
            'user.email=g1-build@users.noreply.github.com','commit','-m',
            'Apply hash-verified adaptive UI, original fonts and Modern render quality [skip ci]'],cwd=ROOT,check=True)
        commit=git('rev-parse','HEAD')
        subprocess.run(['git','push','origin','HEAD:refs/heads/'+BRANCH],cwd=ROOT,check=True)
        with open(os.environ['GITHUB_OUTPUT'],'a') as out:out.write('source_sha='+commit+'\n')
        print(json.dumps({'source_sha':commit,'published_branch':BRANCH,'force_push':False}))
