# G1 Awakening — native iOS reconstruction

The goal is the complete original game running as a **native ARM64 app on iPhone
XR / iOS 17.5**, with **1792×828 landscape rendering, 60 FPS presentation, correct
game timing and reliable saves**. The user signs the resulting IPA with
Sideloadly on a PC; the Apple compilation runs on a hosted Mac.

**The full native game is unfinished.** The current app is a first-mission scene
test: recovered terrain, the two initial animated units, touch range previews,
and native Metal rendering. It stops before the first mission presentation
command. It does not yet implement playable turns, combat, AI, saves, audio or
campaign completion. A test IPA must never be described as the completed port.

## Current native implementation

| Component | Implemented and checked | Boundary |
| --- | --- | --- |
| Resource archive | 559 original payload hashes match | Data reading |
| M3G containers | 36 original inventories match | Model renderer is unfinished |
| Mission framing | 30 streams / 803 commands; original nested opcode-7 grammar | Full command execution is unfinished |
| Initial world | Actual mission315 / map268 / 15×14 cells / two initial units | Stops before command9, opcode3 |
| Movement | Original costs/ranges; 256 cases / 9,092 scalar comparisons | No route execution, undo or turn advancement |
| Terrain | 22 grids, three lookup tables, rules and visual tables; first map's 255 faces match original-function checks | Interior styles0/2; camera-padded border and style1 routing unfinished |
| Sprite geometry | 38 descriptors; original UV/position transforms and type-resource mapping | Original camera hierarchy is unfinished |
| Sprite animation | Millisecond playback; 1,616 original-function cases / 124,432 scalar comparisons | Full gameplay timing remains unverified |
| Sprite placement | Original anchor and S×T×Rx model transform; 130 reference cases | Initial unit state only |
| PNG textures | All140 original images match independent RGBA decoding | No invented/upscaled asset detail |
| iOS integration | UIKit touch/lifecycle, Metal textures/geometry, native display sizing, presented-frame reports | Device execution and sustained60FPS must be measured |

The product compiles recovered code directly to ARM64. It reads original data;
it does not load or execute the old ARM32 program. Offline reference runners
execute original functions only during development and are not linked or
packaged into the app. Source-derived tests and reference records contain
metadata, hashes and bounded test vectors, not the original game executable.

See `PORT_STATUS.json`, the reports in `native/research/`, and
[the native workflow](.github/workflows/native-core.yml) for precise validation
scope. The earlier five-module Apple core build passed at source commit
`7a041985e331696ac174d094bd2a67b1e32e6ab6`
([run40270134442](https://github.com/iammrmikemanmods/G1-Awakening-IOS/actions/runs/40270134442));
that historical result does not certify later app changes.

## Build and package

A host build requires CMake, a C++17 compiler and zlib:

```sh
cmake -S native -B build/native -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON
cmake --build build/native --parallel 2
ctest --test-dir build/native --output-on-failure --no-tests=error
```

The workflow builds an actual unsigned iPhoneOS ARM64 `.app`, checks its Mach-O
architecture/deployment target and system-only dynamic dependencies, and builds
a macOS offscreen Metal pixel probe. A runner with no Metal device records a
skip, never a graphics pass. The code artifact contains no original game assets.

Download the `G1-native-scene-unsigned-code` artifact from a successful app run,
then package it with the original local IPA:

```sh
python3 scripts/package-native-scene.py \
  --code-artifact G1-native-scene-unsigned-code.zip \
  --source-ipa G1awakening_v1.1.3_os30.ipa \
  --out G1_Awakening_Native_Scene_Test.ipa \
  --report G1_Awakening_Native_Scene_Test.validation.json \
  --expected-commit SOURCE_COMMIT_FROM_THE_RUN
```

The packager verifies the original source, new executable, exact asset hashes
and final ZIP contents. It extracts only `iphone.big` plus480 bytes of original
terrain data tables; it never copies the old executable into the new app.
The resulting IPA requires Sideloadly signing. See
[the scene-test instructions](docs/NATIVE_SCENE_TEST.md) for what it can test.

Original source IPA SHA256:

```text
b24fbe5cc4d5cb603189a476c4f81dd2a6ecc18b025eae913262055a7fc443fd
```

Original assets, executable, saves and credentials stay outside Git. The native
PNG codec is unchanged LodePNG at the pinned commit in
`native/third_party/lodepng/UPSTREAM.json`; its Zlib license is preserved.

## PC reference and earlier approach

The supplied PC `G1Awakening.exe` was inspected without execution. Its bundled
launcher package contains touchHLE and all nine unchanged original app files.
That build preserves the original gameplay through its runtime; it does not
supply recovered native gameplay source. Its texture-limit fix and diagnostic
matrix/pixel traces remain useful references. The read-only evidence and
reproduction tool are in `analysis_tools/pc_reference/`.

The former iOS compatibility-host experiment remains only on
`archive/compatibility-experiment`; its cloud run was cancelled. It is not the
native deliverable. This project does not use the GTA repository.

There is no reliable full-game completion estimate yet. The remaining work is
original UI/mission execution, movement actions, turns/combat/AI, model/battle
animation, audio, native save/load and a complete device-tested campaign.
