HVAC Territory Discovery v0.11.12 — Newport News Expansion
===========================================================

Purpose
-------
Commercial-HVAC prospecting triage from public GIS and aerial imagery. The app discovers parcels,
applies a precision-first GIS prescreen, and analyzes passing sites locally as STRONG, REVIEW, or
QUIET. It is a prospecting filter, not an engineering survey. QUIET does not prove that valuable
equipment is absent, and REVIEW still requires a salesperson to inspect the imagery.

What changed
------------
v0.11.12 adds Newport News while preserving the v0.11.7 detector weights and primary thresholds.
Newport News uses the city's official EnerGov address, parcel-assessment, and Building Detail
layers. It retains official place names, use descriptions, classifications, zoning, ownership,
building type, and building height in the discovery/audit path. Imagery comes from VGIN's VBMP
most-recent orthophoto service. A live check at Riverside Regional Medical Center returned a clear
1800 x 1800 export at the pipeline's established physical scale.

Chesapeake is paused because its available orthophotos were not reliable enough for deployment:
known high-value targets were visibly clearer in Google Maps and were missed in the scan imagery.
Chesapeake is hidden from the city selector, but its adapter and regression coverage remain in the
source for a later imagery solution. It has not been silently rerouted to another city's data.

Newport News safeguards
-----------------------
  * Search centers use normalized exact-address matching against official FULLADDR records.
  * Parcels use official SITEADDRESS, assessment land use/use/class fields, zoning, and parcel IDs.
  * Official PLACENAME address records are joined to parcels as facility hints.
  * Building FEATURECODE values are retained as residential, commercial, public, or miscellaneous
    context; BLDGHEIGHT is preserved when present.
  * Discovery stops before prescreening if neither the Newport News nor statewide fallback building
    source returns usable footprints, preventing a service outage from producing false QUIET rows.
  * The existing context-only manual-review route for medical campuses with a building at least
    100,000 ft2 now includes Newport News. It does not claim that equipment was detected.

All prior Norfolk and Virginia Beach controls remain. Chesapeake remains callable in source for
diagnostic/regression purposes but is not a selectable deployment city.

Detector contract
-----------------
No model was retrained. The v0.0.12 model assets and primary operating points remain:

  Stage 1 candidate:             0.07
  Tower/chiller verifier:       0.35
  Large packaged verifier:      0.45
  Shifted rescue candidate:     0.015
  Zoomed perimeter candidate:   0.008

FROZEN_DETECTION_CONTRACT.json protects model hashes, operating points, preserved detector logic,
and bounded territory rules. The complete ResNet18 checkpoint is 22,410,981 bytes with SHA256
7dbdd679df66598a8d9e63f983507eb7900af9553595a3bb250ee6e4795e6ffd.

Recommended Newport News blind test
-----------------------------------
1. Build and extract the Windows artifact, keeping the entire folder together.
2. Select Newport News. The default center is 500 J Clyde Morris Blvd and the default radius is
   0.5 mile.
3. Leave the minimum building size at 10,000 ft2 for the first run.
4. Click Discover + Prescreen. Confirm Newport News addresses, NEWPORT NEWS CITY footprints, and
   the VGIN imagery label. If more than 250 candidates are reported, reduce the radius.
5. Analyze the passing properties. Review every STRONG and REVIEW result and spot-check QUIET sites.
6. Send prospecting_results.csv first. Send individual property folders only for definite misses,
   confusing false positives, or unusually useful controls; the full scan archive is not required.

Use a genuinely new Newport News area for the first blind test. This establishes how well the
existing frozen detector generalizes to the city's imagery before any detector tuning.

City behavior
-------------
The app starts with Norfolk selected. Available cities are Newport News, Norfolk, and Virginia
Beach. Changing the city clears discovered rows so data sources cannot be mixed. Each scan covers
only the selected city's parcel inventory, even when its radius crosses a municipal boundary.

Virginia Beach uses its 2025 ImageServer imagery and existing parcel/building services. Norfolk
uses its 2025 MapServer imagery, city parcel/building services, and FY27 assessment join. Newport
News uses official EnerGov address/parcel/building layers and VGIN VBMP imagery.

All active cities retain the Virginia Civil Reference building-footprint fallback. The actual
footprint source is recorded. Shadows, roof displacement, imagery age, tree cover, screened
equipment, fanless towers, and incomplete GIS geometry can affect results.

Output
------
Results are written to Downloads/HVAC_Prospecting_Scan_<timestamp>/:

  prospecting_results.csv   ranked results plus user review and source fields
  SCAN_METADATA.json        version, data sources, completion state, and discovery counts
  DISCOVERY_AUDIT.json      displayed candidate and prescreen context
  SCAN_SUMMARY.txt          concise run summary and limitations
  <property>/source/        source aerial views and view_manifest.json
  <property>/annotated/     annotated detector evidence
  <property>/cv_result.json detector, attribution, rescue, and audit details

Discovery displays at most 250 candidates with prescreen-passing rows first. Metadata records the
pre-limit counts and whether passing sites were omitted. Reduce the radius when passing properties
were truncated.

Build Windows EXE
-----------------
Upload the CONTENTS of this source folder to the GitHub repository root. Include app.py,
territories.py, release_identity.py, all three test files, FROZEN_DETECTION_CONTRACT.json, models/,
and .github/workflows/build-windows.yml. Do not upload the enclosing folder as an extra directory.

The workflow derives the executable name from APP_VERSION, runs the full offline suite, validates
checkpoint archives and hashes, loads the source models, builds the portable app, compares bundled
model hashes to source, loads the bundled models, and publishes:

  HVAC_Territory_Discovery_v01112_Windows.zip

Extract it and run HVAC_Territory_Discovery_v01112.exe. Keep the bundled files together.

Source validation (Python 3.12)
-------------------------------
  pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
  pip install -r requirements.txt
  python -m unittest -v test_detection_logic.py test_territories.py test_release_contract.py
  python app.py

The offline tests mock GIS requests and do not perform a full detector scan. GitHub Actions performs
the source/bundled model loading and Windows packaging checks.

Official source references (verified 2026-09-20)
------------------------------------------------
https://maps.nnva.gov/arcgis/rest/services/Operational/EnerGov/MapServer/0
https://maps.nnva.gov/arcgis/rest/services/Operational/EnerGov/MapServer/6
https://maps.nnva.gov/arcgis/rest/services/Operational/EnerGov/MapServer/11
https://geohub.nnva.gov/pages/open-data
https://vginmaps.vdem.virginia.gov/arcgis/rest/services/VBMP_Imagery/MostRecentImagery_WGS/MapServer
https://www.norfolk.gov/1596/Geographic-Information-Systems
https://data.norfolk.gov/Real-Estate/Property-Assessment-and-Sales-FY27/qva7-tzrf
