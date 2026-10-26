#!/usr/bin/env python3
"""Compare native M3G samples to a development-only original-function record.

The independent hierarchy check applies original sampler/normalizer outputs
with double-precision TRSM matrices. It is not a GPU or battle timing test.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import struct
import subprocess

import reference
from validate import matrix, multiply


def f32(x):
    return struct.unpack('<f',struct.pack('<f',x))[0]


def posed_matrix(obj):
    if 'quaternion' not in obj:
        return matrix(obj)
    x,y,z,w=obj['quaternion']
    rotation=[1-2*(y*y+z*z),2*(x*y+z*w),2*(x*z-y*w),0,
              2*(x*y-z*w),1-2*(x*x+z*z),2*(y*z+x*w),0,
              2*(x*z+y*w),2*(y*z-x*w),1-2*(x*x+y*y),0,0,0,0,1]
    for column in range(3):
        for row in range(3):rotation[column*4+row]*=obj['scale'][column]
    rotation[12:15]=obj['translation']
    raw=obj['matrix_row_major']
    return multiply(rotation,[raw[row*4+column] for column in range(4) for row in range(4)])


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--model',type=Path,required=True)
    ap.add_argument('--original',type=Path,required=True)
    ap.add_argument('--native-probe',type=Path,required=True)
    ap.add_argument('--native-test',type=Path,required=True)
    ap.add_argument('--user-id',type=int,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    original=json.loads(args.original.read_text());data=args.model.read_bytes()
    digest=lambda b:hashlib.sha256(b).hexdigest()
    if digest(data)!=original['model_sha256']:raise ValueError('model/reference identity differs')
    test=subprocess.run([str(args.native_test.resolve())],check=True,capture_output=True,text=True,timeout=20)
    command=[str(args.native_probe.resolve()),str(args.model.resolve()),str(args.user_id)]
    run=subprocess.run(command,check=True,capture_output=True,text=True,timeout=30)
    native=json.loads(run.stdout)
    if len(native['records'])!=len(original['records']):raise ValueError('sample counts differ')
    scalar_count=bit_equal=0;maximum_error=0
    for expected,actual in zip(original['records'],native['records']):
        if (expected['sequence'],expected['world_time'])!=(actual['sequence'],actual['world_time']):
            raise ValueError('sample identity differs')
        if len(expected['value'])!=len(actual['value']):raise ValueError('sample components differ')
        for x,y in zip(expected['value'],actual['value']):
            x,y=f32(x),f32(y);error=abs(x-y)
            if not math.isfinite(error) or error>2e-6:raise ValueError('native/original animation sample differs')
            scalar_count+=1;bit_equal+=struct.pack('<f',x)==struct.pack('<f',y)
            maximum_error=max(maximum_error,error)
    objects=copy.deepcopy(reference.parse(data));parents={}
    for obj in objects[1:]:
        for child in obj.get('children',[]):parents[child]=obj['index']
    matrix_count=0;matrix_error=0
    if len(original['poses'])!=len(native['poses']):raise ValueError('pose count differs')
    for expected,actual in zip(original['poses'],native['poses']):
        if expected['world_time']!=actual['world_time']:raise ValueError('pose time differs')
        if len(expected['properties'])!=actual['properties']:raise ValueError('active property count differs')
        for prop in expected['properties']:
            obj=objects[prop['target']]
            field={268:'quaternion',270:'scale',275:'translation'}[prop['property']]
            obj[field]=prop['value']
        matrices={}
        def world(index):
            if index not in matrices:
                value=posed_matrix(objects[index])
                if index in parents:value=multiply(world(parents[index]),value)
                matrices[index]=value
            return matrices[index]
        for entry in actual['matrices']:
            value=world(entry['object'])
            for a,b in zip(entry['matrix'],value):
                error=abs(f32(a)-b)
                if not math.isfinite(error) or error>2e-5:raise ValueError('native posed hierarchy differs')
                matrix_count+=1;matrix_error=max(matrix_error,error)
        if not all(math.isfinite(x) for x in actual['minimum']+actual['maximum']):raise ValueError('nonfinite posed bounds')
    if len(original['controller_cases'])!=len(native['controller_cases']):raise ValueError('controller case count differs')
    for expected,actual in zip(original['controller_cases'],native['controller_cases']):
        if {k:v for k,v in expected.items() if k!='position'}!={k:v for k,v in actual.items() if k!='position'}:
            raise ValueError('controller input differs')
        if struct.pack('<f',expected['position'])!=struct.pack('<f',actual['position']):
            raise ValueError('original/native controller position differs')
    if len(original['weighted_cases'])!=len(native['weighted_cases']):raise ValueError('weighted case count differs')
    weighted_scalars=0
    for expected,actual in zip(original['weighted_cases'],native['weighted_cases']):
        if (expected['property'],expected['world_time'])!=(actual['property'],actual['world_time']):
            raise ValueError('weighted case identity differs')
        if [f32(x) for x in expected['weights']]!=[f32(x) for x in actual['weights']]:
            raise ValueError('weighted input differs')
        if len(expected['value'])!=len(actual['value']):raise ValueError('weighted width differs')
        for a,b in zip(expected['value'],actual['value']):
            if struct.pack('<f',a)!=struct.pack('<f',b):raise ValueError('weighted original/native binary32 result differs')
            weighted_scalars+=1
    root=Path(__file__).resolve().parents[2]
    paths=['native/include/g1/M3GAnimation.hpp','native/src/M3GAnimation.cpp',
           'native/tests/m3g_animation_test.cpp','native/tests/m3g_animation_fixture.hpp','native/tools/m3g_animation_probe.cpp',
           'native/include/g1/M3GScene.hpp','native/src/M3GScene.cpp','native/src/M3G.cpp',
           'analysis_tools/m3g/animation_oracle.py','analysis_tools/m3g/animation_validate.py',
           'analysis_tools/m3g/reference.py','analysis_tools/m3g/validate.py','analysis_tools/sprite/render_oracle.py']
    report={'scope':'Native rigid M3G sampling versus original sampler; independent posed hierarchy',
            'model_sha256':digest(data),'original_record_sha256':digest(args.original.read_bytes()),
            'original_instruction_sha256':original['original_sha256'],'original_libgcc_sha256':original['libgcc_sha256'],
            'sequences':original['sequences'],'sample_times':original['samples'],'sample_scalar_comparisons':scalar_count,
            'sample_binary32_identical':bit_equal,'maximum_sample_error':maximum_error,'sample_tolerance':2e-6,
            'pose_times':len(native['poses']),'pose_matrix_scalar_comparisons':matrix_count,
            'controller_mapping_original_cases':len(native['controller_cases']),'controller_mapping_exact_binary32':True,
            'weighted_original_cases':len(native['weighted_cases']),'weighted_scalar_comparisons':weighted_scalars,
            'weighted_exact_binary32':True,
            'maximum_pose_matrix_error':matrix_error,'pose_matrix_tolerance':2e-5,
            'original_math_boundary':original['host_math_boundary'],
            'local_libgcc_data_rebases':original['local_libgcc_data_rebases'],
            'native_contract_output':test.stdout.strip(),'native_probe_sha256':digest(args.native_probe.read_bytes()),
            'native_test_sha256':digest(args.native_test.read_bytes()),'native_output_sha256':digest(run.stdout.encode()),
            'sources':{p:digest((root/p).read_bytes()) for p in paths},'passed':True,
            'apple_compilation':False,'gpu_execution':False,'battle_clip_selection':False,'battle_choreography':False,
            'historical_ios_libm_bit_identity':False}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='sources'},indent=2))


if __name__=='__main__':main()
