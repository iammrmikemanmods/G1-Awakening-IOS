# G1 Awakening — native iOS reconstruction

The target is a **native ARM64 rebuild of Transformers G1 Awakening** for
**iPhone XR on iOS 17.5**, with **60 FPS presentation and correct game timing**.
The user will sign and install the eventual IPA using Sideloadly from a PC.

**There is no playable native IPA yet.** This repository currently contains
native source reconstruction and resource decoding work. A successful native
core build is not a playable game or a completed port.

## Required implementation

- Compile recovered gameplay logic and the new platform integration directly
  for ARM64.
- Load the original game's data assets; do not execute its ARM32 executable.
- Implement rendering, touch input, audio, saves and lifecycle handling using
  native code and modern iOS platform facilities.
- Preserve original campaign rules, content, timing and progression.
- Verify sustained 60 FPS, changed-state save/reload, and a complete normal
  campaign on the requested device before making those claims.

An ARM interpreter, JIT, compatibility host or an importer app is not an
acceptable project deliverable. Renaming a host or automatically launching the
old executable would not satisfy this requirement.

## Current native work

The C++17 core starts with a validated FGIB archive reader and M3G container
decoder. These have been checked locally against all 559 original resource
payloads and all 36 M3G containers. Those checks establish data decoding only.

The native mission decoder matches all 30 recovered streams (803 commands).
The reconstructed movement-cost/range routines match 256 reference cases
executed by the original game functions, including 9,092 scalar comparisons.
Sprite descriptor and raw quad generation code has also been recovered; this
is geometry/data decoding, not a completed GPU renderer.

Decoding a mission stream is separate from executing every command and
reproducing its effects. The movement module computes a range from typed world
inputs; loading those inputs, selecting/executing a route, undo and animation
remain separate work. Native reference tests contain source-derived fixtures;
the original executable and development-only machine-code reference runner
are not linked or included in the native core.

The remaining game-level work includes the tactical renderer and UI, model
animation, turn progression, combat, AI, mission command execution, audio,
save/load and the campaign's end conditions. See `PORT_STATUS.json` for the
recorded validation boundary.

## Build and validation

The native-core workflow compiles the C++ sources and runs the available native
tests. Its Apple job cross-compiles a static library for iPhoneOS ARM64 with an
iOS 17.5 deployment target. **It does not package an app or publish an IPA.**

The hosted Mac supplies the Apple toolchain; the user's PC does not need a local
Mac or Xcode installation. The same cloud route can build the actual native app
once the game implementation exists.

For a host build:

```sh
cmake -S native -B build/native -DCMAKE_BUILD_TYPE=Release
cmake --build build/native --parallel 2
ctest --test-dir build/native --output-on-failure
```

Source-data comparisons use the user's local original IPA. It is not committed
to this repository. The input SHA-256 is:

```text
b24fbe5cc4d5cb603189a476c4f81dd2a6ecc18b025eae913262055a7fc443fd
```

The original executable, extracted assets, saves and signing credentials are
excluded from the source repository. Test reference records contain structural
metadata and hashes, rather than an embedded copy of the game.

## Earlier approach

The earlier compatibility-host work was the wrong implementation for the user's
request. Its cloud build was cancelled, and its source is preserved in the
`archive/compatibility-experiment` branch for historical research. It is not
the native port and will not be presented as one.

There is no reliable completion ETA yet. Resource decoding, compilation and
isolated gameplay routines do not establish a full playable campaign.
