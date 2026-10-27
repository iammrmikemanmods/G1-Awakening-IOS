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
Build 007 has passed Apple validation and its unsigned native game test IPA
is packaged for Sideloadly. Physical iPhone XR validation is still pending.
Build 007 adds the original first-use support tutorial, covered original bitmap
headings, safe profile migration and presentation-epoch protection across
pauses. All 62 portable suites pass on Linux and Apple ARM64; a fresh complete
headless Story run preserves build 006 gameplay. Source and review are on
[pull request 2](https://github.com/iammrmikemanmods/G1-Awakening-IOS/pull/2).
Original HUD/site-marker/tactical camera and wider font/layout fidelity, plus
remaining sound-event coverage, remain release work.
Mission, battle and menu music maintenance are now connected with the original
playing-state queries and menu exclusions.

## Current implementation

| Component | Implemented | Remaining integration or verification |
| --- | --- | --- |
| Original data | Archive,559 verified payloads,140 PNGs,24 Vorbis files,511 localized strings | Original data stays outside Git |
| Missions | All 30 streams / 803 commands, actual world operations and four objective kinds; bounded host pilot completes all 17 Story missions through the campaign ending | Rendered and physical-device playthrough |
| Human actions | Movement, capture, transformation, Undo, attack, upgrade, heal, production and carrier/tape transitions | Original control/presentation parity |
| Enemy | Continuous production, movement, attack, capture and repair through actual native actions; turn reset/income | Broad gameplay and mission-balance verification |
| Combat | Original damage/counterattack/death rules, tactical support artwork/timing and connected animated M3G battles; actual controller health, ordered effects and presented-frame completion | Actual game-scene GPU/device output and tutorial UI validation |
| Rendering | All 23 unit descriptors and21 actual map/style pairs; native Metal sprites/terrain; all three styles' session-owned decoration; ordinary original 3D scene/model/effect assets | Visual/device validation and original tactical artwork/camera/font fidelity |
| Modes | Story, Showdown and Cybertron Arena with profile gates and explicit Arena faction/opponent choices | Physical-device menu, results and ending validation |
| Audio | Original event dispatcher, battle shot/hit cues, native AVAudioEngine, active mission/battle and menu music maintenance; persisted Music/Sound preferences | Remaining sound-event coverage and device output |
| Saving | Atomic profile/results/handoff; format 3 checkpoints preserve all gameplay, RNG and terrain/sprite clocks; cold Continue; profile-v1 migration with exclusive backup and persisted tutorial flag | Physical-device lifecycle testing; busy actions resume from the last durable boundary |
| Timing | Separate 30 ms simulation and up to 60 Hz interpolated tactical/battle display; XR camera aspect adaptation preserves vertical field of view | Sustained physical-XR performance and complete timing validation |

The product compiles portable C++ and Objective-C++ directly to ARM64. It reads
original game data. Offline reference tools execute unchanged original
functions only during development; those tools and the ARM32 executable are
not linked or packaged into the app.

## Evidence and build scope

Build 007 source `62e29e63b3d881eb57345f0276ad00484abee5b4` adds
2,202 original tutorial cases, 806 save/storage checks, 92 campaign checks,
103 presentation-epoch checks and bounded original bitmap-font decoding.
All 23 actual support banners have complete source-font coverage. Its fresh
17-mission Story run retains all 5,461 build-006 event lines byte for byte;
the UI acknowledgements remain synthetic. See
[build 007 notes](docs/NATIVE_GAME_TEST_007.md) and
`validation/NATIVE_GAME_007_HOST.json`. Apple run
[40419564778](https://github.com/iammrmikemanmods/G1-Awakening-IOS/actions/runs/40419564778)
passed actual iPhoneOS app/runtime shader compilation, 62/62 suites on both
hosts, and 14 tactical/support plus 12 M3G synthetic GPU pixel checks. See
`validation/APPLE_NATIVE_GAME_007.json`; physical-device validation remains
outstanding.

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

**The current package is `G1_Awakening_Native_Game_Test_007.ipa`, version 0.7.0 /
build 7**, 7,611,418 bytes, unsigned for Sideloadly. Its SHA-256 is
`1dd01f50abffa352a0b42a4585d73ab5d78cca0d24becd51d734af67ea193556`.
The compiled source is the PR merge commit
`5671a5323f2cc1044a9afd618219578696191b1e`; its tree is verified identical to
branch source `62e29e63b3d881eb57345f0276ad00484abee5b4`. See
[build 007 device notes](docs/NATIVE_GAME_TEST_007.md),
`validation/NATIVE_GAME_IPA_007.json` and `validation/NATIVE_GAME_007_SOURCE.json`.
Existing build-006 profiles load with an exclusive byte-exact backup before
migration to profile format 2. Gameplay checkpoints remain format 3.

**The previous package is `G1_Awakening_Native_Game_Test_006.ipa`, version 0.6.0 /
build 6**, compiled from `97809786653cbf9e99976b0c69bcac093c5ed148`. It is
7,596,333 bytes, unsigned, and ready for Sideloadly signing. Its SHA-256 is
`ef2a7fce7c50eccbce36c796ea0a030d0386971ed45ba45d6fb249537e3da337`.
The packager verified the ARM64 executable, original data hashes, file inventory
and ZIP contents. See [device test notes](docs/NATIVE_GAME_TEST_006.md) and
`validation/NATIVE_GAME_IPA_006.json`. Installation and a rendered playthrough
remain physical-device checks. Build 005's reports and source remain preserved.

Build 006 passed [Apple run 40415854056](https://github.com/iammrmikemanmods/G1-Awakening-IOS/actions/runs/40415854056):
all 59 portable suites on Linux and Apple ARM64, actual iPhoneOS app and shader
compilation, 14 tactical/support and 12M3G offscreen pixel checks. The eight new
support pixel cases verify crop, palette, sampling, part order and depth
isolation through the runtime renderer on synthetic geometry. The GPU is the
hosted Apple Paravirtual device, not an iPhone XR. See
`validation/APPLE_NATIVE_GAME_006.json`.

Fresh complete 17 Story, 8 Showdown and 20 Arena headless runs retain the previous
baseline outcomes, including 11 player-0 and 9 player-1 Arena wins. They validate
1,097 actual battle support preparations, 286 visible cues and 237 lethal
exchanges while preserving live gameplay and full RNG state. Actual encounters
cover helper counts 0–3; separate original-function/controller fixtures cover
0–6. See `validation/NATIVE_GAME_006_STORY_SUPPORT.json` and
`validation/NATIVE_GAME_006_MODES_SUPPORT.json`. Their presentation feedback is
synthetic and their geometry is CPU-prepared; they do not establish a rendered
physical-device playthrough.

The previously packaged `G1_Awakening_Native_Scene_Test_002.ipa` was built from
`4b5708924b8aa51bf01faec470c33623d1dbb5c0`. It is an earlier scene test and does
not contain this checkpoint's interactions. Its exact validation remains in
`validation/NATIVE_SCENE_IPA_002.json`.

Component reports in `native/research/` distinguish original-function
comparisons, synthetic integration checks, Apple compilation and physical
device evidence. `PORT_STATUS.json` keeps the full-game release gates explicit.
No physical XR playthrough is currently recorded.

Build 006 promotes the bounded evidence under
`native/research/support_presentation_recovery/` and
`native/research/overlay_validation/` into native asset decoding and host
presentation. It retains pre-combat rendering snapshots, exact helper identity
and a separately tested presentation gate, while leaving gameplay/RNG intact.
See [build 006 integration notes](docs/NATIVE_GAME_TEST_006.md),
`validation/NATIVE_GAME_006_HOST.json` and the
[applied recovery guide profile](docs/PORTING_SKILL_PROFILE.md). The historical
research packages and build 005 remain unchanged.

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
  --out G1_Awakening_Native_Game_Test_007.ipa \
  --report G1_Awakening_Native_Game_Test_007.validation.json \
  --expected-commit COMPILED_SOURCE_COMMIT_FROM_APP_VALIDATION
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
work includes tutorial UI/device validation, remaining sound events and
original UI/artwork fidelity, rendered campaign/mode traversal, and
actual XR testing of installation, saves/resume, native resolution and sustained
60 Hz presentation.
