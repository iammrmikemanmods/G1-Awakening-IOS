# G1 Awakening — iPhone XR acceptance record

**Target:** iPhone XR, iOS 17.5, installed by the user with Sideloadly.
**Performance goal:** sustained 60 FPS at the device's native refresh target,
with correct game speed and smooth frame pacing.
**Current device status:** every gate below is **unverified**. This document is
a test plan and blank record; no iPhone installation or device test is claimed.

The companion `DEVICE_ACCEPTANCE.json` contains the same gate IDs, required
evidence and empty result fields. A cloud build can supply an IPA and build
logs; a pass requires evidence from the actual target device and identified
IPA. The user does not need a local Mac or Xcode to install with Sideloadly,
record observations, and export diagnostics from a suitably instrumented build.

## Evidence already available

The unchanged original game ran on a Linux x86_64 host with the no-JIT
interpreter and strict memory. Probe35 reached menus, the first mission and
tutorial HUD, and created a save. Compact-memory probe36 reloaded that save
and transformed Bumblebee into a car. Probe38 moved him to one adjacent tile
after destination selection and a second ordinary tap on that same tile.
The latter taps were 18.983 seconds apart. These sessions did not complete a
mission or establish combat, audible output, target performance, or persistence
of newly moved/transformed state: `savegame.dat` remained unchanged in probes36/38.

Reference records, relative to the project checkpoint root:

- `research/approaches/probe35_interpreter_v4_optimized/observations.json`
- `research/approaches/probe36_interpreter_v4_compact_reload/observations.json`
- `research/approaches/probe38_interpreter_v4_same_destination/observations.json`
- `research/compact_memory/runtime_review.json`
- `research/assets/results/game_data_inventory.json`
- `research/approaches/FRAME_TIMING_AUDIT.md` and `frame_timing_audit.json`

The asset inventory frames **30 mission command streams containing 803
commands**. Their full semantics and mapping to user-visible campaign levels
are unresolved. Do not turn that resource count into a claim of 30 tested
levels, or treat resource decoding as mission completion.

## Record before each run

Give each run a unique ID. Record UTC date, tester, device/model, exact iOS
version, IPA filename and SHA-256 before Sideloadly signs it, cloud workflow
run/commit, core/patch revisions, and any changed build options. Record the
signing/installation outcome without storing passwords or signing credentials.
Keep saves from previous builds before replacing them.

Record battery level, charging state, Low Power Mode, display orientation,
screen-recording state, thermal warnings, and test duration. Export available
runtime diagnostics. Retain short videos/screenshots with the run ID and time;
name saved-state snapshots by mission and action. If the required metric or
reference is unavailable, leave its gate unverified instead of guessing.

## Acceptance gates

