<div align="center">

# Transformers: G1 Awakening — iOS

### The original G1 tactical adventure, rebuilt for iPhone and iPad.

**Native restoration and modernization by [iammrmikeman](https://github.com/iammrmikemanmods)**

Native ARM64 · Metal · Classic & Modern · iPhone & iPad

[Releases](https://github.com/iammrmikemanmods/G1-Awakening-IOS/releases) · [Install](docs/INSTALL.md) · [Screenshots](docs/SCREENSHOTS.md) · [Source](https://github.com/iammrmikemanmods/G1-Awakening-IOS/tree/be203a911bc26313615ea450758413e5c9cf6462) · [Roadmap](docs/ROADMAP.md)

</div>

**G1 Awakening iOS** reconstructs the original mobile game as a native 64-bit application, preserving its missions, characters, turn-based rules and bright Generation 1 identity. The runtime is C++/Objective-C++ with Metal rendering—not a packaged ARM32 emulator. It does not need a JIT session.


## Real iPhone XR captures

Four distinct views from the native iOS port: tactical play, story dialogue, the main menu and the pause menu. These are supplied **earlier UI-restoration captures**, associated with Build 012—not current-remaster promotional renders. Old layout defects are visible and have not been painted out.

| Restored original main menu | Pause menu over the live map |
| :---: | :---: |
| [![Native XR main menu](docs/media/xr-menu.webp)](docs/media/xr-menu.webp) | [![Native XR pause menu](docs/media/xr-pause.webp)](docs/media/xr-pause.webp) |

[Open the gallery and capture provenance](docs/SCREENSHOTS.md). Current-build combat, transformation, Tech Specs and later-mission captures are still needed. Original-PC footage, generated art boards and CPU previews are not labelled as iOS gameplay.

## Classic identity. Modern presentation.

| System | Classic | Modern |
| --- | --- | --- |
| Gameplay | Original mission and turn rules | The same rules and saves |
| Interface | Shared adaptive HUD and installed UI remasters | The same shared UI improvements |
| Tactical Transformers | Original sprites | Supported original 3D forms with authored walking/transformation presentation |
| World artwork | Original materials | Installed source-mapped replacement textures; full art pass ongoing |
| Rendering | Native-resolution scene | Default supersampling request with resource/thermal fallbacks |
| Shadows | Original-style presentation | Added soft contact shadows, not complete directional/self-shadowing |


## Installation

Use a complete IPA and an installer/signing route compatible with your exact device and OS.

| Route | Important distinction |
| --- | --- |
| **TrollStore** | Standard TrollStore supports only specific OS builds; stock iOS 17.5.1 is not one of them. TrollStore Lite is a separate jailbreak-dependent route. |
| **AppSync Unified + Filza** | Requires an already working compatible jailbreak/bootstrap and AppSync package. The IPA retains an ad-hoc signature. |
| **Sideloadly** | Re-sign/provision the complete IPA with an Apple ID on Windows/macOS. This exact release route is not yet device-verified. |

### [Read the step-by-step installation guide](docs/INSTALL.md)


## Testing and contributions

[Report a bug](https://github.com/iammrmikemanmods/G1-Awakening-IOS/issues/new/choose) with the exact IPA/resource revision, device, OS, installer, graphics mode, mission and reproduction steps. Include a screenshot or short recording where useful. Remove private account information, passwords and signing tokens.

## Credits and licensing

Project direction, port and remaster work: **iammrmikeman**. Original game, characters, artwork and music belong to their respective rights holders. Independent fan preservation project; not an official Hasbro or Glu release.

New project code uses [MPL-2.0](LICENSE); third-party components retain their licences. This does not relicense original assets, music, trademarks or screenshots. Do not post game dumps, credentials or private saves in issues.

<sub>Updated 31 October 2026. Earlier engineering notes: <a href="docs/history/README-before-public-page.md">archived README</a>.</sub>
