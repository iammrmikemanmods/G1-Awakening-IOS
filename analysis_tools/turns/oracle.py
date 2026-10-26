#!/usr/bin/env python3
"""Original turn/reset/economy reference; four explicit presentation/storage hooks."""
import argparse
import collections
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import struct
import subprocess
import sys

IMAGE_SHA = '0d510516fe3676ee4a0f4dff60ba64e1c5bf79a0c9800f420b1bbdb1c12febfd'
BYTE_FIELDS = {0:0x0d,1:0x0c,2:0x3b,3:0x3c,6:0x4b,7:0x59,9:0x48,10:0x49,
               11:0x4a,12:0x2c,13:0x2d,14:0x2f,15:0x38,16:0x39,17:0x3a}
INT_FIELDS = {4:0x40,5:0x44,8:0x30}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary',type=Path,required=True)
    p.add_argument('--movement-oracle',type=Path,required=True)
    p.add_argument('--capture-reference',type=Path,required=True)
    p.add_argument('--unicorn-dir',type=Path,required=True)
    p.add_argument('--native-probe',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--fixture-out',type=Path,required=True)
    a=p.parse_args()
    sys.path.insert(0,str(a.unicorn_dir))
    import unicorn
    from unicorn import arm_const as ar
    image=a.binary.read_bytes()
    if hashlib.sha256(image).hexdigest()!=IMAGE_SHA:raise ValueError('wrong original image')
    spec=importlib.util.spec_from_file_location('turn_movement_reference',a.movement_oracle)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    capture=json.loads(a.capture_reference.read_text())
    if capture['original_sha256']!=IMAGE_SHA:raise ValueError('wrong capture reference identity')
    rng=random.Random(0x558404E80C)
    results=[];lines=[];hooks=collections.Counter()
    seed={'width':3,'height':3,'unit':{'type':0,'owner':0,'base_budget':2,'spent_budget':0,
        'form':0,'field6':0,'x':1,'y':1},'terrain':[[1,0]]*9,'active_owners':[None]*9}
    for index in range(192):
        network=capture['cases'][(index//4)*4]
        state=[index%2,*(rng.choice([0,1,2,-1]) for _ in range(2)),
               rng.choice([0,100,2147483647,-2147483648]),rng.randrange(-20,200),
               rng.choice([0,10,2147483647]),rng.randrange(30),index%2,
               *network['factions'],*network['counters']]
        unit_count=index%24
        kinds=rng.sample(range(23),unit_count)
        units=[]
        for kind in kinds:
            owner=rng.randrange(2)
            values=[int(rng.randrange(4)!=0),rng.randrange(2),rng.randrange(25),rng.randrange(25),
                rng.randrange(-20,20),rng.randrange(-20,20),rng.randrange(4),rng.randrange(10),
                rng.choice([-1,0,1000]),rng.randrange(25),rng.randrange(25),rng.randrange(4),
                *(rng.randrange(256) for _ in range(6))]
            units.append((kind,owner,values))
        flat=state+[unit_count]
        for kind,owner,values in units:flat += [kind,owner]+values
        flat += [len(network['sites'])]
        for site in network['sites']:
            flat += [site['owner'],len(site['groups'])]
            for group in site['groups']:
                flat += [len(group)]
                for item in group:flat += [item['owner'],item['link']]
        old=module.OriginalMovement(image,seed)
        funds=old.array(state[3:5]);counters=old.array(state[10:12])
        old.vector_at(old.map+0x58,funds,2)
        old.vector_at(old.map+0x60,old.alloc(16),2)
        old.vector_at(old.map+0x68,counters,2)
        old.vector_at(old.map+0x98,old.array(state[1:3],1),2)
        old.vector_at(old.map+0xa0,old.array(state[8:10],1),2)
        old.write8(old.map+0xa8,state[0]);old.write32(old.map+0x274,state[5])
        old.write32(old.map+0x2c,state[6]);old.write8(old.map+0xe1,state[7])
        ptrs=[];owners=[[],[]];counts=[0,0]
        for kind,owner,values in units:
            ptr=old.alloc(0x80);ptrs.append(ptr)
            old.write8(ptr+9,kind);old.write8(ptr+10,owner)
            for n,offset in BYTE_FIELDS.items():old.write8(ptr+offset,values[n])
            for n,offset in INT_FIELDS.items():old.write32(ptr+offset,values[n])
            owners[owner].append((kind,ptr));counts[owner]+=values[0]
        lists=[]
        for owner in owners:
            items=[ptr for _,ptr in sorted(owner)]
            lists.append(old.array(items+[0]*(23-len(items))))
        old.write32(old.map+0x54,23);old.write32(old.map+0x84,old.array(lists))
        old.vector_at(old.map+0x7c,old.array(counts,1),2)
        sites=network['sites'];outer_items=old.alloc(max(8,8*len(sites)))
        outer_links=old.alloc(max(8,8*len(sites)));link_arrays=[]
        old.vector_at(old.map+0x3e8,old.array([s['owner'] for s in sites],1),len(sites))
        for n,site in enumerate(sites):
            gi=old.alloc(max(8,8*len(site['groups'])));gl=old.alloc(max(8,8*len(site['groups'])))
            for g,group in enumerate(site['groups']):
                ip=old.array([i['owner'] for i in group],1);lp=old.array([i['link'] for i in group],1)
                old.vector_at(gi+g*8,ip,len(group));old.vector_at(gl+g*8,lp,len(group))
                link_arrays.append((lp,len(group)))
            old.vector_at(outer_items+n*8,gi,len(site['groups']))
            old.vector_at(outer_links+n*8,gl,len(site['groups']))
        old.vector_at(old.map+0x3f8,outer_items,len(sites));old.vector_at(old.map+0x408,outer_links,len(sites))
        effects={'focus':None,'snapshot':False,'formatted_values':[]}
        def hook(cpu,address,_size,_data):
            if address not in (0x557c4,0x60800,0x60b70,0x5146e):
                if 0xba1e0<=address<0xbaaa0:raise RuntimeError(f'unexpected original import {address:x}')
                return
            hooks[hex(address)]+=1
            if address==0x557c4:
                if cpu.reg_read(ar.UC_ARM_REG_R0)!=old.map:raise RuntimeError('camera wrong world')
                effects['focus']=[cpu.reg_read(ar.UC_ARM_REG_R1),cpu.reg_read(ar.UC_ARM_REG_R2)]
            elif address==0x5146e:effects['snapshot']=True
            elif address==0x60b70:effects['formatted_values'].append(cpu.reg_read(ar.UC_ARM_REG_R1))
            cpu.reg_write(ar.UC_ARM_REG_PC,cpu.reg_read(ar.UC_ARM_REG_LR))
        old.uc.hook_add(unicorn.UC_HOOK_CODE,hook)
        old.call(0x55840,[old.map,1])
        def i32(address):return struct.unpack('<i',old.uc.mem_read(address,4))[0]
        def u8(address):return old.uc.mem_read(address,1)[0]
        focus=effects['focus'] or [-1,-1]
        result=[u8(old.map+0xa8),int(effects['focus'] is not None),*focus,int(effects['snapshot']),
                i32(funds),i32(funds+4),i32(counters),i32(counters+4),i32(old.map+0x274),
                i32(old.map+0x2c),u8(old.map+0xe1)]
        for ptr in ptrs:
            values=[0]*18
            for n,offset in BYTE_FIELDS.items():values[n]=u8(ptr+offset)
            for n,offset in INT_FIELDS.items():values[n]=i32(ptr+offset)
            result+=values
        for lp,count in link_arrays:result+=list(old.uc.mem_read(lp,count))
        if bytes(old.uc.mem_read(0x1000,0xd1000))!=old.original_text:raise RuntimeError('original text mutated')
        lines.append(' '.join(map(str,flat)));results.append(result)
    native=subprocess.run([str(a.native_probe)],input='\n'.join(lines)+'\n',text=True,capture_output=True,check=True,timeout=60)
    actual=[list(map(int,line.split())) for line in native.stdout.splitlines()]
    if actual!=results:
        for i,(x,y) in enumerate(zip(actual,results)):
            if x!=y:raise RuntimeError(f'native/original turn mismatch case{i}: native{x}, original{y}')
        raise RuntimeError('native turn result count mismatch')
    a.fixture_out.parent.mkdir(parents=True,exist_ok=True)
    a.fixture_out.write_text('# Synthetic decoded inputs | unchanged-original gameplay output\n'+
        '\n'.join(line+' | '+' '.join(map(str,result)) for line,result in zip(lines,results))+'\n')
    report={'original_sha256':IMAGE_SHA,'unicorn_version':unicorn.__version__,'result':'passed',
        'case_count':len(results),'scalar_comparisons':sum(map(len,results)),
        'original_entries':['0x55840','0x430fc','0x4e8e8','0x4e80c','0x4a852'],
        'instruction_patches':0,'original_text_readonly_unchanged':True,
        'external_hooks':{'0x557c4':'camera-focus request only; renderer not executed',
            '0x60800':'UI string assignment; formatting not executed',
            '0x60b70':'UI numeric formatting; argument recorded',
            '0x5146e':'snapshot request only; original profile copying/persistence not executed'},
        'external_hook_counts':dict(hooks),'native_fixture_sha256':hashlib.sha256(a.fixture_out.read_bytes()).hexdigest(),
        'capture_input_reference_sha256':hashlib.sha256(a.capture_reference.read_bytes()).hexdigest(),
        'scope':'Original outgoing-unit resets, owner selection, income/links/funds and turn counters; no AI, UI playback, or save proof'}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__=='__main__':main()
