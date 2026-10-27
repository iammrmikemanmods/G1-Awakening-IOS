# G1 Awakening iOS — native original front-end restoration, Build011

## Scope: a port, not a redesign

The product is the original G1: Awakening 32-bit game reconstructed into
**native ARM64 iPhoneOS**, retaining its 32-bit game's menus, artwork, HUD
visual vocabulary, UI flows, campaign rules, combat and resource files.
Neither a touchHLE/ARM32 compatibility runtime nor AI-created menu skins
are included. Source gameplay and saves remain unchanged.

Approved new content: the user's exact 23.0-second **1792×828/60fps**
replacement intro cinematic (with original supplied AAC stereo), optional
source-preserving enhanced texture rendering, removing Glu startup/online
services, and public-facing credit to **iammrmikeman**. The author has
explicitly rejected a front-end redesign.

Source-of-truth comparison: the original IPA `G1awakening_v1.1.3_os30.ipa`
and the PC port's frozen `G1_Awakening_PC_Pass09_UI_Additive_Checkpoint.zip`.
PC Pass09 still executes the original binary under touchHLE, unlike this
native iOS code, but its read-only original menu data and screenshot
observations are useful fidelity targets. It is not proof that the PC and
native UI states share all the same original callbacks.

## Real Build011 changes

1. **Original G1 main-menu backplate**, original archive resource1002,
   480×320 PNG, including source title logo, red menu region, silver
   rails, and Optimus/Megatron portraits. Title occupies the same
   native original blank label rectangle. No fake red UI strip, tint,
   overlay frame or reskin overwrites it. Letterboxing preserves its
   aspect on XR without stretching character portraits.
2. **Functional native touch menu entries overlay the original red menu
   area**, instead of a disconnected row at the bottom of a developer
   results sheet. Original bitmap-font glyph plans render labels when
   complete; readable text fallback remains for unsupported names.
   Touch routes to the existing checked Story/Showdown/Arena/Profile/
   Settings/Continue commands and does not mutate the native game
   state directly.
3. **Original source HUD icons and frame material**, loaded from original
   verified archive IDs. Gameplay action buttons retain their
   authoritative action selectors, but render 52/60×49px source art;
   the original 298×62px HUD frame and 480×93px dialogue panel art
   are now drawn using source nine-slice borders rather than fabricated
   rounded UIKit rectangles. Dialogue's heading uses the already
   recovered native bitmap-font adapter.
4. Help/Credits receive an independent scrollable text view in the
   original G1 menu, with their Back action positioned below the
   scroll area. Settings and mission selection no longer obscure the
   main artwork with unrelated panel backgrounds.
5. **Native 23-second XR intro**: the supplied video
   `G1OpeningXR.mp4` plays through AVFoundation and AVPlayerLayer
   at native Retina size, preserves its AAC audio, can be skipped by
   tapping, pauses/resumes during iOS lifecycle interruptions and
   leads into the already-loaded native main menu. Menu music is held
   until the cinematic exits, preventing overlapping music.
   The old Glu film and launch screen are never called.
6. The existing exact-data packager now requires `--startup-video`
   for native version11, validates SHA256
   `86a1a9a559843e2ab13e8f513617c8c63e29ef6cd56fe0f6a0446fab7e3911d6`
   and includes the MP4 alongside the original `iphone.big`, six
   original icon PNGs, terrain static tables and ARM64 binary.
   **The MP4 and source copyrighted PNGs are not committed to GitHub.**

This does not introduce any AI-generated scenery. The earlier concern
about black areas at grid edges is a separate renderer/terrain extent
task, **not** a prompt to generate an image as background.

## Critical remaining parity gaps

The native port already implements native GameSession, AI, full campaign
modes and 3D battle logic, but the original 32-bit front-end's exact
menu selection automata, original site/pylon geometry, tactical camera
projection and scene hierarchy, all scrolling/HUD layout rules, remaining
native audio routes and full original results/UI timing are still
independent parity work. The introduction and new menu rendering
do not recover those behaviours automatically.

**No complete iPhone XR on-device rendered campaign has been recorded.**
Host-native Story17/Showdown8/Arena20 pilots and hosted Metal synthetic
pixel probes have narrower scopes. Do not call this a finished
32→64 native conversion or guarantee a full issue-free playthrough
on hardware based on a passing source build.

