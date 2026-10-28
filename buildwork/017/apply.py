#!/usr/bin/env python3
"""Hash-pinned art review follow-up to the already published Build017 source.

The first full Apple build passed. Visual inspection found overly flat foliage
and weaker nonlinear red menu glow. Preserve continuous source shading inside
these regions while retaining reconstructed curves. No runtime, shader, game
logic, save or original asset change. Test and publish without force.
"""
from pathlib import Path
import hashlib,json,os,subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
BRANCH='feature/clean-motion-017'
PUBLISHED='43a49371f0f96ad0845a6732af2da961a1a4f356'
TARGET='analysis_tools/presentation_017/clean_art.py'
OLD='859498f32e2ce6eac9b221859e46448ea96c72626887456f61b1a789446ce649'
NEW='9d10f06048a4da127e4c9bfb2ca5c2d85d7096ab09c1fea0791d70f58f723d1d'
EDITS=[
('    defs=[];paths=[]',
 '    defs=[];paths=[]\n    # Curves own silhouettes; continuous source shading owns natural interiors.\n    # This avoids turning foliage into flat blobs or erasing non-linear UI glow.\n    curve_weight=np.full((h,w),0.42 if natural else 0.88,np.float32)'),
('            coef=np.linalg.lstsq(xy,values,rcond=None)[0]',
 "            coef=np.linalg.lstsq(xy,values,rcond=None)[0]\n            residual=float(np.sqrt(np.mean((xy@coef-values)**2)))\n            if role=='ui' and area>=400 and residual>7:\n                curve_weight[yy,xx]=0.12\n            elif role=='character' and area>=150 and residual>12:\n                curve_weight[yy,xx]=0.55"),
('    out=np.array(raster)',
 '    out=np.array(raster)\n    weight=cv2.resize(curve_weight,target,interpolation=cv2.INTER_LINEAR)[:,:,None]\n    base=np.asarray(base_img)[:,:,:3].astype(float)\n    out[:,:,:3]=np.rint(out[:,:,:3]*weight+base*(1-weight)).astype(np.uint8)')]
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify(allow_old=False):
    subprocess.run(['git','merge-base','--is-ancestor',PUBLISHED,'HEAD'],cwd=ROOT,check=True)
    m=json.loads((ROOT/'buildwork/017/manifest.json').read_text())
    if m['branch']!=BRANCH:raise ValueError('Wrong work branch')
    for f in m['files']:
        p=ROOT/f['path'];expected={f['after']}
        if f['path']==TARGET:expected={NEW,OLD} if allow_old else {NEW}
        if not p.is_file() or p.is_symlink() or sha(p) not in expected:raise ValueError('Published source mismatch: '+f['path'])
if len(sys.argv)!=2 or sys.argv[1] not in ('apply','publish'):raise SystemExit('Usage: apply.py apply|publish')
if sys.argv[1]=='apply':
    verify(True);p=ROOT/TARGET
    if sha(p)==OLD:
        s=p.read_text()
        for before,after in EDITS:
            if s.count(before)!=1:raise ValueError('Unexpected art follow-up context')
            s=s.replace(before,after)
        p.write_text(s)
    verify();print(json.dumps({'art_polish_sha256':NEW,'runtime_source_changed':False}))
else:
    verify();previous=git('rev-parse','HEAD')
    if git('ls-remote','origin','refs/heads/'+BRANCH).split()[0]!=previous:raise ValueError('Remote advanced; refusing overwrite')
    subprocess.run(['git','add','--',TARGET],cwd=ROOT,check=True)
    changed=set(git('diff','--cached','--name-only').splitlines())
    if changed not in (set(),{TARGET}):raise ValueError('Unexpected staged source')
    if changed:
        subprocess.run(['git','-c','user.name=G1 Build Validation','-c','user.email=g1-build@users.noreply.github.com','commit','-m','Preserve nonlinear source shading in clean curve artwork [skip ci]'],cwd=ROOT,check=True)
        subprocess.run(['git','push','origin','HEAD:refs/heads/'+BRANCH],cwd=ROOT,check=True)
    commit=git('rev-parse','HEAD')
    with open(os.environ['GITHUB_OUTPUT'],'a') as out:out.write('source_sha='+commit+'\n')
    print(json.dumps({'source_sha':commit,'force_push':False}))