| ID | Exercise and required evidence | Pass condition | Status |
| --- | --- | --- | --- |
| D01 — Install and launch | Install the identified IPA with Sideloadly on XR/iOS 17.5. Cold-launch it three times. Capture the first game screen and exported CPU/memory-mode log. | Installation and all launches succeed using the intended no-JIT interpreter/compact configuration under the user's signing setup. No extra JIT activation is required. | Unverified |
| D02 — Input and rendering | Use menus, all edge buttons, unit/tile selection, ordinary same-tile move confirmation, camera pan/zoom and supported orientation changes. Record dialogue, tutorial and 3D-model screens. | Touches match visible targets; controls remain reachable; scenes, text and overlays render correctly without clipping, missing resources or stuck input. | Unverified |
| D03 — Sustained 60 FPS | Use actual presentation timestamps during an animated mission for at least 20 uninterrupted minutes, including busy AI/combat/camera activity. Repeat after the phone is warm. Preserve raw samples and summaries. | Meets the presentation/pacing limits below while guest animation advances normally. Host overlay counts alone cannot pass this gate. | Unverified |
| D04 — Correct game time | Record wall time, guest monotonic time, timer dispatch and several timed movement/animation/scripted sequences. Compare with an established original-game reference or independently justified timing model; include a pause/resume interval. | No global speed-up, slowdown, extra turns or burst of missed actions; guest clock and foreground wall time remain consistent. Increasing FPS must preserve simulation and scripted timing. | Unverified |
| D05 — Complete normal campaign | Start a new normal campaign at the recorded difficulty. Record each actual mission's title/start, objective completion, victory/transition and the final campaign/end screen. Map encountered resource streams where identified. | The entire selected normal campaign finishes through original controls, without forced progression or a skipped unresolved failure. All 30 resource streams are accounted for as mapped, shared/optional or still unmapped; this is separate from the visible mission count. | Unverified |
| D06 — Mechanics and branches | Record player and enemy turns; close/ranged combat, retaliation, damage/death, transform, upgrade, repair, capture/energy, terrain/pathfinding, tutorial/dialogue, victory and defeat/retry. Include later units and demanding scenes encountered in the campaign. | Each exercised mechanic produces the game's expected observable result; AI turns and scripted objectives complete. Record optional modes, branches and mechanics not covered. | Unverified |
| D07 — Changed-state save/reload | Move/transform a unit, perform combat or capture, and advance campaign progress. Trigger the game's normal save, exit, terminate and cold-launch. Compare before/after saves and visible restored state. Repeat at a later mission. | Newly changed unit/progress state survives cold reload, without corruption or rollback. Loading an old unchanged save is insufficient. | Unverified |
| D08 — Audio | With audible output enabled, check music, dialogue where present, effects and volume/mute controls in menus, battles and transitions. Record a short synchronized clip and listening notes. | Expected audio is audible, synchronized and stable, without missing channels, persistent distortion or playback loss after resume. | Unverified |
| D09 — Lifecycle and endurance | Background/foreground and lock/unlock during a mission, dialogue and a safe save boundary. Test an interruption, repeated cold launches and a long campaign session. Record crashes, memory warnings, frame pacing and thermal changes. | No stuck touches/audio, unintended input, lost progress, allocation failure or crash; foreground play resumes correctly. Warm-session performance still meets D03. | Unverified |

## How to judge 60 FPS and timing

The 60 FPS budget is approximately **16.67 ms per frame**. Proposed project
acceptance limits for active gameplay are: at least 59 successful game-frame
presentations per second in each 10-second window, 95th-percentile presentation
interval no greater than 18.34 ms, 99th-percentile no greater than 34.34 ms,
and no unexplained gameplay stall over 100 ms. Report loading/transition
intervals separately; never silently remove slow gameplay samples. These are
prospective tolerances for this project, not measured results or Apple guarantees.

Record attempted guest presents separately from successful native presentations.
The existing host FPS counter increments before actual presentation succeeds,
so its displayed number does not establish the delivered frame rate. Count
successful presentations at the real presentation/completion boundary and
correlate them with guest-frame IDs plus animation/content progress. Repeating
an old buffer at 60 Hz must not be reported as 60 new game frames. Static scenes
alone cannot establish moving-scene smoothness. Document instrumentation and
screen-recording overhead; collect timing without screen recording as well.

The native timer investigation has identified 10 ms and 30 ms timer intervals
with re-arming after callback work; the selected branch and render/tick relation
still need resolution. Do not infer an XR FPS ceiling from this alone, or change
timer speed merely to make a counter read 60. Preserve original simulation
semantics. The existing Linux capture audit reports roughly 22.0–22.3 render
calls per second in mission windows, measured sparsely before SDL swap. That
is neither an XR measurement nor individual-frame pacing evidence. For D04,
compare guest monotonic-clock advance with foreground wall
time over at least 10 minutes (proposed drift tolerance 1%), and separately
check animation/scripted-event durations against the documented reference.
If the necessary reference or successful-presentation timestamps are missing,
D03/D04 remain unverified even if a video looks smooth.

## Result record and release decision

For each gate, fill in the run ID, IPA hash, result, exact evidence filenames,
observed versus expected behavior, and reproduction steps for failures. For
each campaign mission, record title/identifier, entry/exit times, objective
result, completion screenshot/video timestamp, save hashes and next transition.
Keep CPU/API/memory failures visible and attach their first diagnostic rather
than suppressing them.

All mandatory gates must pass on the **same identified release candidate**,
with affected gates rerun after fixes. A complete normal-campaign playthrough
supports that tested route, difficulty, artifact and device. Additional modes,
branches and unvisited scenarios must retain their own coverage status; no
finite playthrough proves the absence of every possible bug.