## Build gate

Compile on Apple iPhoneOS ARM64 and hosted Apple ARM64/Linux; run all
portable CTest suites and hosted Metal probes. Package the exact
compiled tree, original user archive, 480 bytes terrain tables, six
original icon files and the supplied video. Do not overwrite the
last working Filza/AppSync-signed Build010. Produce separate signed
Filza build after Apple compilation using a standalone Mach-O signature
and `application-identifier=org.g1awakening.native.test`.


## Verified Build011 source, native Apple compile and signed IPA

The signed iPhone package was built from the same reviewed production
source tree, without changing core gameplay, saves, assets or controls
after compilation:

| Evidence | Exact result |
|---|---|
| Reviewed source commit | `3025e446283d55199feb2b2017fc73fa16f3d6c2` |
| Compiled PR merge commit | `5db26ba75ae5175c9653aadadef83a78de75dae6` |
| Identical Git tree | `c8d697ae9ee186384659fb91a7779e8101d0d8ca` |
| Linux+Apple workflow | [40448818218](https://github.com/iammrmikemanmods/G1-Awakening-IOS/actions/runs/40448818218) — success |
| Portable suites | **63/63 Linux and 63/63 Apple ARM64** |
| Hosted GPU probe | 14 tactical/support + 12 M3G checks passed with synthetic geometry |
| iPhoneOS app / shader | Both compiled successfully with iPhoneOS17.5 ARM64 target |
| Unsigned code artifact | `12709905179`, SHA256 `5df47e932ba9c07d41ff41cc19088b263ae2baa1e571d34fa61ccac233f0a38d` |
| Signed-code workflow | [40449223649](https://github.com/iammrmikemanmods/G1-Awakening-IOS/actions/runs/40449223649) — success |
| Signed-code artifact | `12710305079`, SHA256 `d77b2b085b94612a2ff6a5ee5d601c558b9be29a0cfcf8cd57fcbb2f3a4cd0d5` |

The native ARM64 compiled executable was already verified through the
Apple app test. Only its **ad-hoc signature** was added separately with
`application-identifier=org.g1awakening.native.test` and
`get-task-allow=true`, using Apple's `codesign` on the standalone
Mach-O, not the incomplete `.app`, to avoid stale resource seals.

**User-installable Filza/AppSync variant:**

`G1_Awakening_Native_G1_UI_011_Filza_AppSync.ipa`

- Size: **39,557,427 bytes**
- SHA256: `fe4f3f66b4349f24fa62dfd6b135db421b2bea1476b5d27130c844efe9193121`
- Minimum iOS17.5, native ARM64, version0.11.0/build11.
- Original user source `iphone.big` SHA256 remains
  `663d2888982093ce66b7811ccb7a6ad3acd37fc02ffa85144775b88c39e83cb4`.
- Original source `1002` menu art, `1004` HUD frame, `1034`
  dialogue frame and ten actual source PNG action icons validated by
  key, SHA and exact geometry (14 source art contracts).
- The new user startup `G1OpeningXR.mp4` is embedded byte-exact:
  31,809,816 bytes, SHA256
  `86a1a9a559843e2ab13e8f513617c8c63e29ef6cd56fe0f6a0446fab7e3911d6`,
  H.264 1792×828 at60fps, AAC stereo48kHz, 23s.
- ZIP member inventory and CRCs verified. Comparing unsigned and
  AppSync variants, **only**
  `Payload/G1AwakeningNative.app/G1AwakeningNative` differs (signature).
  Film, icons, original data, metadata, license text and source provenance
  are otherwise byte-for-byte identical.
- Source archive, movie and original game payloads were never uploaded
  into Git history.

**This is still an integration candidate**, not a finished fully
parity-matched native original. Apple hosted probes did not draw a full
G1 in-game UIKit screenshot, and the signed Filza IPA has not been
installed on a physical XR from this session. Original front-end
automata, full results/HUD behaviours, energy/power station models,
native tactical camera parity, game audio playback through a real
iPhone speaker and full rendered 17+8+Arena progression are not yet
certified. Do not infer them from the established *headless* campaign
results or synthetic Metal checks.

Machine-readable validation is supplied separately as
`G1_Awakening_Native_UI_011_Validation.json` with the signed IPA.
