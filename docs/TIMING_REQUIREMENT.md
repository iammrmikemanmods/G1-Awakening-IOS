# Native timing and the 60 FPS target

The target remains 60 FPS presentation on iPhone XR / iOS 17.5 with the original
game's simulation and animation speed. No current native result establishes
device execution, presentation rate, frame pacing or campaign timing.

Static inspection of the supplied executable found a one-shot timer selected
by a byte in `CCore_Cocoa`, followed by explicit re-arming after the game tick:

| Original location | Recovered fact |
| --- | --- |
| `AppDelegate::SetTimer`, Thumb `0x28f34` | The byte at `CCore_Cocoa + 8` selects an interval. Its meaning is unresolved. |
| Literal chain at `0x28f9c` | Nonzero branch: `0.009999999776482582` seconds. |
| Literal chain at `0x28fa0` | Zero branch: `0.029999999329447746` seconds. |
| `AppDelegate::HandleTimer`, Thumb `0x29380` | Calls `0x28918`, then schedules the next timer. |
| Dispatcher `0x28918` | Delivers queued events, clears them, then calls the game tick through its vtable. |
| `CGameApp` tick `0x62a10` | Forwards the tick to its child object. |

The original IPA SHA-256 is
`b24fbe5cc4d5cb603189a476c4f81dd2a6ecc18b025eae913262055a7fc443fd`.
The executable SHA-256 is
`0d510516fe3676ee4a0f4dff60ba64e1c5bf79a0c9800f420b1bbdb1c12febfd`.
The complete original disassembly and audit remain in the earlier research
checkpoint (`research/approaches/timer_schedule.asm` and
`FRAME_TIMING_AUDIT.md`). These are historical evidence paths, not build inputs.

These facts do not establish a universal gameplay frame cap. The active branch
and each subsystem's use of elapsed time versus per-tick increments still need
recovery. The native engine must separate display scheduling from simulation
timing wherever necessary; blindly increasing the number of game updates can
change game speed. A requested frame rate or counter value is not a device
performance result.

The eventual device checks must cover actual presentation timestamps, moving
game content, missed frames, correct wall-clock animation/game timing, input,
audio, saved progress and sustained sessions through the complete campaign.
No interpreter benchmark is used as evidence of native performance.

Apple's platform guidance for the eventual native implementation:

- [CADisplayLink](https://developer.apple.com/documentation/quartzcore/cadisplaylink)
- [Display-link frame-rate selection](https://developer.apple.com/documentation/quartzcore/cadisplaylink/preferredframerateRange)

The original-game facts above come from the user's executable. The Apple
references describe platform APIs; they do not certify this port.

## Recovered native sprite clock and playback

Original0x1ac9c converts mach_absolute_time elapsed ticks through timebase numer/
denom into integer milliseconds. Core0x9288 subtracts the preceding reading,
clamps the delta to its configurable maximum (constructor default1000ms), and
stores it at core+0x20. The renderer owner link has been traced through
6432a→62c64→9208→91d4; rendering0x63a90 forwards that delta through the sprite
update chain to0x72cc0. Sprite duration fields therefore measure milliseconds.

The native SpriteAnimation module transcribes0x72d80/0x72cc0, including repeat/
reverse behavior and the original forward large-delta duration quirk. All170
source animations and32 synthetic sequences were compared in1,616 original-
function cases, covering17,776 states/124,432 scalar values. See
`native/research/SPRITE_RENDERING.md` for evidence, substitutions and limits.

The scene app requests the attached display's maximum refresh rate, advances
sprites by monotonic integer milliseconds, and samples drawable.presentedTime
for its report. A60Hz request is a target. This establishes neither a full-game
simulation schedule nor sustained device performance. The app's background
pause policy belongs to the scene test; full original lifecycle/save behavior
is still separate work.
