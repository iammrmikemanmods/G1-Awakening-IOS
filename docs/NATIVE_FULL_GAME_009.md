# G1 Awakening native full-game candidate 009 — integrated UI and graphics

## Release intent

The user's requested target is the **whole original G1: Awakening game**
working natively on iPhone XR/iOS 17.5, with its Story, Showdown and Arena
modes, unchanged gameplay data, and PC-port-inspired G1 menu/settings
presentation. Skip Glu introductions and online-service links; open directly
in the G1 game menu.

This branch is an *integrated release candidate*, **not** a certified full
iPhone XR playthrough. The tester reported a successful native Mission 1
test on an earlier build. The existing native logic, fixed 30 ms updates,
save/checkpoint format, audio routing, campaign handoffs and full original
game archive are preserved from Build 008.

## PC comparison used

Reference: saved `G1_Awakening_PC_Pass09_UI_Additive_Checkpoint.zip`,
`UI_PROGRESS_PASS09.md`, and its actual native-game 4K menu captures.

The PC runtime is an ARM game on modified touchHLE; it is **not** an x64
logic recompile. Its current Pass 09 UI is a prototype, not the completed
Build 6: whole-campaign controls, Windows device/audio acceptance and
complete texture work are still open. The native iOS port does **not**
embed that PC compatibility layer. Common intent is source-preserving G1
artwork, straightforward controls, and genuine Classic/Modern texture
selection.

## Candidate 009 application changes

- Open directly in the native profile/menu rather than playing a Glu
  splash or legacy online-service/intro sequence. The original resource
  archive is retained byte-for-byte, including unused legacy assets; the
  app does not display the Glu logo, blog or feedback menu.
- Decode the verified original G1 menu resource 1002 at **480x320** and
  use it behind the main menu, pause, Help, Settings, Credits and mission
  selection. Preserve its aspect ratio on the XR landscape display;
  pillarbox instead of stretching its artwork.
- G1 red/steel native touch buttons and original decoded bitmap headings
  where their complete text fits. Source art has not been remodeled.
- Separate **Settings** with persisted Music and Sound switches, Classic
  vs Modern graphics and optional debug visibility. Ordinary HUD hides
  dev FPS, legend and report button by default. Diagnostics remain
  available from Settings for device acceptance.
- **Classic** keeps exact source texture bytes and the Build 008 sample
  pipeline. **Modern** applies two bounded, independent Scale2x passes
  (Scale4x) to the original 512x512 2D character/terrain-decoration
  sprite sheets, preserving *only* source RGBA palette values, including
  original alpha, then uses nearest presentation of the expanded data.
  Original terrain cell atlases, bitmap font sheets, 3D battle materials,
  campaign logic and RNG are not touched. The setting persists and
  can switch without replacing an active game session. This is
  **not** a completed modern texture repaint, relight or lighting overhaul.
- Native **Help** explains actual iOS touch gameplay and three modes.
  Native **Credits** identify the iammrmikeman faithful fan port and
  acknowledge original rights holders, without obsolete Glu links.
- Native paged mission selection replaces the platform action sheet
  across Story, Showdown and Arena; 8 unlocked missions per page, with
  original campaign authorization still enforced before startup.
- App version 0.9.0/build 9; existing bundle identifier, deployment
  target and save filename/format unchanged.

## Functionality / safety boundaries

Previous native headless playthroughs already complete 17 Story
missions, 8 Showdown missions and the Arena configuration matrix through
the recovered game state. Their feedback is synthetic, not iPhone touch,
UIKit/Metal pixel output or audio. Candidate 009 makes no modifications
to those core gameplay or checkpoint mechanisms.

As part of release validation, build on GitHub Linux and Apple ARM64,
run all portable suites including the new Scale4x unit test, compile
the actual iPhoneOS executable and Metal shaders, and run hosted pixel
probes. Package only the code artifact with the exact pinned user's
source archive and recovered data tables. Verify source identity and
artifact hashes.

**Still required on physical XR:** launch, UI legibility and art layout,
Modern/Classic during active gameplay, optional FPS diagnostics, touch
mission selection across all modes, mission-to-mission transition, saves
across cold relaunch and sustained frame-time behavior. The entire
rendered iOS campaign and all audiovisual details have not yet been
demonstrated on physical hardware.

Preserve 007 and 008 branches and their IPAs. Never overwrite the
user's saved campaign or original IPA.
