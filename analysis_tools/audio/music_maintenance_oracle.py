#!/usr/bin/env python3
"""Original music-maintenance bodies with one explicit audio-output boundary.

The original singleton accessor, wrapper and style selector execute unchanged.
This development oracle neither renders nor produces sound; its tests supply
the actual-output status boundary independently from all game state.
"""
import argparse
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import subprocess
import sys


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--libgcc', type=Path, required=True)
    parser.add_argument('--unicorn-dir', type=Path, required=True)
    parser.add_argument('--base-oracle', type=Path, required=True)
    parser.add_argument('--native-probe', type=Path, required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.unicorn_dir.resolve()))
    spec = importlib.util.spec_from_file_location('music_original_base', args.base_oracle)
    base = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(base)
    image, gcc = args.binary.read_bytes(), args.libgcc.read_bytes()
    if sha(image) != base.IMAGE_SHA or sha(gcc) != base.LIBGCC_SHA:
        raise ValueError('wrong original source')

    class Reference(base.OriginalCombat):
        def __init__(self):
            self.events = []
            self.playing = 0
            super().__init__(image, gcc)
            self.cine = self.alloc(0x100)
            self.w32(self.cine + 0x4c, self.map)
            self.w32(self.map + 0x29c, self.app)

        def hook(self, cpu, address, size, data):
            if address == 0x2ad12:
                ar = self.ar
                app, operation, argument = [cpu.reg_read(getattr(ar, 'UC_ARM_REG_R' + str(i)))
                                            for i in range(3)]
                if app != self.app or operation not in (3, 5, 6):
                    raise RuntimeError('unexpected original audio request')
                self.events.append([operation, argument])
                cpu.reg_write(ar.UC_ARM_REG_R0, self.playing if operation == 6 else 0)
                cpu.reg_write(ar.UC_ARM_REG_PC, cpu.reg_read(ar.UC_ARM_REG_LR))
            else:
                super().hook(cpu, address, size, data)

        def run(self, values):
            site, enabled, self.playing, style, map_mode, app_mode = values
            self.events = []
            self.w8(self.app + 0xa4, enabled)
            self.w32(self.app + 0x1c0, app_mode)
            self.w32(self.map + 0x2d8, map_mode)
            self.w32(self.map + 0x22c, style)
            self.w32(0x21ff000 + 0x20, self.map)
            self.w32(0x21ff000 + 0x24, self.cine)
            before_map = bytes(self.u.mem_read(self.map, 0x600))
            before_app = bytes(self.u.mem_read(self.app, 0x500))
            entry, stop = (0x5b5a4, 0x5b5e8) if site == 0 else (0x428a4, 0x428c6)
            self.call(entry, [], stop=stop)
            if before_map != bytes(self.u.mem_read(self.map, 0x600)) or \
                    before_app != bytes(self.u.mem_read(self.app, 0x500)):
                raise RuntimeError('maintenance changed gameplay storage')
            return [len(self.events), *[number for event in self.events for number in event]]

    ref = Reference()
    inputs = [list(values) for values in itertools.product(
        (0, 1), (0, 1), (0, 1),
        (-2147483648, -2, -1, 0, 1, 2, 3, 2147483647),
        (0, 2, 6, 7, 8), (0, 3, 10, 100))]
    expected = [ref.run(values) for values in inputs]
    ref.check_text()
    native = subprocess.run([str(args.native_probe.resolve())],
                            input='\n'.join(' '.join(map(str, row)) for row in inputs) + '\n',
                            text=True, capture_output=True, check=True, timeout=30)
    actual = [[int(value) for value in row.split()] for row in native.stdout.splitlines()]
    if actual != expected:
        for n, pair in enumerate(zip(actual, expected)):
            if pair[0] != pair[1]:
                raise RuntimeError(f'music case {n}: input {inputs[n]}, native {pair[0]}, original {pair[1]}')
        raise RuntimeError('music result count mismatch')
    args.fixture.parent.mkdir(parents=True, exist_ok=True)
    args.fixture.write_text('# site enabled playing style map_mode app_mode | count operation argument ...\n' +
                            '\n'.join(' '.join(map(str, a)) + ' | ' + ' '.join(map(str, b))
                                      for a, b in zip(inputs, expected)) + '\n')
    report = {
        'schema': 1, 'status': 'passed', 'cases': len(inputs),
        'scalar_comparisons': sum(map(len, expected)),
        'original_sha256': sha(image), 'libgcc_sha256': sha(gcc),
        'oracle_sha256': sha(Path(__file__).read_bytes()),
        'fixture_sha256': sha(args.fixture.read_bytes()),
        'native_probe_sha256': sha(args.native_probe.read_bytes()),
        'original_entries': ['0x5b5a4..0x5b5e8', '0x428a4..0x428c6', '0x4e7b8', '0x2ad6c', '0x62d1c'],
        'external_boundaries': {'0x2ad12': 'Record operation/argument; operation 6 returns independently supplied actual-output-playing state.'},
        'instruction_patches': 0, 'original_text_readonly_unchanged': True,
        'all_case_map_app_storage_unchanged': True,
        'scope': 'Exact active-body requests, not whole updater execution, audible output, Apple API behavior or physical iPhone testing.',
        'map_outer_dispatch': 'The original map updater reaches this active body under app+0x1c0==100 at 0x5b304..0x5b30e. Inner values are varied independently to exercise transitions/guards.'
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
