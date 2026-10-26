# Original production and transport reference

This is a development-only reference runner. Neither it nor Unicorn is built
into or distributed in the native application. The original ARMv6 executable
and optional original archive are explicit local inputs and are not included.

The runner verifies the executable and shared support hashes, maps original
code read-only, and checks it unchanged after each case. Install the pinned
Python requirement into an isolated local environment. Pass its site-packages
directory through `--unicorn-dir` (the option inserts it into Python's module
search path).

From this repository root:

```sh
python analysis_tools/unit_interactions/oracle.py \
  --image /local/path/G1awakening.armv6 \
  --support analysis_tools/world/world_oracle.py \
  --movement-support analysis_tools/movement/oracle.py \
  --unicorn-dir /local/path/site-packages \
  --archive /local/path/iphone.big \
  --output /local/path/unit-interactions-reference
```

`--archive` adds the one real-data static-link case. Include it to reproduce the
checked-in 869-case native fixture exactly. Without it, the synthetic reference
remains usable but has one fewer native case. The reference executes 877 cases
in total: eight selected-name callback cases are retained as provenance only,
because the native product does not implement that legacy UI dispatcher.

Compare the resulting `unit_interactions_original_vectors.txt` byte-for-byte
with `native/tests/unit_interactions_original_vectors.txt`, then pass that path
to the native `g1_unit_interactions_tests` target. The native tests do not need
Unicorn or the original executable/archive; they use the checked-in vectors.

`REFERENCE.json` records original addresses, exact input/source/output hashes,
and the recorded string/audio/renderer boundaries. No decision, cost,
activation or deactivation function is replaced. A few fragments stop at an
explicit natural boundary before unrelated UI logic. See
`native/research/UNIT_INTERACTIONS.md` for the confirmation-path distinction,
static links and the integration contract.

No Apple build, device test or complete campaign playthrough is implied by
these local function comparisons.
