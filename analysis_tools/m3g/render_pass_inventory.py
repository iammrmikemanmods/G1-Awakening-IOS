#!/usr/bin/env python3
"""Record serialized clear/depth metadata; does not infer runtime pass selection."""
import argparse
import hashlib
import json
from pathlib import Path

import reference


RESOURCE_IDS = [486, 534, 1212, 408, 699, 444, 492, 1300, 561, 369, 565,
                634, 395, 475, 867, 1039, 631, 795, 967, 564, 1299, 829,
                1201, 1070, 489, 490, 500]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    for name in ('manifest', 'extracted', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    entries = {item['resource_id']: item
               for item in json.loads(args.manifest.read_text())['resources']
               if item['kind'] == 'm3g'}
    records = []
    for resource in RESOURCE_IDS:
        entry = entries[resource]
        raw = (args.extracted / 'm3g' / entry['extracted_filename']).read_bytes()
        if sha(raw) != entry['sha256']:
            raise ValueError('asset differs from inspected manifest')
        objects = reference.parse(raw)
        worlds = []
        for obj in objects[1:]:
            if obj['type'] != 22:
                continue
            index = obj['background']
            state = objects[index]['background'] if index else None
            worlds.append({'world': obj['index'], 'background': index,
                           'serialized_state': state})
        depth = [{'object': obj['index'], 'values': obj['compositing_values']}
                 for obj in objects[1:] if obj['type'] == 6]
        records.append({'resource_id': resource, 'sha256': entry['sha256'],
                        'worlds': worlds, 'compositing': depth})
    report = {
        'schema': 1,
        'scope': 'Serialized World clear and CompositingMode metadata only; no original runtime pass selection or GPU execution',
        'manifest_sha256': sha(args.manifest.read_bytes()),
        'reference_parser_sha256': sha(Path(reference.__file__).read_bytes()),
        'background_state_order': ['red', 'green', 'blue', 'alpha', 'image',
                                   'mode_x', 'mode_y', 'crop_x', 'crop_y',
                                   'crop_width', 'crop_height', 'depth_clear',
                                   'color_clear'],
        'resources': records,
        'summary': {
            'resources': len(records),
            'worlds': sum(len(r['worlds']) for r in records),
            'image_backgrounds': sum(bool(w['serialized_state'][4])
                for r in records for w in r['worlds'] if w['serialized_state']),
            'depth_test_disabled_write_enabled': sum(
                not c['values'][0] and bool(c['values'][1])
                for r in records for c in r['compositing']),
        },
    }
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report['summary']))


if __name__ == '__main__':
    main()
