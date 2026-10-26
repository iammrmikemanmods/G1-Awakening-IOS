# Native test artifact policy

This archive is a reproducible development artifact for the G1 Awakening native
port. It is not a full playable release. Preserve its directory structure and
the validation records when moving or extracting it.

The cloud code artifact contains the new ARM64 app, source-commit metadata,
licenses, and build/render verification. Original game assets are added locally
by `scripts/package-native-scene.py` from the hash-verified source IPA. The
original ARM32 executable is never copied into the native app.

The resulting unsigned IPA is a **first-mission scene test**. It renders recovered
terrain and sprites, previews recovered movement ranges, and measures presented
frames on the testing device. Campaign control, combat, AI, saves, audio and a
complete playthrough are unfinished. Its inspection camera and border treatment
are not claims of original visual parity.

The tester signs the IPA with Sideloadly. Compilation and archive verification
do not prove installation or execution on an iPhone XR. Device results must be
recorded separately; the app's **Share test report** action exports its actual
version, source commit, device, OS and recent presentation measurements.

No background service or compatibility interpreter is part of the app. The
offline original-function oracles in the source repository are development
tools and are not linked or bundled into this artifact.
