# Native M3G camera projection and view transform

`M3GCamera` adds a portable decoder for the original Camera bodies and the
projection/view matrices needed by the native Metal renderer. It leaves
camera selection, runtime hierarchy edits, animation, viewport policy, and
battle completion with their separate owners. It does not change the frozen
M3G scene decoder, animation sampler, Metal renderer, or current app.

## Public contract

`decode_m3g_cameras(bytes)` returns Camera projection records indexed by
their real M3G object number. It first invokes the existing scene validator,
then reads Camera bodies, preserving the serialized projection type and
parameters. GENERIC matrices are transposed once from file row-major order
to the native column-major layout. Camera names and duplicate user IDs do
not become implicit selection rules.

`m3g_camera_projection_matrix(camera)` returns the original clip-space
projection. The three types are GENERIC48, PARALLEL49, and PERSPECTIVE50.
Perspective parameters are vertical degrees, aspect, near, and far; parallel
parameters replace degrees with view-volume height. The aspect ratio is not
silently changed to fit the host screen.

`m3g_camera_view_matrix(camera_to_world)` computes the inverse of the supplied
finite affine matrix. It accepts authored scale/rotation/translation and
rejects singular, numerically ill-conditioned, non-affine, nonfinite, or
unrepresentable results. A determinant guard scales its roundoff bound to
the three-by-three basis magnitude; an exact linear dependence that leaves
a small nonzero double-precision cofactor residual is still rejected. The
inverse uses double-precision intermediate cofactors before returning
binary32; this is mathematically checked, not claimed bit-identical to the
original engine's inverse routine.

`m3g_camera_metal_view_projection(camera, camera_to_world)` multiplies the
projection by that inverse, then changes only clip-space Z with
`z_new = (z_old + w) / 2`. It does not flip an axis or substitute placement.
The caller must supply the actual animated world transform and a matching
single-sample render pass/viewport for `MetalM3GRenderer`.

The primary M3G Camera specification defines the camera's local forward
direction as negative Z, the inherited node transforms, and the original
clip-depth interval. It also defines the projection parameter order and
matrix forms: [Nokia M3G 1.1 Camera reference](https://wupp.cc/j2meapi/JSR_184_Mobile_3D_Graphics_API_1_1/javax/microedition/m3g/Camera.html).
Apple specifies Metal's normalized depth interval in the
[Metal Programming Guide, viewport coordinates](https://developer.apple.com/library/archive/documentation/Miscellaneous/Conceptual/MetalProgrammingGuide/Render-Ctx/Render-Ctx.html).
The depth conversion is a host API conversion, not a recovered change to
the game's camera data.

## Original projection evidence

The original `CssCamera` getter at `0x8c4b4` calls dirty projection rebuild
`0x8c2c2` and returns the matrix at internal Camera offset `0xa4`.

| Field / address | Original meaning |
| --- | --- |
| Camera `+0x9c` | Projection type 48 / 49 / 50 |
| Camera `+0xa0` | Rebuild flag |
| Camera `+0xe8` | Perspective vertical degrees |
| Camera `+0xec` | Parallel view-volume height |
| Camera `+0xf0` | Aspect ratio |
| Camera `+0xf4` / `+0xf8` | Near / far distance |
| `0x8c310..0x8c3a8` | Parallel projection arithmetic and matrix construction |
| `0x8c3b4..0x8c460` | Perspective arithmetic and matrix construction |
| `0x8c4c4..0x8c5c2` | Serialized camera loading and parameter checks |

The native implementation preserves the original arithmetic order. Parallel
Y scale is computed as `(1 / height) + (1 / height)`, followed by division by
aspect for X. Perspective computes the argument to platform `tanf` with
three successive binary32 multiplications, using bits `0x3c8efa35`,
`0x4e000000`, and `0x30800000`, then computes `1 / tanf(argument)` and divides
by aspect. Depth terms retain the original addition/multiplication/division
order. Near and far may be reversed. The original loader's absolute
separation check uses float bits `0x377ba882`; perspective additionally
requires positive clipping distances and a field of view strictly below
180 degrees.

The matrix constructor dispatch pointers are explicitly bound to the
symbol-identified original functions for the reference run:

- `0xd2304 → 0x99979`, `CssMatrix::C1(float × 16)`.
- `0xd2308 → 0x99939`, `CssMatrix::C2(float × 16)`.

The constructor body at `0x99938` stores the 16 supplied values directly in
column-major matrix order; the original copy at `0x94d22` installs that
matrix in the Camera. Only data bindings are seeded. No original instruction
is patched.

## Validation

The focused C++ test compiled with `-std=c++17 -O2 -Wall -Wextra -Wconversion
-Werror` and passed 12 original projection cases / 192 exact binary32 scalar
comparisons, plus 28 native contracts. The contracts cover actual serialized
parameter order, a nonsymmetric generic matrix's transpose, an affine
camera inverse, near/far Metal depth mapping, and rejected malformed or
singular inputs.

The original reference executes `0x8c4b4`, `0x8c2c2`, both original matrix
constructors, the copy routine, and the original ARMv6 libgcc arithmetic.
Platform `tanf` is a real host libm single-precision boundary; external
`memcpy` and nonthrowing unwind bookkeeping are also explicit boundaries.
Main and libgcc instruction regions are checked unchanged after every call.
Historical iOS libm bit identity is not claimed. An Apple-side numerical
difference must be attributed before changing this exact comparison gate.

The native body decoder separately passed all 27 model/scene files in the
independent corpus audit: **73 Cameras / 365 exact type-and-parameter
comparisons**. That comparison uses the actual private asset hashes and
does not embed their payloads into the report or tests. Its three battle
scenes and 24 model table entries are the scope of this corpus; other game
assets are not silently included in the claim.

Evidence files:

- `m3g_validation/original_camera_projection.json`: original synthetic
  projection calls and explicit host-math boundaries.
- `m3g_validation/camera_projection_native.json`: native focused comparison.
- `m3g_validation/camera_corpus_native.json`: actual asset decoder parity.
- `m3g_validation/battle_corpus_coverage.json`: independent metadata source.

No Apple/GPU execution, device frame rate, live camera choice, complete
cinematic, or full playthrough is established by this slice.

## Reproduction and integration

Development-only original reference, with the user's private inputs:

~~~bash
python3 analysis_tools/m3g/camera_oracle.py \
  --binary /private/G1awakening.armv6 \
  --libgcc /private/libgcc_s.1.dylib \
  --unicorn-dir /path/to/unicorn/site-packages \
  --output /tmp/original_camera_projection.json \
  --fixture-header /tmp/m3g_camera_fixture.hpp
~~~

It requires the existing `analysis_tools/sprite/render_oracle.py` loader and
Unicorn 2.1.4. Those tools are excluded from all native library/app targets.

The core addition is `src/M3GCamera.cpp`. The host test is
`tests/m3g_camera_test.cpp`, named `m3g_camera_projection_contract`, with no
arguments. It uses `tests/m3g_camera_fixture.hpp` and the existing synthetic
`tests/m3g_animation_fixture.hpp`. The optional tool is
`tools/m3g_camera_probe.cpp`; it emits camera/parameter/matrix bits for one
explicit local M3G input. `analysis_tools/m3g/camera_validate.py` compares
that output to the independent corpus metadata.
