# Native porting and recovery profile

This project applies the methods in
[Game-Decompilation-Skill-For-Claude](https://github.com/lemiur/Game-Decompilation-Skill-For-Claude/tree/eedfe281d4fab7d8cdaf98b9f72f6a6ac4db04be),
pinned to commit `eedfe281d4fab7d8cdaf98b9f72f6a6ac4db04be`.
The guides were read as reference material. They are not a decompiler,
an Apple toolchain, or evidence that an implementation is complete.

## Target and acceptance criteria

The deliverable is native C++17 and Objective-C++ compiled for iPhoneOS
ARM64, with an iOS 17.5 deployment target. The primary device is iPhone XR:
the host allocates a drawable at the attached screen's native pixel scale
and requests 60 presentations per second. The simulation retains its
separate 30 ms steps. A measured presentation rate and a physical-device
playthrough must be reported separately from a requested refresh rate,
successful compilation, or a headless playthrough.

The acceptance target is recovered behavior on the new architecture.
Reproducing the ARMv6 executable's machine-code bytes with its original
compiler is not a gate for an ARM64 platform port. The matching-specific
guides' scores and compiler adapters therefore do not establish a
"percent decompiled" value for this project.

The app contains no interpreter for the old executable. Original-code
execution is confined to offline development oracles. Original game data
is decoded into bounded native structures and supplied locally during
packaging; it is not copied into the source repository.

## Methods used

| Guide | Application in this project |
| --- | --- |
| Native Platform Porting | Express platform boundaries in application terms: archive resources, meshes, textures, audio requests, input actions, and presentation tokens. Use native Metal, UIKit, and AVAudioEngine implementations. Preserve explicit deterministic arithmetic where gameplay requires it. |
| Helper Recovery | Inspect existing owners, headers, callers, and original evidence before extracting a helper. Preserve evaluation order and repeated calls where observable. Use stable unit indices when the host needs identity; a type number alone is not identity. |
| Decomp Code Rules | Use shared typed declarations, fixed-width serialized fields, explicit bounds, and readable domain operations. Avoid offset-cast runtime objects, compiler-steering scaffolding, invented original names, and unsupported parity claims. |
| Wall Identifier | Classify a mismatch as parsing, arithmetic, state ownership, presentation ordering, or platform behavior before changing code. A host rendering mismatch is not resolved by changing recovered combat rules. |
| Orchestrator | Assign disjoint source ownership, record evidence boundaries, integrate changes centrally, and run the relevant native gates after integration. |

The `matcher` and `permute` guides concern original-compiler byte matching;
they are not the working loop for the current platform integration.
`decomp.wtf` is excluded by the user's instruction.

## Platform boundaries

| Recovered responsibility | Native owner |
| --- | --- |
| Archive bytes and image/animation records | `Archive`, bounded image decoders, `AtlasDescriptor`, and the scoped version-1 overlay descriptor |
| Gameplay, RNG, mission and campaign state | Portable `GameSession` and its domain components |
| Fixed update time | `SimulationClock`; rendering does not advance gameplay implicitly |
| Tactical geometry and 2D overlays | Typed vertices, textures and transforms submitted through `MetalRenderer` |
| Ordinary 3D battle scenes | `M3GBattlePresentation` and `MetalM3GRenderer`, using decoded scene and material data |
| Audio operations | Recovered audio requests delivered to `G1AppleAudio` / AVAudioEngine |
| Touch, menus, lifecycle and text | UIKit and native host controllers |
| Completion visible to gameplay | Matching presentation identity after successful Metal completion and an actual drawable presentation |

Serialized offsets are never native pointers. Runtime containers may use
native sizes; on-disk values and recovered wrapping arithmetic use explicit
widths and conversions. Floating-point operation ordering is preserved
where the original oracle establishes it; the portable target uses
`-ffp-contract=off`.

## Evidence and implementation rules

For each recovered subsystem, distinguish four things:

1. **Original evidence:** the exact executable/data hashes, instruction
   ranges, captured inputs and outputs, and any substituted boundary calls.
2. **Portable verification:** comparisons against those captured outputs,
   independent invariants and rejection of unsupported inputs.
3. **Host integration:** ownership of simulation, drawing, audio, pause,
   session replacement and asynchronous callbacks.
4. **Rendered/device verification:** the actual GPU/device, asset or
   synthetic probe, dimensions and observed result.

A parser rejection proves a supported boundary, not general format
coverage. A source-image hash proves decoded source pixels, not GPU blend
or sampling parity. Successful Apple compilation does not prove a physical
iPhone playthrough. Preserve these distinctions in reports.

The support overlay is an example of this separation. Its original phase,
effect clock, descriptor profile and palette have bounded evidence in
`native/research/support_presentation_recovery/` and
`native/research/overlay_validation/`. Native integration must keep the
already-resolved battle and RNG unchanged, display a render-only
pre-combat view, and defer the main cinematic and its construction audio
until support presentation completes. The first-use tutorial flag,
original tactical camera/easing, and original GPU output remain separate
questions unless additional evidence closes them.

## Build and validation commands

Portable configuration and the repository's registered tests:

```sh
cmake -S native -B build/native -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON
cmake --build build/native --parallel 2
ctest --test-dir build/native --output-on-failure --no-tests=error
```

Use warning-enabled and sanitizer builds for new binary decoders and
stateful portable components when they resolve a concrete bounds,
overflow, lifetime or mutation risk. Run asset-dependent probes with the
locally supplied original archive; do not add proprietary payloads to make
CI self-contained.

The authoritative Apple configuration and GPU probe commands live in
`.github/workflows/native-core.yml`. That workflow compiles the iPhoneOS
ARM64 application, verifies its packaged code, runs the portable tests on
Apple ARM64, and executes the available offscreen Metal probes. Report
the workflow's actual results and exact source revision before packaging
a new unsigned test IPA.
