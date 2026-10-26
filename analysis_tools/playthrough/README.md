# Native gameplay input pilot

This development tool drives the source-native game through public `GameSession` commands and lets the actual native opponent AI take its turns. It requires no original executable, emulated CPU, interpreter or Apple SDK. It is not built into or shipped with the iOS application.

The frozen continuous run completed **seven consecutive Story missions, indices 0–6**, saved the real native profile after each, and then lost index 7. The final isolated matrix reached a real terminal handoff in all 30 scripts: 13 success branches and 17 losses. Starting each mission independently is explicitly different from completing a campaign.

World, camera, dialogue, transform, battle, results and menu feedback is **synthetic**. The tool does not verify UIKit/Metal/audio, real input handling, iPhone performance or a fully rendered playthrough. See `native/research/PLAYTHROUGH_PILOT.md` for the evidence and limits.

## Required local inputs

- The audited `iphone.big`, SHA256 `663d2888982093ce66b7811ccb7a6ad3acd37fc02ffa85144775b88c39e83cb4`. Extract it locally from the supplied original IPA. Do not commit it.
- The already recovered 480-byte terrain visual table data. Its exact hash is recorded in the frozen run provenance. It must be the same table data used by the native app and terrain reference.
- A C++17 host build of the native core, plus Python 3.10 or later for this optional metadata wrapper. Python has no third-party dependencies.

The source is `native/tools/session_playthrough_probe.cpp`. The host-only CMake target is `g1_session_playthrough_probe` once integrated by the build owner:

```sh
cmake -S native -B build/native -DCMAKE_BUILD_TYPE=Release
cmake --build build/native --target g1_session_playthrough_probe
```

The independently verified direct Linux build form is:

```sh
c++ -std=c++17 -Wall -Wextra -Wconversion -Werror -pedantic -O2 \
  -I native/include native/tools/session_playthrough_probe.cpp \
  build/native/libg1_resources.a build/native/libg1_png.a \
  build/native/libg1_vorbis.a -lz -o build/native/g1_session_playthrough_probe
```

## Reproduce a continuous attempt

Use new output directories. The runner records the actual command, executable, source and input hashes and refuses to overwrite an earlier run.

```sh
python3 analysis_tools/playthrough/run_probe.py \
  --probe build/native/g1_session_playthrough_probe \
  --native-source native \
  --archive /absolute/local/path/iphone.big \
  --terrain-tables /absolute/local/path/terrain-tables.bin \
  --output /tmp/g1-native-continuous \
  --strategy native-planner-search \
  --group 0 --start-mission 0 --seed 0x4741 \
  --max-missions 17 --max-ticks 200000 \
  --max-human-turns 500 --max-seconds 90
```

The frozen attempt uses 5,920 native ticks of 30 ms, with 87 moves, 90 attacks, 11 captures, 47 transforms, nine human production actions and 100 human end-turn commands. It writes eight actual native profiles, including the loss result. The persisted Story unlock index is 7; neither campaign completion flag is set. These counts describe accepted live human commands, not speculative search branches.

For isolated coverage, add `--matrix --max-ticks 50000 --max-human-turns 100 --max-seconds 30`. Each of the 30 runs starts independently with the requested seed and a fresh profile. An isolated final-mission ending is not evidence that earlier missions were completed.

## Strategy and checkpoint boundary

`direct`, `economy`, `coordinated` and `coordinated-economy` are test-input heuristics. The coordinated variants move the formation before issuing strongest-first attacks. They never add supporting fire or change battle rules.

`native-planner` also uses the recovered AI planner as **read-only input advice** for elimination objectives. Its proposed form/stat side effects are not applied. Every selected move, transform, capture, heal, upgrade, production or attack must pass the ordinary public human command's admission checks. The controller flags are never changed.

`native-planner-search` adds a bounded search only for the unarmed, two-unit escape objective. It restores exact public checkpoints into separate simulation instances, runs only ordinary human commands and real native opponent turns there, and chooses a command sequence. It does **not** install the winning simulated state into the live session. The sequence is replayed on that existing live session; each completed intermediate step must match its entire encoded native checkpoint, including RNG and terrain state.

The continuous frozen run evaluated 6,481 accepted branch commands with no settle-bound failure, then matched 22 intermediate live checkpoints. Limits are 30,000 branch evaluations, ten complete turns and ten seconds per search. This is a bounded beam search, not an exhaustive proof of solvability. The final movement has no checkpoint because the game itself has left the live objective gate.

## Output and interpretation

Each run writes `result.json`, `events.jsonl` and actual native profile/checkpoint files when their real save boundary is reached. The wrapper writes provenance and a combined summary. Preserve the metadata, but do **not** commit `*.g1native`, the input archive/table data or compiled executables.

- `mission_count_bound` after a recorded `next_mission` is a successful native handoff followed by the requested test limit.
- `native_loss_handoff` is an actual native loss. It is not a test crash.
- Tick, turn or wall-time bounds are inconclusive for that strategy.
- `native_exception` or a replay mismatch is a blocker to investigate.
- Process exit 0 means the probe finished normally; it never means every campaign mission was won.

The early development probe mistakenly counted a nonempty insufficient-funds heal result as success and retried it. The frozen source checks `HealOutcome::healed`; old attempt counts are not used as health-restoration evidence. The final source and all 30 final outcomes are recorded separately.

