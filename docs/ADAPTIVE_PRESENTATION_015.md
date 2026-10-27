# Build 015 — adaptive presentation and owner-reviewed visual work

Baseline: Build014 branch `feature/native-tech-specs-014`, immutable head
`0ea4a23fec90d4a66830b4686d15c72f4ec2e97c`.
This is a development candidate, not a declaration that every original screen
or every supported device has been validated.

## User requirements retained

- Faithful original G1 interface, native execution, no PC Glu-intro work.
- Shared enhanced UI in Classic and Modern; Modern adds scene quality.
- One universal iPhone/iPad package with live window/safe-area/capability sizing.
- Long-term iOS 7 (first 64-bit iOS) through current iOS. This iteration can
  compile against iOS 15.0; **iOS 7–14 are not supported by this candidate**.
- Environment upscaling uses original assets only. Decorative map extensions
  and a purple/pink Energon boundary need review and must not enlarge gameplay.
- Three requested workstreams are recorded below. No actual subagents were
  available or launched in this session. Automated compiler/test jobs are not
  represented as AI workers.

## Implemented — track 1: shared UI/HUD

`AdaptivePresentation.hpp` uses the actual view bounds and safe-area insets,
not a finite table of handset identifiers. It recomputes on layout changes.
Portraits, glyphs, models and buttons retain aspect ratio; only decorative
panel interiors/rails extend. Source corner artwork is retained. Menus fill
the view, controls remain in the safe area, and gameplay is visible through
empty regions of the full-screen control container (passthrough hit testing).

Original UI sheets and individual bitmap glyphs are derived at 4x in both
Classic and Modern, with source-pixel metrics preserved. All twelve original
font banks now decode, including their source red/purple colours, translucent
white and the actual orange outlined damage-number bank. No substituted font
files or new painted G1 artwork are shipped. The shared bitmap decoder accepts
only audited PNG/BMP variants and validates resource identity and geometry.

Damage amounts still come from the existing battle status. Their anchor is
projected from the struck actor's actual posed mesh; camera flips therefore do
not require hard-coded left/right screen positions. No gameplay RNG or battle
result is invented. The damage lifetime uses the original presentation clock.
Mission results now include actual units KO'd, units lost and turns taken.
A saved-progress message is shown only after the campaign controller confirms
its file write. These changes do not prove exact original results-frame parity.

## Implemented — track 2: Modern render quality

Modern requests 1.5x per axis (2.25x display-pixel area), renders the game into
real larger Metal colour/depth targets and downsamples into the native drawable.
This is supersampling, not an MSAA-label substitution. UI stays at display
resolution. Memory budgets, texture limits, Low Power Mode, serious thermal
state, memory warnings and allocation failure can reduce the scene to native
resolution. XR-size default is 2688x1242 for a 1792x828 drawable. Sustained XR
frame rate/thermal behaviour is **not measured** by this source change.

Modern adds soft ground-contact blobs. They are not directional shadow maps,
self-shadowing or a fully reconstructed original lighting system. Higher-quality
3D tactical-map unit replacement has **not** been enabled; the already-native
3D battle/Tech Specs paths remain. Full 3D map replacement still needs animation,
map-picking, contact-height and device-performance parity.

## Implemented/proposed — track 3: source-only world work

Terrain atlas cells are upscaled independently to avoid unrelated cell colours
bleeding at tile edges. The original files remain unchanged. The source-only
first-mission comparison and snap-piece kit are separate owner-review outputs.
`VisualBorder.hpp` validates outside-only placements, a bounded extension ring,
original mission palette, duplicate positions and original boundary coordinates.
The first-mission prototype is **not integrated into gameplay or enabled**.

The top-down preview omits 3D cliff faces, sprite depth and animated water. It is
not an iPhone screenshot or a claim that all missions have been extended. Purple/
pink border beams in the preview mark the unchanged original playable footprint;
these cosmetic shapes have no collision, selection, pathfinding or save role.
Other mission themes, buildings and bridge socket validation remain necessary.

## Automated checks and release gates

- 69 portable CTests currently pass in a Debug build (assertions active).
- Geometry cases include phone, XR, notched phone, tablet and window sizes;
  non-landscape cases test the geometry helper, **not** supported portrait UI.
- Independent-cell upscaling, colour isolation, shadow alpha, exterior-only
  placement rejection and actual posed damage-anchor projection have tests.
- Owner-data probe decodes all 12 font banks from the unchanged `iphone.big`.
- Apple app compilation and actual Metal GPU probes must pass before publishing
  a new signed IPA. GPU probes are synthetic and do not certify game art/UI.
- Full XR/iPad install, touch, safe-area screenshots, sound, saves, campaign,
  thermal behaviour and memory testing are still physical-device gates.

## Still open / not hidden by a successful compile

Original modal/results/tutorial/transition visual parity; some original map
objects and energy towers; complete 3D tactical units; directional shadowing;
all-mission decorative extensions and final beam art; iOS 7–14 backend/toolchain;
macOS-native/tvOS/watchOS/visionOS targets. A universal iOS device-family setting
is not a claim that every Apple operating system is supported.
