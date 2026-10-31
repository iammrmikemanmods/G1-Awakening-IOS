# Install G1 Awakening iOS

[Back to the project](../README.md) · [Release register](RELEASES.md) · [Known limitations](STATUS.md)

## Before you start

Use a **complete project IPA**, not GitHub's automatically generated source ZIP or a code-only Actions artifact. Obtain it through the maintainer's release channel; if the release contains no IPA, it is not a one-click game download. No installer supplies missing original game data.

Current candidate: **017R1**, app version **0.17.0 / build 17**. It requires an ARM64, Metal-capable iPhone or iPad running **iOS/iPadOS 15.0 or newer**. This is a compiled lower bound, not proof that every newer device/OS works. Earlier native gameplay was demonstrated on an iPhone XR; 017R1 still needs physical installation and regression checks.

Keep the original IPA and a backup of your saves. Close the app before an upgrade. Do not delete an existing installation to solve a signing error. A different bundle ID, signing team or installer may create a separate data container instead of upgrading it.

## A. Standard TrollStore

**Only for supported devices and OS builds.** Upstream lists iOS 14.0 beta 2–16.6.1, 16.7 RC **20H18**, and 17.0. This game's iOS 15.0 minimum excludes the iOS 14 part of that range. Final 16.7.x is not the supported RC; iOS 17.0.1+ is not supported by standard TrollStore. In particular, **stock iOS 17.5.1 is not a standard TrollStore target**. [Official compatibility source](https://github.com/opa334/TrollStore#trollstore).

1. Install or update TrollStore using the installation guidance linked from its official repository for your exact OS/device. This guide assumes it is already working; it does not instruct you to change iOS or jailbreak.
2. Save the complete game IPA in Files. Share/open it with TrollStore, or use TrollStore's IPA import option, then review and confirm installation.
3. Open the game in landscape. Check intro playback/skipping, menu navigation and a new mission before relying on an existing save.
4. For updates, import the new IPA through the same installer. Follow any replacement prompt without first deleting the app; keep a save backup regardless.

