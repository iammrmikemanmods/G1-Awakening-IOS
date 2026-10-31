# Roadmap

[Back to the project](../README.md)

The target is a faithful, complete native G1 Awakening with optional modern presentation. Priorities are correctness, recoverable builds, original gameplay and readable bright G1 artwork. This is a sequence of work, not a release-date promise.

## Available in the development line

Native ARM64/Metal code; Story/Showdown/Arena logic and checkpoint saves; restored original UI resources and Tech Specs; adaptive iPhone/iPad presentation; Classic/Modern selection; guarded Modern supersampling; soft contact shadows; supported original 3D tactical forms; authored walking and transformation presentation; and optional source-mapped texture replacements. See [status](STATUS.md) for what is implemented versus device-verified.

## 1. Finish original UI, HUD and effects

- [ ] Verify every original menu/modal transition, touch target, disabled state and navigation route.
- [ ] Finish dialogue, tutorials, turn announcements, damage numbers, combat overlays, results and campaign transitions.
- [ ] Complete missing world structures, including power pylons, and remaining audio/effect cues.
- [ ] Check safe areas and readable scale across iPhones and iPads in both landscape directions.

Completion requires matching original reference interactions plus actual device captures, not just a successful build.

## 2. Complete the faithful modern asset library

- [ ] Finish Block 1: all UI, the full forest terrain family, battle floor/sky/horizon and tactical scenery.
- [ ] Complete desert, Cybertron, portraits/character materials and remaining animated/effect atlases.
- [ ] Preserve original palettes, symbols, composition, UV/crop contracts and intended joins.
- [ ] Keep editable SVG/layered masters, runtime PNGs, source identities and before/after QA per asset.

The first Block 1 checkpoint has **72 candidates**, not 72 finally approved shipped assets. Review each tile at map scale: quiet grass, readable rock shapes and no repeated oversized bushes. Avoid fake detail, excessive wear, heavy fog and cute/generic replacement foliage. Do not crop production assets from generated concept boards.

## 3. Refine 3D tactical Transformers

- [ ] Calibrate facing, scale, ground contact and face/body readability for every character.
- [ ] Improve authored gait and mechanical transformation staging, especially the brief masked form exchange.
- [ ] Recover or author acceptable unsupported alternate/support sequences while keeping safe original-sprite fallbacks.
- [ ] Verify selection, terrain occlusion, frame pacing, temperature and memory on actual hardware.

Preserve body proportions and original game timing. A synthetic/CPU pose review is not an on-device visual approval.

## 4. Extend the scenery, not the playable rules

- [ ] Build per-mission exterior plans from that mission's native terrain and scenery families.
- [ ] Match cliff height, bridges, shores, forest density, rocks, lighting and camera perspective.
- [ ] Add a clear G1 purple/pink Energon-style boundary around the original playable footprint.
- [ ] Validate original paths, collision, objectives, turn logic and saves remain unchanged.

Existing snap-piece/tree/rock proposals are **render-only reviews**, not installed map expansions. Do not mark this complete because a top-down collage looks plausible.

## 5. Compatibility and release quality

- [ ] Complete physical-device playthroughs and save/resume/lifecycle regression tests.
- [ ] Validate full packages through AppSync/Filza, standard TrollStore where compatible, and Sideloadly re-signing separately.
- [ ] Expand the device/OS test matrix; publish exact successful combinations and known failures.
- [ ] Investigate iOS 7–14 support with appropriate renderer/toolchain/API fallbacks. Current code remains iOS 15.0 minimum.
- [ ] Evaluate other Apple platforms only with explicit build/input/runtime work; one universal iPhone/iPad IPA is not a tvOS or macOS port.

## Release gate

A build becomes a recommended release only after its exact source, native executable, original-data identity, optional art pack, signing route and checksum are traceable; installation works on the stated devices; and the advertised gameplay/visual scope has been demonstrated. Save backups and rollback packages remain mandatory.
