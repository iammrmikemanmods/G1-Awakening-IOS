#!/usr/bin/env python3
"""Hash-pinned follow-up to the already published Build016 source.
Apple CI caught Objective-C++ compound ivar initialization. Split the three
counters into individual declarations. Also allow the verified forest sky and
ground together within a 12MiB derived-image budget, with source allocation
fallback. Only these exact source replacements are allowed; no force push.
"""
from pathlib import Path
import hashlib,json,os,subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
BRANCH='feature/modern-tactical-016'
PUBLISHED='43747903bc5a7699d754e875e6d33b367c3195a2'
FIXES={
'native/platform/apple/NativeApp.mm':('04c3eadcd5d7e9aa89232cfba95265a9c7f8bd170a19222fdd755e8fea325ec5',
'    std::size_t _tacticalDrawn{},_tacticalFallback{},_battleEnhancedTextures{};',
'    std::size_t _tacticalDrawn{};\n    std::size_t _tacticalFallback{};\n    std::size_t _battleEnhancedTextures{};'),
'native/platform/apple/MetalM3GRenderer.mm':('47d58ad5bea1f48d48a940b0639752e2d9264598fa9f0680179db05f1f0a7dbe',
'''        if(quality!=MaterialEnhancement::original && image.width<=1024 && image.height<=1024 &&
           derivedBytes<=8*1024*1024-enhancedBytes) {
            // GPU pixels only. Retain original source dimensions, Sprite3D
            // crop rectangles, UVs, geometry, transforms and animation keys.
            const auto enhanced=enhance_material(image,quality);
            gpu->images.emplace(entry.first,impl_->texture(enhanced));
            enhancedBytes+=derivedBytes;++gpu->enhanced_textures;
        } else gpu->images.emplace(entry.first,impl_->texture(image));''',
'''        bool upgraded=false;
        if(quality!=MaterialEnhancement::original && image.width<=1024 && image.height<=1024 &&
           derivedBytes<=12*1024*1024-enhancedBytes) {
            // GPU pixels only. The 12MiB ceiling admits the original forest
            // sky AND ground. Failed derived allocations retry source pixels.
            // Source dimensions, Sprite3D crops and animation keys stay exact.
            try {
                const auto enhanced=enhance_material(image,quality);
                gpu->images.emplace(entry.first,impl_->texture(enhanced));
                enhancedBytes+=derivedBytes;++gpu->enhanced_textures;upgraded=true;
            } catch(const std::exception&) { /* original allocation below */ }
        }
        if(!upgraded)gpu->images.emplace(entry.first,impl_->texture(image));''')}
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify(allow_old=False):
    subprocess.run(['git','merge-base','--is-ancestor',PUBLISHED,'HEAD'],cwd=ROOT,check=True)
    m=json.loads((ROOT/'buildwork/016/manifest.json').read_text())
    if m['branch']!=BRANCH:raise ValueError('Wrong work branch')
    for f in m['files']:
        p=ROOT/f['path'];expected={f['after']}
        if f['path'] in FIXES:
            expected={FIXES[f['path']][0]}
            if allow_old:expected.add(f['after'])
        if not p.is_file() or p.is_symlink() or sha(p) not in expected:raise ValueError('Published source mismatch: '+f['path'])
if len(sys.argv)!=2 or sys.argv[1] not in ('apply','publish'):raise SystemExit('Usage: apply.py apply|publish')
if sys.argv[1]=='apply':
    verify(True)
    for path,(expected,before,after) in FIXES.items():
        p=ROOT/path
        if sha(p)==expected:continue
        s=p.read_text()
        if s.count(before)!=1:raise ValueError('Unexpected repair context: '+path)
        p.write_text(s.replace(before,after))
    verify();print(json.dumps({'repairs':{path:v[0] for path,v in FIXES.items()}}))
else:
    verify();previous=git('rev-parse','HEAD')
    if git('ls-remote','origin','refs/heads/'+BRANCH).split()[0]!=previous:raise ValueError('Remote advanced; refusing overwrite')
    subprocess.run(['git','add','--',*FIXES],cwd=ROOT,check=True)
    changed=set(git('diff','--cached','--name-only').splitlines())
    if not changed.issubset(FIXES):raise ValueError('Unexpected staged source')
    if changed:
        subprocess.run(['git','-c','user.name=G1 Build Validation','-c','user.email=g1-build@users.noreply.github.com',
            'commit','-m','Fix Apple counter declarations and bounded battle material budget [skip ci]'],cwd=ROOT,check=True)
        subprocess.run(['git','push','origin','HEAD:refs/heads/'+BRANCH],cwd=ROOT,check=True)
    commit=git('rev-parse','HEAD')
    with open(os.environ['GITHUB_OUTPUT'],'a') as out:out.write('source_sha='+commit+'\n')
    print(json.dumps({'source_sha':commit,'force_push':False}))
