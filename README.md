# G1 Awakening cloud build kit

This repository subtree builds the patched iOS test host on a **GitHub-hosted
Mac**. You can publish and trigger it from a PC; you do not need a local Mac or
Xcode. A successful workflow produces an **unsigned ARM64 IPA** for you to sign
and install with Sideloadly, together with the compiler logs and verification
records.

**Current status: the kit has passed local source-preparation and script checks.
No Apple SDK compilation or cloud workflow run has been performed for this
kit, and no new IPA has yet been produced.** The first real cloud run is a build
and compatibility gate; its logs will determine any remaining platform work.

The first artifact is the existing **Applesauce importer host** with the tested
interpreter and compact-memory changes. After installing it, use **Import Game**
to select your original G1 Awakening IPA from Files. The game is not included in
this repository or cloud build. A dedicated G1-only launch experience is later
integration work.

## Run it from your PC

1. Publish the **contents of this directory** at the root of a dedicated GitHub
   repository. Keep the `.github` directory; the workflow must be located at
   `.github/workflows/build-ios.yml` in the repository root. This kit requires
   no Apple credentials, signing certificates or repository secrets.
2. A relevant push to `main` or ordinary pull request targeting `main` starts
   the workflow, including a draft PR. To run it manually, open the
   repository's **Actions** tab, choose **Build G1 no-JIT iOS test host**, and
   select **Run workflow**. The workflow must be present on the default branch
   for the manual control to appear.
3. Inspect the run's status. On success, download the **g1-ios-unsigned-ipa**
   ZIP artifact and extract **G1-Awakening-nojit-test-host-unsigned.ipa**. Download the
   separate **g1-ios-build-records-…** artifact as well; it includes the IPA
   checksum, selected features, source revisions and build logs.
4. Sign and install the downloaded IPA locally with Sideloadly. Then import
   your unchanged original game into the installed host. The cloud job never
   signs in to an Apple account and never receives the game IPA.

If a build stage fails, the workflow uploads the records available at that
point. Use the first failing stage and its full log to continue the build work.
A hard runner termination can prevent final artifact upload; the Actions job
log remains the first record to inspect. The 180-minute job timeout is a cap,
not an estimated completion time. Artifacts request seven days of retention,
subject to the repository's policy.

The workflow uses standard `macos-26`, not a larger paid runner label. Whether
the run consumes an account's included allowance or incurs a charge depends
on repository visibility and account policy. No remote repository creation,
push, workflow dispatch or charge was started while preparing this kit.

## What the workflow does

The workflow checks out this build kit with a read-only repository token, then
the build driver performs these steps:

1. Selects the explicitly reviewed Xcode installation and installs the pinned
   Rust toolchain plus `aarch64-apple-ios`. It makes CMake, Ninja and `ldid`
   available. `ldid` is needed by the upstream verification script even for an
   unsigned package; this workflow does not invoke its signing mode.
2. Verifies every patch's exact bytes, creates a fresh checkout of the pinned
   Applesauce commit, and initializes its pinned submodules recursively.
3. Applies the seven patches in order, verifies the resulting files against
   the reviewed source snapshots, and checks the pinned `Cargo.lock` hash.
4. Fetches locked Rust dependencies and resolves the iOS entry features.
   The feature check requires `cpu-interpreter`, `compact-memory` and shared
   SDL, and rejects `cpu-dynarmic` or private static SDL selection.
5. Builds shared SDL first, then invokes the existing patched host build script
   for `iphoneos Release`. That script builds the Rust core and invokes Xcode
   with `CODE_SIGNING_ALLOWED=NO`. No second core checkout is selected.
6. Rechecks prepared source and the lockfile, packages the unsigned IPA, runs
   the upstream package verifier, and checks the actual packaged host/core/SDL
   binaries for ARM64, iOS device platform and minimum OS 15.0.
7. Checks the core's exported `touchhle_ios_requires_jit` function for a
   recognized constant-zero ARM64 return. This is a static binary check, not
   execution of the core on an iPhone. An unexpected encoding stops delivery
   for review rather than being assumed equivalent.
8. Stores the already-packaged IPA inside a standard ZIP artifact with no extra
   compression, and uploads logs/checksums/provenance separately. The outer ZIP
   supports the connected workflow-artifact downloader; extracting it preserves
   the inner IPA bytes and the executable permissions within that IPA. The IPA
   upload occurs only after the build and verification step succeeds.

