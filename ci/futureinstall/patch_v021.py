#!/usr/bin/env python3
"""Fix 0.2.0 PreferenceLoader registration; preserve default-off safety."""
from pathlib import Path
import plistlib
import subprocess
import sys

root = Path(sys.argv[1]).resolve()

def edit(rel, old, new):
    p = root / rel
    s = p.read_text(encoding="utf-8")
    if old not in s:
        raise RuntimeError("Unexpected source drift: " + rel)
    p.write_text(s.replace(old, new), encoding="utf-8")

p = root / "layout/Library/PreferenceLoader/Preferences/FutureInstall.plist"
with p.open("rb") as f:
    data = plistlib.load(f)
entry = data["entry"]
if entry.get("bundle") != "FutureInstallPrefs" or entry.get("detail") != "FIRootListController":
    raise RuntimeError("Unexpected loader entry; abort")
entry["isController"] = True
entry["bundlePath"] = "/var/jb/Library/PreferenceBundles/FutureInstallPrefs.bundle"
with p.open("wb") as f:
    plistlib.dump(data, f, sort_keys=False)

p = root / "FutureInstallPrefs/Resources/Root.plist"
with p.open("rb") as f:
    data = plistlib.load(f)
if data["items"][1].get("key") != "storeClaimEnabled":
    raise RuntimeError("Unexpected preferences; abort")
data["items"][0]["footerText"] = (
    "OFF by default. Turn on Claim incompatible apps just before trying the "
    "App Store request. The experiment lasts 10 minutes. Apple may still refuse "
    "the download; this does not upgrade iOS."
)
with p.open("wb") as f:
    plistlib.dump(data, f, sort_keys=False)

edit("control", "Version: 0.2.0", "Version: 0.2.1")
edit("control", "Name: FutureInstall (experimental)", "Name: FutureInstall (experimental, settings fix)")
edit("FutureInstallPrefs/Resources/Info.plist", "<string>0.2.0</string>", "<string>0.2.1</string>")
edit("tests/validate_deb.py", "fields['Version'] != '0.2.0'", "fields['Version'] != '0.2.1'")
edit("tests/validate_source.py",
     "self.assertEqual(plistlib.load(f)['entry']['bundle'], 'FutureInstallPrefs')",
     """entry = plistlib.load(f)['entry']
            self.assertEqual(entry['bundle'], 'FutureInstallPrefs')
            self.assertIs(entry['isController'], True)
            self.assertEqual(entry['detail'], 'FIRootListController')
            self.assertEqual(entry['bundlePath'], '/var/jb/Library/PreferenceBundles/FutureInstallPrefs.bundle')""")
edit("tests/validate_deb.py",
     """        if not (bundle / 'Root.plist').is_file():
            raise RuntimeError('Settings Root.plist not packaged')""",
     """        if not (bundle / 'Root.plist').is_file():
            raise RuntimeError('Settings Root.plist not packaged')
        with (root / PREFIX / 'PreferenceLoader/Preferences/FutureInstall.plist').open('rb') as f:
            entry = plistlib.load(f).get('entry', {})
        if entry.get('isController') is not True or entry.get('detail') != 'FIRootListController':
            raise RuntimeError('PreferenceLoader controller registration missing')
        if entry.get('bundlePath') != '/var/jb/Library/PreferenceBundles/FutureInstallPrefs.bundle':
            raise RuntimeError('Rootless preference bundle path incorrect')
        if info.get('NSPrincipalClass') != 'FIRootListController':
            raise RuntimeError('Preference controller principal class incorrect')""")
edit("README.md", "**Version:** 0.2.0", "**Version:** 0.2.1")
with (root/"README.md").open("a", encoding="utf-8") as f:
    f.write(
        "\n## 0.2.1: Physical-device Settings repair\n\n"
        "The first Dopamine 3 / iOS 17.5.1 installation appeared in Sileo but had no "
        "entry in stock Settings. The two features were disabled by default; the "
        "iOS 26 App Store alert in that state does not yet test the claim hook. "
        "This patch adds PreferenceLoader isController=true and an explicit rootless "
        "bundlePath. After updating, fully close Settings; if needed use a userspace "
        "reboot from Dopamine, then find FutureInstall in Settings. Enable Claim "
        "incompatible apps for one experiment and report the result. This patch "
        "does not guarantee bypass of Apple's server or iOS 26 app execution.\n"
    )
with (root/"docs/VERIFICATION_REPORT.md").open("a", encoding="utf-8") as f:
    f.write(
        "\n## 2026-11-01 on-device observation (v0.2.0)\n"
        "PASS Sileo installation. FAIL Settings entry absent. UNTESTED claim toggle, "
        "because it was inaccessible and default OFF. App Store still displayed the "
        "minimum iOS 26 requirement for No Man's Sky. v0.2.1 corrects controller "
        "registration but needs a new physical test.\n"
    )
subprocess.run([sys.executable, str(root/"scripts/update_manifest.py")], check=True)
print("FutureInstall 0.2.1 preference registration fix applied")
