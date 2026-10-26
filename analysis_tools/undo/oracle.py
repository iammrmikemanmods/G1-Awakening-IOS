#!/usr/bin/env python3
"""Development-only original Undo, selection-lock and command-mask reference.

Original instructions are mapped read-only and are never patched. Undo, its
eligibility and selection locks execute original gameplay functions. The
command-mask cases deliberately provide explicit predicate-return inputs at
nine helper boundaries: these verify composition/short-circuiting ONLY, not the
underlying world predicates. Renderer/audio/range requests are recorded, never
treated as presented. Nothing here is linked into or shipped with the app.
"""
import argparse
import collections
import gc
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import struct
import sys

IMAGE_SHA256="0d510516fe3676ee4a0f4dff60ba64e1c5bf79a0c9800f420b1bbdb1c12febfd"
SUPPORT_SHA256="2c1fc1e53e27c8c0a16a248b4d724f6225f9fdcba05456a9d840cc21d1bc6a79"
FIELDS=["type","active","form","x","y","offset_x","offset_y","facing",
        "spent","timer30","anchor_x","anchor_y","anchor_facing","flag2c",
        "flag2d","flag2f","flag38","flag39","flag3a","health","level",
        "immune","attack_low","attack_high","defense","support","preset34",
        "animation2e","moving8"]
PREDICATES=[0x50ec8,0x4ec0e,0x50236,0x52f84,0x4a6c0,0x4a73c,0x4b050,0x4b394,0x501f2]


def sha(data):return hashlib.sha256(data).hexdigest()
def signed(value,bits=32):return value if value<1<<(bits-1) else value-(1<<bits)


