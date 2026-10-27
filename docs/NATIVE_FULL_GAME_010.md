# Native iOS full-game candidate 010 — original app icon and final campaign-pilot evidence

**Installer:** `G1_Awakening_Native_Full_Game_010.ipa`
**Platform:** genuine iPhoneOS ARM64, minimum iOS17.5, designed for iPhone XR.
**Status:** complete campaign-content *release candidate*, unsigned for Sideloadly,
with **all source-native campaigns re-executed using the original resources**.
A full rendered physical-device playthrough has **not** yet been observed, so
there is no credible universal 'zero issues on every mission' certification.

## Original icon, presentation and settings

The source IPA's untouched **iTunesArtwork** is a 512×512 JPEG,
SHA256 `21503f76f7c3aefdf5d23c5be7229bd43134b2cbf2b08af155982e2543a837f8`.
The original 57/114px PNG files are old and may not decode correctly with modern
libraries. Instead, packaging resizes that original 512 artwork to six valid,
unmodified-design RGB PNGs (60,120,180 and 40,80,120 pixels), with exact
`CFBundleIcons.CFBundlePrimaryIcon.CFBundleIconFiles` names. Those artwork
bytes are added **locally** from the user's source IPA; no copyrighted art is
committed to Git or reconstructed by AI. Modern icon display is only guaranteed
by an actual iPhone install, not a PNG-size check.

The app launches directly into the original G1 art menu; it does not display
legacy Glu intro/video/blog or online feedback. Existing native Story/Showdown/
Arena selector, saved Music/Sound, Classic/Modern 2D sprites, G1 fan-port credits,
pause/resume and Test report are preserved. Added a stored touch pan/pinch
sensitivity choice, 0.75/1.00/1.25/1.50×, with a corrected Help/Credits Back
route when opened from Settings. Bundle ID and all save codecs remain unchanged.

## Current successful compiled source

- Reviewed production source: `802d26180b5c1c6a68d0ebe3ef6af63fc19c0413`.
- Exact Git tree: `eb44ec926a98330c11ed646bc05694edc069d912`.
- GitHub's PR5 synthetic compiled merge: `00952f1c520fdb0b14a758471d2b6988f4240473`;
  **identical Git tree**. The latter SHA is embedded in Info.plist and
  is the packaging identity.
- [GitHub workflow 40435216799](https://github.com/iammrmikemanmods/G1-Awakening-IOS/actions/runs/40435216799):
  **success**, 63/63 portable suites on Linux and Apple ARM64, native
  iPhoneOS app and Metal shaders compiled. 14 tactical/support and
  12 M3G pixel checks passed using **synthetic** images on a hosted
  Apple Paravirtual GPU.
- Hosted code artifact 12703826559 SHA256
  `46384ef6dc82eea1b76135674aaa57234e4c753285b7e42f3ce4a3ee6049b72d`.
- Compiled ARM64 executable 1,649,384 bytes SHA256
  `c6f02ec45ac9646bc4941172c9eaf43598b0ac412fe564a85881458dd1d4ea90`.
- Full signed-by-user IPA source package (unsigned) **7,772,336 bytes**,
  SHA256 `42be2c0a16c8b1f32afeda445c90cd92ba02bf742d5c0ebe2b293d60a4bfdb77`.
  All ZIP member CRCs/bytes, six PNG resolutions, original game data pins,
  ARM64 executable and exact source commit were independently checked.
  No original ARM32 executable/emulator/JIT is packaged.

## Fresh exact-Build010 native source gameplay runs

The compiled, reviewed native C++ sources were exported from the same PR
merge's source snapshot, then compiled locally against the **user's pinned
original `iphone.big` and exact recovered 480-byte terrain data**. This
was a new run, not a relabel of Build006 pilots.

- **Story: 17/17 missions** from a new Story menu start through the actual
  campaign ending. 17 checked profile writes; 797 exact replay checkpoint
  comparisons. Outcome `native_campaign_ending`.
- **Showdown: 8/8 missions** starting from the actual completed Story
  profile and passing native unlocked-mode authorization, through the real
  Showdown ending. Story records preserved.
- **Cybertron Arena: 20/20 configurations**: five maps, two factions and
  human/AI opponents. Every configuration ended normally; each retained
  the previous profile **byte-for-byte**.
- **Actual source-asset support presentation** in another Arena match:
  19 combat exchanges, including seven lethal battles; **25,875 checks**
  passed with 574 native state comparisons.
- Independently checked original `iphone.big`: all **559** resources
  decompressed cleanly (140 PNG, 36 M3G, 52 BMP, 24 OGG, 307 other).
- The three most relevant local profile/graphics tests (Scale4x,
  campaign handoff, checkpoint restore) also passed 3/3, in addition
  to the complete CI CTest suites.

All full-game runs used only authorized GameSession commands and actual
native AI, with separate synthetic world/camera/battle/UI acknowledgement.
**They do not use Metal/UIKit or prove a real touch-enabled phone run.**

Earlier QA's Python Showdown/Arena wrapper hardcoded 330-byte native profile
v1; Build007 added the tutorial field and produces 331-byte v2 profiles.
This evidence-only commit updates the reproducibility wrapper to accept
both validated versions. No game code, save format or shipped executable
has been modified by that post-build QA update.

## Install and remaining device-only gates

Use **Sideloadly and the same signing identity** as Build009/Build008
to install over the app and preserve its sandbox data. Keep a saved
copy of any important progress. Never uninstall the installed app as a
first step, because that can erase its private saves.

The remaining uncertainty requires a physical iPhone XR:
- confirm the original icon is displayed after signing/install;
- cold-launch Continue and gameplay save persistence;
- visually inspect the G1 menus, initial mission, later missions,
  support effect, 3D battles, pause, alerts, mission-to-mission handoff,
  campaign ending, Sound/Music controls and background/resume;
- monitor actual delivered 60 Hz frames, memory pressure and audio
  interruptions during sustained play.

No tool in this session can physically drive the user's XR. The green
CI and full headless mode runs must not be called proof of an
issue-free rendered iPhone campaign.

Machine metadata: `validation/NATIVE_FULL_GAME_010.json`.
