# Development-only form-transition oracle

This directory is excluded from the native library and iOS app. It requires
Unicorn 2.1.4 installed externally and privately supplied original executable
and libgcc files. The script verifies both hashes and selects the original
ARMv6 libgcc slice. Neither proprietary input nor the external CPU tool belongs
in the native product or repository.

From the project root:

```sh
g++ -std=c++17 -O2 -Wall -Wextra -Wpedantic -Werror -I native/include \
  native/src/TransformAction.cpp native/src/Combat.cpp \
  analysis_tools/transform_action/probe.cpp -o /tmp/g1_transform_action_probe
python analysis_tools/transform_action/oracle.py \
  --binary /absolute/private/G1awakening.armv6 \
  --libgcc /absolute/private/libgcc_s.1.dylib \
  --movement-oracle analysis_tools/movement/oracle.py \
  --native-probe /tmp/g1_transform_action_probe \
  --unicorn-dir /absolute/external/python-packages \
  --output native/research/transform_action_validation/original_transform.json
```

The complete original unit function executes with audio disabled. A second
audio-enabled prefix stops at the natural audio-call boundary and records its
real receiver, group and event. Only the existing lazy-symbol data pointer is
bound to the original signed-division helper. No instructions or functions are
replaced. The report distinguishes full execution from prefix observations.
