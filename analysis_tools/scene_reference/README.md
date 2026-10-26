# CPU scene integration reference

`render.py` consumes the JSON and native RGBA files emitted by `native/tools/scene_export.cpp`. It approximates the current Metal renderer's raster state for a bounded visual check. It does not execute Metal, UIKit, the original executable, or any guest CPU.

The workflow, compilation command, counts, and limitations are documented in `native/research/SCENE_REFERENCE.md`; the source and input hashes are in `native/research/scene_reference_validation.json`.

The output contains original artwork. Keep exports, rendered PNGs, and compiled tools out of Git. A source/data decoder parity claim, native GPU screenshot claim, or device performance claim cannot be inferred from this CPU reference.
