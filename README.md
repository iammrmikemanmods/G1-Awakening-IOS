# G1 Awakening — native iOS reconstruction

The target is the complete original game as a **native ARM64 app on iPhone XR,
iOS 17.5**, with **1792×828 landscape rendering, 60 Hz presentation, original
gameplay timing, sound, reliable saves and a full campaign playthrough**. The
user signs the IPA with Sideloadly on Windows. Apple compilation runs on a hosted
Mac; the user does not need a local Mac.

**The full-playthrough release is not yet verified.** The current source
checkpoint connects continuous enemy turns, general world commands, human
actions and production, campaign results/handoff, cold-launch Continue, all
three terrain styles' decorative animation, and the original ordinary M3G
battles. The battle path uses the real models, forms, texture replacements,
cameras, animation clips, shot/hit/destruction effects and completion sequence.
The new Apple build and physical iPhone XR validation are still pending.
Earlier tactical support-fire presentation, original HUD/site-marker/tactical
camera/font fidelity and remaining audio coverage also remain release work.

## Current implementation

| Component | Implemented | Remaining integration or verification |
| --- | --- | --- |
| Original data | Archive,559 verified payloads,140 PNGs,24 Vorbis files,511 localized strings | Original data stays outside Git |
| Missions | All 30 streams / 803 commands, actual world operations and four objective kinds; bounded host pilot completes 14 consecutive Story missions | Remaining continuous campaign/mode traversal and rendered playthrough |
| Human actions | Movement, capture, transformation, Undo, attack, upgrade, heal, production and carrier/tape transitions | Original control/presentation parity |
| Enemy | Continuous production, movement, attack, capture and repair through actual native actions; turn reset/income | Broad gameplay and mission-balance verification |
| Combat | Original damage/counterattack/death rules and connected animated M3G battles; actual controller health, ordered effects and presented-frame completion | Apple/GPU/device output; earlier tactical support-fire sequence |
| Rendering | All 23 unit descriptors and21 actual map/style pairs; native Metal sprites/terrain; all three styles' session-owned decoration; ordinary original 3D scene/model/effect assets | Visual/device validation and original tactical artwork/camera/font fidelity |
| Modes | Story, Showdown and Cybertron Arena with profile gates and explicit Arena faction/opponent choices | Actual end-to-end results, unlock and ending validation |
| Audio | Original event dispatcher, battle shot/hit cues and native AVAudioEngine; persisted Music/Sound preferences | Shared background-music maintenance, remaining coverage and device output |
| Saving | Atomic profile/results/handoff; format 3 checkpoints preserve all gameplay, RNG and terrain/sprite clocks; cold Continue | Physical-device lifecycle testing; busy actions resume from the last durable boundary |
| Timing | Separate 30 ms simulation and up to 60 Hz interpolated tactical/battle display; XR camera aspect adaptation preserves vertical field of view | Sustained physical-XR performance and complete timing validation |

The product compiles portable C++ and Objective-C++ directly to ARM64. It reads
original game data. Offline reference tools execute unchanged original
functions only during development; those tools and the ARM32 executable are
not linked or packaged into the app.

## Evidence and build scope

The preceding native interaction checkpoint at
`5795315e970d34419c739bbd4b81ff2011a9ecd4` passed all 29 host suites, an actual
Apple ARM64 app build and macOS profile-file tests in
[run 40280927071](https://github.com/iammrmikemanmods/G1-Awakening-IOS/actions/runs/40280927071).
Six offscreen Metal pixel checks ran on the hosted Apple GPU. See
`validation/APPLE_NATIVE_INTERACTION_BUILD.json` for exact source/artifact data.
That successful run predates the current continuous-play, resume and animated
battle code. A new recorded Apple run is required. The previous attempt to
commit the prepared campaign checkpoint returned `user rejected MCP tool call`;
no commit or branch update succeeded. The current source is prepared locally
for review, with publication awaiting renewed approval.

The exact staged source passes all 53 portable CTest suites. The final build,
test, mission-entry, battle and continuous-pilot records are collected in
`validation/NATIVE_COMPLETE_HOST_CHECKPOINT.json`, with a separate inventory
of the tested code, fixtures and build files. No implementation bytes were
changed after this staged build. The 74 session-save
checks include actual closed files and fresh sessions, followed by identical
terrain activity, random state and combat results for all three styles. All 30
mission scripts reach their first objective and round-trip their checkpoints;
both faction orders and both opponent settings in Arena produce 45 entries and
540 real world operations. Entry checks do not complete the missions.

The improved bounded input pilot separately completes 14 consecutive Story
missions, indices 0–13, then loses 14 normally. It uses ordinary public player
commands and real native AI, with 689 byte-identical in-memory checkpoint
comparisons after replaying searched command sequences, plus 15 checked
profile-file writes. This pilot writes no checkpoint files; the separate
74-check save suite and 45 cold-entry round trips cover checkpoint persistence.
It never transplants a winning state. Its world/dialogue/battle/results feedback
is synthetic. Missions 15–16
were not reached in that continuous attempt, so it is not a full Story result.

The native battle controller matches 1,225 original updates and 159 original
draw plans. The connected asset adapter exercises 47 bounded model/form/style
and combat-outcome cases. A separate actual GameSession battle drives 534 native
presentation updates and 217 prepared frames, keeps gameplay RNG unchanged,
and retains its real pending token until explicit host feedback. These are
CPU integration results; they do not establish Metal or physical output.

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
system dependencies, runs all portable tests on macOS, compiles the exact M3G
runtime shader for iPhoneOS, and runs separate tactical and M3G offscreen Metal
pixel probes when a GPU is available. A skipped GPU test is recorded as a skip.
Original game data is packaged locally, outside the cloud artifact. The new
M3G Apple checks are prepared and have not yet run.

After a successful run, package the matching code artifact with the original
local IPA:

```sh
python3 scripts/package-native-scene.py \
  --code-artifact G1-native-game-unsigned-code.zip \
  --source-ipa G1awakening_v1.1.3_os30.ipa \
  --out G1_Awakening_Native_Game_Test_005.ipa \
  --report G1_Awakening_Native_Game_Test_005.validation.json \
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
work includes the earlier tactical support-fire presentation, remaining audio
and original UI/artwork fidelity, complete mission/campaign traversal, and
actual XR testing of installation, saves/resume, native resolution and sustained
60 Hz presentation.
