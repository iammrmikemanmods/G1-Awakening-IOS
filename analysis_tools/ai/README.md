# Development-only original AI comparison

These Python tools execute pinned original ARM functions to derive independent
reference values for the native C++ reconstruction. They are not shipped or
linked into the native iOS application. Original executable/resource inputs
must remain local. No game function or AI result is replaced by a host formula.

Run from the project directory containing `native/` and `analysis_tools/`.
The commands below use the already installed isolated Unicorn package and the
locally supplied original inputs. Supply equivalent paths when reproducing.

```sh
python3 analysis_tools/ai/oracle.py \
  --binary research/binary/G1awakening.armv6 \
  --libgcc ../.tools/g1_runtime/Applesauce/touchHLE_dylibs/libgcc_s.1.dylib \
  --unicorn-dir /tmp/g1-movement-oracle-tools/python \
  --output research/native_ai/original_attack.json \
  --fixture native/tests/ai_attack_cases.txt --count 192 \
  --archive research/assets/iphone.big \
  --source-fixture research/native_ai/source_attack_cases.txt

python3 analysis_tools/ai/planner_oracle.py \
  --binary research/binary/G1awakening.armv6 \
  --libgcc ../.tools/g1_runtime/Applesauce/touchHLE_dylibs/libgcc_s.1.dylib \
  --unicorn-dir /tmp/g1-movement-oracle-tools/python \
  --output research/native_ai/original_planner.json \
  --fixture native/tests/ai_planner_cases.txt --count 128

python3 analysis_tools/ai/turn_oracle.py \
  --binary research/binary/G1awakening.armv6 \
  --libgcc ../.tools/g1_runtime/Applesauce/touchHLE_dylibs/libgcc_s.1.dylib \
  --unicorn-dir /tmp/g1-movement-oracle-tools/python \
  --output research/native_ai/original_turn.json \
  --fixture native/tests/ai_turn_cases.txt --count 192

python3 analysis_tools/ai/source_oracle.py \
  --binary research/binary/G1awakening.armv6 \
  --libgcc ../.tools/g1_runtime/Applesauce/touchHLE_dylibs/libgcc_s.1.dylib \
  --unicorn-dir /tmp/g1-movement-oracle-tools/python \
  --world-json research/binary/native_world/native_world_actual.json \
  --output research/native_ai/source_planner.json \
  --fixture research/native_ai/source_planner_cases.txt
```

Omit both archive/source-fixture options from the first command for the
synthetic-only corpus. Planner and turn commands append nine explicit type21
cost-boundary cases to their requested varied counts. The shared original
map+0x14c table applies the loader's type21-to40 override; the raw resource
values remain unchanged in the fixture. See `native/research/EFFECTIVE_UNIT_COST.md`.
The last command consumes the independently validated
native world-probe export; its hash and the explicitly seeded scenario changes
are recorded. It does not claim to observe an actual live opponent turn.

`site_oracle.py` is the separate capture/income owner’s whole-function check.
It imports `OriginalAI` but is not edited as part of the attack/fallback work.
See `native/research/AI_RECOVERY.md` for API/behavior and compact evidence paths.
Never commit source-data fixtures, the original inputs, raw reports containing
decoded source bytes, or local reference executables. The C++ tests run without
Unicorn, original binaries or original game resources.