Standard TrollStore is designed for persistent installation, unlike the seven-day free-development-signing cycle. This describes TrollStore, not completed testing of the game through it. [Official project](https://github.com/opa334/TrollStore).

### TrollStore Lite is different

Upstream introduced **TrollStore Lite for jailbroken iOS versions**. It is not a way to extend standard TrollStore's CoreTrust compatibility to stock iOS 17.5.1 or later. Use the maintainer-linked package, verify compatibility with your jailbreak, and treat it as a jailbreak-dependent installation path. This project does not promise apps will launch outside the jailbroken state. [Upstream release notes](https://github.com/opa334/TrollStore/releases) · [Maintainer-linked package](https://havoc.app/package/trollstorelite).

## B. Jailbreak + AppSync Unified + Filza

The existing `...AppSync.ipa` candidate was prepared for this route. Its embedded ad-hoc signature is **not** a developer provisioning profile and does not make it installable on an ordinary stock device by itself.

1. Confirm your device is already in its working jailbroken state. Check that the **official** AppSync Unified package supports your exact OS and jailbreak/bootstrap. Do not force-install an incompatible rootful package into a rootless setup.
2. Install AppSync Unified from the repository linked by its author, and install Filza from its official distribution. Complete any respring/restart steps those packages request. [Official AppSync instructions](https://github.com/akemin-dayo/AppSync#how-do-i-install-appsync-unified-on-my-jailbroken-ios-device) · [Filza](https://www.tigisoftware.com/default/?page_id=78).
3. Transfer the complete IPA to the device and open it in Filza. Choose the IPA installation action and allow the installer to finish.
4. Launch from the Home Screen, then test the intro, menus, sound, Mission 1 and save/resume.

Filza's author documents opening/installing IPAs and requiring AppSync for unsigned packages. Exact prompts vary by Filza version. An ad-hoc-signed AppSync candidate still depends on the compatible jailbreak installation path. [Filza's IPA installation guide](https://www.tigisoftware.com/default/?page_id=177#4).

After a reboot, a semi-untethered jailbreak may need to be re-enabled before jailbreak-dependent applications launch. Follow your jailbreak's own documentation; do not reinstall/delete the game as the first fix. AppSync compatibility does not lower this application's iOS 15.0 minimum.

## C. Sideloadly on Windows or macOS

**Documented re-signing route; 017R1 has not been verified through it.** Sideloadly must sign/provision the complete IPA with your Apple ID. The game's native ARM64 runtime does not require an emulator, JIT session or debugger attachment.

1. Download Sideloadly from [sideloadly.io](https://sideloadly.io/). On Windows, follow its current iTunes/iCloud dependency instructions; its website specifies the web versions rather than Microsoft Store editions.
2. Connect the unlocked device by USB and accept the device's **Trust This Computer** prompt. Select it in Sideloadly.
3. Load the complete game `.ipa` and enter your Apple ID. Use the same account and bundle-ID settings as an existing Sideloadly installation to attempt an in-place update. Never post passwords, verification codes or signing tokens in a bug report.
4. Start the Apple-ID signing/install process and complete any authentication prompts. Do **not** choose ad-hoc-only signing for a stock device, inject extra tweaks, or lower the minimum iOS value to bypass compatibility checks.
5. If iOS requests developer trust, use **Settings → General → VPN & Device Management** and trust the relevant developer profile. On iOS 16+, enable **Settings → Privacy & Security → Developer Mode** when required, complete the restart and confirm the system prompt.
6. Launch the game. If signing, entitlement or provisioning errors occur, retain the log, redact personal identifiers and report the exact error. Do not assume an AppSync package was successfully converted merely because it uploaded.

A free Apple developer account normally signs for **seven days**; Sideloadly also documents a three-app free-account limit on modern iOS. Paid developer signing can last up to one year. Auto-refresh requires Sideloadly's daemon and a computer able to reach the device by USB or configured Wi-Fi. Keep backups and use the same signing identity for refreshes. [Official FAQ](https://sideloadly.io/faq) · [Apple Developer Mode guide](https://developer.apple.com/documentation/xcode/enabling-developer-mode-on-a-device).

## Verify the file before installing

For the existing 017R1 AppSync candidate:

```text
G1_Awakening_iOS_017R1_Remaster_Intro_AppSync.ipa
37,688,499 bytes
SHA-256: b035acfe0c08aafa715c54f60a59423191046c271328abbca4cd72689dfaed46
```

Windows PowerShell:

```powershell
Get-FileHash .\G1_Awakening_iOS_017R1_Remaster_Intro_AppSync.ipa -Algorithm SHA256
```

macOS:

```sh
shasum -a 256 G1_Awakening_iOS_017R1_Remaster_Intro_AppSync.ipa
```

A re-signed IPA has different bytes and therefore a different checksum. Verify the original download **before** re-signing. Never paste a mismatched hash into a report as a successful check.

## Updates, saves and first-run checks

The resource revision is **017R1**, but Settings may still report **0.17.0/build 17** because this revision preserves the executable and app metadata. The filename/hash and packaged `G1ResourceRevision.json` distinguish it from the earlier package.

Before installing, retain a device/app-data backup appropriate to your installer. With an existing jailbroken installation, back up the app's data container, not only its executable directory. Do not assume cloud saving or Files export is present. Avoid switching between TrollStore, AppSync and Sideloadly without a verified save migration.

For a useful smoke test: play/skip the intro; navigate Play/Settings/Help; enter Mission 1; select/move a unit; check dialogue and combat; complete an action; close/reopen and use Continue. Try Classic and Modern separately. Report visual, audio, input and save problems independently.

## Troubleshooting

| Symptom | First checks |
| --- | --- |
| Missing application identifier / invalid signature | Confirm the correct route, working AppSync or developer provisioning, complete IPA and unmodified download hash. Do not blindly add entitlements. |
| No TrollStore option | Verify standard TrollStore's OS range; Lite is not the same product. |
| Developer Mode / untrusted developer message | Follow the Sideloadly and Apple steps above. |
| App stopped opening after a week | Check development-signing expiry and refresh with the same Apple ID/bundle ID. |
| App stopped opening after reboot | Verify the jailbreak state for AppSync/Lite, or follow standard TrollStore's own registration guidance. |
| Startup crash after a valid install | Record device, OS, resource revision and crash log; this may be a runtime defect rather than signing. |
| Save seems missing after changing installers | Check whether a new data container/identity was created; preserve both installations and backups before further changes. |
| Cropping, black borders, missing art or poor performance | Attach a screenshot and graphics mode. These remain active project QA areas; do not describe them as installation failures. |

Third-party tool guidance checked **31 October 2026**. Follow upstream for changes; this guide is not a universal jailbreak compatibility list.