The ordinary `pull_request` trigger allows the connected GitHub tools to
monitor a concrete draft-PR build. The workflow does not use
`pull_request_target` or grant repository-write permissions. The runner research
also documents raw-file uploads, but this workflow uses the standard ZIP format
supported by the current artifact-download connector.

The wrapper `scripts/cargo-locked.sh` adds `--locked` to Cargo build and
dependency-resolution invocations made by the upstream scripts. It delegates
to the exact installed Cargo binary and preserves arguments and exit status.
This enforces the lockfile without editing the frozen implementation patches
or the upstream script's logic. Dependencies are fetched before the compile,
which then runs with Cargo networking disabled.

The build uses two concurrent Cargo/CMake jobs, release optimization, disabled
debug assertions and enabled overflow checks. These are build settings; they
do not alter the game's timer, force its frame count, or speed up its simulation.
The standard runner's capacity is not an iPhone performance measurement.

## Pinned inputs

`build-manifest.json` is the machine-readable source of the pins, patch order,
complete hashes and expected source snapshots.

| Input | Selection |
| --- | --- |
| Applesauce source | `https://github.com/johnny901901901/Applesauce.git` |
| Source commit | `c75278bda86c80cbcec2d8d1493b5be9d5a9e0d1` |
| Adapted interpreter source | `moleworld-dev/touchhle-arm-interpreter`, commit `adffbbdae912568557f33f8596110cc677809641` |
| Standard runner | `macos-26`, ARM64 |
| Xcode | 26.6 at `/Applications/Xcode_26.6.app/Contents/Developer` |
| Rust | 1.99.1 |
| Device compilation target | `aarch64-apple-ios`, `iphoneos` |
| Deployment target | iOS 15.0, retaining the existing host setting |
| Intended test device | iPhone XR on iOS 17.5 |
| CPU/memory | Interpreter and compact low 1 GiB plus top 1 MiB stack |
| Signing | Disabled; the user signs the result locally |

The patch files are byte-for-byte copies of the verified checkpoint payloads:

| Order | Payload | Purpose |
| --- | --- | --- |
| 1 | `patches/01_applesauce_nojit.patch` | Interpreter integration and reviewed CPU corrections, including the reached VMOV fix |
| 2 | `patches/02_applesauce_ios_nojit_host.patch` | Explicit core JIT requirement, native-host handling and CPU build selection |
| 3 | `patches/03_strict_runtime.patch` | Explicit unresolved-function failures and optional diagnostic capture support |
| 4 | `patches/04_applesauce_strict_memory.patch` | Checked memory access and removal of upstream fault-masking paths |
| 5 | `patches/05_compact_feature.patch` | Cargo feature for compact backing |
| 6 | `patches/06_compact_memory.patch` | Stable low/stack windows and mapped-range checks |
| 7 | `patches/07_applesauce_ios_compact_selection.patch` | Explicit compact-memory selection through the iOS entry and build script |

Historical incremental CPU patches must not be added again after this combined
CPU patch. The core's upstream filename and UI label remain
`libhyperhle_core.dylib` and the existing host label; the selected CPU inside it
is the interpreter.

All submodules are initialized, including Dynarmic's source, because the
unchanged root build script reads its license text even when the JIT backend
is not compiled. The nested SDL under `vendor/rust-sdl2/sdl2-sys/SDL` is the
shared-library input; the separate root SDL submodule is not a substitute.

The runner image and available Homebrew package versions can change. The
workflow records the actual tool and image versions. It deliberately fails if
the selected Xcode path/version disappears, leaving a concrete update to review
instead of silently switching SDKs. CMake/Ninja/ldid are not claimed to be
bit-reproducibly pinned; their actual versions are recorded in the build
records. The existing CMake wrapper supplies its legacy policy minimum.

## Validation completed while preparing the kit

The `validation/` directory records only checks actually performed locally:

- All seven payload hashes and lengths match the frozen checkpoint.
- All seven patches apply sequentially to an isolated checkout at the exact
  pinned commit, and the seven reviewed source snapshots match afterward.
