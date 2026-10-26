# Mission progression reference generator

This directory is a development-only original-function oracle. It is not an
app dependency and must never be linked, embedded or invoked by the native
game. The user supplies the original executable locally; it is not included.

Requirements: Python 3 and `unicorn==2.1.4`. No Ghidra project, Apple SDK,
network access, proprietary archive or original text corpus is needed.

From a repository root with this directory at `analysis_tools/mission_progression`:

```sh
python3 -m venv /tmp/g1-progression-reference-venv
/tmp/g1-progression-reference-venv/bin/pip install -r analysis_tools/mission_progression/requirements.txt
/tmp/g1-progression-reference-venv/bin/python analysis_tools/mission_progression/oracle.py \
  --image /absolute/path/to/G1awakening.armv6 \
  --output /tmp/g1-progression-reference
```

The executable must have SHA-256
`0d510516fe3676ee4a0f4dff60ba64e1c5bf79a0c9800f420b1bbdb1c12febfd`.
Other inputs fail before execution. The generated text fixture must match
`a120950902b56f7a339f774f44f0c7e489f082e533500c24b579c65f78421aa5`.
Compare it with `native/tests/mission_progression_original_vectors.txt`, then
run the native `g1_mission_progression_tests` target against the generated path.
See `native/research/MISSION_PROGRESSION.md` for evidence boundaries.

## Fixture schema

Every row starts with a kind. All integers are decimal. A context has nine
values: group, mission index, owner-0/owner-1 active counts, type-12-active,
owner-0/owner-1 factions, owner-0/owner-1 controller flags.

| Kind | Inputs after kind | Original outputs |
| --- | --- | --- |
| 0 | context; text index | phase; selected owner or -1; audio count; two operation/argument pairs or four -1 values; resolved text-resource ID or -1; configuration flag +0x44 |
| 1 | context; next index; two previous unlock values; two completed flags; three previous record values; three current values; supplied persistence result | two unlock values; two completed flags; finished flag; three updated values; three cached previous values (group2 sentinel 7777/7778/7779); persistence return |
| 2 | context; next index; finished flag | map interaction mode; config mission index; snapshot mission byte; loading-stage value; menu/ending text (-1 menu, -2 next-load); load flag; load group/index or -1/-1 |
| 3 | group; persistence result | mode; save-error flag; error-object field; background offset; handoff call; error-UI call; results-UI call count |
| 4 | background offset Q16.16; image height; input edges; delta ms | updated offset; remaining edges; handoff request |
| 5 | group; mission index | original table resource ID |

External boundaries are listed in `REFERENCE.json`. The supplied persistence
result does not perform a save, and external render/audio/world effects are
requests only. Fragment executions omit C++ unwind setup and teardown while
retaining the actual decision code and ordinary callees. The reference never
turns an unknown instruction, memory fault or unhandled import into a success.
