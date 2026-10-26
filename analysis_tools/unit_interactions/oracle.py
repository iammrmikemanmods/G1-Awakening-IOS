#!/usr/bin/env python3
"""Development-only unchanged-original production/transport reference.

Never linked or bundled into the native app. Original code is read-only.
The explicit string/audio/renderer boundaries only record requests. Decision,
candidate, cost, activation, deactivation and slot-selection code is executed.
"""
import argparse
import collections
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import struct
import sys

IMAGE_SHA256 = "0d510516fe3676ee4a0f4dff60ba64e1c5bf79a0c9800f420b1bbdb1c12febfd"
SUPPORT_SHA256 = "2c1fc1e53e27c8c0a16a248b4d724f6225f9fdcba05456a9d840cc21d1bc6a79"
FIELDS = ["faction", "cost", "field6_0", "field6_1", "field8_0", "field8_1",
          "field9_0", "field9_1", "field12_0", "field12_1", "active", "form",
          "x", "y", "offset_x", "offset_y", "acted", "level", "available"]


def sha(data): return hashlib.sha256(data).hexdigest()
def signed(value, bits=32): return value if value < 1 << (bits-1) else value-(1 << bits)


def defaults():
    return [[t % 2, 8, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
             t % 5, t // 5, 0, 0, 0, 0, 1] for t in range(23)]


def definitions(rows):
    out=[]
    for t,r in enumerate(rows):
        f0=[3,1,1,20,30,5,r[2],0,r[4],r[6],0,0,r[8],1]
        f1=[6,1,2,40,50,8,r[3],0,r[5],r[7],0,0,r[9],1]
        out.append({"type":t,"scalar_fields":[r[0],r[1],0,0,0],"forms":[f0,f1]})
    return out


def make_cases():
    rng=random.Random(0x5412455f8c)
    cases=[]
    def add(kind,name,rows,params):
        cases.append({"kind":kind,"name":name,"rows":rows,"parameters":params})
    # Link ordering includes dual-role/self links and >2 special types.
    for i in range(48):
        rows=defaults()
        for r in rows:
            r[0]=rng.randrange(2)
            r[4:8]=[rng.choice([0,0,1,2,255]) for _ in range(4)]
        add(1,f"static_links_{i:02}",rows,[])
    # Candidate equality is ==1 on either form, not current-form or !=0.
    for i in range(96):
        rows=defaults()
        for r in rows:
            r[0]=rng.randrange(2);r[4:6]=[rng.choice([0,1,2,127,128,255]) for _ in range(2)]
            r[10]=rng.randrange(2);r[11]=rng.randrange(2);r[18]=rng.choice([0,1,2,255])
        add(2,f"candidate_{i:02}",rows,[i%2,(i//2)%2])
    # Budget1/cost0 placement, including unsigned coordinates128..254, terrain
    # 0/99/255, occupied initial north, signed special gate and ignored regions.
    for i in range(96):
        rows=defaults()
        width,height=(255,3) if i>=88 else (rng.randrange(1,7),rng.randrange(1,7))
        x,y=(128+(i-88)*17,1) if i>=88 else (rng.randrange(width),rng.randrange(height))
        field6=[0,1,2,127,128,255][i%6]
        terrain=[rng.choice([0,1,4,99,255]) for _ in range(width*height)]
        occupied=[-1]*(width*height)
        for _ in range(min(10,width*height)):
            occupied[rng.randrange(width*height)]=rng.randrange(2)
        add(3,f"placement_{i:02}",rows,[width,height,x,y,field6]+terrain+occupied)
    # Exact54ebe destination decision; intercept the same-actor UI branch
    # BEFORE its command-mask call. Other accepted paths run to real return.
    for i in range(128):
        rows=defaults();actor=i%2
        a=rows[actor];a[10]=1;a[11]=i%2;a[12:14]=[2,2];a[4:6]=[0,1]
        destination=[2,2] if i%9==0 else [3,2]
        for t in range(2,7):
            r=rows[t];r[0]=rng.randrange(2);r[10]=rng.randrange(2);r[11]=rng.randrange(2)
            r[12:14]=rng.choice([[3,2],[3,2],[4,2]])
            r[14:16]=rng.choice([[0,0],[0,0],[7,0],[0,-2]])
            r[6:8]=[rng.choice([0,1,2,255]) for _ in range(2)]
        if i%7==0: a[4:6]=[2,255]
        add(4,f"destination_{i:03}",rows,[actor,*destination,int(i%11==0),int(i%5!=0)])
    # Actual boarding mutation: offsets do NOT exclude carriers here. Multiple
    # carriers prove repeated wrapping counts; preserve all actor bytes exceptd.
    for i in range(128):
        rows=defaults();actor=i%2
        a=rows[actor];a[10]=1;a[11]=i%2;a[12:14]=[129 if i>=120 else 2,2]
        a[4:6]=[rng.choice([0,1,2,128,255]),rng.choice([0,1,2,128,255])]
        a[16]=i%3
        for t in range(2,9):
            r=rows[t];r[0]=a[0] if t%3 else 1-a[0]
            r[10]=int(t<6 or rng.randrange(2));r[11]=rng.randrange(2)
            r[12:14]=a[12:14] if t<6 else [5,5]
            r[14:16]=[7,-9] if t%2 else [0,0]
            r[6:8]=[rng.choice([0,1,2,128,255]) for _ in range(2)]
            r[8:10]=[rng.randrange(2),rng.randrange(2)]
        owner_slots=[t for t,r in enumerate(rows) if r[0]==a[0]]
        slot=[-1,owner_slots.index(actor),len(owner_slots)-1][i%3]
        add(5,f"arrival_{i:03}",rows,[actor,[0,1,2,17,255][i%5],slot])
    # Full human55f8c commit, independently of its earlier menu guard. Inputs
    # are valid admitted ordinary/deploy cases, including signed negative cost.
    for i in range(96):
        rows=defaults();producer=0;new_type=2 if i%3 else 21;mode=i%2
        rows[new_type][0]=0
        rows[producer][10]=1;rows[producer][12:14]=[129 if i>=56 else 2,1]
        rows[producer][8:10]=[1,1] if mode==0 else [0,0]
        rows[producer][6:8]=[1,1] if mode else [0,0]
        rows[new_type][4:6]=[1,1] if mode else [0,0]
        rows[new_type][1]=[0,1,127,128,255][i%5]
        rows[new_type][11]=1;rows[new_type][16]=1;rows[new_type][17]=7
        width,height=(255,3) if i>=56 else (5,3)
        px,py=rows[producer][12:14];dx,dy=px+1,py
        funds=([0,40,127,2147483647] if i<64 else [-3,0,1,7])[i%4]
        cost=40 if new_type==21 else signed(rows[new_type][1],8)
        if i<64 and funds<cost:funds=cost
        add(6,f"human_commit_{i:02}",rows,
            [producer,new_type,mode,width,height,dx,dy,funds,[0,17,255][i%3],int(i>=64)])
    for i in range(96):
        rows=defaults();actor=[0,1,21][i%3];mode=(i//3)%2
        for r in rows:
            r[4:10]=[rng.choice([0,0,1,2,255]) for _ in range(6)]
            r[10]=int(rng.randrange(5)==0);r[11]=rng.randrange(2);r[18]=rng.randrange(2)
        r=rows[actor];r[10]=int(i%11!=0);r[12:14]=[2,2];r[16]=int(i%13==0)
        r[17]=[0,24,25][i%3];r[2:4]=[rng.choice([0,1,128,255]) for _ in range(2)]
        if i>=84:
            actor=21;mode=0;r=rows[actor];r[10]=1;r[11]=1;r[16]=0;r[17]=0
            r[12:14]=[2,2];r[8:10]=[0,1];r[1]=8
            rows[1][18]=1;rows[1][10]=0;rows[1][4:6]=[0,0]
            funds=[39,40,41][i%3]
        else:funds=[-1,0,7,8,39,40,41,127][i%8]
        terrain=[rng.choice([0,1,4,99,255]) for _ in range(25)]
        if i>=84:terrain=[1]*25
        add(7,f"command_admission_{i:02}",rows,[actor,mode,5,5,funds]+terrain)
    for t in (0,21,22):
        for raw in (0,1,127,128,255):
            for funds in (-129,-128,-2,-1,0,1,39,40,41,126,127,2147483647):
                rows=defaults();rows[t][1]=raw
                add(8,f"menu_cost_t{t}_r{raw}_f{funds}",rows,[t,funds])
    for mode in (0,1):
        for t in (2,6,19,21):
            rows=defaults()
            add(9,f"direct_callback_mode{mode}_type{t}",rows,[t,mode,-3])
    return cases


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--image",type=Path,required=True)
    p.add_argument("--support",type=Path,required=True)
    p.add_argument("--movement-support",type=Path,required=True)
    p.add_argument("--unicorn-dir",type=Path,required=True)
    p.add_argument("--archive",type=Path,help="optional audited local archive for real static-link data")
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.unicorn_dir))
    import unicorn
    from unicorn import arm_const as ar
    image=a.image.read_bytes()
    if sha(image)!=IMAGE_SHA256 or sha(a.support.read_bytes())!=SUPPORT_SHA256:
        raise SystemExit("Original/support hash mismatch")
    def load(name,path):
        spec=importlib.util.spec_from_file_location(name,path)
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
    support=load("world_reference",a.support)
    movement=load("movement_reference",a.movement_support)

    class Reference(support.Reference):
        def __init__(self,rows):
            self.events=[];self.matches=[];self.special_stop=None;self.alternate_stops=set()
            super().__init__(image,definitions(rows),b"")
            self.owners([0,1]);self.w32(self.map+0x54,23)
            self.rows=rows
            for t,r in enumerate(rows):
                unit=self.units[t]
                for off,value in {0xc:r[11],0xd:r[10],0x3b:r[12],0x3c:r[13],
                                  0x2c:r[16],0x1a:r[17],0x18:1,0x19:1,0x2d:3,
                                  0x2e:171,0x2f:4,0x38:5,0x39:6,0x3a:7,
                                  0x48:9,0x49:8,0x4a:2,0x4b:3,0x59:99,0x5a:31}.items():
                    self.w8(unit+off,value)
                for off,value in {0x40:r[14],0x44:r[15],0x24:12,0x28:34,0x30:1234,
                                  0x34:t*7-20,0x5c:t*3-10}.items():self.w32(unit+off,value)
                for off,value in {0x1c:31,0x1e:42,0x20:53}.items():
                    self.u.mem_write(unit+off,struct.pack("<h",value))
            self.vector(self.map+0x24c,self.array([r[18] for r in rows],"B"),23)
            self.candidates_data=self.alloc(23*4);self.w32(self.map+0x114,self.candidates_data)
            self.slot_data=self.array([-1,-1],"i");self.vector(self.map+0x34,self.slot_data,2)
            self.count_data=self.array([17,17],"B");self.vector(self.map+0x7c,self.count_data,2)
            self.status_data=self.array([123+t for t in range(23)],"i")
            self.vector(self.map+0x1a4,self.status_data,23)
            self.strings=self.alloc(23*8);self.vector(self.map+0x1ac,self.strings,23)
            self.renderer=self.alloc(8);self.controller=self.alloc(8)
            self.w32(self.map+0x298,self.renderer);self.w32(self.map+0x29c,self.controller)
            self.vector(self.map+0x98,self.array([0,0],"B"),2)
            self.funds=self.array([0,0],"i");self.vector(self.map+0x58,self.funds,2)
            self.vector(self.map+0x60,self.alloc(16),2)
            self.vector(self.map+0x14c,self.array([r[1] for r in rows],"B"),23)
            self.w32(self.sp+0xf0,21);self.w32(self.sp+0x4c,self.map+0x14c)
            self.start(0x5a8ce,[],end=0x5a8e0) # Actual original type21 cost override.

        def hook(self,u,address,size,unused):
            if address==self.special_stop or address in self.alternate_stops or (self.special_stop==0x59946 and address==0x5994c):
                u.emu_stop();return
            if address==0x59910:
                carrier=u.reg_read(ar.UC_ARM_REG_R4)
                self.matches.append(self.r8(carrier+9))
            if address in (0x60800,0x60b70,0x5ca7e,0x2ad12,0x5cc64,0x54f94,
                           0x5c9b2,0x60918,0x5c9a4):
                r0,r1,r2=[u.reg_read(reg) for reg in
                          (ar.UC_ARM_REG_R0,ar.UC_ARM_REG_R1,ar.UC_ARM_REG_R2)]
                self.boundaries[hex(address)]+=1
                if address==0x5ca7e:self.events.append([1,r1])
                elif address==0x2ad12:self.events.append([2,r1,r2])
                elif address==0x5cc64:self.events.append([3,r1])
                elif address==0x54f94:self.events.append([4])
                elif address==0x5c9b2:self.events.append([5,r1])
                elif address==0x60918:
                    assert r1==0
                    self.events.append([6,(r0-self.strings)//8])
                elif address==0x5c9a4:self.events.append([7,self.r8(r1+9)])
                elif address==0x60b70:self.events.append([8,signed(r1)])
                u.reg_write(ar.UC_ARM_REG_PC,u.reg_read(ar.UC_ARM_REG_LR));return
            super().hook(u,address,size,unused)

        def fragment(self,entry,stop,registers,stack=None,alternate=()):
            for reg in (ar.UC_ARM_REG_R0,ar.UC_ARM_REG_R1,ar.UC_ARM_REG_R2,ar.UC_ARM_REG_R3,
                        ar.UC_ARM_REG_R4,ar.UC_ARM_REG_R5,ar.UC_ARM_REG_R6,ar.UC_ARM_REG_R7,
                        ar.UC_ARM_REG_R8,ar.UC_ARM_REG_R9,ar.UC_ARM_REG_R10,ar.UC_ARM_REG_R11,
                        ar.UC_ARM_REG_R12):self.u.reg_write(reg,0)
            self.u.reg_write(ar.UC_ARM_REG_CPSR,0x30)
            self.u.reg_write(ar.UC_ARM_REG_SP,self.sp)
            self.u.reg_write(ar.UC_ARM_REG_LR,self.return_address|1)
            for reg,value in registers.items():self.u.reg_write(reg,value)
            for offset,value in (stack or {}).items():self.w32(self.sp+offset,value)
            self.special_stop=stop
            self.alternate_stops=set(alternate)
            self.u.emu_start(entry|1,self.return_address,timeout=3_000_000,count=2_000_000)
            pc=self.u.reg_read(ar.UC_ARM_REG_PC)
            if pc not in {stop,0x5994c if stop==0x59946 else stop,*alternate}:
                raise RuntimeError(f"Fragment{entry:#x} stopped unexpectedly at{pc:#x}")
            self.special_stop=None
            self.alternate_stops=set()

        def terrain(self,width,height,costs=None):
            self.w8(self.map+0x15,width);self.w8(self.map+0x16,height)
            costs=costs if costs is not None else [1]*(width*height)
            unique=sorted(set(costs));ids=[unique.index(cost) for cost in costs]
            self.vector(self.map+0x18,self.array(ids,"B"),len(ids))
            self.vector(self.map+0x20,self.array(list(range(len(unique))),"B"),len(unique))
            inner=self.alloc(8*len(unique))
            for i,cost in enumerate(unique):self.vector(inner+8*i,self.array([cost,0,0],"B"),3)
            outer=self.alloc(8);self.vector(outer,inner,len(unique));self.w32(self.map+0x294,outer)
            grid=self.alloc(width*8)
            for x in range(width):self.vector(grid+8*x,self.array([-1]*height,"i"),height)
            self.vector(self.map+0xb4,grid,width)

        def selected(self,actor):self.w32(self.map+0x3cc,self.units[actor])

        def unit_output(self,t):
            u=self.units[t];rb=lambda off:self.r8(u+off);ri=lambda off:signed(self.r32(u+off))
            rh=lambda off:struct.unpack("<h",self.u.mem_read(u+off,2))[0]
            return [rb(0xd),rb(0xc),rb(0x3b),rb(0x3c),ri(0x40),ri(0x44),rb(0x4b),
                    rb(0x59),ri(0x30),rb(0x48),rb(0x49),rb(0x4a),rb(0x2c),rb(0x2d),
                    rb(0x2f),rb(0x38),rb(0x39),rb(0x3a),rb(0x5a),rb(0x1a),rb(0x19),
                    rh(0x1c),rh(0x1e),rh(0x20),ri(0x5c),ri(0x34)]

    cases=make_cases();source_data=None
    if a.archive:
        archive=a.archive.read_bytes()
        if sha(archive)!=support.ARCHIVE_SHA256:raise SystemExit("Original archive hash mismatch")
        ids=[292,294,290,302,291,283,285,295,305,301,288,284,287,299,304,300,293,289,303,286,296,297,298]
        rows=defaults();hashes={}
        for t,resource_id in enumerate(ids):
            raw=support.resource(archive,resource_id);hashes[str(resource_id)]=sha(raw)
            definition=support.decode_definition(raw,t,resource_id);forms=definition["forms"]
            rows[t][:10]=[definition["scalar_fields"][0],definition["scalar_fields"][1],
                         forms[0][6],forms[1][6],forms[0][8],forms[1][8],
                         forms[0][9],forms[1][9],forms[0][12],forms[1][12]]
        cases.append({"kind":1,"name":"actual_source_static_links","rows":rows,"parameters":[]})
        source_data={"archive_sha256":sha(archive),"resource_sha256":hashes}
    results=[];boundaries=collections.Counter();coverage=collections.Counter()
    for n,c in enumerate(cases):
        k,rows,pms=c["kind"],c["rows"],c["parameters"]
        ref=None
        if k==3:
            w,h,x,y,f6=pms[:5];size=w*h;cost=pms[5:5+size];occ=pms[5+size:]
            case={"width":w,"height":h,"unit":{"type":0,"owner":0,"x":x,"y":y,
                  "base_budget":3,"spent_budget":0,"field6":f6,"form":0},
                  "terrain":[[v,0] for v in cost],"active_owners":[None if v<0 else v for v in occ],
                  "points":[[x,y,1]],"rectangles":[[0,0,w,h]]}
            old=movement.OriginalMovement(image,case)
            any_vacant=old.call(0x4a678,[old.map,old.unit])
            old.write32(old.map+0x3cc,old.unit)
            direction_data=old.array([0,0,0,0],1)
            old.vector_at(old.map+0xe4,direction_data,4)
            old.call(0x499c8,[old.map])
            grid=[struct.unpack("<"+"i"*h,old.uc.mem_read(ptr,h*4)) for ptr in old.grid_columns]
            directions=list(old.uc.mem_read(direction_data,4))
            cursor=signed(struct.unpack("<I",old.uc.mem_read(old.map+0xec,4))[0])
            out=[int(bool(any_vacant)),cursor]+directions+[grid[cx][cy] for cy in range(h) for cx in range(w)]
            assert bytes(old.uc.mem_read(0x1000,0xd1000))==old.original_text
        else:
            ref=Reference(rows)
            if k==1:
                ref.fragment(0x5417a,0x54238,{ar.UC_ARM_REG_R8:ref.map})
                inverse={ptr:t for t,ptr in enumerate(ref.units)}
                out=[inverse.get(ref.r32(u+off),-1) for u in ref.units for off in (0x10,0x14)]
            elif k==2:
                owner,mode=pms;ref.start(0x50116,[ref.map,owner,mode])
                count=ref.r8(ref.map+0x110)
                values=[ref.r8(ref.r32(ref.candidates_data+4*i)+9) for i in range(count)]
                out=[count]+values+[-1]*(23-count)
                assert all(ref.r32(ref.candidates_data+4*i)==0 for i in range(count,23))
            elif k==4:
                actor,x,y,moving,route=pms;ref.selected(actor)
                ref.w8(ref.units[actor]+8,moving);ref.w32(ref.map+0x2c0,x);ref.w32(ref.map+0x2c4,y)
                path=ref.alloc(8);ref.vector(path,ref.array([0 if route else -1,0],"i"),2)
                ref.vector(ref.map+0xc8,path,1)
                ref.special_stop=0x54ef8
                try:ref.start(0x54ebe,[ref.map])
                except RuntimeError as error:
                    if ref.u.reg_read(ar.UC_ARM_REG_PC)!=0x54ef8:raise error
                selected=int(ref.u.reg_read(ar.UC_ARM_REG_PC)==0x54ef8)
                out=[ref.r8(ref.map+0xe0),selected,len(ref.events)]
                assert ref.events in ([],[[7,actor]])
            elif k==5:
                actor,count,slot=pms;owner=rows[actor][0]
                ref.w8(ref.count_data+owner,count);ref.w32(ref.slot_data+4*owner,slot)
                before=bytes(ref.u.mem_read(ref.units[actor],0x80))
                ref.fragment(0x59884,0x59946,{ar.UC_ARM_REG_R6:ref.map,ar.UC_ARM_REG_R8:ref.units[actor]})
                after=bytes(ref.u.mem_read(ref.units[actor],0x80))
                assert all(before[i]==after[i] for i in range(0x80) if i!=0xd)
                assert ref.events==[[value,actor] for _ in ref.matches for value in (5,6)]
                out=[ref.r8(ref.units[actor]+0xd),ref.r8(ref.count_data+owner),
                     signed(ref.r32(ref.slot_data+owner*4)),signed(ref.r32(ref.status_data+actor*4)),
                     len(ref.matches)]+ref.matches+[-1]*(23-len(ref.matches))
            elif k==6:
                producer,t,mode,w,h,x,y,funds,count,path=pms;owner=rows[producer][0]
                ref.selected(producer);ref.terrain(w,h);ref.w8(ref.map+0xa8,owner)
                ref.w32(ref.map+0x120,t);ref.w32(ref.map+0x2c0,x);ref.w32(ref.map+0x2c4,y)
                ref.vector(ref.map+0x3d8,ref.array(rows[producer][12:14],"B"),2)
                ref.w32(ref.map+0x3d0,mode)
                for i in range(4):ref.w8(ref.map+0xc4+i,11+i)
                ref.w8(ref.map+0x2d2,1)
                ref.w32(ref.funds+owner*4,funds);ref.w8(ref.count_data+owner,count)
                ref.active_boundaries={0xba288};ref.start(0x55f8c,[ref.map])
                out=ref.unit_output(t)+[ref.r8(ref.units[producer]+0x2c),
                    signed(ref.r32(ref.funds+4*owner)),ref.r8(ref.count_data+owner),
                    signed(ref.r32(ref.map+0x120)),signed(ref.r32(ref.map+0x3d0)),
                    *[ref.r8(ref.map+0xc4+i) for i in range(4)],
                    *[ref.r32(ref.map+off) for off in (0x2c0,0x2c4,0x2c8,0x2cc)],ref.r8(ref.map+0x2d2)]
                assert ref.events==[[8,out[27]],[1,t],[2,5,16],[3,0],[4]],ref.events
                assert ref.r8(ref.units[t]+0x2e)==171
                assert ref.r32(ref.units[t]+0x24)==0xffffffff
            elif k==7:
                actor,mode,w,h,funds=pms[:5];owner=rows[actor][0]
                ref.terrain(w,h,pms[5:]);ref.w32(ref.funds+4*owner,funds)
                # Stop the actual common/ordinary command prefix before attack,
                # or before the ordinary branch when testing independent deploy.
                stop=0x5305e if mode==0 else 0x530ca
                ref.special_stop=stop
                try:ref.start(0x5300e,[ref.map,ref.units[actor]])
                except RuntimeError as error:
                    if ref.u.reg_read(ar.UC_ARM_REG_PC)!=stop:raise error
                arrived=ref.u.reg_read(ar.UC_ARM_REG_PC)==stop;ref.special_stop=None
                if mode==0:allowed=arrived and bool(ref.u.reg_read(ar.UC_ARM_REG_R6)&4)
                elif arrived:
                    ref.start(0x501f2,[ref.map,ref.units[actor]])
                    allowed=bool(ref.u.reg_read(ar.UC_ARM_REG_R0))
                else:allowed=False
                out=[int(allowed)]
            elif k==8:
                t,funds=pms;owner=rows[t][0]
                ref.w32(ref.funds+4*owner,funds)
                slots=[u for u in ref.units if ref.r8(u+0xa)==owner]
                slot=slots.index(ref.units[t])
                ref.fragment(0x555b0,0x555d6,{ar.UC_ARM_REG_R0:ref.map+0x58,
                    ar.UC_ARM_REG_R1:owner,ar.UC_ARM_REG_R2:ref.owner_arrays[owner],
                    ar.UC_ARM_REG_R3:slot*4},{0x18:ref.map},alternate=(0x555f8,))
                out=[int(ref.u.reg_read(ar.UC_ARM_REG_PC)==0x555d6),
                     signed(ref.u.reg_read(ar.UC_ARM_REG_R2))]
            elif k==9:
                t,mode,funds=pms
                self_object=ref.alloc(0x50);ref.w32(self_object+0x48,ref.map)
                ref.w32(ref.funds,funds);ref.w32(ref.funds+4,funds)
                ref.fragment(0x462aa,0x462de,{},
                             {0x18:mode,0x1c:t,0xc:self_object})
                out=[ref.r32(ref.map+0x120),ref.u.reg_read(ar.UC_ARM_REG_R1),
                     signed(ref.r32(ref.funds)),signed(ref.r32(ref.funds+4))]
            else:raise RuntimeError("Unknown case kind")
            assert bytes(ref.u.mem_read(0x1000,0xd1000))==ref.text
            boundaries.update(ref.boundaries)
        results.append(out);coverage[str(k)]+=1
        if (n+1)%100==0:print(f"Executed {n+1}/{len(cases)} original cases",flush=True)
    a.output.mkdir(parents=True,exist_ok=True)
    fixture_count=sum(c["kind"]!=9 for c in cases)
    lines=[f"G1UNITINTERACTIONS1 {fixture_count}"]
    for c,out in zip(cases,results):
        if c["kind"]==9:continue # Callback dispatch is provenance, not native legacy-UI code.
        inputs=c["parameters"]+[v for row in c["rows"] for v in row]
        lines += [f'{c["kind"]} {c["name"]} {len(c["parameters"])} {len(inputs)} {len(out)}',
                  " ".join(map(str,inputs))," ".join(map(str,out))]
    fixture=("\n".join(lines)+"\n").encode()
    (a.output/"unit_interactions_original_vectors.txt").write_bytes(fixture)
    report={"status":"original_reference_executed","cases":len(cases),"fixture_cases":fixture_count,
        "coverage_by_kind":dict(coverage),
        "original_sha256":IMAGE_SHA256,"support_sha256":SUPPORT_SHA256,
        "movement_support_sha256":sha(a.movement_support.read_bytes()),"oracle_sha256":sha(Path(__file__).read_bytes()),
        "fixture_sha256":sha(fixture),"unicorn_version":unicorn.__version__,
        "instruction_patches":0,"original_text_readonly_unchanged":True,
        "kind_mapping":{"1":"static links5417a..54238","2":"complete candidates50116",
            "3":"complete adjacency4a678 and human direction499c8","4":"54ebe with same-actor UI boundary54ef8",
            "5":"transport arrival59884..59946/5994c","6":"complete human commit55f8c",
            "7":"5300e common/ordinary prefix plus independent complete501f2 deploy",
            "8":"original menu funds comparison555b0..555d6/555f8",
            "9":"direct selected-name callback462aa..462de before UI dispatch"},
        "additional_original_fragment":"5a8ce..5a8e0 actual type21 cost-table override",
        "reference_only_callback_cases":[{"name":c["name"],"parameters":c["parameters"],"result":out}
            for c,out in zip(cases,results) if c["kind"]==9],
        "external_boundaries":dict(boundaries),
        "boundary_meanings":{"0xba288":"exact signed division",
            "0x60800":"funds string clear","0x60b70":"funds number output recorded",
            "0x5ca7e":"spawn renderer notification recorded","0x2ad12":"audio request recorded",
            "0x5cc64":"selection visibility renderer request recorded",
            "0x54f94":"post-commit cursor/menu presentation refresh, not executed",
            "0x5c9b2":"deactivate renderer type recorded","0x60918":"status string clear recorded",
            "0x5c9a4":"movement follow renderer request recorded"},
        "input_fields_per_type":FIELDS,
        "scope_limits":["Synthetic data states; no original assets/binary included in generated fixture.",
            "No graphics/audio/UI execution or device gameplay claim.",
            "Native comparison is performed by the separately compiled native test.",
            "Full post-arrival phase controller and same-actor command UI are outside these reference slices."]}
    if source_data:
        source_data["actual_links"]={str(t):{"field10":values[0],"field14":values[1]}
            for t in range(23) if (values:=results[-1][2*t:2*t+2])!=[-1,-1]}
        report["source_data_static_links"]=source_data
    (a.output/"original_unit_interactions_reference.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"cases":len(cases),"coverage":dict(coverage),"fixture_sha256":sha(fixture)}))


if __name__=="__main__":main()
