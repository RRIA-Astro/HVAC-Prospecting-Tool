HVAC Territory Discovery v0.11.13 — Hampton Expansion
======================================================

Purpose
-------
Commercial-HVAC prospecting triage from public GIS and aerial imagery. The app discovers parcels,
applies a precision-first GIS prescreen, and analyzes passing sites locally as STRONG, REVIEW, or
QUIET. It is a prospecting filter, not an engineering survey. QUIET does not prove that valuable
equipment is absent, and REVIEW still requires a salesperson to inspect the imagery.

What changed
------------
v0.11.13 adds Hampton while preserving the v0.11.7 detector weights and primary thresholds.
Hampton uses the city's official address/place-name, parcel, Real Estate improvement, and building-
outline layers. It retains LRSN joins, facility names, use descriptions/codes, improvement types,
and raw classifications in the discovery/audit path. Imagery comes from Hampton's 2026 municipal
aerial service rather than statewide VGIN imagery.

The 2026 source was checked at the production 1800 x 1800 frame before implementation at Sentara
CarePlex, Hampton Roads Convention Center, Hampton Coliseum, and Hampton University. Fan banks,
piping, rooftop equipment, cars, and building edges remained sharply resolved. A live 0.5-mile
discovery at 3000 Coliseum Dr returned 506 parcels, 584 Hampton building footprints, 556 footprint
joins, and 18 prescreen-passing properties without truncation.

Chesapeake and Newport News are paused because field scans showed their available orthophotos were
not reliable enough for blind deployment. Both are hidden from the city selector, but their adapters
and regression coverage remain in source for a later imagery solution. Neither city is silently
rerouted to another jurisdiction's data.

Hampton safeguards
------------------
  * Search centers use normalized exact-address matching against official FullAdd records.
  * Main, non-leasehold address points are preferred when a campus has duplicate address records.
  * Parcels join to official address/place-name and assessment improvements by exact LRSN.
  * Assessment requests are batched, not scraped property by property.
  * Active nonresidential improvements control campus context when the same parcel also contains
    dormitories or residences, preserving the one-good-building campus rule.
  * Pools, tanks, towers, and sheds are excluded from the building-footprint query so they cannot
    inflate building size or become false building centers.
  * Discovery stops before prescreening if neither Hampton nor statewide fallback footprints return.
  * The existing context-only manual-review route for medical campuses with a building at least
    100,000 ft2 now includes Hampton. It does not claim that equipment was detected.

All prior Norfolk and Virginia Beach controls remain. Chesapeake and Newport News remain callable
in source for diagnostic/regression purposes but are not selectable deployment cities.

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

Recommended Hampton blind test
------------------------------
1. Build and extract the Windows artifact, keeping the entire folder together.
2. Select Hampton. The default center is 3000 Coliseum Dr and the default radius is
   0.5 mile.
3. Leave the minimum building size at 10,000 ft2 for the first run.
4. Click Discover + Prescreen. Confirm Hampton addresses, HAMPTON CITY footprints, and Hampton
   municipal aerial 2026 imagery. If more than 250 candidates are reported, reduce the radius.
5. Analyze the passing properties. Review every STRONG and REVIEW result and spot-check QUIET sites.
6. Send prospecting_results.csv first. Send individual property folders only for definite misses,
   confusing false positives, or unusually useful controls; the full scan archive is not required.

Use a genuinely new Hampton area for the first blind test. This establishes how well the existing
frozen detector generalizes to the city's imagery before any detector tuning.

City behavior
-------------
The app starts with Norfolk selected. Available cities are Hampton, Norfolk, and Virginia Beach.
Changing the city clears discovered rows so data sources cannot be mixed. Each scan covers only the
selected city's parcel inventory, even when its radius crosses a municipal boundary.

Virginia Beach uses its 2025 ImageServer imagery and existing parcel/building services. Norfolk
uses its 2025 MapServer imagery, city parcel/building services, and FY27 assessment join. Hampton
uses official address/parcel/building/assessment layers and 2026 municipal aerial imagery.

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

  HVAC_Territory_Discovery_v01113_Windows.zip

Extract it and run HVAC_Territory_Discovery_v01113.exe. Keep the bundled files together.

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
https://webgis3.hampton.gov/server/rest/services/Layers/MapServer/1
https://webgis3.hampton.gov/server/rest/services/Layers/MapServer/0
https://webgis3.hampton.gov/server/rest/services/Web/CQ_Int1/MapServer/0
https://webgis3.hampton.gov/server/rest/services/Web/CQ_RealEstate_Tables/MapServer/3
https://webgis3.hampton.gov/server/rest/services/Aerials_2026/MapServer
https://maps.nnva.gov/arcgis/rest/services/Operational/EnerGov/MapServer/0
https://maps.nnva.gov/arcgis/rest/services/Operational/EnerGov/MapServer/6
https://maps.nnva.gov/arcgis/rest/services/Operational/EnerGov/MapServer/11
https://geohub.nnva.gov/pages/open-data
https://vginmaps.vdem.virginia.gov/arcgis/rest/services/VBMP_Imagery/MostRecentImagery_WGS/MapServer
https://www.norfolk.gov/1596/Geographic-Information-Systems
https://data.norfolk.gov/Real-Estate/Property-Assessment-and-Sales-FY27/qva7-tzrf
