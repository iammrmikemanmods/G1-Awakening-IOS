# G1 Awakening — native iOS reconstruction

The target is the complete original game as a **native ARM64 app on iPhone XR,
iOS 17.5**, with **1792×828 landscape rendering, 60 Hz presentation, original
gameplay timing, sound, reliable saves and a full campaign playthrough**. The
user signs the IPA with Sideloadly on Windows. Apple compilation runs on a hosted
Mac; the user does not need a local Mac.

**The full native game is unfinished.** This checkpoint connects original
text, touch movement, capture, transformation and combat outcomes to the native
app. Enemy planning, turn rules, mission objectives, campaign progression and
profile persistence have portable implementations; completing their integration
into continuous play remains necessary. A build or component test is not a
completed playthrough or proof of iPhone XR performance.

## Current implementation

| Component | Implemented | Remaining integration or verification |
| --- | --- | --- |
| Original data | Archive, 559 verified payloads, all 140 PNGs, all 24 Vorbis files, all 511 localized strings | Original data stays outside Git |
| Mission scripts | All 30 streams / 803 commands parse; dialogue, timers, camera requests, four objective kinds, completion and campaign rules recovered | General world-changing commands, results, actual save and next-map handoff |
| Human actions | Movement/arrival, capture, transformation and attack connected to GameSession and native touch controls | Upgrade/heal/production and broader mission interaction |
| Combat | Original target, RNG, damage, counterattack, death and score-counter rules | Original 3D battle rendering and all presentation cues; current app shows real outcomes in a native panel |
| Enemy | Original attack/capture/fallback planner, full owner slots, production admission/destination and turn reset/income | Continuous AI action execution and visible turn flow |
| Rendering | Native Metal terrain and sprites, original sprite animation/placement, native screen drawable sizing | General map/roster refresh, style1 terrain, original camera and 3D battle models |
| Audio | Original event dispatcher and resource mapping; native AVAudioEngine host | Remaining game event coverage and actual-device output testing |
| Saving | Versioned campaign profile plus checked atomic file replacement | Live session snapshot, actual results save/handoff, cold-launch continuation |
| Timing | Separate 30 ms simulation scheduler and up to 60 Hz interpolated presentation | Correctness and sustained performance on a physical XR |

The product compiles portable C++ and Objective-C++ directly to ARM64. It reads
original game data. Offline reference tools execute unchanged original
functions only during development; those tools and the ARM32 executable are
not linked or packaged into the app.

## Evidence and build scope

The preceding component checkpoint at
`d11fa64e3a5d7dd62b0aded6e8f38f8d8e651efb` passed all 15 host suites and an actual
Apple ARM64 app build in
[run 40275688702](https://github.com/iammrmikemanmods/G1-Awakening-IOS/actions/runs/40275688702).
Six offscreen Metal pixel checks ran successfully on the hosted Apple GPU.
That run predates the new touch/battle/audio integration in this checkpoint.
See `validation/APPLE_GAMEPLAY_COMPONENT_BUILD.json` for the recorded evidence.

The previously packaged `G1_Awakening_Native_Scene_Test_002.ipa` was built from
`4b5708924b8aa51bf01faec470c33623d1dbb5c0`. It is an earlier scene test and does
not contain this checkpoint's interactions. Its exact validation remains in
`validation/NATIVE_SCENE_IPA_002.json`.

Component reports in `native/research/` distinguish original-function
comparisons, synthetic integration checks, Apple compilation and physical
device evidence. `PORT_STATUS.json` keeps the full-game release gates explicit.
No physical XR playthrough is currently recorded.

## Build and package

A host build requires CMake, a C++17 compiler and zlib:

```sh
cmake -S native -B build/native -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON
cmake --build build/native --parallel 2
ctest --test-dir build/native --output-on-failure --no-tests=error
```

The [workflow](.github/workflows/native-core.yml) builds a real unsigned
`iphoneos` ARM64 app targeting iOS 17.5, checks its Mach-O architecture and
system dependencies, tests profile persistence on macOS, and runs an offscreen
Metal pixel probe when a GPU is available. A skipped GPU test is recorded as a
skip. Original game data is packaged locally, outside the cloud artifact.

After a successful run, package the matching code artifact with the original
local IPA:

```sh
python3 scripts/package-native-scene.py \
  --code-artifact G1-native-game-unsigned-code.zip \
  --source-ipa G1awakening_v1.1.3_os30.ipa \
  --out G1_Awakening_Native_Interaction_Test.ipa \
  --report G1_Awakening_Native_Interaction_Test.validation.json \
  --expected-commit SOURCE_COMMIT_FROM_THE_RUN
```

The script retains its historical filename. It verifies the original source,
new executable, asset hashes and final ZIP contents. It extracts only
`iphone.big` and 480 bytes of terrain data tables; it never copies the original
executable. The result requires Sideloadly signing. Scope and source commit are
also embedded in the app's Info.plist and validation report.

Original IPA SHA-256:

```text
b24fbe5cc4d5cb603189a476c4f81dd2a6ecc18b025eae913262055a7fc443fd
```

Original assets, executable, saves and credentials remain outside Git. Pinned
LodePNG and stb_vorbis code retain their upstream licenses in `native/third_party/`.
All delivered ZIPs include `docs/README_MEMORY_ZIP_POLICY.md` content.

## PC reference and scope

The supplied PC executable was inspected without execution. Its package
contains touchHLE and the unchanged original app files; it supplies a useful
reference but no recovered native gameplay source. The audit is under
`analysis_tools/pc_reference/`. The earlier compatibility-host experiment is
retained only on `archive/compatibility-experiment` and is not the requested
native deliverable. This project does not use the GTA repository.

A full-game completion estimate is not established. The outstanding release
work is continuous enemy turns, complete mission/campaign integration, native
session save/reload, the remaining original rendering/presentation, and actual
XR testing through the whole campaign.
