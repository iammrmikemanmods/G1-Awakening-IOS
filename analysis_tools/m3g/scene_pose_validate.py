#!/usr/bin/env python3
"""Evaluate selected local M3G assets through the native scene-pose probe.

Input files must match the existing private resource manifest. This is a native
data/state integration check, not a new original-code or GPU comparison.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    for option in ('manifest', 'extracted', 'probe', 'output'):
        parser.add_argument('--' + option, type=Path, required=True)
    parser.add_argument('--resource', type=int, action='append', required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    entries = {x['resource_id']: x for x in manifest['resources'] if x['kind'] == 'm3g'}
    resources = []
    for resource in args.resource:
        entry = entries[resource]
        path = args.extracted / 'm3g' / entry['extracted_filename']
        data = path.read_bytes()
        if sha(data) != entry['sha256']:
            raise ValueError(f'resource {resource} differs from inspected asset manifest')
        run = subprocess.run([str(args.probe.resolve()), str(path.resolve())],
                             capture_output=True, text=True, timeout=30)
        if run.returncode:
            raise RuntimeError(f'resource {resource}: {run.stderr.strip()}')
        resources.append({'resource_id': resource, 'sha256': sha(data),
                          'native_pose': json.loads(run.stdout)})
    report = {
        'schema': 1,
        'scope': 'Native scene state, hierarchy and camera evaluation at six times; no geometry/GPU/device comparison',
        'manifest_sha256': sha(args.manifest.read_bytes()),
        'probe_sha256': sha(args.probe.read_bytes()),
        'resources': resources,
        'summary': {'resources': len(resources),
                    'poses': sum(len(r['native_pose']['poses']) for r in resources),
                    'nodes': sum(r['native_pose']['nodes'] for r in resources),
                    'cameras': sum(r['native_pose']['cameras'] for r in resources)},
        'apple_compilation': False, 'gpu_execution': False, 'device_execution': False
    }
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report['summary']))


if __name__ == '__main__':
    main()
