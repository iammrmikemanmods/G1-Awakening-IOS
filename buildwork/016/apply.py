#!/usr/bin/env python3
"""Final Apple syntax repair on the already published Build016 source.
Objective-C instance variables cannot use C++ in-class brace initializers.
Keep ordinary size_t ivars, zero-initialized by Objective-C allocation. The
same declaration was checked with clang's Objective-C++ iOS runtime grammar.
Only the three exact declarations are changed; material-budget repair stays.
"""
from pathlib import Path
import hashlib,json,os,subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
BRANCH='feature/modern-tactical-016'
PUBLISHED='18447fe7fedb2efb54e54d04c4ce0781771199b7'
TARGET='native/platform/apple/NativeApp.mm'
OLD='04c3eadcd5d7e9aa89232cfba95265a9c7f8bd170a19222fdd755e8fea325ec5'
NEW='0c2de3ae8ea531b9e74f96970388314f628d29fa888f561e1681d0d4fb93e5a5'
RENDERER='47d58ad5bea1f48d48a940b0639752e2d9264598fa9f0680179db05f1f0a7dbe'
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify(allow_old=False):
    subprocess.run(['git','merge-base','--is-ancestor',PUBLISHED,'HEAD'],cwd=ROOT,check=True)
    m=json.loads((ROOT/'buildwork/016/manifest.json').read_text())
    if m['branch']!=BRANCH:raise ValueError('Wrong work branch')
    for f in m['files']:
        p=ROOT/f['path'];expected={f['after']}
        if f['path']==TARGET:expected={NEW,OLD} if allow_old else {NEW}
        elif f['path']=='native/platform/apple/MetalM3GRenderer.mm':expected={RENDERER}
        if not p.is_file() or p.is_symlink() or sha(p) not in expected:
            raise ValueError('Published source identity mismatch: '+f['path'])
if len(sys.argv)!=2 or sys.argv[1] not in ('apply','publish'):raise SystemExit('Usage: apply.py apply|publish')
if sys.argv[1]=='apply':
    verify(True);p=ROOT/TARGET
    if sha(p)==OLD:
        s=p.read_text()
        for name in ('_tacticalDrawn','_tacticalFallback','_battleEnhancedTextures'):
            before='std::size_t '+name+'{};'
            if s.count(before)!=1:raise ValueError('Unexpected declaration context')
            s=s.replace(before,'std::size_t '+name+';')
        p.write_text(s)
    verify();print(json.dumps({'objc_ivar_repair_sha256':NEW,'material_budget_repair_preserved':True}))
else:
    verify();previous=git('rev-parse','HEAD')
    if git('ls-remote','origin','refs/heads/'+BRANCH).split()[0]!=previous:
        raise ValueError('Branch advanced; refusing overwrite')
    subprocess.run(['git','add','--',TARGET],cwd=ROOT,check=True)
    changed=set(git('diff','--cached','--name-only').splitlines())
    if changed not in (set(),{TARGET}):raise ValueError('Unexpected staged source')
    if changed:
        subprocess.run(['git','-c','user.name=G1 Build Validation','-c','user.email=g1-build@users.noreply.github.com',
            'commit','-m','Use Objective-C-compatible zero-initialized tactical counters [skip ci]'],cwd=ROOT,check=True)
        subprocess.run(['git','push','origin','HEAD:refs/heads/'+BRANCH],cwd=ROOT,check=True)
    commit=git('rev-parse','HEAD')
    with open(os.environ['GITHUB_OUTPUT'],'a') as out:out.write('source_sha='+commit+'\n')
    print(json.dumps({'source_sha':commit,'force_push':False}))
