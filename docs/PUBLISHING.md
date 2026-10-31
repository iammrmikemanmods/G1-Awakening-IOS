# Publish the complete iOS preview

The source-only `v0.17.0-dev1` release is not the game installer. The complete package has been verified locally and renamed **G1-Awakening-iOS-v0.17.0-r1.ipa**. It is byte-identical to the prior 017R1 AppSync package. Repository visibility and the release upload are separate checks.

## Public release identity

- Release: **G1 Awakening for iOS — v0.17.0-r1 · Development Preview**.
- Tag: `v0.17.0-r1`, pinned to `be203a911bc26313615ea450758413e5c9cf6462`.
- Installer: `G1-Awakening-iOS-v0.17.0-r1.ipa` — 37,688,499 bytes; SHA-256 `b035acfe0c08aafa715c54f60a59423191046c271328abbca4cd72689dfaed46`.
- Matching source: `G1-Awakening-iOS-v0.17.0-r1-Source.zip` — 4,501,766 bytes; SHA-256 `af11f0e59e699f9373c9562eb864f4307375e54b82d8e10c40059e7b16a5b932`.
- Checksums: `SHA256SUMS-v0.17.0-r1.txt`.

The Home Screen name is already **G1 Awakening**. Do not change the existing bundle identifier for cosmetic reasons: it is also an update/save-container and signing identity. No internal version bump or new compile is implied by this public filename.

## Publish from the prepared release kit

The kit delivered in the conversation includes the complete IPA, matching source, release notes, checksums and `publish_release.py`. Python 3.9+ and [GitHub CLI](https://cli.github.com/) are required; authenticate through `gh auth login`, not by pasting a token into chat or the script.

Local verification, without network writes:

```sh
python publish_release.py
```

For an already public repository:

```sh
python publish_release.py --publish
```

For this private repository, ONLY after reviewing all history/branches/Actions logs for public exposure:

```sh
python publish_release.py --publish --make-public
```

`--make-public` exposes the whole repository, not merely its release page. It requires administration access. The publisher verifies local file hashes/ZIPs/app identity, pins the tag, creates or resumes a draft, uploads all three attachments, verifies remote sizes and SHA-256 digests, then changes visibility when explicitly requested and publishes as a prerelease. Existing conflicting attachments or tags stop publication; it does not clobber, force-push, change the engine or delete prior releases.

Do not publish an empty/source-only release under the installer title. Do not use a `sandbox:` URL as a GitHub download link. Successful publication must be verified using the actual release assets and anonymous public access.

Official reference: [release upload](https://cli.github.com/manual/gh_release_upload), [release creation](https://cli.github.com/manual/gh_release_create), [release editing](https://cli.github.com/manual/gh_release_edit), [asset digests](https://docs.github.com/en/rest/releases/assets).

## Manual equivalent

Create a draft tagged `v0.17.0-r1` at the pinned source commit, use the [release notes](releases/v0.17.0-r1.md), attach the IPA, matching source and checksum file, verify the uploaded hashes, mark it as a development prerelease, and publish. A private repository still needs a deliberate visibility change before uninvited visitors can access it.
