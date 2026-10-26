# Native battle integration reproduction

The native product uses C++/Objective-C++/Metal and data assets. These host probes
exercise that native implementation; they do not execute the original ARM game.
The separate historical-reference scripts in this directory are development-only
and are excluded from CMake/app delivery.

## Portable public-fixture check

From the project root:

```sh
cmake -S native -B /tmp/g1-battle-native-build -DCMAKE_BUILD_TYPE=Release
cmake --build /tmp/g1-battle-native-build --parallel 2
ctest --test-dir /tmp/g1-battle-native-build \
  -R '^m3g_battle_controller_original_vectors$' --output-on-failure
```

Expected controller result: 1,225 original update records, 159 draw records and
82,600 field checks. The text fixture is reproducible without an ARM binary:

```sh
python analysis_tools/m3g/battle_controller_fixture.py \
  native/research/m3g_validation/original_battle_controller.json \
  /tmp/g1-battle-controller-cases.txt
cmp /tmp/g1-battle-controller-cases.txt native/tests/m3g_battle_controller_cases.txt
```

The converter pins the historical JSON SHA256. Regenerating that original JSON
is a separate task with private original executable/libgcc inputs and the
existing `battle_controller_oracle.py`; see its frozen evidence report. Do not
add those inputs, development emulator dependencies or tools to the app.

## Actual-asset native adapter probe

Requires a privately supplied original `iphone.big`, SHA256
`663d2888982093ce66b7811ccb7a6ad3acd37fc02ffa85144775b88c39e83cb4`.
The archive is not part of these source files or the public fixture. Use an
absolute path for the local private input:

```sh
/tmp/g1-battle-native-build/m3g_battle_presentation_probe /PRIVATE/iphone.big
```

Optional arguments are attacker type, defender type, style, attacker form,
defender form and scenario. These are explicitly synthetic resolved-exchange
inputs; they do not authorize gameplay actions.

| Scenario | Input variation |
| --- | --- |
| 0 | Nonlethal attack and counterattack; both start at 100 HP |
| 1 | Defender destroyed, no counterattack |
| 2 | Attacker destroyed by actual counterattack |
| 3 | Nonlethal attack without counterattack |
| 4 | Nonlethal exchange with attacking faction reversed |
| 5 | Defender destroyed with attacking faction reversed |
| 6 | Already damaged pre-exchange health; no full-health intro |
| 7 | Immune defender retains HP, followed by counterattack |

The recorded model corpus uses types 0–22 as the attacker, type 19 as defender
except attacker 19 uses defender 11; style is `type % 3`, attacker form `type % 2`
and defender form `(type / 2) % 2`. Three additional type 11/type 17 cases cover
the special side B alternate model across all styles. The outcome corpus uses
types 11/19, both form 0, scenarios 1–7 under every style. Each run must reach the
actual controller completion with all eight original submissions prepared.

## Real native session bridge

A second private input is `terrain-tables.bin`, exactly 480 bytes, SHA256
`b870e3d74244741003c8068178e7f58bb5fbe35599599c918e024227463725a8`.
It is a data-only extraction of recovered terrain tables, not executable code.

```sh
/tmp/g1-battle-native-build/m3g_battle_session_probe \
  /PRIVATE/iphone.big /PRIVATE/terrain-tables.bin
```

This creates the actual first Story mission with seed 0x4741 and the core's shared
terrain RNG. Public actions perform transform, movement, a real native AI turn,
movement, transform and attack. Startup world/focus/dialogue/transform feedback
is explicitly synthetic so the test can run without UIKit. The resolved battle
must contain actual attacker HP 95 and defender HP 50.

The adapter then completes its original sequence while preserving the real
pending session token and full game RNG. Repeated frame preparation checks that
intermediate poses differ while controller state/audio remain unchanged. Only
after the final prepared frame does this CPU probe send an explicitly synthetic
host report. It is **not** an Apple drawable acknowledgement or a device test.

The recorded run produced setup tick 81, 534 battle updates, 217 prepared frames,
54 repeated-sampling checks and 46 distinct intermediate cases. Source/data pins
and results are in `native/research/m3g_validation/battle_presentation_validation.json`.

## Apple boundary

`NativeApp.mm` uses the GPU models' retained immutable asset identities, applies
the native drawable-aspect policy, and submits World/A/B/effects/death separately.
Its main-queue completion latch requires successful command completion plus a
positive drawable `presentedTime`, then checks current scene/token/revision and
a drawn final HUD revision before releasing GameSession. No CPU probe fabricates
that callback. The prepared macOS Metal pixel tests, iPhoneOS shader compile and
physical XR run remain separate required gates.
