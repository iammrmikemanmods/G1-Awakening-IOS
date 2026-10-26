#!/usr/bin/env python3
"""Original audio control dispatch with explicit resource/output boundaries."""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import struct
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('audio_shared_reference',ROOT/'analysis_tools/ai/oracle.py')
shared=importlib.util.module_from_spec(spec);spec.loader.exec_module(shared)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary',type=Path,required=True)
    p.add_argument('--libgcc',type=Path,required=True)
    p.add_argument('--unicorn-dir',type=Path,required=True)
    p.add_argument('--native-probe',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--fixture',type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.unicorn_dir))
    image,gcc=a.binary.read_bytes(),a.libgcc.read_bytes()
    if shared.combat.sha(image)!=shared.combat.IMAGE_SHA or shared.combat.sha(gcc)!=shared.combat.LIBGCC_SHA:
        raise ValueError('wrong original inputs')
    resources=list(struct.unpack_from('<24I',image,0xce8ec-0x1000))
    rng=random.Random(0x2ad122b2d2)
    results=[];inputs=[];calls=Counter()
    boundaries={0x61f14:'resource load: report identity and return a distinct nonnull handle',
                0x61ddc:'resource release: report original identity only',
                0x3000100:'platform enabled: supplied test state',
                0x3000110:'platform playing: supplied/output-updated test state',
                0x3000120:'platform stop all: record request and clear test playing state',
                0x3000130:'platform play: record exact slot, flags and one event request'}
    for index in range(512):
        operation=index%9-1
        argument=index%3 if operation==0 else rng.randrange(-1,26)
        values=[operation,argument,rng.randrange(1<<24),rng.randrange(-1,24),rng.randrange(-1,24),
                *(int(rng.randrange(2)) for _ in range(5))]
        op,arg,mask,last_music,last_played,suppressed,a3,a4,enabled,playing=values
        old=shared.OriginalAI(image,gcc)
        ar=old.ar
        manager=old.alloc(0x100);vtable=old.alloc(0xc0)
        old.w32(manager,vtable)
        singleton=old.r32(old.r32(0xd2038));old.w32(singleton+0x28,manager)
        for offset,pc in ((0x14,0x3000100),(0x40,0x3000110),(0x54,0x3000120),(0x50,0x3000130)):
            old.w32(vtable+offset,pc|1)
        for slot in range(24): old.w32(old.app+4+slot*4,0x5f000100+slot if mask&(1<<slot) else 0)
        old.w32(old.app+0x64,last_played);old.w32(old.app+0x9c,last_music)
        for offset,value in ((0xa0,suppressed),(0xa3,a3),(0xa4,a4)):old.w8(old.app+offset,value)
        events=[];host={'playing':playing}
        # Add a hook before OriginalAI's existing catch-all import handling;
        # these are game-resource/native-platform boundaries, not imports.
        def hook(cpu,address,_size,_data):
            if address not in boundaries:return
            calls[hex(address)]+=1
            r0,r1,r2,r3=[cpu.reg_read(getattr(ar,'UC_ARM_REG_R'+str(i))) for i in range(4)]
            if address==0x61f14:
                slot=resources.index(r1);events.extend([0,slot]);value=0x5f000100+slot
            elif address==0x61ddc:
                slot=resources.index(r1);events.extend([1,slot]);value=0
            elif address==0x3000100:value=enabled
            elif address==0x3000110:value=host['playing']
            elif address==0x3000120:
                if r1!=0:raise RuntimeError('unexpected original stop selector')
                events.extend([2,0]);host['playing']=0;value=0
            else:
                if r2!=0 or r3!=0:raise RuntimeError('original audio play flags changed')
                slot=r1-0x5f000100
                if not 0<=slot<24:raise RuntimeError('original played an invalid resource handle')
                events.extend([3,slot]);host['playing']=1;value=1
            cpu.reg_write(ar.UC_ARM_REG_R0,value)
            cpu.reg_write(ar.UC_ARM_REG_PC,cpu.reg_read(ar.UC_ARM_REG_LR))
        old.u.hook_add(old.uc.UC_HOOK_CODE,hook)
        returned=old.call(0x2ad12,[old.app,op,arg])
        outmask=sum((1<<slot) for slot in range(24) if old.r32(old.app+4+slot*4)!=0)
        result=[outmask,shared.combat.signed(old.r32(old.app+0x9c)),
                shared.combat.signed(old.r32(old.app+0x64)),returned,len(events)//2,*events]
        old.check_text();inputs.append(values);results.append(result)
    native=subprocess.run([str(a.native_probe)],input='\n'.join(' '.join(map(str,v)) for v in inputs)+'\n',
                          text=True,capture_output=True,check=True,timeout=30)
    actual=[list(map(int,line.split())) for line in native.stdout.splitlines()]
    if actual!=results:
        for n,(x,y) in enumerate(zip(actual,results)):
            if x!=y:raise RuntimeError(f'audio dispatch mismatch case{n}, input{inputs[n]}: native{x}, original{y}')
        raise RuntimeError('audio dispatch result count mismatch')
    a.fixture.parent.mkdir(parents=True,exist_ok=True)
    a.fixture.write_text('# Synthetic audio input | unchanged original output boundary requests\n'+
        '\n'.join(' '.join(map(str,x))+' | '+' '.join(map(str,y)) for x,y in zip(inputs,results))+'\n')
    report={'schema':'g1.native.audio-dispatch-original.v1','original_sha256':shared.combat.sha(image),
        'case_count':len(inputs),'scalar_comparisons':sum(map(len,results)),'result':'passed',
        'original_entries':['0x2ad12','0x2b2d2','0x2b3ac','0x2b3e2'],
        'original_text_readonly_unchanged':True,'instruction_patches':0,
        'external_boundaries':{hex(k):v for k,v in boundaries.items()},'boundary_counts':dict(calls),
        'resources':[v&0xffffff for v in resources],
        'music_resume_flags':list(image[0xce94c-0x1000:0xce94c-0x1000+24]),
        'fixture_sha256':shared.combat.sha(a.fixture.read_bytes()),
        'scope':'Control/event requests only. No actual audio API, sound output, or iPhone execution.'}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__=='__main__':main()
