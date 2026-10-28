#!/usr/bin/env python3
"""Apply reviewed source-only changes, test before publication, never force-push.
The gzip/base64 parts are connector transport for ordinary game presentation
source. The manifest pins every old/new file; no game assets are transported.
"""
from pathlib import Path,PurePosixPath
import base64,hashlib,json,os,subprocess,sys,zlib
ROOT=Path(__file__).resolve().parents[2]
BRANCH='feature/modern-tactical-016'
BASE='8a1dad674a08c577ab09882007621b308b165eaf'
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
def sha(data):return hashlib.sha256(data).hexdigest()
def load():
    m=json.loads((ROOT/'buildwork/016/manifest.json').read_text())
    if m['base']!=BASE or m['branch']!=BRANCH or m['schema']!=1:raise ValueError('Wrong work order')
    subprocess.run(['git','merge-base','--is-ancestor',BASE,'HEAD'],cwd=ROOT,check=True)
    names=set()
    for f in m['files']:
        name=f['path'];p=PurePosixPath(name)
        if p.is_absolute() or '..' in p.parts or '\\' in name or name in names:raise ValueError('Unsafe path')
        if not name.startswith(('native/','docs/','analysis_tools/')):raise ValueError('Unapproved source path')
        if (ROOT/name).is_symlink():raise ValueError('Symlink rejected')
        names.add(name)
    return m
def matches(m,after):
    for f in m['files']:
        p=ROOT/f['path'];expected=f['after' if after else 'before']
        if expected is None:
            if p.exists():return False
        elif not p.is_file() or sha(p.read_bytes())!=expected:return False
        if after and p.stat().st_size!=f['bytes']:return False
    return True
if len(sys.argv)!=2 or sys.argv[1] not in ('apply','publish'):raise SystemExit('Usage: apply.py apply|publish')
m=load()
if sys.argv[1]=='apply':
    if not matches(m,True):
        if not matches(m,False):raise ValueError('Baseline source mismatch; refusing patch')
        packed=''.join((ROOT/f'buildwork/016/patch.{i:02}.b64').read_text().strip() for i in range(4))
        if len(packed)>262144:raise ValueError('Oversized patch')
        decoder=zlib.decompressobj(16+zlib.MAX_WBITS)
        patch=decoder.decompress(base64.b64decode(packed,validate=True),1048577)
        if not decoder.eof or decoder.unused_data or len(patch)>1048576:raise ValueError('Malformed source transport')
        if len(patch)!=m['patch_bytes'] or sha(patch)!=m['patch_sha256']:raise ValueError('Patch hash mismatch')
        for mode in (['--check'],[]):subprocess.run(['git','apply',*mode,'--unidiff-zero','-'],input=patch,cwd=ROOT,check=True)
        if not matches(m,True):raise ValueError('Patched source mismatch')
    print(json.dumps({'verified_source_files':len(m['files']),'patch_sha256':m['patch_sha256']}))
else:
    if not matches(m,True):raise ValueError('Source changed since verification')
    previous=git('rev-parse','HEAD')
    if git('ls-remote','origin','refs/heads/'+BRANCH).split()[0]!=previous:raise ValueError('Remote branch advanced; refusing overwrite')
    subprocess.run(['git','add','--',*[f['path'] for f in m['files']]],cwd=ROOT,check=True)
    changed=set(git('diff','--cached','--name-only').splitlines())
    if changed and changed!={f['path'] for f in m['files']}:raise ValueError('Unexpected staged source')
    if changed:
        subprocess.run(['git','-c','user.name=G1 Build Validation','-c','user.email=g1-build@users.noreply.github.com',
            'commit','-m','Publish verified Modern tactical models and battle materials [skip ci]'],cwd=ROOT,check=True)
        subprocess.run(['git','push','origin','HEAD:refs/heads/'+BRANCH],cwd=ROOT,check=True)
    commit=git('rev-parse','HEAD')
    with open(os.environ['GITHUB_OUTPUT'],'a') as out:out.write('source_sha='+commit+'\n')
    print(json.dumps({'source_sha':commit,'published_branch':BRANCH,'force_push':False}))
