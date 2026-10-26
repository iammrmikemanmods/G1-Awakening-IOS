# Native game test 006 — tactical support integration

The target remains iPhone XR on iOS 17.5, landscape 1792×828, with a requested
60 Hz display rate and separate original 30 ms gameplay updates. Build 006
adds the recovered tactical support presentation before the ordinary 3D
battle. It is a test build; a complete physical-device playthrough and
sustained 60 FPS have not been recorded.

## Runtime changes

The app loads the original support image through property resource 1000,
indexed BMP 997 and version-1 descriptor 256. The bounded decoder implements
the proven narrow-coordinate, single-image, identity-variant profile. The
bitmap decoder expands the original palette to top-down straight RGBA,
preserving the original low-24-bit color-key rule. The 69×63 source expansion
matches SHA-256
`3df200499e9a45936a3d7ae57d1a16fd847083e5366540e9387ad449c4c51e05`.

Combat retains exact helper roster indices alongside the existing sorted
type list. Its health calculation and random draws are unchanged. A pending
battle now also retains its pre-combat movement snapshot so a unit destroyed
by the resolved exchange remains visible during the preceding support phase.
The snapshot is transient and is not added to the checkpoint format.

Each helper gets its original primary-name banner plus text 503 and the
separate percentage effect. At 30 ms updates, the effect completes and becomes
hidden after 56 ticks, or 1,680 ms. The cue continues to tick 67, or 2,010 ms.
The original phase presents at most five helpers even when all six contribute
to the combat calculation. Zero helpers bypass the phase immediately.

The host constructs the 3D cinematic and sends its initial audio only at the
handoff. Support drawing cannot acknowledge a mission camera, world update,
AI focus, transform, or battle completion. The existing successful Metal
completion, positive drawable presentation and final HUD checks still own
the main battle's completion.

## Native presentation choices

The source artwork is drawn directly through Metal at the native drawable
size. A 320-unit logical height gives uniform artwork scale while the
horizontal view expands to the XR aspect. There is no legacy framebuffer
being enlarged. The original world anchor, integer logical-screen truncation,
signed part offsets, exact crops and reverse part order are preserved.

The tactical camera is still the project's inspection camera. Helper focus
is immediate, normal tactical unit poses are frozen during support, the
percentage bitmap uses nearest sampling, and its screen-space pass neither
tests nor writes tactical depth. These are explicit native host choices;
original camera easing, ordinary idle scheduling and GPU pixel parity are
not asserted.

Each helper must reach one successful presented frame with its banner drawn
before its support clock starts. This is a native host policy, separate from
the original always-true helper. Later animation revisions advance without
waiting for every GPU callback. The production display gate rejects old
tokens, helper slots, revisions and pause/session epochs. Pause preserves
the sequence while resetting catch-up time and first-frame readiness.

## Validation layers

The source integration passes 59 portable suites on Linux. The new bounded
checks cover 1,280 original phase updates / 5,120 compared fields; seven
complete helper-count sequences; actual source assets and 711 malformed or
unsupported asset rejections; 166 geometry checks; 25 asynchronous display
gate checks; and a real synthetic-fixture lethal exchange held through 134
support ticks without changing gameplay or the full RNG state.

The modified combat test also reverses its native roster in 136 cases and
verifies identical damage/state/RNG with exact helper identities. The
existing real first-mission battle still performs 534 controller updates
and 217 prepared frames with unchanged RNG and explicit host completion.

`validation/NATIVE_GAME_006_HOST.json` records the local results. An opt-in
`--verify-support 1` in the development campaign pilots validates actual
source-asset support sequences immediately before their explicitly synthetic
battle feedback. These runs prepare geometry on the CPU; they do not prove
UIKit, GPU or device output.

The Apple workflow compiles the actual ARM64 iPhone app and runtime shader,
runs portable tests on Apple ARM64, and executes offscreen Metal probes when
a device is available. The tactical probe now includes eight synthetic
support checks, covering crop, palette, nearest boundaries, part order and
depth isolation. A successful hosted run remains separate from a physical
iPhone test. Exact run, source and IPA identities are recorded in the
source-specific validation reports when that build finishes.

## Sideloadly and device testing

The packaged IPA is unsigned and uses the same test bundle identifier as
build 005. Sign it with Sideloadly on the Windows PC. Installing over the
existing test app with the same signing identity is preferable when retaining
its local saves; do not remove the existing app merely to update it.

On the XR, use the app's **Test report** button after checking:

1. Launch, landscape drawing and touch selection. The report should show
   1792×828 drawable pixels and a 60 FPS request.
2. A normal attack with no helper, followed by an adjacent friendly-support
   attack. The helper banner and percentage artwork should precede the 3D
   scene; battle input remains blocked until the cinematic finishes.
3. A lethal exchange. The combatants should remain visible during support,
   then their actual resulting health/death state should appear after battle.
4. Pause and resume during a support cue, followed by backgrounding and
   returning. Progress should resume without skipped helpers or duplicate
   cinematic audio.
5. Continue after a completed action, a mission transition, Story/Showdown
   progress, and Arena. Busy actions retain the last durable checkpoint.

The report includes support sequence/tick/frame counters and the active
helper slot alongside existing battle, save, audio and frame-pacing data.

## Remaining release work

The original first-use support tutorial flag is not integrated. Original
tactical HUD, site/marker art, font and camera fidelity, remaining sound-event
coverage, device audibility, lifecycle behavior and sustained XR frame pacing
remain validation or implementation work. A complete headless campaign is
not evidence of a complete rendered iPhone playthrough.

The app compiles native C++/Objective-C++ to ARM64, uses original data and
native Apple frameworks, and contains no original executable, interpreter or
compatibility runtime. The guide application is recorded in
[PORTING_SKILL_PROFILE.md](PORTING_SKILL_PROFILE.md); `decomp.wtf` is excluded.
