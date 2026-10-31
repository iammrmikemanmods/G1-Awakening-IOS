# Status and compatibility

[Back to the project](../README.md) · [Release register](RELEASES.md)

Reviewed **31 October 2026**. Latest packaged candidate in the project record: **017R1**, based on native Build 017. Art Block 1 is a later, separate source-art checkpoint and is not automatically part of that IPA.

## Platform scope

| Property | Current evidence |
| --- | --- |
| Native target | ARM64 iPhoneOS; UIKit, Metal and native audio/video frameworks |
| Device families | iPhone and iPad (`UIDeviceFamily` 1 and 2) |
| Compiled minimum | iOS/iPadOS 15.0; ARM64 and Metal capabilities required |
| Primary device | Earlier build demonstrated on user-supplied iPhone XR captures; reported OS 17.5.1 |
| 017R1 physical test | Not established by this documentation update |
| Newer OS/devices | Test candidates, not blanket compatibility guarantees |
| iOS 7–14 | Not supported by this binary; legacy compatibility remains research |
| macOS / tvOS / visionOS | Not validated release targets |
| Installation | AppSync-oriented package; standard TrollStore and Sideloadly paths documented but exact package tests outstanding |

## Features versus evidence

The development source implements campaign/mode flows, actions, AI, saves, tactical rendering, original-data 3D battles and audio paths. Earlier automated pilots completed Story, Showdown and Arena through synthetic presentation feedback. They are not full rendered/device playthroughs.

[Build 017 PR #13](https://github.com/iammrmikemanmods/G1-Awakening-IOS/pull/13) records **72/72 Linux and 72/72 Apple native tests**, actual iPhoneOS ARM64/shader compilation, and **14 tactical + 64 M3G hosted GPU checks**. Hosted checks use synthetic scenes. The exact compiled source is [`be203a911bc26313615ea450758413e5c9cf6462`](https://github.com/iammrmikemanmods/G1-Awakening-IOS/tree/be203a911bc26313615ea450758413e5c9cf6462).

017R1 preserves that executable. Its local integration record reports a fresh 72-test Linux pass, 27 resource/packaging tests, 88 source-key mappings, 1,024 grass-edge checks and 509 native join types checked. It adds the supplied 23-second intro and 15 remastered regions across eight replacement PNGs. Those are recorded historical checks, not tests rerun merely by updating this page.

## Known limits

The art pass is incomplete; some environment and effect textures retain earlier reconstruction. Thirty-three previously recorded desert/Cybertron join types remain flagged for review. Authored 3D transformations include a brief masked form exchange, and unsupported model/form/support cases fall back to sprites. Contact shadows are not a complete shadow-mapping system. Exterior scenery proposals and the final boundary effect are not installed.

Current-device checks still include UI clipping/touch, original menu/tutorial fidelity, intro/music handoff, character motion quality, frame pacing/heat/memory, complete campaigns and save/resume across app lifecycle events. Report them independently rather than treating every issue as a signing problem.

## Branch layout

`main` contains the visitor documentation and an earlier engine checkpoint. The newer native source remains on the development stack. Documentation publication does not merge draft gameplay changes. Use the pinned commit above for Build 017 reproduction and the [roadmap](ROADMAP.md) for open work. Historical main-branch build evidence remains in [the previous README](history/README-before-public-page.md).
