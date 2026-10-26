#!/usr/bin/env python3
"""Development-only original arrival prefix, stopped at natural boundary0x59884.

No instruction modification or function replacement. This does not execute the
remaining arrival callback or claim a complete world transition.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import struct
import subprocess
import sys

ORIGINAL_SHA256="0d510516fe3676ee4a0f4dff60ba64e1c5bf79a0c9800f420b1bbdb1c12febfd"


def make_cases():
    # Unit record is type,owner,x,y,facing,active.
    actor=[11,0,5,5,3,1]
    cases=[
        {"name":"opposite_sides_type_tie","actor":actor,"units":[[19,1,6,5,1,1],[2,1,4,5,1,1]],"low":1,"high":1,"field13":0},
        {"name":"vertical_only","actor":actor,"units":[[19,1,5,4,1,1]],"low":1,"high":1,"field13":0},
        {"name":"vertical_tie_break","actor":actor,"units":[[2,1,5,3,1,1],[19,1,7,5,1,1]],"low":1,"high":2,"field13":0},
        {"name":"first_spawn_neighbors","actor":[11,0,1,2,1,1],"units":[[19,1,4,7,1,1]],"low":1,"high":1,"field13":0},
        {"name":"first_unit_after_right_step","actor":[11,0,2,2,3,1],"units":[[19,1,4,7,1,1]],"low":1,"high":1,"field13":0},
        {"name":"preserve_form1_facing","actor":actor,"units":[[19,1,6,5,1,1]],"low":1,"high":1,"field13":1},
    ]
    rng=random.Random(0x5979859884)
    for i in range(186):
        kind=rng.randrange(23)
        actor=[kind,rng.randrange(2),rng.randrange(20),rng.randrange(20),rng.randrange(4),1]
        types=rng.sample([t for t in range(23) if t!=kind],rng.randrange(23))
        units=[[t,rng.randrange(2),rng.randrange(20),rng.randrange(20),rng.randrange(4),rng.randrange(2)] for t in types]
        low=rng.randrange(5);high=rng.randrange(1,40)
        cases.append({"name":f"mixed_{i:03}","actor":actor,"units":units,
                      "low":low,"high":high,"field13":rng.choice([-128,-1,0,0,1,1,2,127])})
    return cases


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--binary",type=Path,required=True)
    p.add_argument("--movement-oracle",type=Path,required=True)
    p.add_argument("--unicorn-dir",type=Path,required=True)
    p.add_argument("--native-probe",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.unicorn_dir))
    import unicorn
    from unicorn import arm_const as ar
    spec=importlib.util.spec_from_file_location("g1_arrival_original",a.movement_oracle)
    old_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(old_module)
    image=a.binary.read_bytes()
    if hashlib.sha256(image).hexdigest()!=ORIGINAL_SHA256:raise SystemExit("Wrong original input")
    cases=make_cases();results=[];native_input=[]
    for index,c in enumerate(cases):
        actor=c["actor"]
        fixture={"width":32,"height":32,"unit":{"type":actor[0],"owner":actor[1],"x":actor[2],
                 "y":actor[3],"base_budget":5,"spent_budget":0,"field6":0,"form":index%2},
                 "terrain":[[1,0]]*1024,"active_owners":[None]*1024}
        old=old_module.OriginalMovement(image,fixture)
        read32=lambda addr:struct.unpack("<I",old.uc.mem_read(addr,4))[0]
        stat_forms=old.alloc(16)
        for f in range(2):
            stats=[0]*14;stats[0]=5
            stats[1],stats[2],stats[13]=c["low"],c["high"],c["field13"]
            old.vector_at(stat_forms+8*f,old.array(stats,1),14)
        type_records=read32(old.map+0x174)
        old.vector_at(type_records+8*actor[0],stat_forms,2)
        old.write8(old.unit+0x4B,actor[4])
        addresses={actor[0]:old.unit};records={actor[0]:actor}
        for u in c["units"]:
            records[u[0]]=u;address=old.alloc(0x80);addresses[u[0]]=address
            for off,value in ((9,u[0]),(10,u[1]),(0x3B,u[2]),(0x3C,u[3]),(0x4B,u[4]),(13,u[5])):
                old.write8(address+off,value)
            # Moving targets are intentionally still eligible in this collector.
            old.write32(address+0x40,7 if u[0]%2 else 0)
        owner_lists=[[addresses[t] for t in sorted(records) if records[t][1]==owner] for owner in range(2)]
        capacity=max(1,*(len(v) for v in owner_lists))
        old.write32(old.map+0x54,capacity)
        old.write32(old.map+0x84,old.array([old.array(v+[0]*(capacity-len(v))) for v in owner_lists]))
        targets=old.alloc(capacity*4)
        old.write32(old.map+0xF4,targets)
        # A stale, valid cache makes the field13=1 no-write boundary observable.
        old.write8(old.map+0xF0,1);old.write32(targets,old.unit)
        cache_before=bytes(old.uc.mem_read(targets,capacity*4))
        for reg in (ar.UC_ARM_REG_R0,ar.UC_ARM_REG_R1,ar.UC_ARM_REG_R2,ar.UC_ARM_REG_R3,
                    ar.UC_ARM_REG_R4,ar.UC_ARM_REG_R5,ar.UC_ARM_REG_R6,ar.UC_ARM_REG_R7,
                    ar.UC_ARM_REG_R8,ar.UC_ARM_REG_R9,ar.UC_ARM_REG_R10,ar.UC_ARM_REG_R11,
                    ar.UC_ARM_REG_R12):old.uc.reg_write(reg,0)
        old.uc.reg_write(ar.UC_ARM_REG_CPSR,0x30)
        old.uc.reg_write(ar.UC_ARM_REG_SP,0x21FF000)
        old.uc.reg_write(ar.UC_ARM_REG_LR,old.return_address|1)
        old.uc.reg_write(ar.UC_ARM_REG_R0,old.map);old.uc.reg_write(ar.UC_ARM_REG_R1,old.unit)
        old.uc.emu_start(0x59799,0x59884,timeout=5_000_000,count=500_000)
        if old.uc.reg_read(ar.UC_ARM_REG_PC)!=0x59884:raise RuntimeError("Prefix did not reach boundary")
        if old.uc.reg_read(ar.UC_ARM_REG_SP)!=0x21FF000-52:raise RuntimeError("Unexpected prefix frame")
        facing=bytes(old.uc.mem_read(old.unit+0x4B,1))[0]
        if c["field13"]==1:
            if bytes(old.uc.mem_read(targets,capacity*4))!=cache_before or bytes(old.uc.mem_read(old.map+0xF0,1))[0]!=1:
                raise RuntimeError("Skip branch unexpectedly altered target cache")
            result={"writes_facing":False,"facing":facing,"targets":None,"nearest":None}
        else:
            count=bytes(old.uc.mem_read(old.map+0xF0,1))[0]
            inverse={value:key for key,value in addresses.items()}
            target_types=[inverse[read32(targets+4*i)] for i in range(count)]
            nearest=target_types[old.uc.reg_read(ar.UC_ARM_REG_R12)] if count else None
            result={"writes_facing":True,"facing":facing,"targets":target_types,"nearest":nearest}
        if bytes(old.uc.mem_read(0x1000,0xD1000))!=old.original_text:raise RuntimeError("Original text mutated")
        results.append(result)
        fields=actor+[c["low"],c["high"],c["field13"],len(c["units"])]+[v for u in c["units"] for v in u]
        native_input.append(" ".join(map(str,fields)))
    completed=subprocess.run([str(a.native_probe.resolve())],input=str(len(cases))+"\n"+"\n".join(native_input)+"\n",
                             text=True,capture_output=True,check=True)
    native=json.loads(completed.stdout)
    if native!=results:
        for c,n,o in zip(cases,native,results):
            if n!=o:raise RuntimeError(json.dumps({"case":c,"native":n,"original":o}))
        raise RuntimeError("Result count mismatch")
    report={"kind":"Original arrival callback prefix comparison",
            "start":"0x59798","natural_stop_before":"0x59884",
            "original_sha256":ORIGINAL_SHA256,"unicorn_version":unicorn.__version__,
            "case_count":len(cases),"native_original_exact_match":True,
            "instruction_patches":0,"function_stubs":0,"original_text_readonly_unchanged":True,
            "original_owner_slot_order":"ascending type, original0x496e4",
            "synthetic_state":True,"full_arrival_callback_executed":False,
            "original_movement_oracle_sha256":hashlib.sha256(a.movement_oracle.read_bytes()).hexdigest(),
            "cases":cases,"results":results}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"cases":len(cases),"native_original_exact_match":True,
                      "original_prefix":"0x59798..0x59884","full_arrival_callback_executed":False}))


if __name__=="__main__":main()
