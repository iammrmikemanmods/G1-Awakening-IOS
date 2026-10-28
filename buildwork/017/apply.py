#!/usr/bin/env python3
"""Publish only hash-pinned Build017 source on its isolated branch.

The compressed text is ordinary reviewed source, never an executable or game
asset. Two exact connector transcription errors are repaired against BOTH old
and canonical Git blob identities before decompression. Every source old/new
SHA-256 and the complete patch SHA-256 must match. Never force-push or alter main.
"""
from pathlib import Path,PurePosixPath
import base64,hashlib,json,os,subprocess,sys,zlib
ROOT=Path(__file__).resolve().parents[2]
BRANCH='feature/clean-motion-017'
BASE='21ab79573f67134d6234ce707210efe0b7ae0477'
PARTS=['521423dbd347251f328a9129ef618bb4f7c30784','5337115ff4cca626d67ebbceaed76e646d7ee5fa','e93b2cb3eefbf020d439381a039b0c9b8b6721f7','4930ab6b9fe36002578cf520fb1cbc528d24fa0f','c15e9b87fc972d84b28ec1e887a0e408cccaa040','abab4e03826f5c3bce9784c1bb0815ee3051bb3c']
FIXES={0:('33d13087f6223cd972521364042d6fc122c738b7',[('Dm1bGdPylu','Dm1bGdDylu'),('qNW3/d+fl3sBgH','qNW3/d+vl9sBgH')]),1:('2605a5fc66d9b1bcab140144b83b222eff096b1a',[('O2m4Z0f721514bsuUO1vTqMO','O2m4Z0f6TqMO')])}
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
def sha(b):return hashlib.sha256(b).hexdigest()
def blob(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def load():
    m=json.loads((ROOT/'buildwork/017/manifest.json').read_text())
    if m['base']!=BASE or m['branch']!=BRANCH or m['schema']!=1 or m['patch_parts']!=6:raise ValueError('Wrong work order')
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
def transport(repair):
    chunks=[]
    for i,expected in enumerate(PARTS):
        p=ROOT/f'buildwork/017/patch.{i:02}.b64';data=p.read_bytes()
        if repair and blob(data)!=expected and i in FIXES:
            old,replacements=FIXES[i]
            if blob(data)!=old:raise ValueError('Unrecognized transfer error')
            text=data.decode('ascii')
            for before,after in replacements:
                if text.count(before)!=1:raise ValueError('Unexpected transfer repair context')
                text=text.replace(before,after)
            data=text.encode('ascii')
            if blob(data)!=expected:raise ValueError('Corrected transport identity mismatch')
            p.write_bytes(data)
        if blob(data)!=expected:raise ValueError('Transport part identity mismatch')
        chunks.append(data.strip())
    return b''.join(chunks)
if len(sys.argv)!=2 or sys.argv[1] not in ('apply','publish'):raise SystemExit('Usage: apply.py apply|publish')
m=load()
if sys.argv[1]=='apply':
    packed=transport(True)
    if not matches(m,True):
        if not matches(m,False):raise ValueError('Baseline source mismatch')
        if len(packed)>262144:raise ValueError('Oversized transport')
        decoder=zlib.decompressobj(16+zlib.MAX_WBITS)
        patch=decoder.decompress(base64.b64decode(packed,validate=True),1048577)
        if not decoder.eof or decoder.unused_data or len(patch)>1048576:raise ValueError('Malformed source transport')
        if len(patch)!=m['patch_bytes'] or sha(patch)!=m['patch_sha256']:raise ValueError('Patch identity mismatch')
        for mode in (['--check'],[]):subprocess.run(['git','apply',*mode,'--unidiff-zero','-'],input=patch,cwd=ROOT,check=True)
        if not matches(m,True):raise ValueError('Patched source mismatch')
    print(json.dumps({'verified_source_files':len(m['files']),'patch_sha256':m['patch_sha256']}))
else:
    transport(False)
    if not matches(m,True):raise ValueError('Source changed since verification')
    previous=git('rev-parse','HEAD')
    if git('ls-remote','origin','refs/heads/'+BRANCH).split()[0]!=previous:raise ValueError('Remote advanced; refusing overwrite')
    allowed={f['path'] for f in m['files']}|{'buildwork/017/patch.00.b64','buildwork/017/patch.01.b64'}
    subprocess.run(['git','add','--',*sorted(allowed)],cwd=ROOT,check=True)
    changed=set(git('diff','--cached','--name-only').splitlines())
    if not changed.issubset(allowed):raise ValueError('Unexpected staged source')
    if changed:
        subprocess.run(['git','-c','user.name=G1 Build Validation','-c','user.email=g1-build@users.noreply.github.com','commit','-m','Publish verified authored tactical motion and clean artwork runtime [skip ci]'],cwd=ROOT,check=True)
        subprocess.run(['git','push','origin','HEAD:refs/heads/'+BRANCH],cwd=ROOT,check=True)
    commit=git('rev-parse','HEAD')
    with open(os.environ['GITHUB_OUTPUT'],'a') as out:out.write('source_sha='+commit+'\n')
    print(json.dumps({'source_sha':commit,'force_push':False}))
