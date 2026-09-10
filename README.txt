HVAC Territory Discovery v0.11.1 — Local CV Prospecting
===========================================================

This is the first prospecting build with the custom detector integrated into the territory-discovery app.
It uses the GIS/property/campus logic from the previous app and replaces GPT vision as the primary equipment recognizer with the frozen v0.0.12 local CV pipeline. No OpenAI API key is required.

FROZEN OPERATING POINT
- Stage 1 candidate: 0.07
- Tower/chiller verifier: 0.35
- Large packaged HVAC verifier: 0.45

ROUND-4 BLIND FIELD RESULT
- Strict true-localized property recall: 16/18 = 88.9%
- Business/property surface recall: 17/18 = 94.4%
- Clean-negative property FPR: 5/22 = 22.7%
- Cooling-tower localized site recall: 6/9 = 66.7%
- Chiller localized site recall: 6/6 = 100%
- Large-packaged localized site recall: 11/12 = 91.7%

HOW TO USE
1. Enter a Virginia Beach center address, radius, and size threshold.
2. Click 1. Discover + Prescreen.
3. Click 2. Analyze Prescreened.
4. SURFACE properties rise to the top and receive an OPP score.
5. Double-click a row for prospect details.
6. Open Scan Folder to inspect prospecting_results.csv and annotated aerials.
7. Analyze Selected can scan any individual property, even if it failed the GIS prescreen.

IMPORTANT
MODEL EVIDENCE HITS are evidence hits across campus/building views, not guaranteed physical equipment-unit counts. Mechanical evidence dominates the OPP score; GIS can only add a small bonus. A QUIET result is not proof that no valuable mechanical opportunity exists.

OUTPUT
Downloads\HVAC_Prospecting_Scan_YYYYMMDD_HHMMSS\
- prospecting_results.csv
- SCAN_SUMMARY.txt
- source aerials by property
- annotated views with retained detections
- cv_result.json per property

WINDOWS BUILD
Upload this source tree to GitHub, preserving .github/workflows/build-windows.yml and models/. Run the Build Windows EXE action. The artifact contains a portable folder zipped as HVAC_Territory_Discovery_v0111_Windows.zip.

This build intentionally uses PyInstaller --onedir. Bundling PyTorch/Ultralytics into one giant self-extracting EXE would make startup much slower and is less reliable for this first integrated ML build.

Keep v0.10.1 as the dedicated Training-Safe labeling app for now. v0.11.1 is focused on prospecting and model integration.


v0.11.1 PACKAGING FIX
---------------------
The Stage-2 ResNet18 state is now stored as:
  models\resnet18_embedder_state_fp16.pt

Prior FP32 file: 42.7 MiB
New FP16 file:   21.4 MiB

The FP16 file is below GitHub's browser per-file upload limit.

The GitHub Action now fails before building if a model file is missing, and fails
after building if PyInstaller did not actually include all model assets.

If CV startup still fails, the app writes:
  Downloads\HVAC_CV_ERROR.txt
with the full traceback and model paths.

CV thresholds are unchanged:
  candidate 0.07 / tower-chiller 0.35 / large packaged 0.45
