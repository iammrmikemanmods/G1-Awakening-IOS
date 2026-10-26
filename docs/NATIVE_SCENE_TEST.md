# Native scene test — scope and device check

This is an unfinished development build of the native port. The original first
mission's data is loaded by new C++ code and rendered through Metal. No original
CPU program or compatibility runtime is included in the app.

## Included behavior

- Original map268, interior terrain mesh, textures and two initial units.
- Original sprite UV transforms, initial animation identity, millisecond
  playback and initial unit placement/model matrices.
- Touch a unit to preview the recovered movement field. Touch elsewhere to
  clear it. Drag/pinch inspect the scene; Reset view restores the overview.
- Full physical drawable sizing from the attached screen's nativeScale.
  On the requested XR in landscape the target is1792×828 and60 presentations/s.
- Background/foreground handling pauses this test's animation clock.
- Share test report exports the actual device/OS, app source commit, drawable
  dimensions, Metal presentation samples and any startup error.

The camera is an explicit inspection overview. It is not the original tactical
camera. Camera-padded border geometry, original HUD/dialogue, actions, combat,
turns, AI, audio and saves are unfinished. Range preview does not execute a move.
The mission cursor remains before command9/opcode3; the test cannot complete a
mission or campaign. The original sprite bitmaps keep their source detail even
though their geometry is rendered into a native-resolution surface.

## Packaging and installation

Use only a successful cloud build whose executable hash and source commit match
its `native-app-validation.json`. Run `scripts/package-native-scene.py` from the
repository checkout with that artifact and the hash-verified source IPA. Sign
and install the resulting unsigned IPA with Sideloadly as requested.

A successful compile or package is not an installation/device-launch result.
If launch succeeds, verify visible terrain and both units, animation, range
selection, pan/zoom, rotation and background/resume. Export the report after an
active scene session. The reported FPS window covers only recent presented
frames in this scene, not battle performance or a full playthrough.

The release requirements remain a complete playable campaign, correct original
behavior and timing, changed-state save/reload, and sustained60FPS on the XR.
All of those must be tested before being marked complete.
