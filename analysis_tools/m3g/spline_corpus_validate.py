#!/usr/bin/env python3
"""Bounded real-asset curve sampling and existing rigid-pose coverage.

This checks native parsing/sampling of hash-verified local model assets. It is
not another original-instruction oracle and does not execute a GPU renderer.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def digest(data):return hashlib.sha256(data).hexdigest()


def main():
    parser=argparse.ArgumentParser()
    for option in ('manifest','corpus','extracted','curve-probe','pose-probe','output'):
        parser.add_argument('--'+option,type=Path,required=True)
    args=parser.parse_args()
    manifest=json.loads(args.manifest.read_text()); prior=json.loads(args.corpus.read_text())
    entries={x['resource_id']:x for x in manifest['resources'] if x['kind']=='m3g'}
    results=[]
    for source in prior['resources']:
        entry=entries[source['resource_id']]
        path=args.extracted/'m3g'/entry['extracted_filename']; data=path.read_bytes()
        if digest(data)!=source['sha256'] or digest(data)!=entry['sha256']:
            raise ValueError('resource hash mismatch')
        curve=subprocess.run([str(args.curve_probe.resolve()),str(path.resolve())],capture_output=True,text=True,timeout=30)
        if curve.returncode:raise RuntimeError(f"curve resource {source['resource_id']}: {curve.stderr.strip()}")
        curve_result=json.loads(curve.stdout)
        root=source['native_animation_probe']['root_user_id']
        pose=subprocess.run([str(args.pose_probe.resolve()),str(path.resolve()),str(root)],capture_output=True,text=True,timeout=30)
        row={'resource_id':source['resource_id'],'role':source['role'],'sha256':digest(data),
             'curve_probe':curve_result,'pose_root_user_id':root,'pose_exit_code':pose.returncode,
             'pose_output_sha256':digest(pose.stdout.encode()),'pose_error':pose.stderr.strip()}
        if pose.returncode==0:
            parsed=json.loads(pose.stdout)
            row['pose_samples']=len(parsed['poses']);row['pose_properties']=[p['properties'] for p in parsed['poses']]
        results.append(row)
    report={'schema':1,'scope':'Native prepared curves and six rigid-pose samples of verified actual assets; no GPU/device/original execution in this check',
            'manifest_sha256':digest(args.manifest.read_bytes()),'prior_corpus_sha256':digest(args.corpus.read_bytes()),
            'curve_probe_sha256':digest(args.curve_probe.read_bytes()),'pose_probe_sha256':digest(args.pose_probe.read_bytes()),
            'resources':results,'summary':{'resources':len(results),'curve_sequences':sum(x['curve_probe']['sequences'] for x in results),
                 'curve_samples':sum(x['curve_probe']['samples'] for x in results),'curve_scalars':sum(x['curve_probe']['scalars'] for x in results),
                 'all_curves_finite':True,'pose_probes_passed':sum(x['pose_exit_code']==0 for x in results),
                 'pose_probes_blocked':sum(x['pose_exit_code']!=0 for x in results)},
            'apple_compilation':False,'gpu_execution':False,'historical_ios_libm_bit_identity':False}
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report['summary']))
    for x in results:
        if x['pose_exit_code']:print(json.dumps({'resource_id':x['resource_id'],'remaining_error':x['pose_error']}))


if __name__=='__main__':main()
