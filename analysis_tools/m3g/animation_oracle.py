#!/usr/bin/env python3
"""Development-only original rigid-animation sampling oracle.

Executes original sampler 0x9346c and original controller/math instructions on
explicitly supplied local data. No binary, emulator or game asset is shipped.
Audited ARMv6 libgcc imports execute unchanged. The original platform sqrtf
and sinf boundaries use host libm rounded to binary32 and are reported.
"""
import argparse
from collections import Counter
import ctypes
import ctypes.util
import hashlib
import json
from pathlib import Path
import struct
import sys


def f32bits(value):
    return struct.unpack('<I', struct.pack('<f', value))[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--binary', type=Path, required=True)
    ap.add_argument('--libgcc', type=Path, required=True)
    ap.add_argument('--bindings', type=Path, required=True)
    ap.add_argument('--model', type=Path, required=True)
    ap.add_argument('--unicorn-dir', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()
    sys.path.insert(0, str(args.unicorn_dir))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'sprite'))
    import reference
    import render_oracle as base
    original, gcc = args.binary.read_bytes(), args.libgcc.read_bytes()
    if hashlib.sha256(original).hexdigest() != base.IMAGE_SHA or hashlib.sha256(gcc).hexdigest() != base.LIBGCC_SHA:
        raise ValueError('original instruction input differs from audited revision')
    bindings = json.loads(args.bindings.read_text())
    base.MATH = {x['address']: x['symbol'] for x in bindings
                 if x['address'] < 0xd2000 and (x['symbol'].endswith('vfp') or x['symbol'] in
                     ('___modsi3', '___divsi3', '___divdi3', '___muldi3', '___floatdidf', '___floatdisf',
                      '___udivdi3', '___udivsi3', '___umodsi3'))}

    class OriginalAnimation(base.OriginalRenderer):
        def __init__(self, image, gcc):
            super().__init__(image,gcc)
            self.libm=ctypes.CDLL(ctypes.util.find_library('m'))
            for name in ('sqrtf','sinf'):
                function=getattr(self.libm,name)
                function.argtypes=[ctypes.c_float];function.restype=ctypes.c_float
            # Integer64 helpers reference libgcc's local lookup tables through
            # non-lazy symbol pointers. Apply their declared LOCAL rebases;
            # instruction bytes remain unchanged. The earlier float-only
            # renderer oracle did not need these data bindings.
            sections=[];cursor=28
            for unused in range(struct.unpack_from('<I',self.thin,16)[0]):
                command,length=struct.unpack_from('<II',self.thin,cursor)
                if command==1:
                    for n in range(struct.unpack_from('<I',self.thin,cursor+48)[0]):
                        sections.append(struct.unpack_from('<16s16s9I',self.thin,cursor+56+n*68))
                elif command==11:
                    indirect_offset,indirect_count=struct.unpack_from('<II',self.thin,cursor+56)
                cursor+=length
            self.local_rebases=[]
            for section in sections:
                if section[8]&255!=6:
                    continue
                for index in range(section[3]//4):
                    indirect=section[9]+index
                    if indirect>=indirect_count:raise ValueError('libgcc indirect table bounds')
                    symbol=struct.unpack_from('<I',self.thin,indirect_offset+indirect*4)[0]
                    if symbol!=0x80000000:continue
                    address=section[2]+index*4
                    value=self.read_word(0x40000000+address)
                    if value>=0x9000:raise ValueError('unexpected local libgcc table binding')
                    self.word(0x40000000+address,0x40000000+value)
                    self.local_rebases.append({'offset':address,'target':value})

        def hook(self, instance, address, size, user):
            if address == 0xb1bc6:
                raise RuntimeError('original animation rejected seeded state')
            if address in (0xbab58,0xbab40):
                raw=instance.reg_read(self.ar.UC_ARM_REG_R0)
                value=struct.unpack('<f',struct.pack('<I',raw))[0]
                function=self.libm.sqrtf if address==0xbab58 else self.libm.sinf
                instance.reg_write(self.ar.UC_ARM_REG_R0,f32bits(function(value)))
                instance.reg_write(self.ar.UC_ARM_REG_PC,instance.reg_read(self.ar.UC_ARM_REG_LR))
                self.calls['platform_'+('sqrtf' if address==0xbab58 else 'sinf')+'_host_boundary']+=1
                return
            if 0xba000 <= address < 0xbb000 and address not in self.math:
                raise RuntimeError(f'unexpected external call {address:#x}; no math substitute supplied')
            super().hook(instance, address, size, user)

        def seed(self, sequence):
            seq, controller, track = self.alloc(0x60), self.alloc(0x40), self.alloc(0x30)
            values = self.alloc(len(sequence['keyframes'])*(1+sequence['components'])*4)
            for offset, value in ((0x20, sequence['interpolation']), (0x24, sequence['repeat_mode']),
                                  (0x28, f32bits(sequence['duration'])), (0x2c, sequence['duration']),
                                  (0x30, sequence['first']), (0x34, sequence['last']),
                                  (0x38, sequence['components']), (0x3c, len(sequence['keyframes'])),
                                  (0x44, values), (0x50, 0)):
                self.word(seq+offset, value)
            for n, (time, raw) in enumerate(sequence['keyframes']):
                data = raw
                if sequence['encoding']:
                    maximum = 255 if sequence['encoding'] == 1 else 65535
                    data = [sequence['bias'][i]+sequence['scale'][i]*v/maximum for i, v in enumerate(raw)]
                self.u.mem_write(values+n*(sequence['components']+1)*4, struct.pack('<I'+'f'*len(data), time, *data))
            for offset, value in ((0x20, 0), (0x24, 0), (0x28, f32bits(0)), (0x2c, 0),
                                  (0x30, f32bits(1)), (0x34, f32bits(1))):
                self.word(controller+offset, value)
            self.word(track+0x24, controller)
            return seq, controller, track

        def sample(self, handles, components, time, speed=1.0, reference_sequence=0.0, reference_world=0, weight=1.0):
            seq, controller, track = handles
            self.word(controller+0x28, f32bits(reference_sequence)); self.word(controller+0x2c, reference_world)
            self.word(controller+0x30, f32bits(speed))
            out = self.alloc(components*4)
            self.u.mem_write(out, bytes(components*4))
            self.call(0x9346c, [seq, time, track, components, out, f32bits(weight)])
            return list(struct.unpack('<'+'f'*components, self.u.mem_read(out, components*4)))

        def normalize_orientation(self,value):
            out=self.alloc(16);self.u.mem_write(out,struct.pack('<4f',*value))
            self.call(0x9f03c,[out])
            return list(struct.unpack('<4f',self.u.mem_read(out,16)))

    obj = reference.parse(args.model.read_bytes())
    selected = [x for x in obj[1:] if x['type'] == 19]
    records, handles_by_sequence = [], {}
    oracle = OriginalAnimation(original, gcc)
    for sequence in selected:
        if sequence['interpolation'] not in (176, 177, 180):
            raise ValueError('oracle seed layout intentionally excludes spline auxiliary storage')
        handles = oracle.seed(sequence)
        handles_by_sequence[sequence['index']]=handles
        times = sorted({-1, 0, 1, sequence['duration']-1, sequence['duration'], sequence['duration']+1,
                        *[t for t, v in sequence['keyframes']],
                        *[(a[0]+b[0])//2 for a, b in zip(sequence['keyframes'], sequence['keyframes'][1:])]})
        if args.limit:
            times = times[:args.limit]
        for time in times:
            value = oracle.sample(handles, sequence['components'], time)
            records.append({'sequence':sequence['index'], 'world_time':time, 'value':value})
    poses=[]
    for time in (0,1,166,500,1000,11666):
        properties=[]
        for target in obj[1:]:
            for track_index in target.get('animation_tracks',[]):
                sequence_index,controller_index,prop=obj[track_index]['track']
                if obj[controller_index]['controller']!=[1.,1.,0,0,0.,0]:
                    raise ValueError('pose probe requires the observed default shared controller')
                sequence=obj[sequence_index]
                value=oracle.sample(handles_by_sequence[sequence_index],sequence['components'],time)
                if prop==268:value=oracle.normalize_orientation(value)
                properties.append({'target':target['index'],'property':prop,'value':value})
        poses.append({'world_time':time,'properties':properties})
    controller_cases=[(0,1,0,0,0),(1,1,0,0,0),(100,0,12,20,0),(24,-.5,12,20,0),
                      (100000001,1,0,0,100),(100000001,2,3,0,100),(100000001,.25,-2,19,100),
                      (100000001,-.5,0,23,100),(-100000001,1,5,0,100),
                      (-100000001,-2.5,100,-999,100),(1234,1.25,4.5,200,0),(0,1,0,100000001,100)]
    controller_records=[]
    controller=oracle.alloc(0x40)
    for world,speed,reference_sequence,reference_world,duration in controller_cases:
        oracle.word(controller+0x28,f32bits(reference_sequence));oracle.word(controller+0x2c,reference_world)
        oracle.word(controller+0x30,f32bits(speed))
        oracle.call(0x88d44 if duration else 0x88d0c,[controller,world,duration])
        result=struct.unpack('<f',struct.pack('<I',oracle.u.reg_read(oracle.ar.UC_ARM_REG_R0)))[0]
        controller_records.append({'world':world,'speed':speed,'reference_sequence':reference_sequence,
                                   'reference_world':reference_world,'loop_duration':duration,'position':result})
    # Independent synthetic two-track contributions: the original sampler
    # adds each weighted value into the SAME output buffer. This exercises
    # sums below/above1, not merely the actual model's unit-weight tracks.
    weighted_records=[]
    for prop in (275,268):
        values=([[[0,0,0],[10,20,30]],[[8,-4,1],[18,6,-9]]] if prop==275 else
                [[[0,0,0,1],[0,0,.70710677,.70710677]],[[.70710677,0,0,.70710677],[0,1,0,0]]])
        components=3 if prop==275 else 4
        handles=[]
        for keys in values:
            handles.append(oracle.seed({'interpolation':176 if prop==275 else 177,'repeat_mode':192,
                'encoding':0,'duration':100,'first':0,'last':1,'components':components,
                'keyframes':[[0,keys[0]],[100,keys[1]]]}))
        for weights in ((.25,.75),(.2,.6),(2,.25)):
            weights=[struct.unpack('<f',struct.pack('<f',w))[0] for w in weights]
            for world in (0,25,50,99):
                out=oracle.alloc(components*4);oracle.u.mem_write(out,bytes(components*4))
                for handle,weight in zip(handles,weights):
                    seq,controller,track=handle
                    oracle.call(0x9346c,[seq,world,track,components,out,f32bits(weight)])
                value=list(struct.unpack('<'+'f'*components,oracle.u.mem_read(out,components*4)))
                if prop==268:value=oracle.normalize_orientation(value)
                weighted_records.append({'property':prop,'world_time':world,'weights':weights,'value':value})
    report = {'scope':'Original unchanged ARM sampler with real asset keyframes; development-only',
              'original_sha256':base.IMAGE_SHA, 'libgcc_sha256':base.LIBGCC_SHA,
              'model_sha256':hashlib.sha256(args.model.read_bytes()).hexdigest(),
              'original_function':'0x9346c', 'sequences':len(selected), 'samples':len(records),
              'local_libgcc_data_rebases':oracle.local_rebases,
              'host_math_boundary':'host libm sqrtf/sinf with float arguments/results; no historical libSystem bit-identity claim',
              'records':records, 'poses':poses, 'controller_cases':controller_records,
              'weighted_cases':weighted_records,'calls':dict(oracle.calls)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('records','poses','controller_cases','weighted_cases','calls')}, indent=2))


if __name__ == '__main__':
    main()
