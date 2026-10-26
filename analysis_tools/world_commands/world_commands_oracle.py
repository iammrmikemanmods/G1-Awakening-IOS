#!/usr/bin/env python3
"""Bounded original world-command/RNG reference, for development only."""
import argparse
import collections
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import struct

IMAGE_SHA256 = "0d510516fe3676ee4a0f4dff60ba64e1c5bf79a0c9800f420b1bbdb1c12febfd"
SUPPORT_SHA256 = "f0505848b34b88b6653cbb8ebe5f74fa8fd5394f4e1727fa93f0b3f2c18374ad"


def sha(data): return hashlib.sha256(data).hexdigest()
def s32(value): return value if value < 0x80000000 else value - 0x100000000


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image",type=Path,required=True)
    parser.add_argument("--support",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    image=args.image.read_bytes()
    if sha(image)!=IMAGE_SHA256 or sha(args.support.read_bytes())!=SUPPORT_SHA256:
        raise SystemExit("original image/reference support hash mismatch")
    spec=importlib.util.spec_from_file_location("mission_support",args.support)
    support=importlib.util.module_from_spec(spec);spec.loader.exec_module(support)

    class Reference(support.Reference):
        def __init__(self):
            super().__init__(image)
            self.outputs=[];self.draws=0;self.owner_rebuilds=0
            self.units=[self.alloc(0x80) for _ in range(23)]
            self.w32(self.map+0x90,self.array(self.units,"I"))
            self.w32(self.map+0x94,23);self.w8(self.map+0x130,23)
            self.definition_factions=self.array([i%2 for i in range(23)],"B")
            self.vector(self.map+0x144,self.definition_factions,23)
            self.owner_arrays=[self.array([0]*24,"I") for _ in range(2)]
            self.w32(self.map+0x84,self.array(self.owner_arrays,"I"))
            for i,unit in enumerate(self.units):
                self.w8(unit+9,i);self.w8(unit+0xb,i%2)
            self.available=self.array([0]*23,"B")
            self.vector(self.map+0x24c,self.available,23)
            self.markers=[]
            for offset in (0x254,0x25c):
                data=self.array([97,98],"i");self.markers.append(data)
                self.vector(self.map+offset,data,2)
            self.renderer=self.alloc(8);self.w32(self.map+0x298,self.renderer)
            self.rng=self.alloc(0x9d4)
            self.w32(self.rng+0xc,0);self.w32(self.rng+0x10,0x9908b0df)
            self.w32(self.app+0x3e8,self.rng)

        def hook(self,u,address,size,unused):
            ar=self.ar
            if address==0x7b26:self.draws+=1
            if address==0x496e4:self.owner_rebuilds+=1
            if address in (0x5c8a8,0x5c680,0x5c9ec,0x6549a,0x5c9f8,0x2b46c,0xba36c,
                           0xba5dc,0xbaa14,0xbaa5c,0x301aa,0x608b2,0x604b4):
                self.boundaries[hex(address)]+=1
                a=[u.reg_read(r) for r in (ar.UC_ARM_REG_R0,ar.UC_ARM_REG_R1,ar.UC_ARM_REG_R2)]
                if address==0x5c8a8:
                    # Copy a word-vector at the storage boundary; no command
                    # decoding or state decision is supplied by this hook.
                    count=self.r32(a[1]+4);ptr=self.r32(a[1])
                    target=self.alloc(count*2)
                    if count:u.mem_write(target,bytes(u.mem_read(ptr,count*2)))
                    self.vector(a[0],target,count)
                elif address==0x5c680:pass # Dispose only the temporary marshaled vector.
                elif address==0x5c9ec:
                    assert a[0]==self.renderer
                    self.outputs.append(["renderer_mode",s32(a[1])])
                elif address==0x6549a:self.outputs.append(["marker_geometry",s32(a[0]),s32(a[1])])
                elif address==0x5c9f8:
                    assert a[0]==self.renderer
                    self.outputs.append(["points_renderer"])
                elif address==0x2b46c:u.reg_write(ar.UC_ARM_REG_R0,self.rng)
                elif address==0xba36c:
                    left,right=s32(a[0]),s32(a[1])
                    if right==0:raise RuntimeError("original modulo by zero")
                    quotient=abs(left)//abs(right)
                    if (left<0)!=(right<0):quotient=-quotient
                    u.reg_write(ar.UC_ARM_REG_R0,(left-quotient*right)&0xffffffff)
                elif address==0xba5dc:
                    # Original free: storage ownership only. The bounded
                    # monotonic arena is never recycled during this oracle.
                    if a[0] and not 0x1000000<=a[0]<self.next:
                        raise RuntimeError("original free outside reference heap")
                elif address==0xbaa14:
                    if a[0]>0x10000:raise RuntimeError("original allocation exceeds oracle bound")
                    u.reg_write(ar.UC_ARM_REG_R0,self.alloc(a[0]))
                elif address==0xbaa5c:
                    if a[2]>0x10000 or not 0x1000000<=a[0]<=a[0]+a[2]<=self.next:
                        raise RuntimeError("original memset outside reference heap")
                    if a[2]:u.mem_write(a[0],bytes([a[1]&255])*a[2])
                elif address==0x301aa:self.outputs.append(["title_resource",a[1]])
                elif address==0x608b2:
                    assert a[0]==self.map+0x1e4
                    self.outputs.append(["title_copy"])
                elif address==0x604b4:pass # Dispose only the external string.
                u.reg_write(ar.UC_ARM_REG_PC,u.reg_read(ar.UC_ARM_REG_LR))
                return
            super().hook(u,address,size,unused)

        def command(self,opcode,arguments,phase=99):
            entries=self.alloc(16)
            self.vector(entries,self.array([0],"H"),1)
            self.vector(entries+8,self.array([opcode,*arguments],"H"),len(arguments)+1)
            self.vector(self.map+0x214,entries,2)
            self.w32(self.map+0x21c,1);self.w32(self.map+0x1e0,phase)
            self.w32(self.sp+0x7c,self.map);self.outputs=[]

        def dispatch(self,opcode,arguments,phase=99):
            self.command(opcode,arguments,phase)
            self.run(0x560c0,stop=0x578e4)

    ref=Reference();rows=[];counts=collections.Counter()
    def row(tag,inputs,outputs):
        rows.append((tag,list(inputs),list(outputs)));counts[tag]+=1
    for stage,old in itertools.product((-2,0,1,3),(0,1)):
        ref.w32(ref.app+0x78,stage);ref.w8(ref.map+0x225,old)
        ref.dispatch(0,[])
        row("L",[stage,old],[ref.r32(ref.map+0x1e0),ref.r8(ref.map+0x225),s32(ref.r32(ref.app+0x78))])
    for title,stage in itertools.product((208,232,377),(-2,0,2,3)):
        ref.w32(ref.app+0x78,stage);ref.dispatch(16,[title])
        titles=[item[1] for item in ref.outputs if item[0]=="title_resource"]
        assert len(titles)==1 and ref.outputs[-1]==["title_copy"]
        row("T",[title,stage],[ref.r32(ref.map+0x1e0),s32(ref.r32(ref.app+0x78)),titles[0]])
    for opcode,old in itertools.product((13,14),(0,1)):
        ref.w8(ref.map+0x227,old);ref.dispatch(opcode,[])
        row("F",[opcode,old],[ref.r32(ref.map+0x1e0),ref.r8(ref.map+0x227)])
    for opcode,pair in itertools.product((18,19),((4,3),(0xffff,7),(0x7fff,0x8000),(0,0))):
        ref.dispatch(opcode,list(pair))
        slot=0 if opcode==18 else 1
        xy=[s32(ref.r32(ref.markers[slot]+i*4)) for i in range(2)]
        mode=[event[1] for event in ref.outputs if event[0]=="renderer_mode"]
        geometry=[event[1:] for event in ref.outputs if event[0]=="marker_geometry"]
        assert len(mode)==1 and (not geometry or geometry==[[1,1]])
        row("M",[opcode,*pair],[ref.r32(ref.map+0x1e0),*xy,*mode,len(geometry)])
    for unit_type,value in itertools.product((0,11,21,22),(0,1,0xffff)):
        ref.w8(ref.units[unit_type]+0x19,77);ref.dispatch(20,[unit_type,value])
        row("I",[unit_type,value],[ref.r32(ref.map+0x1e0),ref.r8(ref.units[unit_type]+0x19)])
    for group,index in ((0,0),(0,2),(1,0),(2,0)):
        ref.w8(ref.config+12,group);ref.w32(ref.config+8,index)
        for types in ([],[11],[0,22,11]):
            ref.u.mem_write(ref.available,b"\x01"*23)
            ref.dispatch(15,[len(types),*types])
            ref.available=ref.r32(ref.map+0x24c)
            row("A",[group,index,len(types),*types],
                [ref.r32(ref.map+0x1e0),*ref.u.mem_read(ref.available,23)])
    for points in ([],[(1,2,0)],[(1,3,1),(1,6,0)]):
        outer=ref.alloc(max(1,len(points))*8)
        for i in range(len(points)):
            ref.vector(outer+i*8,ref.array([77]*4,"i"),4)
        ref.vector(ref.map+0x420,outer,len(points))
        site_states=ref.array([-1,-1,-1],"b");ref.vector(ref.map+0x3e8,site_states,3)
        flat=[value for point in points for value in point]
        ref.dispatch(17,[len(points),*flat])
        outer=ref.r32(ref.map+0x420)
        output=[ref.r32(ref.map+0x1e0)]
        for i in range(len(points)):
            data=ref.r32(outer+i*8)
            output.extend(s32(ref.r32(data+j*4)) for j in range(4))
        output.extend(struct.unpack("<3b",ref.u.mem_read(site_states,3)))
        assert ref.outputs==[["points_renderer"]]
        row("P",[len(points),*flat],output)
    for number,phase in itertools.product((0,1,3),(17,99)):
        arguments=[number,*[i*117%65536 for i in range(number*4)]]
        ref.command(21,arguments,phase)
        before=bytes(ref.u.mem_read(ref.map,0x600));app_before=bytes(ref.u.mem_read(ref.app,0x500))
        ref.run(0x560c0,stop=0x578e4)
        assert before==bytes(ref.u.mem_read(ref.map,0x600))
        assert app_before==bytes(ref.u.mem_read(ref.app,0x500)) and not ref.outputs
        row("N",[phase,*arguments],[ref.r32(ref.map+0x1e0),0])
    for unit_type,old,inverted,swap in itertools.product((0,11,21,22),(0,1),(0,1),(0,1)):
        for i,u in enumerate(ref.units):ref.w8(u+0xb,i%2)
        ref.w8(ref.units[unit_type]+0xb,old)
        ref.u.mem_write(ref.factions,bytes([swap,1-swap]))
        ref.run(0x496e4,[ref.map]);ref.owner_rebuilds=0
        ref.w32(ref.sp+0x7c,ref.map);ref.w32(ref.sp+0xb8,inverted);ref.w32(ref.sp+0x114,unit_type)
        ref.run(0x566fa,stop=0x5674c)
        row("S",[unit_type,old,inverted,swap],
            [ref.r8(ref.units[unit_type]+0xb),ref.r8(ref.units[unit_type]+0xa),ref.owner_rebuilds])
    for seed,faction,mask_kind in itertools.product((0,1,42,0xffffffff,0x80000000,0x4741),(0,1),range(4)):
        remaining=22 if faction==0 else 21
        mask=(0,(1<<10)-1,((1<<23)-1)^(1<<remaining),sum(1<<i for i in range(0,23,3)))[mask_kind]
        for i,u in enumerate(ref.units):ref.w8(u+0xd,1 if mask&(1<<i) else 0)
        ref.run(0x7acc,[ref.rng,seed]);ref.draws=0
        for attempt in range(100000):
            selected=ref.run(0x4e53a,[ref.map,faction])
            if not ref.r8(ref.units[selected]+0xd):break
        else:raise RuntimeError("bounded original random retry did not terminate")
        output=[selected,ref.draws,ref.r32(ref.rng+8)]
        output.extend(ref.run(0x7b26,[ref.rng]) for _ in range(8))
        row("R",[seed,faction,mask],output)
    for style,a4 in itertools.product((0,1,2),(0,1)):
        ref.w32(ref.map+0x22c,style);ref.w8(ref.app+0xa4,a4)
        ref.run(0x4e7b8,[ref.map],allowed={0x2ad12})
        audio=[event[1:] for event in ref.events if event[0]=="audio"]
        row("U",[style,a4],[len(audio),*[value for event in audio for value in event]])
    args.output.mkdir(parents=True,exist_ok=True)
    fixture=(f"G1WORLDCOMMANDS1 {len(rows)}\n"+"".join(
        f"{tag} {len(a)} "+" ".join(map(str,a))+f" {len(b)} "+" ".join(map(str,b))+"\n"
        for tag,a,b in rows)).encode()
    (args.output/"world_commands_original_vectors.txt").write_bytes(fixture)
    report={"status":"passed","cases":len(rows),"kinds":dict(counts),"original_sha256":IMAGE_SHA256,
        "support_sha256":SUPPORT_SHA256,"oracle_sha256":sha(Path(__file__).read_bytes()),
        "fixture_sha256":sha(fixture),"external_boundaries":dict(ref.boundaries),
        "original_dispatch_body":"0x560c0..0x578e4, unchanged body with seeded frame",
        "other_original_entries":["0x496e4","0x566fa..0x5674c","0x4e53a","0x7acc","0x7b26","0x4e7b8"],
        "limits":["Command21 proved no map/app mutation in original body; not guessed as regions.",
                  "Vector copy/disposal hooks are storage-only; renderer notifications recorded.",
                  "malloc/free/memset imports implement bounded storage only; original vector resizing executes.",
                  "Title string construction/copy/disposal are recorded presentation boundaries; original text-index switch executes.",
                  "Shared RNG service lookup returns seeded original generator; original MT executes.",
                  "Signed modulo import supplied as exact arithmetic; no random words fabricated.",
                  "Site opcode7 and complete map I/O not executed by this oracle.",
                  "No original text/assets, native campaign playthrough, or Apple/device execution."]}
    (args.output/"original_world_commands_reference.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report))


if __name__=="__main__":main()
