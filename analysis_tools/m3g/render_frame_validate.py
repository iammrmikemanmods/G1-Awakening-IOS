#!/usr/bin/env python3
"""Prepare native M3G frames from verified local assets and explicit camera seeds.

This checks connected native data/pose/queue/quad preparation, not a GPU frame.
The original Appearance-order fixture independently verifies canonical keys for
its two recorded resources. Full original asset loading is not claimed.
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
    for name in ('manifest', 'extracted', 'probe', 'appearance-reference', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--resource', type=int, action='append', required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    entries = {item['resource_id']: item for item in manifest['resources'] if item['kind'] == 'm3g'}
    original = json.loads(args.appearance_reference.read_text())
    reference = {item['resource_id']: item for item in original['resources']}
    results = []
    order_comparisons = 0
    for resource in args.resource:
        entry = entries[resource]
        path = args.extracted / 'm3g' / entry['extracted_filename']
        if sha(path.read_bytes()) != entry['sha256']:
            raise ValueError(f'resource {resource} changed from inspected manifest')
        run = subprocess.run([str(args.probe.resolve()), str(path.resolve())],
                             capture_output=True, text=True, timeout=30)
        if run.returncode:
            raise RuntimeError(f'resource {resource}: {run.stderr.strip()}')
        output = json.loads(run.stdout)
        if resource in reference:
            case = reference[resource]
            if entry['sha256'] != case['source_sha256']:
                raise ValueError('Appearance oracle input differs')
            for source in case['runs']:
                expected = [[a['index'], a['serial'] - source['serial_base']] for a in source['appearances']]
                if expected != output['appearance_order_keys']:
                    raise ValueError('canonical order differs from original Appearance construction')
                order_comparisons += len(expected) * 2
        results.append({'resource_id': resource, 'sha256': entry['sha256'], 'native': output})
    report = {
        'schema': 1,
        'scope': 'Native frame preparation using first/last serialized Camera seeds at six supplied times; not actual battle selection or GPU output',
        'manifest_sha256': sha(args.manifest.read_bytes()),
        'probe_sha256': sha(args.probe.read_bytes()),
        'appearance_reference_sha256': sha(args.appearance_reference.read_bytes()),
        'resources': results,
        'summary': {
            'resources': len(results),
            'prepared_frames': sum(len(r['native']['frames']) for r in results),
            'mesh_draw_records': sum(f['mesh_draws'] for r in results for f in r['native']['frames']),
            'projected_sprite_draw_records': sum(f['sprite_draws'] for r in results for f in r['native']['frames']),
            'culled_sprite_records': sum(f['culled_sprites'] for r in results for f in r['native']['frames']),
            'original_appearance_index_rank_comparisons': order_comparisons,
        },
        'apple_compilation': False, 'gpu_execution': False, 'device_execution': False,
    }
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report['summary']))


if __name__ == '__main__':
    main()
