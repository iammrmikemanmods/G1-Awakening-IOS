# Native game test 005 — iPhone XR

`G1_Awakening_Native_Game_Test_005.ipa` is the unsigned native ARM64 game test
package for Sideloadly. It contains the reconstructed C++/Objective-C++ game,
native Metal rendering and AVAudioEngine playback, plus the verified original
game archive and terrain tables. The original ARM32 executable and development
reference tools are not included.

## Build identity

| Item | Value |
| --- | --- |
| App name | G1 Native Test |
| Version / build | 0.5.0 / 5 |
| Compiled source | `083057b20b3b10269ca48e0d9816a62b3214869b` |
| Device / deployment target | iPhone XR / iOS 17.5 |
| Display target | 1792 × 828 landscape, up to 60 presentations per second |
| Simulation | Fixed 30 ms steps; display interpolation does not advance gameplay |
| Package bytes | 7,572,942 |
| Package SHA-256 | `92988b5eedb10149f1863fe3cb4a5ac2799c0fe7a0e946901bfa0fca4b028563` |
| Signing | Unsigned; sign and install with Sideloadly |

The [successful Apple build](https://github.com/iammrmikemanmods/G1-Awakening-IOS/actions/runs/40368043701)
compiled the iPhoneOS ARM64 app and the exact runtime M3G shader. All 55 portable
suites passed on Linux and Apple ARM64. Six tactical and twelve M3G pixel checks
passed on the hosted Apple Paravirtual GPU; neither probe was skipped. These
GPU probes use synthetic geometry, not a full original game scene.

Exact build and package evidence is recorded in
[`APPLE_NATIVE_GAME_005.json`](../validation/APPLE_NATIVE_GAME_005.json) and
[`NATIVE_GAME_IPA_005.json`](../validation/NATIVE_GAME_IPA_005.json). Later
documentation or host-only probe commits do not change the compiled source
identity embedded in this IPA.

## What to test on the XR

1. Sign and install the IPA with Sideloadly, then launch **G1 Native Test** in
   landscape. Start a fresh Story game.
2. Advance the opening dialogue and exercise movement, transformation, attack
   and End Turn. Check that the animated 3D battle finishes and returns control
   to the tactical map, then that the enemy turn finishes normally.
3. Check music and sound during the main menu, tactical play and battles.
   Exercise the in-game Music and Sound settings.
4. After an action has completed, save, close the app and relaunch. Use Continue
   and check unit positions, health, mission progress and the next enemy turn.
   Saving during a busy action retains the last durable boundary.
5. Use **Share test report** after playing on the map and after a 3D battle.
   It exports the actual device and OS, source commit, drawable pixel size,
   requested refresh rate, presented-frame samples, recent pacing statistics,
   campaign state and any recorded native failure.

An XR report should show a 1792-by-828 drawable in landscape and a requested
rate of 60. That requested value is configuration; the measured presentation
statistics are needed to assess delivered performance. A short test report
does not establish sustained performance across an entire campaign.

## Scope and remaining work

The native app includes continuous human and AI turns, the recovered mission
commands and objectives, Story/Showdown/Arena selection, campaign results and
unlocks, checkpoint restoration, original model-based 3D battles, all three
terrain styles and original audio resources. Automated runs use ordinary
public gameplay commands and real native rules. Their world, dialogue, battle
and results acknowledgements are synthetic, so headless completion is kept
separate from a rendered playthrough.

Observed headless coverage includes all 17 Story missions, all 8 Showdown
missions and all 20 Arena map/faction/opponent configurations. Both campaign
endings and the Arena unlock used normal profile progression. The 20 Arena
finishes include wins for either player; they are not all player-0 victories.
See the [Story](../native/research/COMPLETE_STORY_HEADLESS.md) and
[Showdown/Arena](../native/research/COMPLETE_MODES_HEADLESS.md) reports.

This is a development test package. The original tactical support percentage
presentation, original interface/site-marker/font/tactical-camera fidelity and
some original sound triggers remain incomplete. Physical XR installation,
touch interaction, audible output, lifecycle restoration, native resolution,
sustained 60 Hz presentation and a full rendered playthrough have not yet been
observed. `PORT_STATUS.json` retains those release gates as open.

The source review ZIP named `G1_Awakening_Native_Build_005_Source.zip` is an
earlier source checkpoint. Use the compiled commit above when reproducing or
reviewing this IPA. The historical build 002 scene-test IPA is also separate.

All ZIP-format deliverables, including this IPA, preserve
`README_MEMORY_ZIP_POLICY.md`. The copy inside the immutable IPA is the policy
from its compiled source commit; this document records the later completed
Apple build and packaging evidence.
