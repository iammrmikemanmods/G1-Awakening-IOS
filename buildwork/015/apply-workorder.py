#!/usr/bin/env python3
"""Repair the Apple-only Rect lookup collision in the published Build015 source.

Initial patch publication succeeded at 508d9f8. Apple then reported the exact
MacTypes.h Rect ambiguity. This second phase checks all 28 original published
file hashes, changes only two lambda parameter type names, reruns CI, and
publishes only NativeApp.mm on the existing isolated branch without force.
"""
from pathlib import Path
import hashlib,json,os,subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
BRANCH='feature/adaptive-presentation-015'
PUBLISHED='508d9f8b7fab4d1bc21c36280b668a18a63a0f66'
TARGET='native/platform/apple/NativeApp.mm'
OLD='f0f7834b6b34220ef4dbcabce0c250e3ae3c2f51ab19610047e4307e7a7ac739'
NEW='0d6945422e2370c996c07ebcec4461e36b7afecad6dde97f6ecae8d3fda80bdb'
def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify(allow_old=False):
    subprocess.run(['git','merge-base','--is-ancestor',PUBLISHED,'HEAD'],cwd=ROOT,check=True)
    m=json.loads((ROOT/'buildwork/015/manifest.json').read_text())
    assert m['branch']==BRANCH and m['build']==15
    for f in m['files']:
        p=ROOT/f['path']
        expected={NEW,OLD} if f['path']==TARGET and allow_old else {NEW} if f['path']==TARGET else {f['after']}
        if not p.is_file() or p.is_symlink() or digest(p) not in expected:
            raise ValueError('Published source identity mismatch: '+f['path'])
if len(sys.argv)!=2 or sys.argv[1] not in ('apply','publish'):
    raise SystemExit('Usage: apply-workorder.py apply|publish')
if sys.argv[1]=='apply':
    verify(True);p=ROOT/TARGET
    if digest(p)==OLD:
        s=p.read_text()
        for before,after in [
            ('[&](Rect r,Anchor h=Anchor::center,Anchor v=Anchor::center)',
             '[&](g1::adaptive::Rect r,Anchor h=Anchor::center,Anchor v=Anchor::center)'),
            ('[&](UIButton* button,Rect r,Anchor h)',
             '[&](UIButton* button,g1::adaptive::Rect r,Anchor h)')]:
            if s.count(before)!=1:raise ValueError('Unexpected Apple repair context')
            s=s.replace(before,after)
        p.write_text(s)
    verify();print(json.dumps({'apple_rect_repair_sha256':NEW,'modified_file':TARGET}))
else:
    verify();prior=git('rev-parse','HEAD')
    if git('ls-remote','origin','refs/heads/'+BRANCH).split()[0]!=prior:
        raise ValueError('Branch advanced during tests; refusing overwrite')
    subprocess.run(['git','add','--',TARGET],cwd=ROOT,check=True)
    changed=set(git('diff','--cached','--name-only').splitlines())
    if changed not in (set(),{TARGET}):raise ValueError('Unexpected staged source')
    if changed:
        subprocess.run(['git','-c','user.name=G1 Build Validation','-c','user.email=g1-build@users.noreply.github.com',
            'commit','-m','Qualify adaptive Rect against Apple MacTypes collision [skip ci]'],cwd=ROOT,check=True)
        subprocess.run(['git','push','origin','HEAD:refs/heads/'+BRANCH],cwd=ROOT,check=True)
    commit=git('rev-parse','HEAD')
    with open(os.environ['GITHUB_OUTPUT'],'a') as out:out.write('source_sha='+commit+'\n')
    print(json.dumps({'source_sha':commit,'published_branch':BRANCH,'force_push':False}))
