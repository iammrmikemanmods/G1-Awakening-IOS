# Mission/text development references

These tools reproduce the original-function reference and local resource
comparison for the portable `Text` / `MissionExecution` modules. They are
development tools only. They are never built into, linked into, loaded by, or
packaged with the native app.

The original ARM32 executable and `iphone.big` are explicit **local inputs**.
Neither is committed here. Both tools verify the recorded SHA256 identity
before using an original input. The scripts have no workspace-specific path
assumptions and no network or remote-write operations.

## Original function reference

Python 3 and Unicorn **2.1.4** are required. For example, from the repository root:

```sh
python3 -m venv /tmp/g1-mission-reference-env
/tmp/g1-mission-reference-env/bin/python -m pip install -r analysis_tools/mission_execution/requirements.txt
/tmp/g1-mission-reference-env/bin/python analysis_tools/mission_execution/oracle.py \
  --image /local/path/G1awakening.armv6 \
  --output /tmp/g1-mission-reference
```

If Unicorn is already installed in an isolated directory, `--python-tools`
accepts that directory instead. It is optional; ordinary installed imports work.

The reference executes the unchanged original text-index mapper, dialogue
gate, input-consumption helper, capture predicate and its success/unit-reset
functions, and mission clock. Code pages are read-only. Unknown imports or
unexpected external boundaries abort. Each call must return within bounded
instruction/time limits and balance its stack.

External boundaries supply imported integer multiply/divide arithmetic,
synthetic font selection and metrics, or record an audio notification. The
clock-only test records a next-command-dispatch call instead of executing the
large dispatcher. These boundaries do not choose a dialogue/capture result.
The report lists all boundaries and their invocation counts.

Expected generated vectors:

- `text_index_original_vectors.txt`: 972 index/variant cases.
- `dialogue_original_vectors.txt`: 476 complete original gate executions.
- `capture_original_vectors.txt`: 164 case shapes, each checked under two
  live-player count contexts, including the first campaign's `[1,1]`.
- `mission_clock_original_vectors.txt`: 48 timer/transition cases.
- `original_mission_execution_reference.json`: hashes, versions, boundary
  records and limitations.

The four committed fixtures under `native/tests/` contain numeric inputs and
observed outputs, not original instructions or string payloads. Regeneration
can be compared directly to those files. Native tests consume them without
requiring Unicorn or any original executable.

## Native tests and actual-resource comparison

After the normal native CMake targets are configured:

```sh
cmake -S native -B /tmp/g1-native -DBUILD_TESTING=ON
cmake --build /tmp/g1-native
ctest --test-dir /tmp/g1-native --output-on-failure
python3 analysis_tools/mission_execution/validate_resources.py \
  --archive /local/path/iphone.big \
  --probe /tmp/g1-native/mission_execution_probe \
  --output /tmp/g1-mission-resources
```

The resource validator independently extracts resource 1 and compares all 511
string IDs, offsets and UTF-8 bytes against the native decoder. It also checks
the native continuation on actual mission resource 315, starting at command 9
and stopping before command 26/opcode 8.

**That latter check is a control-flow fixture, not a playthrough.** Its renderer
layout, camera responses and capture-state observation are deliberately
synthetic, and its returned gameplay/audio effects are not applied. It neither
performs a capture action nor demonstrates UI, battle, mission completion,
saving, an iOS build or device behavior. The output states those limits.

`native_resource_probe.json` contains decoded local game text in hexadecimal
and should remain local. The compact committed validation report contains
hashes, IDs and branch observations instead. Do not add the original inputs,
full decoded text output, a CPU interpreter or these reference dependencies to
the app's runtime resources.

## Evidence and integration contract

Read `native/research/MISSION_EXECUTION.md` for addresses, first-mission command
flow, input-edge consumption, camera tokens, capture state versus coordinates,
one-phase-per-tick semantics, required external effects, and the current
unsupported completion/campaign boundaries. Machine-readable evidence is in
`native/research/MISSION_EXECUTION.json` and its adjacent
`mission_execution_validation/` directory.
