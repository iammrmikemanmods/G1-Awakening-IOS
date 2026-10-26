#!/usr/bin/env python3
"""Development-only original transform comparison. Excluded from the product.

Uses the real original ARMv6 libgcc signed division helper, bound by writing the
original lazy-symbol DATA pointer. No instruction patches or function stubs.
Full transform calls run with audio disabled. Separate enabled-audio prefixes
stop before the original audio call and record its real requested arguments.
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

IMAGE_SHA = "0d510516fe3676ee4a0f4dff60ba64e1c5bf79a0c9800f420b1bbdb1c12febfd"
GCC_SHA = "d758fbf1ac952532955d62866bd02df55315c0599f64bdd978ff941fccbdcf83"


def load_gcc(data):
    magic,count=struct.unpack_from(">II",data)
    if magic!=0xcafebabe:raise ValueError("Expected universal original libgcc")
    slices=[struct.unpack_from(">5I",data,8+i*20) for i in range(count)]
    _,_,offset,size,_=next(s for s in slices if s[0]==12 and s[1]==6)
    thin=data[offset:offset+size]
    ncmds=struct.unpack_from("<I",thin,16)[0]
    cursor=28;segments=[]
    for _ in range(ncmds):
        cmd,length=struct.unpack_from("<II",thin,cursor)
        if cmd==1:segments.append(struct.unpack_from("<4I",thin,cursor+24))
        elif cmd==2:symoff,nsyms,stroff,_=struct.unpack_from("<4I",thin,cursor+8)
        cursor+=length
    for i in range(nsyms):
        idx,_,_,desc,value=struct.unpack_from("<IBBHI",thin,symoff+12*i)
        name=thin[stroff+idx:thin.index(b"\0",stroff+idx)]
        if name==b"___divsi3":return thin,segments,value|(1 if desc&8 else 0)
    raise ValueError("Original signed division export absent")


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("binary","libgcc","movement-oracle","native-probe","unicorn-dir","output"):
        p.add_argument("--"+name,type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.unicorn_dir))
    import unicorn
    from unicorn import arm_const as ar
    spec=importlib.util.spec_from_file_location("movement_oracle",a.movement_oracle)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    image=a.binary.read_bytes();gcc=a.libgcc.read_bytes()
    if hashlib.sha256(image).hexdigest()!=IMAGE_SHA or hashlib.sha256(gcc).hexdigest()!=GCC_SHA:
        raise RuntimeError("Pinned original input hash mismatch")
    thin,segments,division=load_gcc(gcc)
    rng=random.Random(0x43A54);cases=[]
    for i in range(128):
        forms=[]
        for f in range(2):
            values=[0]*14;values[0]=5
            values[3:6]=[rng.randrange(-128,128) for _ in range(3)]
            values[8]=rng.choice([0,0,1,-1]);values[13]=rng.choice([0,1,-1])
            forms.append(values)
        cases.append({"type_flag":rng.choice([0,1,255]),"form":i%2,"active":i%11!=0,
                      "flag2c":1 if i%13==0 else 0,"flag2d":1 if i%7==0 else 0,
                      "flag2e":rng.randrange(4),"flag2f":rng.randrange(4),"facing":rng.randrange(4),
                      "spent":rng.randrange(6),"level":rng.choice([0,1,2,5,127,255]),
                      "record":i%3!=0,"audio":i%4!=0,
                      "terrain0":rng.choice([1,3,99,-1]),"terrain2":rng.randrange(2),"forms":forms})
    results=[];lines=[];audio_cases=0;division_calls=0
    registers=[getattr(ar,"UC_ARM_REG_R"+str(i)) for i in range(13)]
    for c in cases:
        fixture={"width":2,"height":2,
                 "unit":{"type":11,"owner":0,"base_budget":5,"spent_budget":c["spent"],
                         "form":c["form"],"field6":0,"x":0,"y":0},
                 "terrain":[[c["terrain0"],c["terrain2"]]]*4,"active_owners":[None]*4}
        old=module.OriginalMovement(image,fixture)
        read32=lambda address:struct.unpack("<I",old.uc.mem_read(address,4))[0]
        app=read32(read32(read32(0xD2038))+0x58)
        old.uc.mem_map(0x40000000,0x10000)
        for vm,_,offset,size in segments:old.uc.mem_write(0x40000000+vm,thin[offset:offset+size])
        old.uc.mem_protect(0x40000000,0x9000,unicorn.UC_PROT_READ|unicorn.UC_PROT_EXEC)
        old.write32(0xD26A4,0x40000000+division)
        old.uc.reg_write(ar.UC_ARM_REG_C1_C0_2,0x00F00000)
        old.uc.reg_write(ar.UC_ARM_REG_FPEXC,0x40000000)
        forms=old.alloc(16)
        for f,values in enumerate(c["forms"]):old.vector_at(forms+8*f,old.array(values,1),14)
        type_records=read32(old.map+0x174);old.vector_at(type_records+8*11,forms,2)
        flags=[0]*12;flags[11]=1 if c["type_flag"] else 0
        old.vector_at(old.map+0x154,old.array(flags,1),12)
        def seed_unit():
            for off,value in ((0xC,c["form"]),(0xD,int(c["active"])),(0x1A,c["level"]),
                              (0x2C,c["flag2c"]),(0x2D,c["flag2d"]),(0x2E,c["flag2e"]),
                              (0x2F,c["flag2f"]),(0x4B,c["facing"]),(0x59,c["spent"])):
                old.write8(old.unit+off,value)
        seed_unit()
        active=old.call(0x492EC,[old.map,old.unit])!=0
        eligible=active and old.call(0x430EE,[old.unit])==0 and old.call(0x4A6C0,[old.map,old.unit])!=0
        # Full unit transition and genuine signed division helper, audio off.
        old.write8(app+0xA3,0)
        old.call(0x43A54,[old.unit,int(c["record"])])
        division_calls+=3
        unit=[old.uc.mem_read(old.unit+off,1)[0] for off in (0xC,0x2C,0x2D,0x2E,0x2F,0x4B,0x59)]
        stats=list(struct.unpack("<hhh",old.uc.mem_read(old.unit+0x1C,6)))
        audio=None
        if c["record"] and c["audio"]:
            seed_unit();old.write8(app+0xA3,1)
            for register in registers:old.uc.reg_write(register,0)
            old.uc.reg_write(ar.UC_ARM_REG_CPSR,0x30)
            old.uc.reg_write(ar.UC_ARM_REG_SP,0x21FF000)
            old.uc.reg_write(ar.UC_ARM_REG_LR,old.return_address|1)
            old.uc.reg_write(ar.UC_ARM_REG_R0,old.unit);old.uc.reg_write(ar.UC_ARM_REG_R1,1)
            old.uc.emu_start(0x43A55,0x43AAE,timeout=5_000_000,count=100_000)
            if old.uc.reg_read(ar.UC_ARM_REG_PC)!=0x43AAE or old.uc.reg_read(ar.UC_ARM_REG_SP)!=0x21FF000-16:
                raise RuntimeError("Enabled-audio prefix failed natural boundary")
            if old.uc.reg_read(ar.UC_ARM_REG_R0)!=app or old.uc.reg_read(ar.UC_ARM_REG_R1)!=5:
                raise RuntimeError("Unexpected original audio receiver/group")
            audio=old.uc.reg_read(ar.UC_ARM_REG_R2);audio_cases+=1
            if unit!=[old.uc.mem_read(old.unit+off,1)[0] for off in (0xC,0x2C,0x2D,0x2E,0x2F,0x4B,0x59)]:
                raise RuntimeError("Audio-enabled prefix altered other unit outputs")
        if bytes(old.uc.mem_read(0x1000,0xD1000))!=old.original_text:
            raise RuntimeError("Original text changed")
        results.append({"eligible":bool(eligible),"unit":unit,"stats":stats,"audio":audio})
        fields=[c[k] for k in ("type_flag","form","active","flag2c","flag2d","flag2e","flag2f","facing","spent","level","record","audio","terrain0","terrain2")]
        fields.extend(v for form in c["forms"] for v in form)
        lines.append(" ".join(str(int(v)) for v in fields))
    proc=subprocess.run([str(a.native_probe.resolve())],input=str(len(lines))+"\n"+"\n".join(lines)+"\n",text=True,capture_output=True,check=True)
    native=json.loads(proc.stdout)
    if native!=results:
        for i,(n,o) in enumerate(zip(native,results)):
            if n!=o:raise RuntimeError(json.dumps({"case":cases[i],"native":n,"original":o}))
        raise RuntimeError("Result count mismatch")
    report={"original_sha256":IMAGE_SHA,"original_libgcc_sha256":GCC_SHA,"libgcc_slice":"ARMv6 subtype6",
            "libgcc_binding":"original DATA slot0xd26a4 -> original ___divsi3",
            "unicorn_version":unicorn.__version__,"native_original_exact_match":True,
            "full_transform_cases":len(cases),"eligibility_gate_cases":len(cases),
            "audio_request_prefix_cases":audio_cases,"original_signed_division_calls":division_calls,
            "audio_playback_executed":False,"synthetic_state":True,
            "instruction_patches":0,"function_stubs":0,"original_text_readonly_unchanged":True,
            "full_function":"0x43a54, with audio flag0","audio_prefix_stop_before":"0x43aae",
            "eligibility_functions":["0x492ec","0x430ee","0x4a6c0"],
            "movement_oracle_sha256":hashlib.sha256(a.movement_oracle.read_bytes()).hexdigest(),
            "cases":cases,"results":results}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:report[k] for k in ("native_original_exact_match","full_transform_cases","audio_request_prefix_cases")}))


if __name__=="__main__":main()
