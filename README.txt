HVAC Territory Discovery v0.11.10 — Norfolk Rescue-Coverage Patch
==================================================================

Purpose
-------
Commercial HVAC sales-prospecting triage from public aerial imagery. Discover parcels, apply
the GIS prescreen, then analyze the passing sites locally as STRONG, REVIEW, or QUIET.
This is a prospecting filter, not an engineering survey or equipment inventory. QUIET is not
proof that valuable equipment is absent. Ambiguous evidence still requires salesperson review.

What changed
------------
v0.11.10 applies the latest Norfolk blind-scan findings without globally lowering a model threshold.
It preserves the established Virginia Beach branch and adds four bounded Norfolk-only safeguards:

  * Zoomed perimeter rescue now uses a fully overlapping 4 x 4 grid instead of a gapped 3 x 3 grid.
    On an 1800-pixel source image this removes two 132-pixel blind bands on each axis.
  * Norfolk priority sites use a 50,000-ft2 mechanical-focus floor. This gives 610 May Ave's
    72,444-ft2 school building a higher-resolution view; the general 75,000-ft2 floor is unchanged.
  * Hotels qualify for added focus/rescue only when they look substantial and urban/dense in GIS:
    >=30,000-ft2 building footprint and >=30% parcel coverage. With missing parcel area, the floor
    is >=60,000 ft2. Explicit convention identity qualifies at >=30,000 ft2. Low-rise suburban
    hotels are deliberately not promoted. This targets 777 Waterside without making HOTEL a blanket
    priority class.
  * Rescue evidence on a <=100,000-ft2 single-building Norfolk site must be within 10 ft of the
    parcel or within 5 ft of its joined building. This rejects the neighboring equipment at
    601 E Brambleton while retaining genuine in-parcel and split-building evidence.

The 124 W Freemason grouped-equipment false positive may remain REVIEW by design. That ambiguity is
preferable to a global restriction that could hide real prospects. Model weights and every primary,
shifted-rescue, zoomed-rescue, ranking, and triage threshold are unchanged.

All v0.11.9 safeguards remain: split-parcel joined-building REVIEW attribution, distinct-building
rescue selection, bounded public/institutional near-miss REVIEW, and rejected-rescue audit records.

Norfolk remains selectable alongside Virginia Beach. The app starts with Norfolk selected,
centered at 800 E City Hall Ave with a 0.5-mile radius. Select Virginia Beach to use its existing
services, defaults, and v0.11.7 ranking behavior.

Norfolk uses city address points, parcel boundaries, building polygons, and public 2025 aerial
imagery. Parcel GPINs join to the city's daily-updated Property Assessment and Sales FY27 data.
The adapter translates assessment classes into the descriptive context expected by the existing
prescreen. Building-improvement classes take precedence over land-ownership classifications;
a public owner is not proof of public building use. Commercial condos are not treated as homes.
Self-storage, residential types, universities, hospitals, schools, and utilities are mapped
explicitly. Raw classifications are retained for audit. Unmatched GPINs stay UNKNOWN and produce
a warning; they are not assumed residential, public, or military. Assessment-service failures
stop discovery instead of silently running an unvalidated prescreen.

Norfolk's building service filters demolished structures and known non-building feature codes
(water towers/storage tanks). Its public feature-code descriptions supplement institutional
context. Both cities retain the existing Virginia Civil Reference footprint fallback, with the
actual source recorded. Norfolk discovery stops if neither source returns usable footprints.

Imagery is requested using the same projected frame, pixel count, and view scales as v0.11.7.
Norfolk uses MapServer/export; Virginia Beach retains ImageServer/exportImage. The downloader
rejects service error pages, wrong-sized exports, and completely blank images before inference.
It never substitutes another city's imagery, an older year, or a lower-resolution basemap.

Core detector and territory contract
------------------------------------
The v0.0.12 model files and primary operating points remain byte-for-byte unchanged from the
v0.11.7 detector baseline. Virginia Beach rescue selection, attribution, and triage remain on that
branch. v0.11.10 adds only the bounded Norfolk territory logic described above. Operating points stay:

  Stage 1 candidate: 0.07
  Tower/chiller verifier: 0.35
  Large packaged verifier: 0.45

Shifted rescue retains 0.015; zoomed perimeter rescue retains 0.008. This release does not retrain
fanless-tower recognition. FROZEN_DETECTION_CONTRACT.json protects model hashes, core constants,
the preserved baseline branch, and the explicit Norfolk logic in tests.
JSON asset hashes normalize CRLF to LF to tolerate Windows Git checkout line endings. All other
JSON bytes remain protected, and binary .pt model assets retain strict byte-for-byte hash checks.
Virginia Beach's service URLs and normal discovery/ranking behavior remain available unchanged.

Norfolk validation rerun
------------------------
1. Build and extract the Windows artifact as usual, keeping its entire folder together.
2. Leave Norfolk selected. Start with the 0.5-mile radius and 10,000 ft2 size setting.
3. Click Discover + Prescreen. Inspect the city, addresses, footprint source, and warnings.
4. Aim for about 75-100 passing properties. Shrink/expand the radius if needed, then Analyze.
5. Re-run the same 0.5-mile control area first. Confirm that Scope Arena, 610 May, and 777 Waterside
   surface at least REVIEW; 601 E Brambleton becomes QUIET; and 124 W Freemason may remain REVIEW.
