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
