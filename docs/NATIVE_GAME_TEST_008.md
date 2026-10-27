# Native game test 008 — original campaign and battle headings

## Baseline and device feedback

This branch is a direct descendant of verified native test 007, not a
reimplementation. The tester reports the native Mission 1 test was
successful on an iPhone. That is valuable first-hand feedback, but the
exact installed build, full mission-completion screen, crash log, screen
capture, frame-time report and subsequent mission playback were not
supplied. It is **not** treated as independently observed 60 Hz or a
complete 17-mission native device playthrough.

Build 007 remains immutable on `resume/native-game-007`. Build 008
resides on `resume/native-game-008` for separate review.

## Change

- The campaign and results panel now uses original keyed bitmap font
  slot 0, falling back to original slot 2, for *complete* single-line
  headings that fit their actual available dimensions.
- The real 3D battle HUD uses original slot 2 for combatant names where
  the full name fits; HP digits, health tracks and longer/uncovered text
  retain the existing readable UIKit rendering.
- The original palette, crop, per-glyph advances, and nearest sampling
  are handled by the existing decoded bitmap-font adapter. These
  changes do not rescale the game into a legacy framebuffer.
- The report exposes `campaign_original_heading_font_slot` and the
  precise original/fallback policy.
- Target app version is 0.8.0 / build 8. Bundle ID, minimum iOS 17.5
  and save/checkpoint codecs are unchanged. Campaign rules, AI, RNG,
  original audio/event routing, script acknowledgements and tactical
  Metal geometry are untouched.

Font role selection and panel geometry are **native host policies**,
not recovered proof of the exact original results screen.

## Required acceptance evidence

A GitHub Actions pass must confirm iPhoneOS ARM64 compile/link,
62 portable suites (unless suite count increases) on both platforms
and hosted Metal probes. That evidence is not a substitute for UIKit
pixel parity and a native iPhone XR run.

On the XR, upgrade with the same signing identity and check a cold
Continue, Story result-to-Mission-2 handoff, title/body legibility,
long combatant names and pause/Test report/resume. Compare screenshots
if original iOS reference captures are available. Keep the original
gameplay save; no migration is required from native test 007.

The initial Build 008 source commit and compiled artifact identities
must be added only after those exact builds have been verified.


## Verified Apple and IPA build evidence

The reviewed source commit is `fd78ea5138e4a1beb8a2224b304e72099ffc0266`,
Git tree `e10f37569685acebaf40bb12e8310404cbc7388a`.
The GitHub pull-request workflow compiled merge commit
`bc4ab991bee493d282ed12bccafe9d07bc31895f`, whose Git
tree is **identical** to the reviewed source. That exact compiled
identity is embedded in the executable's Info.plist.

[GitHub workflow 40424515585](https://github.com/iammrmikemanmods/G1-Awakening-IOS/actions/runs/40424515585)
succeeded: 62/62 portable tests on Linux and 62/62 on Apple ARM64, native
iPhoneOS app compilation and runtime M3G Metal shader compilation, 14
tactical/support and 12 M3G hosted Metal pixel checks. The GPU probes
used synthetic geometry on Apple Paravirtual hardware; they are not
original-game frame captures or an iPhone XR run.

The unsigned `G1_Awakening_Native_Game_Test_008.ipa` has version
0.8.0/build 8, size **7,611,886 bytes**, SHA256
`e68a3830ad292e71cd8a4173940923e16f110ac400b51de1056129a39304e024`.
The verified native ARM64 executable is 1,629,640 bytes, SHA256
`5131341bff53fcd0ba2d8c9ba390f0790afb85dba46947b4bf01bfe60a27a7e7`.
Hosted code artifact 12699223872 has SHA256
`54de2db56b1a5e32d9b351065d7353828b8d33e0ff5e664eaa5e6f680cf0e20c`.

The packaged ZIP, member bytes and CRCs were checked. It contains the
hash-pinned original `iphone.big` and 480-byte static terrain data,
native ARM64 executable, app metadata and licenses; it **does not**
contain the original ARM32 executable, JIT or interpreter. The IPA is
unsigned for Sideloadly signing. The existing bundle identifier and
iOS 17.5 minimum are unchanged to support installing over Build 007
with the same signing identity, preserving application data.

The new UI heading/render changes were compiled but have not been
visually compared with original screenshots on an actual XR. The
user-reported Mission 1 success predates Build 008; it is **not** proof
that the new Build 008 binary was executed on the phone. The existing
headless complete Story run is not a rendered device playthrough.

Machine-readable metadata:
`validation/APPLE_NATIVE_GAME_008.json` and
`validation/NATIVE_GAME_IPA_008.json`.