6. Reconfirm the prior controls: 600 Church, 441 Bank, Scope Arena, and 333 Waterside surface while
   110 W Main stays QUIET. Then move to a fresh Norfolk area.

Discovery still displays at most 250 candidates, with prescreen-passing sites sorted first.
The status line and metadata disclose when this cap is reached. Compare displayed passing sites
with passing sites before the cap; if passing sites were truncated, reduce radius or use several
overlapping searches. The cap warning can also mean only filtered/nonpassing rows were omitted.
The scan covers the selected city's parcel inventory only, even when a radius crosses city limits.

Shadows, tall-building roof displacement relative to footprints, imagery age, GIS completeness,
and equipment concealed by screens/penthouses can affect results. The named controls validate
the repair targets, not citywide accuracy; the next fresh-area run remains a blind generalization test.

Output
------
Results remain in Downloads/HVAC_Prospecting_Scan_<timestamp>/ with source/annotated images,
per-property cv_result.json, source/view_manifest.json, and prospecting_results.csv.
New audit output adds:

  SCAN_METADATA.json: release/baseline, actual source URLs, scan state, discovery/cap diagnostics.
  DISCOVERY_AUDIT.json: the displayed candidates and their prescreen/assessment/footprint context.
  CSV: city/territory, GPIN, coordinates, raw use/class, assessment match, footprint/imagery source.
  cv_result.json: rescue_candidate_audit and rescue_candidate_decisions for verified rescue proposals.

Old Virginia Beach scan CSVs remain readable for review. New scan CSVs retain coordinates for
Download Aerial. CSVs do not contain full parcel/building geometry; rediscover before reanalyzing.
Review marks and notes continue to write to the existing results CSV.

Build Windows EXE
-----------------
Upload the CONTENTS of this source folder to the GitHub repository root, including app.py,
territories.py, release_identity.py, all three test files, FROZEN_DETECTION_CONTRACT.json,
models/, and the included .github/workflows/build-windows.yml. Do not nest the project one
folder deeper. Replace the workflow too; uploading app.py alone leaves the old build configuration.

The workflow reads APP_VERSION from app.py to derive the EXE/artifact names. Regression tests use
stable filenames and check the detector baseline separately from the app release number, avoiding
the stale v0.11.5/v0.11.6 version assertion failures encountered previously. Node-24 actions are used.

Historical v0.11.8 build-check repair: if the original build failed only on the
pipeline_config.json and verifier_runtime.json hashes, replace test_release_contract.py at the
repository root with this corrected copy and commit. No model, configuration, app.py, or workflow
replacement is required for this repair. Re-running the old failed commit will use the old test.

Historical v0.11.8 Stage-2 checkpoint repair: the initial Norfolk source package included a
truncated resnet18_embedder_state_fp16.pt. This corrected package restores the complete original
v0.11.7 checkpoint: 22,410,981 bytes; SHA256
7dbdd679df66598a8d9e63f983507eb7900af9553595a3bb250ee6e4795e6ffd.
The damaged copy was the exact first 22,071,296 bytes of that file, missing 339,685 trailing bytes.
No training, weights, thresholds, or runtime detection logic were changed. The frozen contract's
embedder hash now refers to the intact original instead of the damaged cached copy.

For this repair replace FOUR files in GitHub (paths are relative to the repository root):
  models/resnet18_embedder_state_fp16.pt
  FROZEN_DETECTION_CONTRACT.json
  test_release_contract.py
  .github/workflows/build-windows.yml
Commit the replacements and use the new build run. Uploading the model alone leaves the old hash
check; re-running an old commit still uses its old files. The binary is below GitHub's 25 MiB web
upload limit. Updated README, changelog, regression notes, and model card are optional documentation.

The 78-test suite opens each checkpoint and verifies all archive CRCs, with regressions for
missing central directories, corrupted tensor bytes, and generic ZIPs that are not checkpoints.
The workflow additionally loads the actual source models before PyInstaller, compares every
bundled asset byte-for-byte with its source, and loads the bundled assets using the same LocalCV
initializer. These checks do not run a full detector scan or launch the packaged Windows GUI.

For this release the artifact is HVAC_Territory_Discovery_v01110_Windows.zip.
Extract it and run HVAC_Territory_Discovery_v01110.exe. Keep its other bundled files intact.

Source run / offline validation (Python 3.12)
--------------------------------------------
  pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
  pip install -r requirements.txt
  python -m unittest -v test_detection_logic.py test_territories.py test_release_contract.py
  python app.py

The automated suite does not require live GIS requests or load the ML runtime. It covers preserved
Virginia Beach behavior, model/code hashes, the Norfolk field controls, classifications/joins,
acquisition scale, error handling, auditing, and release packaging. Windows EXE assembly runs in GitHub Actions.
Keep v0.10.1 as the separate training-safe labeling app.

Official source references (verified 2026-09-18)
-----------------------------------------------
https://www.norfolk.gov/1596/Geographic-Information-Systems
https://gisshare.norfolk.gov/pubserver/rest/services/OpenData/Parcels/FeatureServer
https://gisshare.norfolk.gov/server/rest/services/NORFOLKAIR/AIR_Basemap/MapServer/34
https://gisshare.norfolk.gov/pubserver/rest/services/AerialPhotos/2025/MapServer
https://data.norfolk.gov/Real-Estate/Property-Assessment-and-Sales-FY27/qva7-tzrf
