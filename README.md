<div align="center">

# Transformers: G1 Awakening — iOS

### A native return to the original G1 tactical adventure.

**Restoration and modernization by [iammrmikeman](https://github.com/iammrmikemanmods)**

Native ARM64 · Metal rendering · iPhone & iPad · Classic & Modern

[Releases](https://github.com/iammrmikemanmods/G1-Awakening-IOS/releases) · [Install](docs/INSTALL.md) · [Source](https://github.com/iammrmikemanmods/G1-Awakening-IOS/tree/be203a911bc26313615ea450758413e5c9cf6462) · [Roadmap](docs/ROADMAP.md) · [Report a bug](https://github.com/iammrmikemanmods/G1-Awakening-IOS/issues/new/choose)

</div>

---

**G1 Awakening iOS** reconstructs the original mobile game as a native 64-bit application, with a modern presentation layer built around its original missions, characters, tactical rules and artwork. The goal is to bring the game back to current devices without losing its bright Generation 1 identity.

The application compiles C++ and Objective-C++ to ARM64 and renders through Metal. It is **not a packaged ARM32 emulator**, and the game runtime does not require JIT. Original game data is used separately from the new engine source.

> **Development preview, not a finished release.** Earlier builds have been shown running on a physical iPhone XR. The latest packaged candidate is **017R1**, a resource update to Build 017. Its full campaign, installation routes and final artwork are not yet certified on-device. The compiled minimum is **iOS/iPadOS 15.0**, not iOS 7. See [compatibility and evidence](docs/STATUS.md).

## See it running

These are **real screenshots supplied from the iPhone XR**, from the earlier UI-restoration checkpoint identified in the project as Build 012. They are not concept art, simulator mockups or proof of the latest remaster. The visible old layout defects have not been retouched.

| Original-menu restoration | Mission 1 on the tactical map |
| :---: | :---: |
| ![Earlier native iPhone XR capture of the restored G1 main menu](docs/media/xr-menu.webp) | ![Earlier native iPhone XR capture of Mission 1 tactical gameplay](docs/media/xr-gameplay.webp) |

[Capture provenance and screenshot policy](docs/SCREENSHOTS.md)

## Classic identity. Modern presentation.

| System | Classic | Modern |
| --- | --- | --- |
| Tactical gameplay | Original mission and turn rules | The same rules; no visual-mode gameplay advantage |
| Interface | Shared adaptive HUD and installed UI remasters | The same shared UI improvements |
| Tactical Transformers | Original sprite presentation | Original 3D models for supported states, with authored walking/transformation presentation |
| World artwork | Original world materials | Installed source-mapped texture replacements; full art pass is ongoing |
| Rendering | Native-resolution scene rendering | Supersampling requested by default, with device/resource fallbacks |
| Shadows | Original-style presentation | Additional soft contact shadows; not complete directional/self-shadowing |

The current engine includes Story, Showdown and Arena flows, tactical actions, original-data battle scenes, Tech Specs, music/sound paths and checkpoint saving. Automated campaign tests are not a substitute for a complete rendered device playthrough.

Modern mode aims for **clean, bright G1 HD-2D**: readable Transformers, restrained ground detail, crisp mechanical UI, blue water and vivid faction colours. It is not a gloomy remake with heavy fog, invented wear or a different art direction. The new artwork is produced as individual mapped assets with editable masters and seam checks—not flattened concept boards.

## Downloads and source

**Start with the [Releases page](https://github.com/iammrmikemanmods/G1-Awakening-IOS/releases).** Read the asset descriptions before downloading: a source ZIP or native-code artifact is **not** a complete installable IPA. Any release marked source-only requires separately supplied original game resources.

| Item | What it means |
| --- | --- |
| **017R1 packaged candidate** | Version 0.17.0 / build 17, with a new intro and the completed Pass01 resource replacements. A complete package is identified by its filename and SHA-256 in the [release register](docs/RELEASES.md). |
| **Build 017 source** | [Exact compiled commit `be203a9`](https://github.com/iammrmikemanmods/G1-Awakening-IOS/tree/be203a911bc26313615ea450758413e5c9cf6462); [development PR #13](https://github.com/iammrmikemanmods/G1-Awakening-IOS/pull/13). |
| **Block 1 asset checkpoint** | 72 individual asset candidates in a separate source-art package. Review pending; not all included in 017R1. |

**The root `main` engine source still represents an earlier checkpoint.** This front page has been updated without silently merging the development stack. Use the pinned Build 017 source above when reproducing that candidate. [Build instructions](docs/BUILDING.md) explain the distinction.

## Installation options

A complete IPA, compatible device and an appropriate installation/signing method are required. None of the tools below changes the game's compiled OS requirement.

| Method | Suitable setup | Read first |
| --- | --- | --- |
| **TrollStore** | A device/OS combination supported by standard TrollStore, also running iOS 15+ | Standard TrollStore does **not** support stock iOS 17.5.1. TrollStore Lite is a separate jailbreak-dependent route. |
| **AppSync Unified + Filza** | An already jailbroken device with a compatible AppSync package and Filza | The supplied AppSync candidate uses an ad-hoc executable signature, not Apple provisioning. |
| **Sideloadly** | Windows or macOS, an Apple ID and a compatible device | Re-sign the complete IPA. This exact 017R1 route remains unverified; do not treat the AppSync filename as stock-iOS signing. |

### [Follow the step-by-step installation guide](docs/INSTALL.md)

Back up saves before updating. Keep the same installer/signing identity when possible. **Do not uninstall the game just to troubleshoot an update**—that can remove its local data.

## What comes next

The priorities are full original UI/HUD/effect parity; per-character motion and transformation polish; a complete faithful asset library; and coherent visual terrain extensions using native scenery. Extensions must leave the original playable map, collision, objectives and saves unchanged.

[The roadmap](docs/ROADMAP.md) separates implemented systems, art candidates and future work. Legacy iOS 7–14 support and broader Apple-hardware support are goals, not current compatibility claims. There is no promised completion date.

## Help test and contribute

Useful reports include the exact IPA/resource revision, iPhone/iPad model, iOS version, installation method, graphics mode, mission and reproduction steps. Attach a screenshot or short recording where possible; redact personal information and signing credentials.

[Report a bug](https://github.com/iammrmikemanmods/G1-Awakening-IOS/issues/new/choose) · [Read the source/build guide](docs/BUILDING.md) · [Review known limitations](docs/STATUS.md)

## Credits and licensing

Project direction, port and remaster work: **iammrmikeman**. Original game, characters, artwork and music belong to their respective rights holders. This is an independent fan preservation project, not an official Hasbro or Glu release.

New project code is covered by the repository's [MPL-2.0 licence](LICENSE); bundled third-party components keep their own licences. That licence does **not** relicense the original game data, trademarks, music or screenshots. Supply your own legitimately obtained source-game resources; do not upload game dumps, credentials or private saves in issues.

<sub>Project page updated 31 October 2026. Historical engineering notes are preserved in <a href="docs/history/README-before-public-page.md">the previous README</a>.</sub>
