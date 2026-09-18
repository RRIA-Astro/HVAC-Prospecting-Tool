HVAC Territory Discovery v0.11.8 — Norfolk + Virginia Beach
=========================================================

Purpose
-------
Commercial HVAC sales-prospecting triage from public aerial imagery. Discover parcels, apply
the GIS prescreen, then analyze the passing sites locally as STRONG, REVIEW, or QUIET.
This is a prospecting filter, not an engineering survey or equipment inventory. QUIET is not
proof that valuable equipment is absent. Ambiguous evidence still requires salesperson review.

What changed
------------
Norfolk is now a selectable territory alongside Virginia Beach. The app starts with Norfolk
selected, centered at 800 E City Hall Ave with a 0.5-mile radius. You can use another Norfolk
street address. Select Virginia Beach to use its existing services and previous defaults.

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

Frozen detector contract
------------------------
Detection, rescue, prescreen rules, scoring, attribution, and triage remain at the v0.11.7 baseline.
Only jurisdiction inputs/normalization, acquisition routing/validation, UI, and audit output change.
The v0.0.12 model files are byte-for-byte unchanged. Primary operating points stay:

  Stage 1 candidate: 0.07
  Tower/chiller verifier: 0.35
  Large packaged verifier: 0.45

Shifted rescue retains 0.015; zoomed perimeter rescue retains 0.008. Rescue routing and REVIEW-only
limits are unchanged. This release does not add fanless-tower recognition or tune any reviewed miss.
FROZEN_DETECTION_CONTRACT.json protects model hashes, baseline code, and detector constants in tests.
Virginia Beach's service URLs and normal discovery/ranking behavior remain available unchanged.

First Norfolk test
------------------
1. Build and extract the Windows artifact as usual, keeping its entire folder together.
2. Leave Norfolk selected. Start with the 0.5-mile radius and 10,000 ft2 size setting.
3. Click Discover + Prescreen. Inspect the city, addresses, footprint source, and warnings.
4. Aim for about 75-100 passing properties. Shrink/expand the radius if needed, then Analyze.
5. Assess all STRONG/REVIEW properties and spot-check QUIET sites as before. This is not a
   statistically complete recall test without checking every target-positive property.

Discovery still displays at most 250 candidates, with prescreen-passing sites sorted first.
The status line and metadata disclose when this cap is reached. Compare displayed passing sites
with passing sites before the cap; if passing sites were truncated, reduce radius or use several
overlapping searches. The cap warning can also mean only filtered/nonpassing rows were omitted.
The scan covers the selected city's parcel inventory only, even when a radius crosses city limits.

Shadows, tall-building roof displacement relative to footprints, imagery age, GIS completeness,
and equipment concealed by screens/penthouses can affect results. Norfolk accuracy is not yet
field-validated. Treat the first run as a new-territory blind test, not a demonstrated accuracy claim.

Output
------
Results remain in Downloads/HVAC_Prospecting_Scan_<timestamp>/ with source/annotated images,
per-property cv_result.json, source/view_manifest.json, and prospecting_results.csv.
New audit output adds:

  SCAN_METADATA.json: release/baseline, actual source URLs, scan state, discovery/cap diagnostics.
  DISCOVERY_AUDIT.json: the displayed candidates and their prescreen/assessment/footprint context.
  CSV: city/territory, GPIN, coordinates, raw use/class, assessment match, footprint/imagery source.

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

For this release the artifact is HVAC_Territory_Discovery_v0118_Windows.zip.
Extract it and run HVAC_Territory_Discovery_v0118.exe. Keep its other bundled files intact.

Source run / offline validation (Python 3.12)
--------------------------------------------
  pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
  pip install -r requirements.txt
  python -m unittest -v test_detection_logic.py test_territories.py test_release_contract.py
  python app.py

The automated suite does not require live GIS requests or load the ML runtime. It covers frozen
detection behavior, model/code hashes, Norfolk classifications/joins/routing, acquisition scale,
error handling, auditing, and release packaging. Windows EXE assembly runs in GitHub Actions.
Keep v0.10.1 as the separate training-safe labeling app.

Official source references (verified 2026-09-18)
-----------------------------------------------
https://www.norfolk.gov/1596/Geographic-Information-Systems
https://gisshare.norfolk.gov/pubserver/rest/services/OpenData/Parcels/FeatureServer
https://gisshare.norfolk.gov/server/rest/services/NORFOLKAIR/AIR_Basemap/MapServer/34
https://gisshare.norfolk.gov/pubserver/rest/services/AerialPhotos/2025/MapServer
https://data.norfolk.gov/Real-Estate/Property-Assessment-and-Sales-FY27/qva7-tzrf