- The root Cargo lockfile remains unchanged.
- Real Cargo 1.99.1 metadata resolution for the prepared iOS entry selects only
  `compact-memory`, `cpu-interpreter` and `dynamic-sdl` in the root core; the
  entry selects `compact-memory` and `cpu-interpreter`.
- Four wrapper checks verify insertion of `--locked`, no duplicate insertion,
  preservation of spaced arguments/version calls, and failure-code propagation.
- Python syntax, shell syntax and workflow YAML parsing pass.

The local preparation check skipped network submodule initialization and used
an existing clean, matching pinned rust-sdl2 source through a temporary link
only for Cargo metadata. It did not compile SDL, Swift or the Rust iOS core.
The cloud build refuses a preparation record that skipped submodules.
The additional Mach-O/package checks are implemented but have not yet run on a
new Apple-built artifact. No GitHub-hosted job or iPhone test is represented by
these local checks.

To repeat only the payload check on any machine with Python 3:

```sh
python3 scripts/prepare.py --verify-kit
```

To prepare a new source checkout, without building:

```sh
python3 scripts/prepare.py --destination /absolute/path/to/new/Applesauce
```

On a suitably configured Mac, the same driver can also run outside Actions:

```sh
G1_BUILD_WORK=/absolute/path/to/fresh/work bash scripts/build-ios.sh
```

That alternative is not needed when using the hosted workflow. Existing work
directories are not reset or deleted; choose a new path for another local run.

## Device acceptance: 60 FPS and the complete game

The performance requirement is **sustained 60 FPS on the XR with correct game
speed and frame pacing**, followed by a **complete normal campaign playthrough**
through original controls. Both remain unverified. A successful cloud compile,
an IPA checksum, an overlay FPS label, or the completed Linux probes cannot
establish those outcomes.

The tested Linux checkpoint reached menus and the first mission, wrote and
reloaded a save, transformed Bumblebee, opened the 3D Tech Specs screen, and
moved Bumblebee one adjacent tile. It did not complete a mission or verify
combat, audible output, newly changed-state persistence or target performance.
For the observed movement, select the unit, tap a valid destination to place
the cursor, then tap the same destination again to confirm; a rapid double-tap
or forced UIKit tap count is unnecessary.

[DEVICE_ACCEPTANCE.md](docs/DEVICE_ACCEPTANCE.md) and its
[JSON record](docs/DEVICE_ACCEPTANCE.json) provide the concrete target tests and
empty result fields. They are exact copies from the full checkpoint; their
source-reference paths identify contextual records in that checkpoint, not
dependencies required to execute this standalone build kit. Every device gate
starts as unverified. The kit does not contain an FPS-forcing or game-clock
modification.

## Source, licenses and build records

The patches retain upstream authorship and MPL headers. The adapted interpreter
patch includes its complete MPL license and provenance. The kit's scripts use
MPL-2.0; `LICENSE` contains that text. The checked-out upstream source retains
its other license notices and dependency attribution. This kit does not replace
those notices or claim ownership of the original game.

Keep the kit revision, patch manifest, lockfile, workflow logs and checksum with
any IPA you test. The full source remains reconstructible from its pinned
commit, submodule revisions and these exact patches. Review the upstream
distribution/license terms before distributing derived binaries publicly.

Primary build references, reviewed 2026-10-26:

- [Pinned host scripts and guide](https://github.com/johnny901901901/Applesauce/tree/c75278bda86c80cbcec2d8d1493b5be9d5a9e0d1/platform/ios)
- [GitHub standard hosted runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
- [macOS 26 ARM64 image inventory](https://github.com/actions/runner-images/blob/main/images/macos/macos-26-arm64-Readme.md)
- [Pinned checkout action](https://github.com/actions/checkout/commit/3d3c42e5aac5ba805825da76410c181273ba90b1)
- [Pinned upload-artifact action](https://github.com/actions/upload-artifact/commit/cf430e030ddbb5b0abf93d22962f4752f3646cd9)
- [Artifact upload behavior](https://github.com/actions/upload-artifact)
- [Rust 1.99.1 release](https://github.com/rust-lang/rust/releases/tag/1.99.1)

`docs/CLOUD_RUNNER_SOURCES.json` retains the primary-source research details,
including current runner inventory, action pins, artifact behavior and limits.
