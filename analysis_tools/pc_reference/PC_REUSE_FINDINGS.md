# Audit of the uploaded PC build

## Result

The supplied `G1Awakening.exe` is a native Windows x86-64 launcher which contains
touchHLE and the unchanged original ARMv6 game. Its gameplay is supplied by the
original executable through touchHLE/Dynarmic. This is a useful playable reference
for recovering and checking the native iOS rebuild; it is not recovered native
gameplay source.

This assessment is tied to the actual uploaded executable, rather than inferred
from a similarly named temporary project. Nothing was run, patched, extracted into
the PC project, or written back to the executable. The user's report that the PC
version plays is not contradicted by this architecture finding. Packaged build
notes describe testing at the time the package was made and can predate that report.

## Independently checked artifact facts

| Item | Result |
| --- | --- |
| Uploaded EXE | 28,814,848 bytes; SHA-256 `50dd5702e6cf6c0e79ec26757f84934c210be4576ff85a1d4d7303749b2e9cd7` |
| Launcher architecture | PE32+, machine `0x8664` (AMD64), GUI subsystem, 11 sections; no CLR directory |
| Resource tree | Version information and an AMD64 launcher manifest only |
| File overlay | None: last section's raw end equals file length |
| Embedded ZIP | Inside `.rdata`, offset 370775 to 28727130 exclusive; 28,356,355 bytes; 95 entries |
| ZIP hash | `a606605adfcc89972d1586d5fe60673df0bc7e2c690cd02418a89e924302fc37` |
| Runtime inside ZIP | `touchHLE.exe`, PE32+ AMD64; 39,630,811 bytes; SHA-256 `56d92bb44f51671fe9b2e1008325e9545a22a9af8092143e05952ba8074d0c3d` |
| Game inside ZIP | `game/G1awakening.app/G1awakening`, thin 32-bit little-endian ARMv6 Mach-O; 956,496 bytes; SHA-256 `0d510516fe3676ee4a0f4dff60ba64e1c5bf79a0c9800f420b1bbdb1c12febfd` |
| Data inside ZIP | `iphone.big`, 6,994,213 bytes; SHA-256 `663d2888982093ce66b7811ccb7a6ad3acd37fc02ffa85144775b88c39e83cb4` |
| Comparison with original IPA | All nine bundled app files are byte-identical, including the game executable and data archive |
| ZIP integrity | Every one of the 95 entries read successfully with CRC verification |
| Bundled manifests | 63 runtime-manifest entries and 94 diagnostic-manifest entries match actual bytes and hashes; zero mismatches |
| Link to shared source | All 14 modified source files recorded inside this EXE match `/tmp/g1-touchhle-windows` by SHA-256 |

`UPLOADED_PC_AUDIT.json` contains section, resource, import, member-hash and
comparison details. The outer launcher imports `CreateProcessW`; its own strings
name `touchHLE.exe`, `game/G1awakening.app`, `--gles1=gles1_on_gl2`,
`--scale-hack=1`, `--print-fps` and `--fps-limit=`. The embedded
`G1-Classic.cmd` explicitly launches that runtime with the app bundle.

The embedded `build_provenance.json` identifies upstream touchHLE revision
`ca1de89c578e79746f33c1332e28efd106c334ba` and Dynarmic revision
`e0f6bd9d0b48ed6e536672c0c9abbe87961be861`. The matching checkout's unmodified
`Cargo.toml`, `src/cpu.rs` and `src/environment.rs` were separately byte-compared
with the recorded upstream commit. They respectively depend on the Dynarmic
wrapper, construct/run it, and load/branch to the original Mach-O entry point:

- `/tmp/g1-touchhle-windows/Cargo.toml`, dependency at line 73.
- `/tmp/g1-touchhle-windows/src/cpu.rs`, constructor near line 167 and
  `run_or_step` near line 287.
- `/tmp/g1-touchhle-windows/src/environment.rs`, Mach-O load near line 438,
  entry-point selection near line 500, branch near line 729, CPU execution near
  line 1652.

## Concrete reuse for the native rebuild

