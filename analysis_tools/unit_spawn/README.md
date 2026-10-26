# Original unit activation reference

Development-only original-function verification, never built into or shipped with the native app. The original executable is a local input and is not included. Install `requirements.txt`, then run:

```sh
python analysis_tools/unit_spawn/unit_spawn_oracle.py --image /local/path/G1awakening.armv6 --support analysis_tools/world/world_oracle.py --output /local/path/reference-output
```

Both original image and support script hashes are enforced. The output fixture should match native/tests/unit_spawn_original_vectors.txt. The native g1_unit_spawn_tests executable takes that fixture path.

The oracle runs full original 0x54016 and its actual activation/terrain/stat/reset callees. Original signed division is supplied as arithmetic; funds string formatting and renderer notifications are recorded external requests. This is not a renderer, game runtime, Apple build or campaign playthrough. See REFERENCE.json and native/research/UNIT_SPAWN.md for exact boundaries.
