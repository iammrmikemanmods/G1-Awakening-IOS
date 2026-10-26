# Development-only capture reference

Nothing in this directory is linked into the native library or iOS app.
Supply the original ARMv6 executable privately; do not commit it. The binary
must have SHA-256
`0d510516fe3676ee4a0f4dff60ba64e1c5bf79a0c9800f420b1bbdb1c12febfd`.
The script uses externally installed Unicorn 2.1.4 and the existing shared
`analysis_tools/movement/oracle.py` harness. No instruction patches or function
stubs are installed.

From the project root:

```sh
g++ -std=c++17 -O2 -Wall -Wextra -Wpedantic -Werror -I native/include \
  native/src/CaptureAction.cpp analysis_tools/capture_action/probe.cpp \
  -o /tmp/g1_capture_action_probe
python analysis_tools/capture_action/oracle.py \
  --binary /absolute/private/G1awakening.armv6 \
  --movement-oracle analysis_tools/movement/oracle.py \
  --native-probe /tmp/g1_capture_action_probe \
  --unicorn-dir /absolute/external/python-packages \
  --output native/research/capture_action_validation/original_capture.json
```

The full link/counter function executes to its real return. The human coordinate
scan starts at an explicitly seeded basic-block boundary and stops when the
original code chooses an item, site or no target. Capture mutation prefixes stop
after ownership/link writes and before UI/audio/renderer calls. The report makes
these boundaries explicit; it is not a complete original gameplay run.
