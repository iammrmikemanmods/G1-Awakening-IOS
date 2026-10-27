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
