# Native game test 007 — support tutorial, bitmap headings and pause ownership

The target remains iPhone XR on iOS 17.5, landscape 1792×828, with a requested
60 Hz display rate and separate original 30 ms gameplay updates. Build 007
adds the recovered first-use support tutorial, original bitmap headings,
profile migration and protection against delayed presentation callbacks
crossing a pause. Physical XR output and a complete rendered playthrough
remain unverified.

## Build identity

The source is on [pull request 2](https://github.com/iammrmikemanmods/G1-Awakening-IOS/pull/2),
branch `resume/native-game-007`. Production source commit:
`62e29e63b3d881eb57345f0276ad00484abee5b4`.

| Field | Value |
| --- | --- |
| IPA | `G1_Awakening_Native_Game_Test_007.ipa` |
| Version / build | 0.7.0 / 7 |
| Size | 7,611,418 bytes |
| Compiled source | `5671a5323f2cc1044a9afd618219578696191b1e` |
| Minimum system | iPhoneOS 17.5, ARM64 |
| Apple workflow | [40419564778](https://github.com/iammrmikemanmods/G1-Awakening-IOS/actions/runs/40419564778) — success |
| Portable suites | 62/62 Linux and 62/62 Apple ARM64 |
| Hosted GPU checks | 14 tactical/support and 12 M3G; synthetic geometry |
| Physical XR / full playthrough | Not verified |

IPA SHA-256:
`1dd01f50abffa352a0b42a4585d73ab5d78cca0d24becd51d734af67ea193556`.

The compiled identity is GitHub's pull-request merge commit. Its tree is
verified identical to production source `62e29e63b3d881eb57345f0276ad00484abee5b4`.
Both identities are recorded, and packaging requires the exact compiled one.
The unsigned IPA retains the test bundle identifier and requires Sideloadly
signing. Packaging verified the ARM64 executable, original data hashes,
licenses and every ZIP member. See `validation/APPLE_NATIVE_GAME_007.json`,
`validation/NATIVE_GAME_IPA_007.json` and `validation/NATIVE_GAME_007_SOURCE.json`.

## Runtime changes

### First-use support tutorial

The entry predicate follows unchanged original function `0x58796..0x5884e`.
It inspects all six allocated helper slots, requires a helper owned by the
current player, a pending profile flag and controller value exactly zero.
The visible support sequence still presents at most five helpers. Eligible
entry clears the flag and requests original text resource 1192.

The native host saves consumption atomically before opening its existing
message panel. The original entry function itself performs no file write;
this ordering is an explicit native durability policy. A failed save keeps
the same battle and pending flag behind a retry panel. Simulation and support
timing remain paused while either panel owns the screen. The original
presenter's wider UI guards have not been claimed as recovered.

### Profile migration

Campaign profile format 2 adds the tutorial flag before the checksum. All
existing record offsets remain unchanged. Valid format-1 profiles load with
the tutorial pending. Before the first format-2 write, their exact original
bytes are preserved as `campaign.g1native.v1-backup` using an exclusive write.
An identical existing backup permits retry; a conflicting backup blocks the
write without replacing it. State becomes consumed only after a successful
profile write. Ordinary campaign results retain the flag. Gameplay checkpoint
format 3 is unchanged.

### Original bitmap headings

The portable decoder implements the original font descriptor, metric,
character lookup, width fitting and glyph draw-plan rules. Five keyed BMP
font sheets are supported. The other seven catalog entries remain descriptor
only while their PNG conversion needs separate evidence.

The title adapter uses original slot 0 when it covers the complete heading,
and slot 2 when needed for characters such as the support percentage sign.
All 23 actual unit-name plus text-503 support banners have complete glyph
coverage in slot 2 without fallback. Source palette colors are retained;
the native adapter requests nearest sampling and uses a 17-point glyph height.
These are native presentation choices; original GPU sampling and screen
layout have not been verified. Unsupported or mixed-case text
keeps the existing readable UIKit label. Dialogue pagination remains TextKit.

### Pause, background and Test report

Asynchronous Metal receipts now carry a presentation epoch. Modal changes,
production choices, session installation and application activity changes
invalidate earlier receipts before they can acknowledge an unseen frame.
The existing GPU-success, drawable-presentation, token and revision checks
still apply. Stale GPU failures cannot affect a newly resumed presentation.

Opening Test report during active gameplay enters Pause. Closing the share
sheet leaves the pause screen visible until Resume is chosen. Existing
message/menu ownership is retained when a report is opened from those screens.

## Verification

| Evidence | Result | Boundary |
| --- | --- | --- |
| Integrated portable suites | 62/62 Linux and 62/62 Apple ARM64 | Hosted tests; separate from device play |
| Original tutorial predicate | 2,202 cases / 6,606 scalar comparisons | Unchanged original function; substituted presenter boundary |
| Save/storage and campaign | 806 and 92 checks | Actual host files, migration, backup, retry and campaign ownership |
| Presentation epochs | 103 checks | Portable queued-callback model |
| Original font rules | 240 cases / 1,052 draw submissions | Original metrics and draw plans, not GPU pixels |
| Font decoder/contract suite | 71,678 fixture checks; 72,042 with source assets | CPU metrics, geometry and decoded source pixels |
| Fresh Story campaign | All 17 missions, 17 profile writes, native ending | Synthetic presentation feedback |

The Story run retains all 5,461 build-006 event lines byte for byte. Its
support report is also identical. Only the nondeterministic host elapsed-time
field differs in the result. The pilot does not execute the UIKit tutorial
path, so its resulting profile correctly still has the tutorial pending.
Dedicated controller/storage tests cover consumption and persistence.

See `validation/NATIVE_GAME_007_HOST.json`,
`native/research/support_tutorial_recovery/README.md` and
`native/research/font_recovery/README.md`. The Apple report confirms app and runtime shader compilation plus actual
offscreen Metal execution on the hosted Apple Paravirtual GPU. Those probes
use synthetic geometry and do not render the new UIKit font/tutorial path.
Physical-device evidence remains separate.

## Sideloadly and device testing

Use the same Sideloadly signing identity as the existing test app and install
over it to retain its local files. The test bundle identifier is unchanged.
Existing build-006 profiles are read and backed up before migration.

On the XR, check:

1. Launch and cold Continue with existing progress. Open Test report and
   confirm 1792×828 drawable pixels and a 60 FPS request.
2. The first eligible friendly-support battle displays the original tutorial
   once. Continue it, finish the battle, relaunch and check another supported
   attack for correct one-time behavior.
3. The helper's original name and percentage text appear legibly before the
   M3G battle. Check a long name and a lethal exchange.
4. Pause, background and return during support or a battle. Open Test report,
   dismiss the share sheet and confirm gameplay waits for Resume.
5. Complete an action, relaunch and Continue; then check a mission handoff,
   Showdown and Arena when available.

The report includes tutorial requests/pending state, profile format,
presentation epoch and the active original font slot, alongside existing
save, support, battle, audio and frame-pacing diagnostics.

## Remaining release work

Original tactical HUD/site-marker art, camera and wider text layout fidelity,
remaining sound-event coverage, actual device audio, lifecycle behavior and
sustained XR frame pacing still require work or verification. The successful
headless campaign does not establish a rendered iPhone playthrough.

The app compiles native C++/Objective-C++ to ARM64 and uses original data with
native Apple frameworks. Offline original-function oracles are development
tools; the original executable and compatibility runtimes are not packaged.
