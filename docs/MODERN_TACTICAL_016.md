# Build016 — guarded original 3D tactical models and restrained scene materials

Baseline: Build015, source 8a1dad674a08c577ab09882007621b308b165eaf.
Scope: native iOS/iPadOS presentation only; PC Glu work is excluded.

## Actual implementation
- `TacticalModel` decodes the original type-to-M3G resource table, exact material replacements and original robot/car visibility nodes. Its rigid pose is sampled at the same original clip-1 start used by native battle setup. The complete hierarchy is retained; no joint retargeting or vertex deformation is introduced.
- Convert original Z-up meshes to tactical Y-up using a right-handed, positive uniform transform. Place feet on the actual mission terrain height. Source forward +Y was checked against textured CPU previews; facing up/down/left/right preserves the native gameplay orientation.
- Modern inspection camera elevation is 35 degrees to expose more of the face/chest. Classic keeps its previous 45-degree inspection camera. This is a new presentation policy, not recovered original camera behaviour.
- Modern idle/ready units draw real meshes instead of their tactical sprite in the same terrain/depth encoder. Projected mesh bounds feed touch selection. The original sprite playback and original presentation acknowledgements remain intact underneath.
- **Guarded fallback:** walking/movement, transformation, support sequences, unsupported alternate meshes, model-specific failures and memory pressure retain original sprites. This does NOT implement full 3D walking or mechanical transformation animation. Switching between a sprite and mesh may be visually noticeable and needs device review.
- Per-type model caching avoids recreating geometry per frame. Classic never uses the tactical model path. New scene installation clears the caches; failed models retain a visible sprite.
- `enhance_material` applies modest 2x reconstruction to Modern battle environment, character and effect GPU textures. It preserves CPU source-image dimensions and Sprite3D crop/UV metadata. Sky/ground/rock/tree images included in the original environment asset use this same path. All three original environment containers route through it; special images are not guessed by filename.
- Alpha uses premultiplied interpolation and is not sharpened. Environment contrast correction is capped at 3/255, characters 1/255, effects 0; flat gradients get no artificial grain. Maximum derived texture allocation is bounded per uploaded asset. These are source-derived refinements, not newly invented material detail or a neural upscale.

## Local evidence
All 23 original model containers decoded. 35 named robot/car form combinations produced nonempty draw queues in four cardinal directions. Eleven missing alternate-form bindings explicitly remain sprite fallbacks; missing bindings are not substituted with guessed geometry.
The original archive SHA-256 is 663d2888982093ce66b7811ccb7a6ad3acd37fc02ffa85144775b88c39e83cb4.
70/70 assertion-enabled portable tests passed. New tests exercise uniform scale/handedness/ground contact, invalid inputs, fallback gates, alpha-safe material interpolation and unchanged Classic source pixels.
CPU pose previews are generated from the actual prepared triangles/materials. They are NOT Metal or iPhone screenshots. The review renderer preserves original inverted-hull outline culling; disabling it incorrectly obscures the coloured model with its black outline shell.

## Apple gates
Compile iPhoneOS ARM64 at iOS15.0 minimum; run 70 native tests with assertions; run tactical and M3G GPU checks, including new shared-depth occlusion and Modern material/source-identity checks, plus the existing supersampling resolve. Only successful code is signed/packaged. See final validation for actual results.

## Still open
Physical XR/iPad visuals, taps, frame pacing and full first-mission playthrough; 3D walk/transform/deploy clips; per-character readability calibration; exact original camera/animation parity; coherent runtime map extensions and Energon barrier; complete legacy iOS7–14 support. Terrain detail previews remain separate review-only outputs and do not alter any original playable grid, save or mission data.
