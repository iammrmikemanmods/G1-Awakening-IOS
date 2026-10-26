# Battle timeline reference runner

This is a development-only reference for two functions in the user's original
ARMv6 executable. It is not built or linked into the source-native game.

## Required inputs

- Python 3.10 or newer.
- Unicorn 2.1.4, used for the recorded run. Pass the directory containing the
  unicorn Python package to --unicorn-dir.
- The exact original ARMv6 Mach-O image; the script checks SHA256
  0d510516fe3676ee4a0f4dff60ba64e1c5bf79a0c9800f420b1bbdb1c12febfd.
- The exact original universal libgcc_s.1.dylib; it checks SHA256
  d758fbf1ac952532955d62866bd02df55315c0599f64bdd978ff941fccbdcf83.
- The adjacent analysis_tools/combat/oracle.py from this repository. This
  supplies the existing checked Mach-O/libgcc loader, synthetic memory, and
  bounded function caller. --combat-oracle can override its location.

The main original image uses a VM-to-file offset of 0x1000 for the inspected
sections; this is specific to the checked image. The original libgcc's
ARMv6 slice is selected from its universal Mach-O header and mapped by its
actual segments. No system library or host float substitute provides the
original function results.

The runner is portable as copied. Its only default filesystem assumption is
that m3g/ and combat/ are siblings under analysis_tools/. All private input,
dependency, and output locations are command-line arguments.

## Run

~~~bash
python3 analysis_tools/m3g/battle_timeline_oracle.py \
  --binary /private/G1awakening.armv6 \
  --libgcc /private/libgcc_s.1.dylib \
  --unicorn-dir /path/to/unicorn/site-packages \
  --output /tmp/original_battle_timeline.json
~~~

The committed output fixture is
native/research/m3g_validation/original_battle_timeline.json. It contains six
start cases and 48 update cases: each clip is tested before its end, at the
integer part of its end, across its end, and with a large step, with restart
both disabled and enabled. The in-range case uses a positive delta to expose
the original sample-before-clock-update ordering.

## Exact scope

The unchanged original functions at 0x3c23a and 0x3c950 and the unchanged
original ARMv6 libgcc arithmetic execute. Synthetic endpoints record
retain/release and the public virtual-slot-0x24 time argument. Nonthrowing
SjLj register/unregister calls are external boundaries.

The result verifies original instruction regions remain unchanged. It
records requested times; it does not execute an actual model, evaluate
tracks, run the complete cinematic, compare pixels, or measure frame rate.
The public animate-wrapper identification is separate static evidence in
native/research/M3G_PUBLIC_ANIMATE.md. The state/model/clip binding evidence
is native/research/M3G_BATTLE_BINDING.md.

The runner and JSON contain no original machine-code, library, M3G, image,
audio, or game-text payload. Keep private reference inputs outside the
repository and the shipped application.
