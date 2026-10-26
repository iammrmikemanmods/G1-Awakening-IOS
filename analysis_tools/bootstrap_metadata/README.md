# Original bootstrap metadata reference

Development-only verification. This is never built into or shipped with the native app. No original executable or archive is included.

Install `requirements.txt`, then run from the repository root:

```sh
python analysis_tools/bootstrap_metadata/bootstrap_metadata_oracle.py --image /local/path/G1awakening.armv6 --support analysis_tools/mission_progression/oracle.py --output /local/path/reference-output
```

The script enforces the original executable and unchanged support script hashes reported in REFERENCE.json. It executes two original function-body fragments, with no external function replacement, and emits552synthetic input/output rows. Compare the generated fixture byte-for-byte with native/tests/world_funds_original_vectors.txt, or pass it to g1_world_tests. It does not execute a campaign or an Apple build.
