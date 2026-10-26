# Original objective reference

Development-only: Python3, `unicorn==2.1.4`, the original hash-checked ARMv6
executable, and the pinned sibling progression harness. Neither Python,
Unicorn nor original machine code is a native-app dependency.

```sh
python3 analysis_tools/mission_objectives/objective_oracle.py \
  --image /absolute/path/to/G1awakening.armv6 \
  --support analysis_tools/mission_progression/oracle.py \
  --output /tmp/g1-objective-reference
```

The executable and support hashes are enforced by the script. The support
module is required unchanged and must have SHA-256
`f0505848b34b88b6653cbb8ebe5f74fa8fd5394f4e1727fa93f0b3f2c18374ad`.
The expected generated fixture hash is
`6e070197d3455bdc3dbd13f7f366a51ce93e571f9bdae83315dbac507b74df0c`.
Compare with `native/tests/mission_objectives_original_vectors.txt`, then run
the native `g1_mission_objectives_tests` target against that generated path.

Each fixture row has the nine-value progression context, current owner,
synthetic script shape, objective kind, parameter count/parameters, unit
count, seven fields per indexed unit (present,active,owner,x,y,offsetX,offsetY),
site count and nested site states, followed by seven original outputs:
resume flag,cursor,variant231,phase,mode,objective-active,reset-unit-count.
Site framing is state,group count, then each group's item count and item states.
All synthetic scripts have40 commands, objective at10; shape0 has opcode1 at
30 and36, shape1 at20, shape2 has none.

`0x559b4`, `0x558e4` and `0x430fc` execute unchanged. No success/capture callback,
world mutation, instruction or external import is replaced. Unsupported
instructions, invalid memory and unreached stop addresses fail execution.
The native test compares decision outputs; the actual action-reset helper is
a separate native gameplay subsystem. These are not playthrough results.
