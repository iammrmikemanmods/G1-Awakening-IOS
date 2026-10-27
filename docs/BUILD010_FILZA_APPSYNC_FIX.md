# Native Build010 — Filza/AppSync Unified installation hotfix

## Symptom and exact original defect

On a jailbroken iPhone XR with AppSync Unified, Filza's direct IPA
installation reported **"Application is missing the application-identifier
entitlement."**

This did not mean CFBundleIdentifier was missing. The unmodified Build010 IPA
has `CFBundleIdentifier=org.g1awakening.native.test` and the correct
version/icon/game data, but its iPhoneOS ARM64 Mach-O contains **no
LC_CODE_SIGNATURE**, no embedded entitlements and no provisioning profile.
That is expected of the old unsigned-for-Sideloadly delivery, but insufficient
for this direct Filza install path.

Apple's TN2319 documents the missing-identifier error:
https://developer.apple.com/library/archive/technotes/tn2319/_index.html

The AppSync Unified hook can synthesize signing information once it can read
the executable's entitlements, and handles missing application-identifier as a
special case. It cannot get a signing dictionary from a binary with no valid
entitlement-bearing signature:
https://github.com/akemin-dayo/AppSync/blob/master/AppSyncUnified-installd/AppSyncUnified-installd.x

## Fixed separate IPA

**File:** `G1_Awakening_Native_Full_Game_010_Filza_AppSync.ipa`
**IPA SHA256:** `dca308f16617fb48bdfc4aa0f70da6a182c385961034183f48a0fc261e55a639`
**Size:** 7,777,280 bytes.

- The existing, previously tested Build010 iPhoneOS executable from signed
  source **`00952f1c520fdb0b14a758471d2b6988f4240473`** was reused, not
  recompiled or edited for gameplay.
- Hosted macOS `codesign --sign -` applied an **ad-hoc signature** to the
  *standalone* Mach-O (outside the partial app directory), with
  `application-identifier=org.g1awakening.native.test` (string) and
  `get-task-allow=true`. Using a standalone target avoids an invalid
  `_CodeSignature/CodeResources` seal after the original data is added locally.
- The signed ARM64 executable is 1,671,440 bytes; SHA256
  `e71256843a055b24b8ba54e79b045609aaa66624b248fea2d1e259ede422786f`.
- Apple's `codesign --verify --strict` passed and a separate binary parser
  checked LC_CODE_SIGNATURE, CodeDirectory, signed XML entitlements and
  identical bundle ID. The code artifact contains no bundle CodeResources.
- The fixed IPA was produced by replacing **only**
  `Payload/G1AwakeningNative.app/G1AwakeningNative` in the pinned, already
  validated original Build010 IPA. Every other ZIP member is byte-for-byte
  identical, including all original G1 resources, 480-byte terrain data, six
  original iPhone icons, Info.plist, bundle identifier, license files and
  original source provenance.
- Fixed version stays 0.10.0 / build 10, minimum iOS17.5.
  **No Apple Developer certificate/provisioning profile** is included.

**Apple CI:** [40442335711](https://github.com/iammrmikemanmods/G1-Awakening-IOS/actions/runs/40442335711)
succeeded and preserved signed *code only* in artifact
`12707080814` (SHA256
`c722b4f672d798e0c034369eee7a8f7c615194959eb0eeb96da9a0533f88ac22`).
No copyrighted original game data was uploaded to Github for signing.

The fixed IPA and its validation sidecar are in the user's
**G1 Awakening Port** ChatGPT Library folder. The original unsigned Build010
IPA remains preserved for Sideloadly.

## User installation and residual uncertainty

This variant is intended for **Filza + AppSync Unified on an actively
jailbroken phone**, not for an ordinary non-jailbroken iPhone or App Store.
In Filza, choose the new `...Filza_AppSync.ipa` and Install; never try the
old unsigned `...Full_Game_010.ipa` for this direct route.

If an earlier differently signed copy of the **same bundle ID** is installed,
iOS may reject an upgrade because its original application-identifier team
prefix does not match the ad-hoc signature. Do not uninstall just to force
the installation: first preserve the installed application's private
`Documents` and `Library` save data through Filza. Signature and bundle
identities should be compared from the actual phone error before deciding on
any migration.

**No physical iPhone XR installation was performed by this GitHub/macOS
workflow.** Neither this signature nor the previous host Story/Showdown/Arena
pilots prove a full rendered device playthrough or sustained 60fps.

Machine-readable manifest:
`validation/NATIVE_FULL_GAME_010_FILZA_APPSYNC.json`.
