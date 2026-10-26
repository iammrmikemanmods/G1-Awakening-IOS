# Movement action reference tools

These files are development-only. `probe.cpp` uses the portable native module;
`oracle.py` runs original ARM functions using an externally supplied Unicorn
package and a private executable, then compares their state traces. Do not add
these tools or the original executable to the iOS app or native library.

Required inputs:

- Original G1 Awakening 1.1.3 ARMv6 executable, SHA-256
  `0d510516fe3676ee4a0f4dff60ba64e1c5bf79a0c9800f420b1bbdb1c12febfd`.
- External Python Unicorn 2.1.4, installed outside the product repository.
- Unchanged `analysis_tools/movement/oracle.py`, which defines the shared
  original-code memory fixture. Its hash is recorded in the output.
- C++17 compiler and the native `Movement`/`MovementAction` sources.

From a repository containing `native/` and `analysis_tools/`:

```sh
c++ -std=c++17 -O2 -Wall -Wextra -Wpedantic -Werror \
  -I native/include native/src/Movement.cpp native/src/MovementAction.cpp \
  analysis_tools/movement_action/probe.cpp -o /tmp/g1_movement_action_probe

python analysis_tools/movement_action/oracle.py \
  --binary /path/to/private/G1awakening.armv6 \
  --movement-oracle analysis_tools/movement/oracle.py \
  --unicorn-dir /path/to/external/python-packages \
  --native-probe /tmp/g1_movement_action_probe \
  --output /tmp/original_actions.json
```

The fixed case generator covers all four movement directions, tied routes,
weighted original range fields, forms 0/1/2, varied time deltas, signed form-zero
stat values, ordinary undo flags, and eight-bit budget wraparound. Original
functions run with read-only text pages, no instruction patches and no function
stubs. The output records every range, route and state snapshot, plus exact-match
counts. It does not run a full mission or validate an iPhone build.

Focused contracts also cover rejection of malformed, cyclic, disconnected and
oversized unsupported states. Those safeguards intentionally do not try to
reproduce undefined original memory accesses or an infinite recursive route.

The CMake owner may add `src/MovementAction.cpp`, a test executable from
`tests/movement_action_test.cpp`, and a fixture-free test named
`movement_action_contract`. This directory is excluded from product targets.