| PC finding | Evidence tied to this package | Native use and limit |
| --- | --- | --- |
| Sprite clipping overflow at a reported texture limit of 32768 | Embedded `build_source/touchhle_g1_texture_limit_pass05.patch`; matching `src/frameworks/opengles/gles_guest.rs` near lines 212–229 caps the old game's reported `GL_MAX_TEXTURE_SIZE` to `min(host,16384)` | Preserve the recovered arithmetic carefully and use wide, checked native values. This is a specific compatibility diagnosis; it is not a cap to apply blindly to Metal resolution. The package's reproduction notes describe the causal controls; this audit did not rerun them. |
| Original draw-state observability | Embedded graphics-diagnostics patch and matching `src/gles/g1_gl_diagnostics.rs`: upload metadata/input prefixes near 134–144, draw-state/vertex/UV samples near 147–216, column-major projection/modelview/texture matrices at 215–216 | Useful reference instrumentation for comparing our native atlas geometry, matrices, blend/depth behavior and texture pixels to the original. It logs bounded samples, not a complete game source reconstruction or complete texture dump. No runtime needs to ship in the native app to use this as a development reference. |
| Resize and input-coordinate handling | Embedded resize patch; matching `src/window.rs` functions `fitted_viewport`, `window_to_drawable_point`, `input_viewport`; `src/window/resize_tests.rs` | Reuse the demonstrated separation between logical game canvas, physical drawable and input coordinates. The original viewport remains 3:2; this is desktop fitting/letterboxing, not proof of a recovered widescreen game layout. Actual native UIKit input should use its own platform contract. |
| Frame-rate selection and diagnostics | Outer-launcher strings and embedded `README.md` describe 60/144/unlimited ceilings; source build notes explicitly exclude timer/simulation changes | Useful UI and measurement reference. It does not establish native 60-FPS simulation, animation-rate correctness, sustained XR performance or campaign completeness. |
| Menus, campaign and saves in a playable original | Exact original executable/data identity and the user's PC playability report | The PC build can provide behavioral/screenshot/input/save reference observations. Its menus are still original game logic running through the runtime; no native menu or campaign implementation was found in the package. A full playthrough was not performed by this audit. |
| Startup fixes | Bundled `touchhle_g1_startup.patch` changes CFNetwork/CFStream/EAGL and detached-view coordinate behavior in touchHLE | Relevant for understanding why the reference starts. These are runtime framework implementations, not game rules to transplant into the native product. |

No embedded source patch changes original gameplay instructions. The four patch
files concern startup framework support, graphics diagnostics, desktop resize,
and the texture capability correction. All original game bytes also independently
match the IPA, rather than merely relying on that claim in the packaged notes.

## Other shared PC work: kept separate from the uploaded build

`/tmp/g1-widescreen-project` contains a Ghidra project (`G1Wide.gpr` and its
database), not a buildable native game source tree. It may hold additional analysis
worth reading later, but this audit did not alter or open that database for writes.

`/tmp/g1-touchhle-desktop-pass06` is a later experimental touchHLE checkout. Its
`src/options.rs` adds an opt-in `g1_widescreen` setting; `src/window.rs` near
343–347 changes logical portrait dimensions to 540×960 (960×540 landscape);
`src/frameworks/uikit/ui_screen.rs` exposes that logical size. This experiment and
its scale-target code are not the Build05 source embedded in the uploaded EXE.
The uploaded build explicitly says these experiments are not included. Their
existence should not be reported as working native game logic or as tested features
of the actual supplied executable.

## Reproduce this read-only audit

```sh
python3 inspect_pc_package.py \
  --exe /path/to/G1Awakening.exe \
  --ipa /path/to/G1awakening_v1.1.3_os30.ipa \
  --source-checkout /tmp/g1-touchhle-windows \
  --output /path/to/UPLOADED_PC_AUDIT.json
```

Python's standard library is sufficient. `--source-checkout` is optional. The
script opens inputs read-only, bounds the archive member sizes, reads members in
memory, and writes only the requested JSON report. It never executes any payload.
The development report and script can be preserved without uploading the original
game, the PC executable, or an interpreter into the native product repository.
