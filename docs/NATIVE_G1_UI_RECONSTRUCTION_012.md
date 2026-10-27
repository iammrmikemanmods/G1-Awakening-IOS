# G1 Awakening — Build012 native original UI recovery checkpoint

Source of truth: unmodified G1 Awakening iOS v1.1.3 resource data (`iphone.big` SHA-256 `663d2888982093ce66b7811ccb7a6ad3acd37fc02ffa85144775b88c39e83cb4`); last recorded native Build011 branch `feature/native-g1-ui-hud-011`. Do not confuse native iOS ARM64 port with PC touchHLE execution. Never commit proprietary source IPA, resource payloads, new user cinematic, compiled Mach-O or signed IPA to this source branch.

## Recovered original artwork and layout

- Source menu PNG 1002: exact 480×320 background, preserved aspect on wide iPhone screens. Heading, the central red panel, menu button grid and scrollable Help/Credits text use explicit source-space geometry from `g1/OriginalUI.hpp`.
- Gameplay original icons 721,639,793,660,726,1118,719,454,919,1076 and menu icon 905: verified original PNG bytes and dimensions, rendered without a redundant system title/background, with VoiceOver names and a visible selected/disabled affordance. Icon image scale is explicitly 1.0 where UIKit button points match source-pixel dimensions, avoiding half-size source art.
- Existing original HUD (1004) and dialogue frame (1034) are retained unchanged; no fabricated imagery replaces them.
- Menu choices fit the recovered source red panel (three columns / maximum three rows). Mission pages have six choices plus Previous, Next and Back within nine slots, preventing overlay onto original heading. Information pages scroll within the source panel; Back remains independent of scrolling content.

## Functional native routes restored in this checkpoint

- Main Menu → Play Game → Game Modes → Story/Showdown/Arena → mission pages → game; Return paths correct the prior picker and arena navigation.
- Original Help hierarchy now uses the four *actual original game* headings and contents from the untouched text bank: OVERVIEW (630/861), CONTROLS (1181/458), GAME MODES (983/788), TIPS (1200/393). Topic Back returns to Help; Help Back returns to its caller (pause, settings or main menu). This replaces the fabricated single-paragraph Help screen.
- Original game strings SELECT FACTION (1022), SELECT OPPONENT (1313) and AI (580) are used on Arena configuration screens; correct Back propagation preserves the pending selected mission.
- Music/sound toggle titles come from original game text IDs (495/1222, 855/923); touch camera-speed, diagnostics and graphics options remain native-port enhancements. Diagnostic report control is hidden in default settings until diagnostics is enabled. No Glu link, feedback or blog is reinstated.
- While any menu/overlay is open, the source pause icon and gameplay HUD frame behind it are hidden, preventing duplicate controls outside the artwork.
- Buttons dispatch to existing engine actions; no gameplay rules, campaign state encoding, checkpoint format, intro video bytes, PNGs or original binary are changed.

## Tested guarantees and limits

- 64/64 Linux portable CTest tests passed including new `original_ui_source_geometry`. This verifies 480×320/XR/other aspect geometry, row budget and information Back placement, **not** UIKit drawing or physical touch accuracy.
- User original IPA: 14 important source UI PNGs passed dimensions/SHA-256 checks using `scripts/verify-original-ui-assets.py`, including exact original archive identity.
- Apple iPhoneOS ARM64/Objective-C++ compilation must still run in GitHub CI for this branch. Physical iPhone XR installation, rendered screenshot equivalence, original ARM32 touch-dispatcher/hit-box parity, complete in-game modal transition parity and every game mode are **not yet verified**.
- The native reconstruction does not contain the original 32-bit UI callback dispatcher. These native routes are evidence-backed equivalents, not a claim of byte-identical ARM32 behaviour. Remaining parity work includes the original tactical camera and source scene geometry (energy pylons), original gameplay interaction overlays, result-dialogue presentation accuracy and full physical device verification. Black outside terrain is a separate world extension, not UI art.

## QA procedure after Apple code build

1. Build iPhoneOS ARM64 code on Apple runner, preserve `G1-native-game-unsigned-code` artifact. Independently verify the SHA of source archive before rebuilding the Filza/AppSync IPA with the original resources and iOS XR opening cinematic. Keep Build011 backup.
2. Install on jailbroken iPhone XR iOS 17.5.1, capture an original-art screen and compare heading, three-column menus, icon sizing and touch bounds against original 480×320 source artwork. Verify that Back never jumps to Main Menu unexpectedly.
3. Navigate Main Menu → Help → each of four source topics → Help → Main, and Pause → Help → topic → Pause. Use VoiceOver to inspect source icon accessibility. Check long original text scroll and labels.
4. Navigate Story mission paging, unlock-gated Showdown, Arena map → faction → opponent (AI/Human), Back at each level. Confirm Start and Continue perform their original data-preserving paths.
5. During real missions exercise every source icon, confirm disabled/active indicators, HUD frame, dialogue, pause and resume (including app background and relaunch); verify music/sound toggles and both graphics modes.
6. Retest campaign playthrough on hardware. Only then publish any statement claiming UI completion, fidelity, performance or gameplay compatibility.
