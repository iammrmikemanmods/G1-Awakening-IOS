# Development reference for the native world bootstrap

This tool executes bounded routines from a locally supplied original G1
Awakening 1.1.3 ARMv6 executable to check reconstructed native C++ behavior.
It is **development-only**. Neither this tool, Unicorn nor the original
executable is built into or shipped with the native iOS app.

The exact original executable and iphone.big hashes are recorded in
REFERENCE.json and enforced before execution. These original files are not
included in this repository. The script accepts explicit paths and has no
scratch-workspace assumptions.

## Run from the repository root

Build the portable native world_probe with the normal host CMake build.
Install external Unicorn 2.1.4 in an isolated Python environment, or supply
its Python package directory with the optional --unicorn-dir argument.

    cmake -S native -B build/native -DCMAKE_BUILD_TYPE=Release
    cmake --build build/native --target world_probe

    python3 analysis_tools/world/world_oracle.py \
      --binary /local/path/G1awakening.armv6 \
      --archive /local/path/iphone.big \
      --native-probe build/native/world_probe \
      --movement-oracle analysis_tools/movement/oracle.py \
      --unicorn-dir /local/path/to/Unicorn-2.1.4/python \
      --output build/world_original_reference.json

The existing movement reference is loaded as a development module and is
required for the two actual first-map integration cases. A libgcc binary is
**not required**. The one reached imported function, ___divsi3 at 0xba288,
is explicitly supplied as signed integer division toward zero. The second
boundary, the original resource loader at 0x507fc, records the original
resource IDs and supplies actual decoded archive lookup bytes. All other
imports fail explicitly.

## Scope of the comparison

The script independently decodes 23 unit definitions and reads the original
resource tables. It executes original owner assignment and both starting
unit resets, compares 66 map/style selections and terrain overrides, then
compares both 210-cell movement fields and entry-cost arrays on the actual
first map.

The original code is mapped read-only and checked unchanged. The test uses
seeded object layouts; the map/style check enters a bounded dispatcher
fragment with an explicitly seeded stack slot. It does not run the original
resource parser, full dispatcher, dialogue, renderer, campaign, or iOS app.
Complete evidence and limits are in native/research/WORLD_BOOTSTRAP.md and
native/research/world_validation/original_world_oracle.json.
