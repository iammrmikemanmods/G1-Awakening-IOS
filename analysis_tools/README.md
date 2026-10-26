# Development reference tools

These optional tools preserve how the native reconstruction was checked against
the original program and its data. **They are not included by native CMake, not
dependencies of the cloud native-core build, and not part of the eventual app.**
The normal native tests use retained numerical fixtures and need no original
executable or CPU emulator.

The original executable/IPA, extracted assets and downloaded third-party tools
remain local inputs. `PRESERVATION.json` records the unchanged source hashes and
their paths in the historical research checkpoint.

## Movement comparison: portable command-line tools

`movement/oracle.py` executes the original movement routines with synthetic
state and checks that the original code stays unchanged. It requires Python
(tested with 3.12), a separately installed `unicorn==2.1.4`, and the local
original executable. `movement/make_cases.py` uses the Python standard library.
All input/output paths are explicit arguments.

Extract the original executable from the user's IPA member
`Payload/G1awakening.app/G1awakening`. It must be 956,496 bytes with SHA-256
`0d510516fe3676ee4a0f4dff60ba64e1c5bf79a0c9800f420b1bbdb1c12febfd`.
The oracle rejects a different executable hash. It uses zero instruction
patches and zero function stubs.

For example, replay the retained synthetic cases into a new output directory:

```sh
python3 analysis_tools/movement/oracle.py \
  --binary /path/to/local/G1awakening.armv6 \
  --cases analysis_tools/movement/cases.json \
  --output /tmp/g1-movement-replay/original_results.json

python3 analysis_tools/movement/make_cases.py \
  --cases analysis_tools/movement/cases.json \
  --oracle /tmp/g1-movement-replay/original_results.json \
  --fixture /tmp/g1-movement-replay/movement_cases.txt
```

The expected fixture is 65,806 bytes with SHA-256
`ba6b138459a4016101f8ad22e35564faafa6635defc75437695d26408e0425d3`.
The oracle accepts `--unicorn-dir` for a separate development installation.
The retained `original_results.json` records the actual historical comparison.

## Atlas arithmetic: immutable historical harness

`atlas/quad_oracle_frozen.py` is an exact copy of the harness used for the
recorded atlas comparison. **Its filesystem paths describe the original
research workspace; it is preserved for audit and does not run unchanged from
this relocated directory.** Keep this copy immutable if making a portable
adapter.

It requires Python, external Unicorn 2.1.4, the original executable, locally
extracted descriptor data/manifest, `native/tests/generate_atlas_reference.py`,
and a host build of `atlas_probe`. Its hardcoded binary, audit, probe, package,
import and output paths must be supplied explicitly by a future adapter.
`inspect_assets.py` and `inspect_game_data.py` preserve the original independent
data-audit tools; their original layout and command-line help identify how to
regenerate audit inputs from the user's local IPA.

This comparison preserves original coordinate arithmetic but substitutes six
documented infrastructure boundaries: unwind registration/unregistration,
read-only vector copy/teardown and two GPU uploads. It does not validate GPU
rendering. Seven empty metadata descriptors are excluded from that original
arithmetic claim. See `native/research/atlas_validation/original_quad_oracle.json`
and `native/research/ATLAS_DECODER.md` for exact coverage and limitations.

The native app implementation is the C++ code under `native/`. These analysis
tools do not turn it into an emulator-based product.
