# Turn reference tool

Run `python3 analysis_tools/turns/oracle.py --help` from the native project root.
The tool authenticates the original executable, executes unchanged gameplay
functions with Unicorn, and compares a separately compiled native stdin probe
from `native/tests/turn_test.cpp`. Supply the movement oracle at
`analysis_tools/movement/oracle.py` if present in your checkout, or the actual
path to the original movement reproducer; use the capture-action reference
JSON produced by its oracle. The tool records all external camera/UI/snapshot
boundaries and refuses a native mismatch. Original input files stay local.

The maintained result is `native/research/turn_validation/original_turns.json`.
No reference emulator is packaged into the native app.