def make_cases():
    rng=random.Random(0x5a2ce50d42)
    cases=[]
    def sample(index):
        state=[index%23,index%11!=0,index%2,129+index%127,137+index%119,
               rng.choice([0,7,-9,2147483647,-2147483648]),rng.choice([0,6,-8]),
               index%4,rng.choice([0,1,3,127,128,255]),
               rng.choice([-1,0,1,1234,-2147483648,2147483647]),
               128+index%128,127+index%129,(index+1)%4,0,
               rng.choice([0,1,2,255]),rng.choice([0,1,2,255]),
               rng.choice([0,1,2,255]),rng.choice([0,1,2,255]),
               rng.choice([0,1,2,255]),rng.randrange(256),
               rng.choice([0,1,24,25,127,255]),index%2,
               -1234,2345,-3456,-17,12345,rng.randrange(256),index%2]
        forms=[]
        for _ in range(2):
            forms.append([rng.choice([0,1,3,127,128,255]),1,2,
                rng.choice([0,1,20,127,128,255]),rng.choice([0,30,127,128,255]),
                rng.choice([0,5,127,128,255]),0,0,0,0,0,0,0,1])
        return [int(v) for v in state],forms
    def add(kind,name,state,forms,parameters=()):
        cases.append(dict(kind=kind,name=name,state=state,forms=forms,parameters=list(parameters)))
    for i in range(160):
        state,forms=sample(i);state[13]=rng.choice([0,0,0,1,255])
        add(1,f"availability_{i:03}",state,forms,[int(i%29!=0)])
    # Explicit byte subtraction, XOR rather than logical-not, and lock branches.
    for base in (0,1,3,127,128,255):
        for spent in (0,1,127,128,255):
            for locked in (0,1):
                state,forms=sample(len(cases));state[8]=spent;state[14]=1
                state[17]=2 if locked else 1;state[18]=locked
                forms[state[2]][0]=base
                add(1,f"byte_budget_{base}_{spent}_{locked}",state,forms,[1])
    for i in range(192):
        state,forms=sample(i);state[1]=1;state[13]=0
        if i<64:
            state[8]=[1,3,127,128,255][i%5];state[14]=0;state[18]=0
        elif i<128:
            state[8]=0;state[14]=[1,2,255][i%3];state[17]=[0,2,255][i%3];state[18]=0
        else:
            state[14]=[1,2,255][i%3];state[17]=[0,2,255][i%3]
            state[18]=[1,2,255][i%3]
        add(2,f"undo_{i:03}",state,forms)
    for i in range(96):
        state,forms=sample(i)
        state[8]=[0,1,128,255][i%4];state[14]=[0,1,255][(i//3)%3]
        add(3,f"selection_lock_{i:02}",state,forms,[i%3]) # no old/same/different
    for i in range(32):
        state,forms=sample(i);state[1]=1;state[13]=0
        add(4,f"end_action_{i:02}",state,forms)
    # All Boolean predicate combinations; only the mask composition is claimed.
    for mask in range(512):
        state,forms=sample(mask);state[1]=1;state[13]=0;state[8]=0
        add(5,f"mask_combination_{mask:03}",state,forms,[1,mask])
    for i in range(48):
        state,forms=sample(i);state[1]=i%4!=0;state[13]=[0,1,255][i%3]
        state[8]=[0,1,128,255][i%4]
        add(5,f"mask_guard_{i:02}",state,forms,[int(i%5!=0),511])
    return cases


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image",type=Path,required=True)
    parser.add_argument("--support",type=Path,required=True)
    parser.add_argument("--unicorn-dir",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args();sys.path.insert(0,str(args.unicorn_dir))
    import unicorn
    from unicorn import arm_const as ar
    image=args.image.read_bytes()
    if sha(image)!=IMAGE_SHA256 or sha(args.support.read_bytes())!=SUPPORT_SHA256:
        raise SystemExit("Original image/support SHA256 mismatch")
    spec=importlib.util.spec_from_file_location("g1_world_reference",args.support)
    support=importlib.util.module_from_spec(spec);spec.loader.exec_module(support)

    class Reference(support.Reference):
        def __init__(self,case):
            self.events=[];self.stop=None;self.predicate_values=None;self.calls=[]
            state,forms=case["state"],case["forms"]
            definitions=[dict(type=t,scalar_fields=[t%2,8,0,0,0],
                forms=([list(v) for v in forms] if t==state[0] else
                       [[3,1,1,20,30,5,0,0,0,0,0,0,0,1]]*2)) for t in range(23)]
            super().__init__(image,definitions,b"")
            self.actor=self.units[state[0]]
            byte_offsets={9:0,0xd:1,0xc:2,0x3b:3,0x3c:4,0x4b:7,0x59:8,
                0x48:10,0x49:11,0x4a:12,0x2c:13,0x2d:14,0x2f:15,0x38:16,
                0x39:17,0x3a:18,0x5a:19,0x1a:20,0x19:21,0x2e:27,8:28}
            for offset,index in byte_offsets.items():self.w8(self.actor+offset,state[index])
            for offset,index in {0x40:5,0x44:6,0x30:9,0x5c:25,0x34:26}.items():
                self.w32(self.actor+offset,state[index])
            for offset,index in {0x1c:22,0x1e:23,0x20:24}.items():
                self.u.mem_write(self.actor+offset,struct.pack("<h",state[index]))
            self.w8(self.actor+0x18,193);self.w32(self.actor+0x24,123);self.w32(self.actor+0x28,456)
            self.w32(self.map+0x3e4,self.actor);self.w32(self.map+0x298,self.alloc(8))
            self.w32(self.map+0x29c,self.app);self.w8(self.map+0xe0,1)
            self.active_boundaries={0xba288}

        def hook(self,u,address,size,unused):
            if address==self.stop:
                u.emu_stop();return
            if self.predicate_values is not None and address in PREDICATES:
                self.calls.append(address)
                u.reg_write(ar.UC_ARM_REG_R0,self.predicate_values[PREDICATES.index(address)])
                u.reg_write(ar.UC_ARM_REG_PC,u.reg_read(ar.UC_ARM_REG_LR));return
            if address in (0x56044,0x50ec8,0x50844,0x5494c,0x544d0,0x2ad12,0x5c9a8,0x2c930):
                r0,r1,r2=[u.reg_read(reg) for reg in
                         (ar.UC_ARM_REG_R0,ar.UC_ARM_REG_R1,ar.UC_ARM_REG_R2)]
                self.events.append([address,r1,r2])
                u.reg_write(ar.UC_ARM_REG_PC,u.reg_read(ar.UC_ARM_REG_LR));return
            super().hook(u,address,size,unused)

        def fragment(self,entry,stop,registers=None):
            for reg in (ar.UC_ARM_REG_R0,ar.UC_ARM_REG_R1,ar.UC_ARM_REG_R2,ar.UC_ARM_REG_R3,
                        ar.UC_ARM_REG_R4,ar.UC_ARM_REG_R5,ar.UC_ARM_REG_R6,ar.UC_ARM_REG_R7,
                        ar.UC_ARM_REG_R8,ar.UC_ARM_REG_R9,ar.UC_ARM_REG_R10,ar.UC_ARM_REG_R11,
                        ar.UC_ARM_REG_R12):self.u.reg_write(reg,0)
            self.u.reg_write(ar.UC_ARM_REG_CPSR,0x30)
            self.u.reg_write(ar.UC_ARM_REG_SP,self.sp)
            self.u.reg_write(ar.UC_ARM_REG_LR,self.return_address|1)
            for reg,value in (registers or {}).items():self.u.reg_write(reg,value)
            self.w32(self.sp+0x3c,self.map);self.w32(self.sp+4,-1)
            self.stop=stop
            self.u.emu_start(entry|1,self.return_address,timeout=2_000_000,count=1_000_000)
            if self.u.reg_read(ar.UC_ARM_REG_PC)!=stop:
                raise RuntimeError(f"Original fragment{entry:#x} stopped at unexpected PC")
            if self.u.reg_read(ar.UC_ARM_REG_SP)!=self.sp:
                raise RuntimeError("Original fragment did not preserve its seeded stack")
            self.stop=None

        def output(self):
            rb=lambda off:self.r8(self.actor+off)
            ri=lambda off:signed(self.r32(self.actor+off))
            rh=lambda off:struct.unpack("<h",self.u.mem_read(self.actor+off,2))[0]
            return [rb(9),rb(0xd),rb(0xc),rb(0x3b),rb(0x3c),ri(0x40),ri(0x44),rb(0x4b),
                    rb(0x59),ri(0x30),rb(0x48),rb(0x49),rb(0x4a),rb(0x2c),rb(0x2d),rb(0x2f),
                    rb(0x38),rb(0x39),rb(0x3a),rb(0x5a),rb(0x1a),rb(0x19),
                    rh(0x1c),rh(0x1e),rh(0x20),ri(0x5c),ri(0x34),rb(0x2e),rb(8)]

    cases=make_cases();outputs=[];coverage=collections.Counter();events=collections.Counter()
    predicate_short_circuit_checks=0
    for index,case in enumerate(cases):
        ref=Reference(case);kind=case["kind"];parameters=case["parameters"]
        before=bytes(ref.u.mem_read(ref.actor,0x80));allowed=set()
        if kind==1:
            if not parameters[0]:ref.w32(ref.map+0x3e4,0)
            ref.start(0x50d42,[ref.map]);out=[int(ref.u.reg_read(ar.UC_ARM_REG_R0)!=0)]
        elif kind==2:
            ref.start(0x50d42,[ref.map])
            if ref.u.reg_read(ar.UC_ARM_REG_R0)==0:raise RuntimeError("Undo vector was not eligible")
            ref.fragment(0x5a2ce,0x5a4b2)
            out=ref.output()
            cursor=[e for e in ref.events if e[0]==0x56044]
            ranges=[e for e in ref.events if e[0] in (0x50ec8,0x50844)]
            audio=[e for e in ref.events if e[0]==0x2ad12]
            if len(cursor)!=1 or len(ranges)!=1 or len(audio)!=1:
                raise RuntimeError("Undo presentation request boundary changed")
            out += [int(ref.r32(ref.map+0x3e4)!=0),cursor[0][1],cursor[0][2],
                    int(ranges[0][0]==0x50ec8),audio[0][1],audio[0][2],ref.r8(ref.map+0xe0)]
            allowed={8,0xc,0x1a,0x1c,0x1d,0x1e,0x1f,0x20,0x21,
                     0x2c,0x2d,0x2f,0x38,0x39,0x3a,0x3b,0x3c,0x48,0x49,0x4b,0x59}
        elif kind==3:
            mode=parameters[0]
            if mode==0:ref.w32(ref.map+0x3e4,0)
            new=ref.actor if mode==1 else ref.units[(case["state"][0]+1)%23]
            ref.fragment(0x54dcc,0x54e14,{ar.UC_ARM_REG_R4:ref.map,ar.UC_ARM_REG_R5:new})
            out=ref.output();allowed={0x39,0x3a}
        elif kind==4:
            ref.fragment(0x5a254,0x5a4b2)
            out=ref.output()+[int(ref.r32(ref.map+0x3e4)==0)]
            allowed={0x2c}
        elif kind==5:
            selected,mask=parameters
            # Explicit independent inputs at decision-helper interfaces. The
            # original common gates, branch order and bit arithmetic execute.
            ref.predicate_values=[(1 if mask&(1<<bit) else 0) for bit in range(9)]
            ref.start(0x5300e,[ref.map,ref.actor if selected else 0])
            out=[ref.u.reg_read(ar.UC_ARM_REG_R0)]
            state=case["state"]
            expected=[]
            if selected and state[1] and state[13]==0:
                if state[8]==0:expected.append(0x50ec8)
                expected.append(0x4ec0e)
                if not mask&2:expected.append(0x50236)
                expected+=PREDICATES[3:]
            if ref.calls!=expected:raise RuntimeError("Original predicate short-circuit order mismatch")
            predicate_short_circuit_checks+=1
        else:raise RuntimeError("Unknown case kind")
        after=bytes(ref.u.mem_read(ref.actor,0x80))
        if any(before[i]!=after[i] and i not in allowed for i in range(0x80)):
            raise RuntimeError(f"Unexpected original unit write in {case['name']}")
        if bytes(ref.u.mem_read(0x1000,0xd1000))!=ref.text:
            raise RuntimeError("Original executable text changed")
        for event in ref.events:events[hex(event[0])]+=1
        outputs.append(out);coverage[str(kind)]+=1
        del ref
        if index%32==0:gc.collect()
        if (index+1)%100==0:print(f"Executed {index+1}/{len(cases)} original cases",flush=True)
    args.output.mkdir(parents=True,exist_ok=True)
    lines=[f"G1UNITCOMMANDS1 {len(cases)}"]
    for case,out in zip(cases,outputs):
        inputs=[int(v) for v in case["parameters"]+case["state"]+
                [v for form in case["forms"] for v in form]]
        lines += [f"{case['kind']} {case['name']} {len(case['parameters'])} {len(inputs)} {len(out)}",
                  " ".join(map(str,inputs))," ".join(map(str,out))]
    fixture=("\n".join(lines)+"\n").encode()
    (args.output/"unit_commands_original_vectors.txt").write_bytes(fixture)
    report={"status":"original_reference_executed","cases":len(cases),"coverage":dict(coverage),
        "image_sha256":IMAGE_SHA256,"support_sha256":SUPPORT_SHA256,
        "oracle_sha256":sha(Path(__file__).read_bytes()),"fixture_sha256":sha(fixture),
        "unicorn_version":unicorn.__version__,"instruction_patches":0,
        "original_text_readonly_unchanged":True,"unit_write_whitelist_checked_every_case":True,
        "command_predicate_call_order_checks":predicate_short_circuit_checks,
        "state_fields":FIELDS,"form_fields":"Two fourteen-byte synthetic forms, in index order",
        "kind_mapping":{"1":"complete undo eligibility50d42",
            "2":"undo unit/control fragment5a2ce..5a4b2 with recorded presentation/range boundaries",
            "3":"original friendly selection-lock fragment54dcc..54e14",
            "4":"operation10 fragment5a254..5a4b2 with recorded menu-close boundary",
            "5":"complete5300e composition with explicit supplied predicate-return inputs ONLY"},
        "recorded_boundary_counts":dict(events),
        "predicate_input_boundaries":[hex(address) for address in PREDICATES],
        "scope_limits":["Mask cases do not execute or validate the underlying nine world predicates.",
            "Unit action/selection tests do execute original eligibility/reset/transform/stat helpers.",
            "Synthetic inputs only; no original executable or resource payload appears in fixtures.",
            "Range/renderer/audio/menu boundary calls record requests, not actual UI or audio delivery.",
            "Operation10's human touch-menu reachability remains unproven; no visible Wait control claimed.",
            "Native comparison is performed by the separately compiled C++ test."]}
    (args.output/"original_unit_commands_reference.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"cases":len(cases),"coverage":dict(coverage),"fixture_sha256":sha(fixture)}))


if __name__=="__main__":main()
