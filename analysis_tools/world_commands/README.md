# Original world-command reference

Development-only verification. This script and Unicorn are never built into,
linked with, or shipped in the native app. No original executable, archive,
text, or image payload is included here.

Install `requirements.txt`, then run from the repository root:

```sh
python analysis_tools/world_commands/world_commands_oracle.py \
  --image /local/path/G1awakening.armv6 \
  --support analysis_tools/mission_progression/oracle.py \
  --output /local/path/world-command-reference
```

The image is the user's extracted ARMv6 executable from the audited iOS1.1.3
IPA. Its required SHA256 is
`0d510516fe3676ee4a0f4dff60ba64e1c5bf79a0c9800f420b1bbdb1c12febfd`.
The support-script SHA256 is
`f0505848b34b88b6653cbb8ebe5f74fa8fd5394f4e1727fa93f0b3f2c18374ad`.
Both are checked before execution. No original libgcc image is needed: the
one signed-modulo import is supplied as explicit truncation-toward-zero
arithmetic. The script has no network access or fixed scratch-path dependency.

The resulting151-row fixture must match
`native/tests/world_commands_original_vectors.txt`, SHA256
`eca49489020d81a467afff1839f91afa4dadc291aa569a3c58eac3a73d5ef656`.
Pass that fixture to `g1_world_commands_tests` for native comparisons.
`REFERENCE.json` lists exact original entries and external boundaries.

The oracle runs original world dispatch, owner rebuilding, type/faction
selection, MT generation, and music selection. It records external presentation
requests and implements bounded storage operations. It does not implement a
renderer, execute a whole mission, or prove Apple/device behavior. The complete
site and map I/O handlers are outside this particular original-function run.
See `native/research/WORLD_COMMANDS.md` for the native consumption contract,
corpus probe, and precise limits.
