#!/usr/bin/env python3
"""Compare native camera body decoding with the independent corpus audit.

Requires private extracted assets locally. Writes counts/hashes only; does not
copy assets or use any original executable. The separate camera_oracle.py
establishes original projection arithmetic with synthetic inputs.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess


def sha(data):return hashlib.sha256(data).hexdigest()
def bits(value):return struct.unpack('<I',struct.pack('<f',value))[0]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','corpus-audit','extracted','native-probe','output'):
        ap.add_argument('--'+name,type=Path,required=True)
    args=ap.parse_args();manifest_data=args.manifest.read_bytes();corpus_data=args.corpus_audit.read_bytes()
    resources=json.loads(manifest_data)['resources'];corpus=json.loads(corpus_data)['resources']
    rows=[];cameras=0;comparisons=0
    for reference in corpus:
        resource=reference['resource_id']
        candidates=[r for r in resources if r['resource_id']==resource and r['kind']=='m3g']
        if len(candidates)!=1:raise ValueError('ambiguous private M3G resource '+str(resource))
        row=candidates[0];path=args.extracted/'m3g'/row['extracted_filename']
        data=path.read_bytes()
        if sha(data)!=reference['sha256'] or sha(data)!=row['sha256']:raise ValueError('private asset hash mismatch')
        run=subprocess.run([str(args.native_probe.resolve()),str(path)],capture_output=True,text=True,timeout=30,check=True)
        native=json.loads(run.stdout)['cameras'];expected=reference['cameras']
        if len(native)!=len(expected):raise ValueError('camera count differs for resource '+str(resource))
        native_by_index={c['object']:c for c in native}
        for c in expected:
            n=native_by_index[c['object']]
            if n['type']!=c['projection_type']:raise ValueError('camera projection type differs')
            comparisons+=1
            if c['projection_type']==48:raise ValueError('generic actual-data oracle mapping must be added explicitly')
            if n['parameter_bits']!=[bits(v) for v in c['projection_parameters']]:raise ValueError('camera parameter bits differ')
            comparisons+=4;cameras+=1
        rows.append({'resource_id':resource,'sha256':reference['sha256'],'cameras':len(native),'native_output_sha256':sha(run.stdout.encode())})
    report={'schema':1,'kind':'native camera body decoder against independent asset audit','resources':len(rows),'cameras':cameras,'exact_field_comparisons':comparisons,
        'manifest_sha256':sha(manifest_data),'corpus_audit_sha256':sha(corpus_data),'probe_sha256':sha(args.native_probe.read_bytes()),
        'runner_sha256':sha(Path(__file__).read_bytes()),'rows':rows,'passed':True,'gpu_execution':False,'live_camera_selection':False}
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('resources','cameras','exact_field_comparisons','passed')}))


if __name__=='__main__':main()
