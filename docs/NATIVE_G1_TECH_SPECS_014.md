# Build 014: Original faction Tech Specs UI, native ARM64 reconstruction

Source: owner's `G1awakening_v1.1.3_os30.ipa` (exact `iphone.big` SHA-256 `663d2888982093ce66b7811ccb7a6ad3acd37fc02ffa85144775b88c39e83cb4`) and original PC playback/stats screenshots supplied 2026-10-27. This feature builds *on top of* the separate Build 013 original tactical/dialogue/combat UI branch. The PC Glu intro is not part of this change.

## Implemented and verifiable from source

- Full original 480×320 **Autobot red** frame (PNG resource **1224**) and **Decepticon purple** frame (PNG **417**). Draw unchanged at the original aspect ratio, not AI-generated imitations.
- Original **Energon icon 709**, original robot/vehicle icons 442/904/657, original bitmap font when glyphs are supported, and source indexed BMP miniatures for known characters (Bumblebee 731, Frenzy 646, Optimus 878, Megatron 670). No modified or redistributed source assets.
- Robot and alternate-mode **ATK/DEF/SPD** and price are read from the original `UnitDefinition` and `combat_stats` function (real level scaling), with original source text and owner-confirmed attributes. Bumblebee base robot 65–75 / 55 / 2, alternate N/A / 65 / 5, price 17; Frenzy base 45–55 / 30 / 3, price 8.
- Native read-only M3G 3D viewer (`TechSpecsModel`) maps actual 23-unit type table to original M3G container, authored robot/car/tape form visibility, M3G original materials, and platform-native Metal upload. Local portable probe verified **renderable geometry** (not on-device pixels) for multiple forms of Bumblebee, Frenzy, Optimus and Megatron. The native orbit camera is new; the exact recovered original ARM32 viewer camera/animation sequence remains unknown. A swipe rotates the actual mesh.
- Transparent touch regions coincide with original back/previous/next and robot/alternate icons, visible in original 480×320 artwork. The carousel advances across **active** mission unit types; opening from selected unit focuses that character. The selection screen is read-only and does not submit `GameSession` commands or write saves.
- Open from the source tactical portrait hit region or from Pause Menu -> TECH SPECS. No menu hierarchy changes beyond this additive entry. Closing restores tactical HUD/menu buttons or original pause menu correctly and unpauses the game only in the gameplay path.
- Character localizations/ability lines use source text and source live-combat data; no fabricated character stats. Missing model fails visibly through an accessibility hint instead of substituting a wrong 3D asset.

## Verification contract

- `ctest` includes `tech_specs_source_data_contract` in addition to existing native tests.
- `scripts/verify-original-presentation-assets.py` validates 28 original PNG and 7 original BMP identities by dimensions and SHA-256 directly from the frozen original IPA, including full sheets 1224/417 and portrait 646; also checks runtime source references.
- Metal compiler+native iPhoneOS ARM64, Linux/Apple CTest, signing, full IPA assembly, and physical iPhone XR QA are separate gates. Do not claim any succeeded without the exact run artifact and hash evidence.

## Known gaps / no false parity claims

- Original ARM32 Tech Specs dispatchers, exact 3D orbit/camera/light/idle animations and some character-specific descriptive text may differ. 3D model pixels and transparent layered composition require the physical iPhone XR.
- The current original unit definitions have no universal miniature portrait mapping for every roster entry; unknown characters intentionally omit the miniature image.
- This task neither changes terrain/energy towers nor the PC Glu cinematic. It does not rebuild every other source UI screen or warrant claiming an entire game finished.
- App installation, no-crash, 60 FPS performance, device audio and mission completion must be established from physical XR evidence, not CTest or synthetic GPU probes.

## Regression checklist on XR

1. Enter first mission, select Bumblebee, tap bottom-left portrait: original red Tech Specs appears; robot model, ATK 65–75, DEF 55, SPD 2, alternate DEF 65, SPD 5, price 17 and quote readable.
2. Swipe the original 3D Bumblebee mesh and tap robot/alternate form; original geometry changes without consuming a tactical action.
3. Next/previous arrows navigate active units; choose Frenzy: purple original source frame, ATK45–55 DEF30 SPD3, price8 and original quote; no duplicated overlays.
4. Back returns to the exact previous tactical state and restores the gameplay HUD/menu without changing selected unit/health/turn/funds/save.
5. Open Pause -> Tech Specs -> Back -> Pause -> Resume; should restore controls and resume same mission, no black scene or second menu.
6. Confirm video intro, source dialogue panels, M3G battle visuals, save/resume, other modes still work as in Build 013.
