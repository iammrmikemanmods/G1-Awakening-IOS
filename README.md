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
The updated Apple build has passed and the unsigned native game test IPA is
packaged for Sideloadly. Physical iPhone XR validation is still pending.
The build006 source now integrates the original tactical support percentage
artwork, helper order and timing before the 3D cinematic. Its Apple validation
and packaging are tracked separately from the verified build005 below.
Original HUD/site-marker/tactical camera/font fidelity, the first-use support
tutorial and remaining sound-event coverage remain release work.
Mission, battle and menu music maintenance are now connected with the original
playing-state queries and menu exclusions.

## Current implementation

| Component | Implemented | Remaining integration or verification |
| --- | --- | --- |
| Original data | Archive,559 verified payloads,140 PNGs,24 Vorbis files,511 localized strings | Original data stays outside Git |
| Missions | All 30 streams / 803 commands, actual world operations and four objective kinds; bounded host pilot completes all 17 Story missions through the campaign ending | Rendered and physical-device playthrough |
| Human actions | Movement, capture, transformation, Undo, attack, upgrade, heal, production and carrier/tape transitions | Original control/presentation parity |
| Enemy | Continuous production, movement, attack, capture and repair through actual native actions; turn reset/income | Broad gameplay and mission-balance verification |
| Combat | Original damage/counterattack/death rules, tactical support artwork/timing and connected animated M3G battles; actual controller health, ordered effects and presented-frame completion | Actual game-scene GPU/device output and original first-use support tutorial |
| Rendering | All 23 unit descriptors and21 actual map/style pairs; native Metal sprites/terrain; all three styles' session-owned decoration; ordinary original 3D scene/model/effect assets | Visual/device validation and original tactical artwork/camera/font fidelity |
| Modes | Story, Showdown and Cybertron Arena with profile gates and explicit Arena faction/opponent choices | Physical-device menu, results and ending validation |
| Audio | Original event dispatcher, battle shot/hit cues, native AVAudioEngine, active mission/battle and menu music maintenance; persisted Music/Sound preferences | Remaining sound-event coverage and device output |
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
battle code. Publication subsequently succeeded at
`c75306907ecea8f2fb1926a5ba3228e3094a0fdf`. Its
[first Apple run](https://github.com/iammrmikemanmods/G1-Awakening-IOS/actions/runs/40365634564)
compiled the ARM64 iPhone app and exact runtime iPhoneOS Metal shader. It passed
52 of 53 Apple portable suites; a camera test incorrectly treated its captured
GNU-host `tanf` results as universal platform-library bytes. The follow-up
separates that boundary while retaining exact matrix comparisons and unchanged
production camera code. The corrected follow-up at
`083057b20b3b10269ca48e0d9816a62b3214869b` passed
[run 40368043701](https://github.com/iammrmikemanmods/G1-Awakening-IOS/actions/runs/40368043701).
All 55 portable suites passed on both Linux and Apple ARM64. The iPhoneOS app
and exact runtime shader compiled, and six tactical plus twelve M3G offscreen
pixel checks passed on the Apple Paravirtual GPU. Both GPU probes used synthetic
geometry. See `validation/APPLE_NATIVE_GAME_005.json`.

The follow-up passes all 55 portable CTest suites, including recovered
mission/battle and menu music maintenance. Current host records are collected
in `validation/NATIVE_GAME_005_FOLLOWUP_HOST.json`. The preceding 53-suite
snapshot remains separately recorded in
`validation/NATIVE_COMPLETE_HOST_CHECKPOINT.json`. The 74 session-save
checks include actual closed files and fresh sessions, followed by identical
terrain activity, random state and combat results for all three styles. All 30
mission scripts reach their first objective and round-trip their checkpoints;
both faction orders and both opponent settings in Arena produce 45 entries and
540 real world operations. Entry checks do not complete the missions.

The improved bounded input pilot completes all 17 Story missions, indices
0–16, from a fresh start and reaches the native campaign ending. It uses
ordinary public player commands and real native AI, with 797 byte-identical
in-memory checkpoint comparisons after replaying searched command sequences,
plus 17 checked profile-file writes. The persisted Story completion flag is
true. This pilot writes no checkpoint files; the separate 74-check save suite
and 45 cold-entry round trips cover checkpoint persistence. It never
transplants a winning state or changes gameplay rules. Its world, dialogue,
battle and results feedback is synthetic, so this is a complete headless
Story path, not a rendered/device playthrough. See
`native/research/COMPLETE_STORY_HEADLESS.md` for the input policy and evidence.

A separate mode pilot completes all eight Showdown missions from the actual
completed Story profile, writes eight mission results and unlocks Arena through
the native campaign ending. All twenty Arena configurations (five maps, two
factions, human or AI opponent) finish normally with unchanged profile bytes.
The Arena results include eleven player-0 and nine player-1 wins. These runs
use public gameplay commands and synthetic presentation acknowledgements; they
do not establish rendering or physical-device play. See
`native/research/COMPLETE_MODES_HEADLESS.md` for exact inputs and results.

The native battle controller matches 1,225 original updates and 159 original
draw plans. The connected asset adapter exercises 47 bounded model/form/style
and combat-outcome cases. A separate actual GameSession battle drives 534 native
presentation updates and 217 prepared frames, keeps gameplay RNG unchanged,
and retains its real pending token until explicit host feedback. These are
CPU integration results; they do not establish Metal or physical output.

**The current package is `G1_Awakening_Native_Game_Test_005.ipa`, version 0.5.0 /
build 5**, compiled from `083057b20b3b10269ca48e0d9816a62b3214869b`. It is 7,572,942
bytes, unsigned, and ready for Sideloadly signing. Its SHA-256 is
`92988b5eedb10149f1863fe3cb4a5ac2799c0fe7a0e946901bfa0fca4b028563`.
The packager verified the ARM64 executable, original data hashes, file inventory
and ZIP contents. See [device test notes](docs/NATIVE_GAME_TEST_005.md) and
`validation/NATIVE_GAME_IPA_005.json`. Installation and a rendered playthrough
remain physical-device checks.

The previously packaged `G1_Awakening_Native_Scene_Test_002.ipa` was built from
`4b5708924b8aa51bf01faec470c33623d1dbb5c0`. It is an earlier scene test and does
not contain this checkpoint's interactions. Its exact validation remains in
`validation/NATIVE_SCENE_IPA_002.json`.

Component reports in `native/research/` distinguish original-function
comparisons, synthetic integration checks, Apple compilation and physical
device evidence. `PORT_STATUS.json` keeps the full-game release gates explicit.
No physical XR playthrough is currently recorded.

Build006 promotes the bounded evidence under
`native/research/support_presentation_recovery/` and
`native/research/overlay_validation/` into native asset decoding and host
presentation. It retains pre-combat rendering snapshots, exact helper identity
and a separately tested presentation gate, while leaving gameplay/RNG intact.
See [build006 integration notes](docs/NATIVE_GAME_TEST_006.md),
`validation/NATIVE_GAME_006_HOST.json` and the
[applied recovery guide profile](docs/PORTING_SKILL_PROFILE.md). The historical
research packages and build005 remain unchanged.

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
Original game data is packaged locally, outside the cloud artifact. The first
M3G Apple pixel checks were blocked by the preceding camera-test failure;
the corrected follow-up ran and passed all 12 planned M3G pixel checks.

After a successful run, package the matching code artifact with the original
local IPA:

```sh
python3 scripts/package-native-scene.py \
  --code-artifact G1-native-game-unsigned-code.zip \
  --source-ipa G1awakening_v1.1.3_os30.ipa \
  --out G1_Awakening_Native_Game_Test_006.ipa \
  --report G1_Awakening_Native_Game_Test_006.validation.json \
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
work includes the original first-use support tutorial, remaining sound events
and original UI/artwork fidelity, rendered campaign/mode traversal, and
actual XR testing of installation, saves/resume, native resolution and sustained
60 Hz presentation.
