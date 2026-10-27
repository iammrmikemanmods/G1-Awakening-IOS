# G1 Awakening native iOS: original first-mission presentation recovery, Build 013

## Source of truth

- User-owned **G1awakening v1.1.3 iOS IPA**, including SHA-256 pinned source `iphone.big` (`663d2888982093ce66b7811ccb7a6ad3acd37fc02ffa85144775b88c39e83cb4`).
- User's *original-game reference* 2026-10-27 07-11-14.mp4, at 33s (dialogue), 42s (Bumblebee selected and HUD), ~60–93s (cinematic combat), 108s (results), plus supplied Bumblebee/Frenzy statistics screenshots.
- **Not** evidence that anything in Build 013 ran on an iPhone XR. Build 012 XR screenshots establish deficiencies and prove **Build 012**, not 013, has run on a physical XR.

## Actual implementation (UI-only)

1. Replaces the Build 012 top-left debug/legend-style tactical HUD and unsupported generic action strip with a source-coordinate 480×320 **bottom source asset 514 HUD**, proper existing-game health, selected-unit name, ATK/DEF/SPD and faction funds. Resource 874 is the original gridded backing; 709 is the Energon motif. Original selected-unit portrait is read from the legacy indexed BMP group, not generated art. Mission title/objective appear in the HUD in nonselection states, not in a screen-space diagnostic banner.
2. Native touch buttons are positioned in two banks of four, with pause/skip in the top left and end-turn in the top centre using the original source G1 PNG icons. Disabled buttons render the original disabled variants. Actions continue calling the existing `GameSession` methods; gameplay rules and saves are unchanged. When production and tape deployment are both eligible for the selected unit, the one corresponding source location presents both choices (non-original interim arbitration for a collision; never suppress a valid action).
3. Dialogue is positioned as the original 480×93 bottom panel using source 1034 (no stretched full-scene red glass panel). Native text is now compact and page/progress-sensitive, and the speaker portrait loads directly from verified original BMP bank for Bumblebee, Ratchet, Optimus and Megatron. Tapping panel advances; top-left source skip icon remains separate. Eliminates artificial oversized UIKit Back / Continue / Skip dialogue buttons.
4. Combat HUD renders original mechanical status plates source 1038, faction red/purple gridded artwork 874/799, at bottom with names, health and damage numbers sourced from native `M3GBattleStatus`, rather than a generic opaque top overlay. Does **not** assert the M3G battle camera/animation matches the source game.
5. Public game HUD hides debug text, permanent legend and test report buttons when diagnostics are disabled. Internal diagnostics and source save/mission executors are retained.
6. Adds a pure C++ layout contract with geometry assertions for 480×320, iPhone XR-ish 896×414 and other sizes; asset script checks all 25 original UI PNGs and 6 BMP identity/dimensions/SHA-256 directly in the original IPA without exporting the art.

## Remaining gaps — must not be called complete

- Original full-screen Transformer **stats screens** (including rotating models, robot/vehicle stats, quote, cube count and both-side browsing) are **not implemented** by this change.
- Original battle camera choreography, attack animations, damage number placement and cinematic transitions are **not** fully reconstructed/verified by these UI-only changes.
- Original 32-bit menu dispatchers, every icon's source hit box, end-turn/tactical input corner cases, 100% UI screenshot parity, sound timing, and end-to-end iPhone XR playthrough remain unverified.
- Original terrain boundaries / missing energy-tower geometry are separate world-rendering tasks. PC Glu intro is **not in scope**.
- Some rare ambiguous production/deployment action states still use a temporary native action sheet because the original dispatcher for this case is not recovered; no action is dropped.

## Regression gates

- `python scripts/verify-original-presentation-assets.py /path/to/G1awakening_v1.1.3_os30.ipa`
- `cmake -S native -B build -DCMAKE_BUILD_TYPE=Release; cmake --build build; ctest --test-dir build --output-on-failure`
- Build native arm64 iPhoneOS and Metal shaders on Apple CI.
- Install resulting correctly signed complete IPA on the physical iPhone XR, compare screenshot checkpoints for original 33/42/60/108s and confirm touch response, dialogue gate, menu, sound and saves. **Never infer physical verification from CI.**

## Asset policy

No original game artwork/model/audio bytes, original application executable, original IPA, user's opening video or replacement art is committed into GitHub. Runtime decodes the original byte-exact archive from locally assembled user-provided IPA. `README_MEMORY_ZIP_POLICY.md` and SHA manifests protect any exported patch/release.
