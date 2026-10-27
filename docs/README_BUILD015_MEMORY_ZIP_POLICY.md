# Build015 source and package integrity policy

This is a development candidate for native ARM64 iPhone/iPad presentation. It is not a complete UI-parity release or a claim of physical-device validation.

- Preserve repository paths; extract source archives without flattening directories.
- Freeze the exact compiled source commit, CI run, artifact hashes and final per-member manifest. Verify ZIP CRCs and reject absolute paths, traversal paths and duplicate members.
- Preserve prior Build014 source, IPA and save data. Never replace user saves or the original mission grids while applying presentation fixes.
- Original assets remain byte-identical in the user-supplied archive. Its SHA-256 is `663d2888982093ce66b7811ccb7a6ad3acd37fc02ffa85144775b88c39e83cb4`. No original game executable or copyrighted asset bytes are committed to this repository.
- Source ZIPs do not include the original IPA, game art, cinematic, private keys, tokens, save files, build caches or separately exported font files.
- Final IPA packaging uses the validated signed native executable, compiled Info.plist and the user's existing resources. Derived iPad app icons must come from the original app icon, not invented art.
- AppSync ad-hoc executable signing is not Apple developer provisioning or App Store approval.
- Current candidate deployment target is iOS 15.0. Desired iOS 7 onward compatibility is an open legacy-renderer/toolchain task; it must not be claimed from a plist edit.
- Hosted GPU checks use synthetic geometry and do not establish XR/iPad frame pacing or original-game screenshot parity.
- Environment-extension previews and snap pieces are unapproved, non-playable proposals. They must not change navigation, terrain rules, missions, saves or playable bounds. Do not silently enable them in the candidate.

Reproduce portable checks with `cmake -S native -B build/native -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTING=ON`, `cmake --build build/native`, and `ctest --test-dir build/native --output-on-failure`.

See `docs/ADAPTIVE_PRESENTATION_015.md` for implemented changes and explicit remaining work. A source backup is immutable after export; corrections receive new hashes and a new checkpoint.
