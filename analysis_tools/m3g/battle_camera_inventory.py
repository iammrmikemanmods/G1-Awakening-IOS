#!/usr/bin/env python3
"""Check raw fallback Camera bindings in the three actual battle scene files."""
import argparse
import hashlib
import json
from pathlib import Path

import battle_camera_oracle
import reference


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    for name in ('manifest', 'extracted', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    entries = {e['resource_id']: e for e in json.loads(args.manifest.read_text())['resources']
               if e['kind'] == 'm3g'}
    records = []
    for resource in (486, 534, 1212):
        entry = entries[resource]
        raw = (args.extracted / 'm3g' / entry['extracted_filename']).read_bytes()
        if sha(raw) != entry['sha256']:
            raise ValueError('actual scene differs from inspected manifest')
        objects = reference.parse(raw)
        worlds = [o['index'] for o in objects[1:] if o['type'] == 22]
        if len(worlds) != 1:
            raise ValueError('expected one serialized World in the actual scene')
        world = worlds[0]
        parents = {c: o['index'] for o in objects[1:] for c in o.get('children', [])}
        nodes = {o['index']: o for o in objects[1:] if o['type'] in (5, 9, 12, 14, 15, 16, 18, 22)}
        rows = []
        for name in battle_camera_oracle.SCENE_NAMES:
            key = battle_camera_oracle.name_hash(name)
            pending, found, visited = [world], None, set()
            while pending:
                index = pending.pop()
                if index in visited:
                    raise ValueError('cyclic or shared Node hierarchy')
                visited.add(index);obj = nodes[index]
                if obj['user_id'] == key:
                    found = index;break
                pending.extend(reversed(obj.get('children', [])))
            rows.append({'name': name, 'user_id': key, 'object': found,
                         'type': nodes[found]['type'] if found else None,
                         'parent': parents.get(found),
                         'grandparent': parents.get(parents.get(found))})
        records.append({'resource_id': resource, 'sha256': entry['sha256'],
                        'world': world, 'fallbacks': rows})
    report = {
        'schema': 1,
        'scope': 'Independent serialized Node-first lookup of raw fallback camera names; not runtime choice or GPU output',
        'reference_parser_sha256': sha(Path(reference.__file__).read_bytes()),
        'name_helper_sha256': sha(Path(battle_camera_oracle.__file__).read_bytes()),
        'resources': records,
        'summary': {'queries': sum(len(r['fallbacks']) for r in records),
                    'found_camera5': sum(row['type'] == 5 for r in records for row in r['fallbacks']),
                    'missing': [{'resource_id': r['resource_id'], 'name': row['name']}
                                for r in records for row in r['fallbacks'] if row['object'] is None]},
    }
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report['summary']))


if __name__ == '__main__':
    main()
