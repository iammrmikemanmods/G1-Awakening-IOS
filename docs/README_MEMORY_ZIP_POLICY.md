# Native development artifact policy

Preserve this file, the archive's directory structure, source identity and
validation records when moving or extracting a G1 Awakening native-port
artifact. These artifacts are development checkpoints. A complete playable
release requires the separate gates recorded in `PORT_STATUS.json`.

## Source review archive

`G1_Awakening_Native_Build_005_Source.zip` is an earlier review checkpoint. It
contains the reviewed native source,
build workflow, development tools and validation evidence. It contains no
compiled iPhone app, installable IPA, original game archive or original
executable. Its root `README.md` describes implementation scope and remaining
work. `validation/NATIVE_COMPLETE_HOST_CHECKPOINT.json` records the exact final
host checks. `validation/native_source_manifest.json` identifies every included
repository file except that manifest itself.

The source connects native gameplay, enemy turns, campaign handoffs, saves,
all three terrain styles and ordinary animated 3D battles. The current host
pilot completes all seventeen Story missions and persists the campaign ending.
Its presentation feedback is synthetic. That result is a complete headless Story path, not a rendered
or device playthrough. Build 005 passed Apple app/shader compilation and both synthetic Metal pixel
probes. A separate native mode pilot also completes all 8 Showdown missions and
all 20 Arena configurations through natural handoffs. Remaining support
percentage, sound-event and original-presentation work, and physical XR checks
still apply. See docs/NATIVE_GAME_TEST_005.md for the exact shipped IPA identity.

## Hosted code artifact and packaged test IPA

After a successful Apple build, the separate cloud code artifact contains the
new ARM64 app, source-commit metadata, licenses and build/render verification.
Original game assets are then added locally by `scripts/package-native-scene.py`
from the hash-verified source IPA. The original ARM32 executable is never
copied into the native app. Keep the code and validation from the same commit.

The tester signs the resulting IPA with Sideloadly. Compilation and archive
verification do not prove installation or execution on an iPhone XR. Device
results must be recorded separately; the app's **Share test report** action
exports its actual version, source commit, device, OS and recent presentation
measurements. The earlier build 002 scene-test IPA is not this source checkpoint.

No compatibility interpreter is part of the app. Offline original-function
oracles in the source archive are development tools; neither those tools nor
the original executable are linked or bundled into the app.
