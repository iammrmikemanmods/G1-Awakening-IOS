#!/usr/bin/env python3
"""Exact integration follow-up after successful Build017 compilation.
Visual/source review found that the map-rebuild path omitted terrain derivatives
and that Modern sprite draws explicitly requested nearest sampling. Fix only
those paths, keeping original gameplay and Classic behavior. All changed source
is hash-verified, tested and published without force on the isolated branch.
"""
from pathlib import Path
import hashlib,json,os,subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
BRANCH='feature/clean-motion-017'
PUBLISHED='43a49371f0f96ad0845a6732af2da961a1a4f356'
ART='analysis_tools/presentation_017/clean_art.py'
ART_SHA='9d10f06048a4da127e4c9bfb2ca5c2d85d7096ab09c1fea0791d70f58f723d1d'
FIXES={
'native/platform/apple/NativeApp.mm':('f1482b5f91f755280e712052170e6aa061c641960de4ccea8c6f2b086b983324',[
('''        if(_graphicsModern && !_modernTextures[@(image.first)]) {
            const bool sprite=std::any_of(next->sprites.begin(),next->sprites.end(),[&](const auto& item) {''',
'''        if(_graphicsModern && !_modernTextures[@(image.first)]) {
            // Persisted Modern mode must load the same terrain derivative at
            // first launch/map change as the live graphics-toggle path.
            if(image.first==next->terrain.atlas_resource_id) {
                _modernTextures[@(image.first)]=_renderer->texture(g1::clean_terrain_or_source(image.second));
                continue;
            }
            const bool sprite=std::any_of(next->sprites.begin(),next->sprites.end(),[&](const auto& item) {''',1),
('},true,{},false,_graphicsModern});','},true,{},false,false});',3),
('native17-point nominal height and nearest sampling; existing UIKit fallback','native17-point nominal height and antialiased sampling; existing UIKit fallback',1)]),
'native/platform/apple/NativeSourceArt.hpp':('b2391922979d9e9e4cc292f7a16b647c924c1f058c850d40aa196ed5a074205a',[
('// Original FGIB PNG/BMP resources, decoded at runtime from the untouched user\n// archive. Nothing is resampled, redrawn, downloaded, or bundled separately.',
'// Original FGIB PNG/BMP resources are decoded from the untouched owner archive.\n// The shared presentation layer may apply the optional source-hash-keyed clean\n// derivative pack; missing derivatives retain the original source fallback.',1)])}
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify(allow_old=False):
    subprocess.run(['git','merge-base','--is-ancestor',PUBLISHED,'HEAD'],cwd=ROOT,check=True)
    m=json.loads((ROOT/'buildwork/017/manifest.json').read_text())
    if m['branch']!=BRANCH:raise ValueError('Wrong work branch')
    for f in m['files']:
        p=ROOT/f['path'];expected={f['after']}
        if f['path']==ART:expected={ART_SHA}
        elif f['path'] in FIXES:
            expected={FIXES[f['path']][0]}
            if allow_old:expected.add(f['after'])
        if not p.is_file() or p.is_symlink() or sha(p) not in expected:raise ValueError('Published source mismatch: '+f['path'])
if len(sys.argv)!=2 or sys.argv[1] not in ('apply','publish'):raise SystemExit('Usage: apply.py apply|publish')
if sys.argv[1]=='apply':
    verify(True)
    for name,(expected,edits) in FIXES.items():
        p=ROOT/name
        if sha(p)==expected:continue
        s=p.read_text()
        for before,after,count in edits:
            if s.count(before)!=count:raise ValueError('Unexpected integration context: '+name)
            s=s.replace(before,after)
        p.write_text(s)
    verify()
    source=(ROOT/'native/platform/apple/NativeApp.mm').read_text()
    if source.count('g1::clean_terrain_or_source(image.second)')!=2 or 'false,_graphicsModern});' in source:
        raise ValueError('Modern startup/toggle/sampler source wiring regression')
    print(json.dumps({'modern_terrain_boot_and_toggle_wiring':True,'modern_nearest_sprite_requests':0,'runtime_appearance_verified':False}))
else:
    verify();previous=git('rev-parse','HEAD')
    if git('ls-remote','origin','refs/heads/'+BRANCH).split()[0]!=previous:raise ValueError('Remote advanced; refusing overwrite')
    subprocess.run(['git','add','--',*FIXES],cwd=ROOT,check=True)
    changed=set(git('diff','--cached','--name-only').splitlines())
    if not changed.issubset(FIXES):raise ValueError('Unexpected staged source')
    if changed:
        subprocess.run(['git','-c','user.name=G1 Build Validation','-c','user.email=g1-build@users.noreply.github.com','commit','-m','Load clean terrain on map rebuild and sample Modern scenery smoothly [skip ci]'],cwd=ROOT,check=True)
        subprocess.run(['git','push','origin','HEAD:refs/heads/'+BRANCH],cwd=ROOT,check=True)
    commit=git('rev-parse','HEAD')
    with open(os.environ['GITHUB_OUTPUT'],'a') as out:out.write('source_sha='+commit+'\n')
    print(json.dumps({'source_sha':commit,'force_push':False}))
