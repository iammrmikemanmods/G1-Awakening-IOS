# Publication and recovery package policy

This checkpoint changes visitor documentation, screenshots, issue reporting and an explicitly source/native-code-only release publisher. It does not merge or alter native gameplay source, replace saves, repack the game IPA or change repository visibility.

Preserve repository-relative paths and the archive/pre-public-page-20261031 rollback branch. Verify ZIP CRCs, reject duplicate/traversal paths and compare every per-file SHA-256 before applying a recovery package. The previous README is preserved byte-for-byte under docs/history/README-before-public-page.md.

Source releases must identify the exact compiled commit and contain no original game archive, original executable, owner saves, credentials, signing keys or standalone font files. A code artifact is not a complete installable game. Screenshots must retain their actual capture provenance and distinguish older device evidence from newer development previews.

Never silently overwrite a published release asset with different bytes. Record corrections as a new revision or clearly documented release change.
