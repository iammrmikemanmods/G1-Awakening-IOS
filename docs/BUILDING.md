# Source and build guide

[Back to the project](../README.md) · [Releases](RELEASES.md)

## Choose the source that matches the package

The default branch's engine code is an older checkpoint. Build 017 and its resource-only 017R1 revision use **`be203a911bc26313615ea450758413e5c9cf6462`**. Do not compile default-branch code and label it Build 017 because the front page mentions that build.

```sh
git clone https://github.com/iammrmikemanmods/G1-Awakening-IOS.git
cd G1-Awakening-IOS
git checkout --detach be203a911bc26313615ea450758413e5c9cf6462
```

A private repository requires authorized access. The [source-only release](https://github.com/iammrmikemanmods/G1-Awakening-IOS/releases) is an alternative to cloning; it is not a game-data download.

## Portable native checks

Requirements: CMake, a C++17 compiler and zlib development headers. Use Debug for assertions; Release-only testing can omit assertion checks.

```sh
cmake -S native -B build/native -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTING=ON
cmake --build build/native --parallel 2
ctest --test-dir build/native --output-on-failure --no-tests=error
```

At the pinned source the recorded portable result is 72 tests. GPU probes are additional Apple checks; neither their counts nor a passing host suite establishes device fidelity. See the pinned [CMake configuration](https://github.com/iammrmikemanmods/G1-Awakening-IOS/blob/be203a911bc26313615ea450758413e5c9cf6462/native/CMakeLists.txt).

## Native iPhone/iPad build

Requires macOS with Xcode and its iPhoneOS SDK, CMake and a compatible generator. These are the arguments used by the native candidate workflow, shown with the default CMake generator rather than requiring Ninja:

```sh
cmake -S native -B build/iphoneos \
  -DCMAKE_SYSTEM_NAME=iOS \
  -DCMAKE_OSX_SYSROOT=iphoneos \
  -DCMAKE_OSX_ARCHITECTURES=arm64 \
  -DCMAKE_OSX_DEPLOYMENT_TARGET=15.0 \
  -DCMAKE_TRY_COMPILE_TARGET_TYPE=STATIC_LIBRARY \
  -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_TESTING=OFF \
  -DG1_BUILD_APP=ON \
  -DG1_SOURCE_COMMIT=be203a911bc26313615ea450758413e5c9cf6462
cmake --build build/iphoneos --parallel 2
python3 scripts/verify-native-app.py build/iphoneos/G1AwakeningNative.app
```

Refer to the exact [Build 017 workflow](https://github.com/iammrmikemanmods/G1-Awakening-IOS/blob/be203a911bc26313615ea450758413e5c9cf6462/.github/workflows/clean-motion-017.yml) for the recorded SDK, shader validation and native probes. It contains a historical source-publication step: do not rerun that old publisher against a newer branch. The commands above do not publish source or sign the app.

Changing deployment metadata does not make unavailable Apple APIs compatible with older iOS. Signing/provisioning and physical testing are separate from compiling.

## Original resources and optional artwork

The source-only release intentionally excludes `iphone.big`, the original ARM32 application, audio/movie assets, owner saves and the generated remaster pack. A code-only app cannot display/play the full game without its expected original resources. Do not rename it to a playable IPA.

The source game's recorded original IPA SHA-256 is:

```text
b24fbe5cc4d5cb603189a476c4f81dd2a6ecc18b025eae913262055a7fc443fd
```

The expected extracted `iphone.big` SHA-256 is:

```text
663d2888982093ce66b7811ccb7a6ad3acd37fc02ffa85144775b88c39e83cb4
```

Use the packaging tools and exact inputs from the chosen source/recovery checkpoint. Start by reading their `--help`; the older `package-native-scene.py` filename does not mean it assembles the complete later intro/remaster revision. Full 017R1 reproduction additionally needs its separately delivered recovery scripts, the Build 017 baseline IPA, completed Pass01 art ZIP and supplied intro. These are not all part of the pinned Git source.

017R1 changes resources only, keeping version 0.17.0/build 17 and the compiled source identity. Do not rebuild and label a new executable with the old binary checksum.

## Contributor boundaries

Keep gameplay/RNG/saves separate from presentation changes. Validate exact asset mapping, alpha, dimensions, animated frames and legitimate terrain neighbours. Preserve old builds and provide reproducible checksums. Original media and derivative art are not automatically licensed under the new engine's MPL-2.0 licence. Do not add credentials, standalone font files, private saves or game dumps to source releases.
