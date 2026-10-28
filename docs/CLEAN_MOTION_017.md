# Build017 — authored 3D motion and source-derived clean artwork

## Starting point and scope

Based on Build016 source `21ab79573f67134d6234ce707210efe0b7ae0477`.
This is a development candidate, not complete original UI parity or a physical
XR validation. No parallel AI agent service was available; the work and
reviews were performed in the main session with real compiler/test processes.
The user's instruction to accept good-looking authored transforms supersedes
waiting for nonexistent original tactical 3D clips. Do not call these recovered
native animation clips or claim an implementation was copied from PC Merge.

## Modern model presentation

- Original ready-pose hierarchy and vertices are immutable. The presenter finds
  a single authored sibling pair of lower-limb groups, checking floor-reaching
  geometry, pivot heights and lateral separation. It also uses a conservative
  optional shoulder pair; the head/face branch is not individually deformed.
- Robot locomotion rotates whole rigid limb subtrees, compensates for the posed
  ground-contact minimum, and derives phase from actual interpolated position.
  Vehicle endpoints follow the same original motion without fake wheel spin.
- Transformation uses a reversible staged rigid-part fold, a short complementary
  screen-space coverage exchange, and an endpoint settle. This is an authored
  approximation, not a part-for-part physically accurate transformation. A
  modest pale-blue highlight reduces the perceptual hard exchange; no opaque
  double model, vertex collapse, nonuniform scaling or invented mesh topology.
- The existing SpriteAnimation state supplies the canonical robot-to-vehicle
  fraction, including reverse playback. The original sprite player still runs
  and owns generation/completion acknowledgements. Rendering never completes
  a game action, changes a turn, consumes RNG, or rewrites a save.
- All 23 robot hierarchies pass the CPU gait-selection audit; 12 models have
  paired 3D form endpoints. Missing alternate endpoints, support effects,
  allocation/model failures and memory-pressure states still retain sprites.
  The 35-degree Modern camera and original facing conventions are preserved.
- Original data CPU probe checks 3,500 frames across facings and both directions
  through canonical phase. Maximum prepared endpoint matrix difference from
  the original posed endpoint is below 1e-5. This is not a GPU playthrough.

## Artwork pipeline, not another pixel-preserving scale pass

`analysis_tools/presentation_017/clean_art.py` uses source colour regions,
curve-fitting and fitted gradients. It rasterizes those paths for existing
UIKit/Metal textures. Tiny source details have a continuous source-image base;
skies/smooth large fields use continuous reconstruction rather than banded
colour quantization. This is a vector-boundary/raster-gradient hybrid, not an
entirely resolution-independent SVG renderer and not neural detail invention.

UI is shared between Classic and Modern; world/character material replacements
are Modern-only. The offline pack is keyed by SHA-256 of the exact original
RGBA image, category and dimensions. UIKit uses 4x reconstructed UI imagery;
Modern M3G materials use 2x images within the existing bounded derived-memory
budget. The original source dimensions, UVs and Sprite3D crop metadata remain
unchanged. Modern M3G samplers now use linear filtering; Classic retains its
source sampling state. Original glyph layout remains unchanged and glyph
rendering enables high-quality interpolation/antialiasing; no font files are
extracted or distributed as a separate pack.

Terrain atlases 693/761/777 are processed per 64px cell. Scenery sprite atlas961
uses the union of all six original scenery descriptors, reconstructing each
rectangle independently. No original grid, collider, mission boundary or
terrain decoration RNG is modified. The previous exterior proposal is not
silently enabled or changed by this work.

The pack is assembled locally from the user's original archive; no original
asset bytes or derived owner textures are committed to GitHub. Runtime lookup
is optional and validates bounded PNG dimensions. A missing/rejected pack
falls back to the earlier source path, never makes a unit invisible.

## Concrete source-format bug fixed

Portrait646 is a 24-bit BI_RGB image, not the 8-bit palette format accepted by
the old shared portrait loader. Some original portrait files also have up to
three whole-file zero padding bytes. `UIBitmap.hpp` dispatches 24-bit explicitly
and trims verified zero padding in a temporary copy before calling the strict
indexed decoder. The original indexed decoder and archive bytes are unchanged.
Malformed headers, out-of-bounds rows and nonzero trailers are rejected.

## Reproduction and verification boundaries

Portable Debug CTest adds authored-motion and UI-BMP regression checks.
`tactical_motion_probe` loads the original archive privately for rig/endpoint
checks and exports private raw triangles for the labelled CPU review video.
Those raw meshes are not included in the public source checkpoint or review
ZIP. `g1_clean_texture_probe` privately emits source image inputs, not fonts.

Hosted Metal checks cover complementary assembly visibility even with texture
REPLACE, legacy pixel behavior, Modern material sampling, shared depth and
SSAA. A separate Foundation probe tests source-hash lookup, missing/corrupt
pack fallback, wrong-dimension rejection and source immutability. No real
UIKit window or physical iPhone behavior is implied by those probes.

Acceptance still needs on-device controls, movement/transformation appearance,
all-character proportions, startup/caches/thermal behavior, saves and campaign
playthrough. Other missing UI/effect work, unsupported 3D alternate forms,
all-mission decorated exterior integration and iOS7–14 support remain open.
