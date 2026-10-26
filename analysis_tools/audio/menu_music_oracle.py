#!/usr/bin/env python3
"""Execute the unchanged original menu music body against native requests.

Only the platform audio boundary at 0x2ad12 is supplied. The original menu
guards, parent-chain walk and operation-6 wrapper execute without patches.
This is a development reference, never part of the native application.
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


def inputs():
    # Distinct original identities, null pointers, aliases and exclusions at
    # multiple ancestor depths. Every synthetic parent graph is acyclic.
    graphs = set()
    chains = [()]
    for length in range(1, 4):
        chains.extend(itertools.permutations(range(1, 9), length))
    chains.extend([(1, 2, 3, 8, 4, 5, 6, 7), (1, 2, 3, 8, 4),
                   (1, 2, 3, 8, 5), (1, 2, 3, 8, 6), (1, 2, 3, 8, 7)])
    for chain in chains:
        parents = [0] * 8
        for child, parent in zip(chain, chain[1:]):
            parents[child - 1] = parent
        current = chain[0] if chain else 0
        graphs.add((current, 4, 5, 6, 7, *parents))
    # A null exact-current excluded pointer must still compare by identity;
    # null ancestor exclusions do not match a traversed non-null menu.
    for current, prompt in itertools.product((0, 1, 4), (0, 1, 4)):
        for roots in ((0, 0, 0), (1, 1, 1), (4, 4, 4), (4, 5, 6)):
            graphs.add((current, prompt, *roots, *([0] * 8)))
    return [list(flags + graph) for flags in itertools.product(
        (0, 1), (0, 1), (-2147483648, 0, 3, 10, 100, 2147483647))
        for graph in sorted(graphs)]


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
    spec = importlib.util.spec_from_file_location('menu_original_base', args.base_oracle)
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
            self.nodes = [0] + [self.alloc(0x2c) for _ in range(8)]

        def hook(self, cpu, address, size, data):
            if address == 0x2ad12:
                ar = self.ar
                app, operation, argument = [cpu.reg_read(getattr(ar, 'UC_ARM_REG_R' + str(i)))
                                            for i in range(3)]
                if app != self.app or operation not in (5, 6) or argument != 0:
                    raise RuntimeError('unexpected original menu audio request')
                self.events.append([operation, argument])
                cpu.reg_write(ar.UC_ARM_REG_R0, self.playing if operation == 6 else 0)
                cpu.reg_write(ar.UC_ARM_REG_PC, cpu.reg_read(ar.UC_ARM_REG_LR))
            else:
                super().hook(cpu, address, size, data)

        def run(self, values):
            enabled, self.playing, app_mode, current, prompt, pause, opponent, actions = values[:8]
            self.events = []
            self.w8(self.app + 0xa4, enabled)
            self.w32(self.app + 0x1c0, app_mode)
            for offset, node in ((0x244, current), (0x258, prompt), (0x260, pause),
                                 (0x278, opponent), (0x268, actions)):
                self.w32(self.app + offset, self.nodes[node])
            for i, parent in enumerate(values[8:], 1):
                self.w32(self.nodes[i] + 8, self.nodes[parent])
            before_app = bytes(self.u.mem_read(self.app, 0x500))
            before_nodes = [bytes(self.u.mem_read(pointer, 0x2c)) for pointer in self.nodes[1:]]
            ar = self.ar
            for i in range(13):
                self.u.reg_write(getattr(ar, 'UC_ARM_REG_R' + str(i)), 0)
            self.u.reg_write(ar.UC_ARM_REG_CPSR, 0x30)
            self.u.reg_write(ar.UC_ARM_REG_SP, 0x21ff000)
            self.u.reg_write(ar.UC_ARM_REG_LR, 0x3000001)
            self.u.reg_write(ar.UC_ARM_REG_R4, self.app)
            self.u.emu_start(0x36eaf, 0x36f22, count=10000, timeout=3000000)
            if self.u.reg_read(ar.UC_ARM_REG_PC) != 0x36f22 or \
                    self.u.reg_read(ar.UC_ARM_REG_SP) != 0x21ff000:
                raise RuntimeError('menu body did not reach exact stop with balanced stack')
            if before_app != bytes(self.u.mem_read(self.app, 0x500)) or \
                    before_nodes != [bytes(self.u.mem_read(pointer, 0x2c)) for pointer in self.nodes[1:]]:
                raise RuntimeError('menu maintenance changed application/menu storage')
            return [len(self.events), *[number for event in self.events for number in event]]

    ref = Reference()
    cases = inputs()
    expected = [ref.run(values) for values in cases]
    ref.check_text()
    native = subprocess.run([str(args.native_probe.resolve())],
                            input='\n'.join(' '.join(map(str, row)) for row in cases) + '\n',
                            text=True, capture_output=True, check=True, timeout=30)
    actual = [[int(value) for value in row.split()] for row in native.stdout.splitlines()]
    if actual != expected:
        for n, pair in enumerate(zip(actual, expected)):
            if pair[0] != pair[1]:
                raise RuntimeError(f'menu case {n}: input {cases[n]}, native {pair[0]}, original {pair[1]}')
        raise RuntimeError('menu result count mismatch')
    args.fixture.parent.mkdir(parents=True, exist_ok=True)
    args.fixture.write_text('# enabled playing app_mode current prompt pause opponent actions parent1..parent8 | count operation argument ...\n' +
                            '\n'.join(' '.join(map(str, a)) + ' | ' + ' '.join(map(str, b))
                                      for a, b in zip(cases, expected)) + '\n')
    report = {
        'schema': 1, 'status': 'passed', 'cases': len(cases),
        'scalar_comparisons': sum(map(len, expected)),
        'original_sha256': sha(image), 'libgcc_sha256': sha(gcc),
        'oracle_sha256': sha(Path(__file__).read_bytes()),
        'fixture_sha256': sha(args.fixture.read_bytes()),
        'native_probe_sha256': sha(args.native_probe.read_bytes()),
        'original_entries': ['0x36eae..0x36f22', '0x2ad6c'],
        'external_boundaries': {'0x2ad12': 'Record operation/argument; operation 6 returns independently supplied any-voice-playing state.'},
        'instruction_patches': 0, 'original_text_readonly_unchanged': True,
        'all_case_application_menu_storage_unchanged': True,
        'scope': 'Exact original menu-body requests; not whole application update, constructor execution, audible output, Apple timer behavior or physical iPhone testing.'
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
