# Releases and package identities

[Back to the project](../README.md) · [GitHub Releases](https://github.com/iammrmikemanmods/G1-Awakening-IOS/releases) · [Install](INSTALL.md)

**Development previews only.** No full-playthrough stable release is certified. GitHub's automatic source ZIP/tarball is not an IPA. A native-code/evidence ZIP is not a complete game either.

## Published release scope

The initial repository publication is a **Build 017 source/native-code prerelease**. It points to the exact compiled source and can preserve the existing signed-code verification artifact. It excludes original game resources and the full owner-data IPA. Check the actual attached asset list; do not infer that an IPA exists from the tag name.

The complete 017R1 IPA exists in the project's delivered build files, but is **not uploaded by the source-only publication workflow**. A maintainer can attach that exact package after a distribution review; until an `.ipa` is actually attached, visitors should use the source route or contact the maintainer, not download a source ZIP expecting an app.

## 017R1 — remastered resources and new intro

Resource revision of Build 017; app metadata remains **0.17.0 / build 17**. Native source: [`be203a9`](https://github.com/iammrmikemanmods/G1-Awakening-IOS/tree/be203a911bc26313615ea450758413e5c9cf6462).

```text
File: G1_Awakening_iOS_017R1_Remaster_Intro_AppSync.ipa
Size: 37,688,499 bytes
SHA-256: b035acfe0c08aafa715c54f60a59423191046c271328abbca4cd72689dfaed46
```

Eight forest grass cells and seven UI images from completed Pass01 replace eight PNG files in the 88-texture inventory. The other 80 texture replacements are preserved. The new supplied intro is copied without re-encoding. Its actual stream is **1108 × 512 / 30 FPS / 23 seconds**, despite a filename mentioning 3584 × 1656 / 60 FPS. The executable, source game archive, icon set and save logic are unchanged. This is not the complete Block 1 art checkpoint.

## Build 017 — clean-art runtime and authored motion

```text
File: G1_Awakening_Native_UI_017_Filza_AppSync.ipa
Size: 54,132,445 bytes
SHA-256: d1d74b06ec03bf5a6c0a99e034fe2d9854aa7b8cf0dbfc3c95cb079e104a9f2e
Compiled source: be203a911bc26313615ea450758413e5c9cf6462
Executable SHA-256: 2b0b140201e8a7f700f04a7a9c1e7845f2aa576a9620db06cdf4b98100e5741d
```

Adds supported authored tactical gait/form transitions, source-keyed texture loading, Modern sampling fixes and UI decoding improvements. Includes 88 initial texture replacements. Unsupported states fall back to original sprites. Recorded validation: 72 Linux + 72 Apple tests, actual ARM64/shader compilation and hosted synthetic GPU checks. [PR #13](https://github.com/iammrmikemanmods/G1-Awakening-IOS/pull/13) · [Recorded CI run](https://github.com/iammrmikemanmods/G1-Awakening-IOS/actions/runs/40634462289).

## Earlier checkpoints

| Checkpoint | Focus | Record |
| --- | --- | --- |
| 016 | Guarded stationary tactical 3D models and battle material enhancement | [PR #12](https://github.com/iammrmikemanmods/G1-Awakening-IOS/pull/12) |
| 015 | Adaptive UI, universal device family, Modern supersampling/contact shadows | [PR #11](https://github.com/iammrmikemanmods/G1-Awakening-IOS/pull/11) |
| 014 | Original faction-coloured Tech Specs and 3D viewer | [PR #10](https://github.com/iammrmikemanmods/G1-Awakening-IOS/pull/10) |
| 013 | Tactical/dialogue/combat interface recovery | [PR #9](https://github.com/iammrmikemanmods/G1-Awakening-IOS/pull/9) |
| 012 | Menu/Help navigation and source-art controls; earlier XR captures | [PR #8](https://github.com/iammrmikemanmods/G1-Awakening-IOS/pull/8) |

## Asset production is a separate track

Block 1 Checkpoint 01 contains 72 mapped candidates: 54 UI, 17 forest cells and one battle pine. They include editable masters and QA, not automatic final visual approval. Its existence must not be used to claim that all 72 new assets ship in 017R1.

## Maintainer release checklist

Publish source and precise scope before claiming stability. Attach only reviewed packages, preserve their original filenames, record byte counts/SHA-256 and distinguish pre-signing from re-signed hashes. Include source commit, resource revision, installer/device matrix, save/rollback notes and known issues. Keep original build/evidence files recoverable; never replace a release asset silently with different bytes.

For the existing local IPA, use the release attachment UI or GitHub CLI after reviewing its redistribution scope. Do not upload Apple credentials, developer profiles/private keys, owner saves or standalone font files. Publishing a release does not change a private repository's visibility.
