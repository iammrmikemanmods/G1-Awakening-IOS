# Development reference: Undo and unit commands

This directory reproduces the unchanged-original reference behind
`native/research/UNDO_AND_COMMANDS.md`. It is analysis tooling only: Unicorn and
the original ARMv6 program are never built into, linked with or bundled in the
native application. The repository fixture is numeric synthetic state, not an
original executable/resource payload.

## Required inputs

- A local copy of the audited original iOS1.1.3 ARMv6 Mach-O, SHA256
  `0d510516fe3676ee4a0f4dff60ba64e1c5bf79a0c9800f420b1bbdb1c12febfd`.
  The script accepts it only by an explicit `--image` argument. It is not
  downloaded and must not be uploaded to the source repository.
- `analysis_tools/world/world_oracle.py`, SHA256
  `2c1fc1e53e27c8c0a16a248b4d724f6225f9fdcba05456a9d840cc21d1bc6a79`.
  This existing support supplies the original memory layout and integer import
  boundary, not expected Undo results.
- Python3 and `unicorn==2.1.4`, installed into a chosen isolated directory.
- A C++17 compiler for the independent native comparison.

No original archive, libgcc payload, Apple SDK or compatibility host is needed.
The only imported arithmetic used by reverse-transform stat calculation is
signed integer division, supplied as exact truncation toward zero.

From the repository root, using paths of your choice:

```sh
python3 -m pip install --target /tmp/g1-undo-python -r analysis_tools/undo/requirements.txt
python3 analysis_tools/undo/oracle.py \
  --image /absolute/local/path/G1awakening.armv6 \
  --support analysis_tools/world/world_oracle.py \
  --unicorn-dir /tmp/g1-undo-python \
  --output /tmp/g1-undo-reference
```

The runner refuses mismatched source/support hashes, maps original instructions
read-only, patches zero instruction bytes and checks executable text after each
case. It additionally checks every unit mutation against a specific byte-write
whitelist. Original request boundaries are recorded without claiming graphics,
audio or UI delivery.

Compare the resulting `unit_commands_original_vectors.txt` with
`native/tests/unit_commands_original_vectors.txt` byte-for-byte. Run the existing
`g1_unit_commands_tests` CMake target against the generated fixture, or compile
the same direct-source comparison from the repository root:

```sh
c++ -std=c++17 -Wall -Wextra -Wconversion -Werror -pedantic -O2 \
  -ffunction-sections -fdata-sections -I native/include \
  native/src/UndoAction.cpp native/src/UnitCommands.cpp \
  native/src/TransformAction.cpp native/src/Combat.cpp \
  native/src/MovementAction.cpp native/src/Movement.cpp \
  native/tests/unit_commands_test.cpp -Wl,--gc-sections \
  -o /tmp/g1-unit-commands-test
/tmp/g1-unit-commands-test /tmp/g1-undo-reference/unit_commands_original_vectors.txt
```

The direct link command above is the verified Linux/GNU linker form. On Apple
platforms use the project's CMake test target instead of GNU `--gc-sections`.
Expected output: 1,100 vectors, 11,436 scalar comparisons, 17 native guards.

## Meaning of the reference

The 540 availability, Undo, selection-lock and end-action vectors execute their
original unit logic. The other 560 cases are explicitly **command composition
tests**: nine helper results are supplied as Boolean inputs at the original
helper interfaces, and the runner verifies the original common guards, bit
arithmetic, priority and short-circuit call order. Those cases do not independently
validate the underlying movement/production/combat/etc. predicates.

The operation10 action-ending body is real, but its reachability from a human
touch-menu gesture remains unproven. Neither the script nor the native module
adds a new visible Wait button or treats bit0x100 as proof of one.

`REFERENCE.json` records the frozen original reference metadata. The native
comparison and source hashes are in `native/research/undo_validation/` and
`native/research/UNDO_AND_COMMANDS.json`. This is not a device/full-playthrough
result.
