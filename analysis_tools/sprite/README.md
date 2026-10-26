# Development-only sprite references

These scripts execute narrowly selected original functions for comparison with the portable C++ implementation. They are **excluded from CMake, the native library, and the app**. No original executable, guest library, external emulator package, original image, or descriptor payload is stored here.

## Inputs

- Python 3 and external Unicorn **2.1.4**. `--unicorn-dir` is the directory containing its Python package. The audited wheel SHA-256 was `9d6e6dea140560de4ebd8446661f7ef84a357d428c14a3ef09dacd306ec8c239`.
- The explicitly supplied original `G1awakening` executable, SHA-256 `0d510516fe3676ee4a0f4dff60ba64e1c5bf79a0c9800f420b1bbdb1c12febfd`.
- For render/placement/matrix references, supplied fat `libgcc_s.1.dylib`, SHA-256 `d758fbf1ac952532955d62866bd02df55315c0599f64bdd978ff941fccbdcf83`; the loader selects its ARMv6 subtype-6 slice.
- For the animation corpus, the separately produced asset audit directory containing `results/asset_manifest.json` and the extracted original descriptor payloads under `results/extracted/bin`. The original asset audit tools are separate input preparation; this directory is not a distributable game-asset bundle.
- GCC or Clang supporting C++17 to build the two small native probes.

The scripts validate input identities. The frozen `render_oracle.py` is also imported by terrain geometry analysis; preserve it byte-for-byte when copying these tools. Its SHA-256 is `f3fa8b4d3df77c82bfc3d249109f650e3ec6e9c5421fd29dcf81adb3d3e1124c`.

## Reproduce from the repository root

Set `G1_ORIGINAL_IMAGE`, `G1_LIBGCC`, `G1_UNICORN_PYTHON` and `G1_ASSET_AUDIT` to the local inputs above. Use a disposable output directory; these commands do not modify the original inputs.

```sh
mkdir -p /tmp/g1-sprite-check
c++ -std=c++17 -O2 -Wall -Wextra -Wconversion -Werror -I native/include \
  native/src/SpriteAnimation.cpp analysis_tools/sprite/animation_probe.cpp \
  -o /tmp/g1-sprite-check/animation_probe
c++ -std=c++17 -O2 -Wall -Wextra -Wconversion -Werror -I native/include \
  native/src/SpritePlacement.cpp analysis_tools/sprite/placement_probe.cpp \
  -o /tmp/g1-sprite-check/placement_probe

python3 analysis_tools/sprite/render_oracle.py \
  --binary "$G1_ORIGINAL_IMAGE" --libgcc "$G1_LIBGCC" \
  --unicorn-dir "$G1_UNICORN_PYTHON" \
  --output /tmp/g1-sprite-check/original_render_setup.json

python3 analysis_tools/sprite/animation_oracle.py \
  --binary "$G1_ORIGINAL_IMAGE" --unicorn-dir "$G1_UNICORN_PYTHON" \
  --atlas-decoder native/tests/generate_atlas_reference.py \
  --audit-dir "$G1_ASSET_AUDIT" \
  --native-probe /tmp/g1-sprite-check/animation_probe \
  --output /tmp/g1-sprite-check/original_animation.json

python3 analysis_tools/sprite/placement_oracle.py \
  --binary "$G1_ORIGINAL_IMAGE" --libgcc "$G1_LIBGCC" \
  --unicorn-dir "$G1_UNICORN_PYTHON" \
  --native-probe /tmp/g1-sprite-check/placement_probe \
  --output /tmp/g1-sprite-check/original_placement.json

python3 analysis_tools/sprite/matrix_oracle.py \
  --binary "$G1_ORIGINAL_IMAGE" --libgcc "$G1_LIBGCC" \
  --unicorn-dir "$G1_UNICORN_PYTHON" \
  --native-probe /tmp/g1-sprite-check/placement_probe \
  --output /tmp/g1-sprite-check/original_matrix.json
```

## Boundaries

The references map original code read-only and check its bytes after every call. They do not patch original instructions. The render reference records GPU API boundaries; the animation reference records geometry refresh; the placement component reference records transform API arguments. The matrix reference executes original transform mathematics but uses host `sinf`/`cosf` and external `memcpy` boundaries. Its scalar vector dispatch pointers select original symbol-identified code. These substitutions and seeded caller state are listed in the JSON outputs.

Neither an emulator executing a function in an analysis script nor a native contract test proves GPU rendering, device performance, a complete game state machine, or full-playthrough correctness. The product path is the recovered portable C++ implementation plus the separate native platform renderer.
