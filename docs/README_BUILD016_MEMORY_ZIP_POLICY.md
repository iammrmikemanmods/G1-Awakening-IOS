# Build016 memory ZIP policy

Preserve exact repository paths, prior Build015 source/IPA and user saves. This is a development candidate, not a complete animated 3D tactical port or a claim of on-device fidelity.

Source exports include the exact compiled source, source commit, relevant test evidence and a per-file SHA-256 manifest. Reject duplicate paths, traversal, absolute paths, CRC failures and mismatched source/binary identities. Do not include build caches, credentials, original game executables, original asset archives, raw mesh/image dumps or separately exported font files.

Original owner archive SHA-256: 663d2888982093ce66b7811ccb7a6ad3acd37fc02ffa85144775b88c39e83cb4. Original game and cinematic package members must remain byte-identical to Build015. Gameplay rules, mission boundaries, pathfinding and save formats must remain unchanged.

Modern uses original 3D character poses for supported stationary states, with uniform whole-model transforms. Walking, transformations, unsupported alternates, special effects, memory-pressure states and model failures retain original sprites. Do not describe these fallbacks as complete 3D locomotion or transformation animation.

Material enhancement alters derived GPU image pixels only; source image geometry, texture coordinates, alpha contracts and animation bindings remain original. Classic retains original tactical sprites and material uploads.

CPU mesh review renders are labelled CPU reference renders, not screenshots from UIKit, Metal or a physical iPhone. Hosted synthetic Metal tests do not establish original-model visual quality, frame pacing or XR touch correctness. Exterior detail proposals remain render-only review files, not additions to the playable mission grid.

The compiled target remains iOS 15.0 for iPhone/iPad. iOS 7-14 and other Apple platforms are not established. Ad-hoc AppSync executable signing is not Apple developer provisioning or App Store approval.

Reproduce portable checks: cmake -S native -B build/native -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTING=ON; cmake --build build/native; ctest --test-dir build/native --output-on-failure. A frozen export is immutable; corrections require new hashes and a new checkpoint.
