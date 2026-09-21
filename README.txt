HVAC Territory Discovery v0.11.16 — Williamsburg Expansion
===========================================================

Purpose
-------
Commercial-HVAC prospecting triage from public GIS and aerial imagery. The app discovers parcels,
applies a precision-first GIS prescreen, and analyzes passing sites locally as STRONG, REVIEW, or
QUIET. It is a prospecting filter, not an engineering survey. QUIET does not prove that valuable
equipment is absent, and REVIEW still requires a salesperson to inspect the imagery.

What changed
------------
v0.11.16 adds Williamsburg while preserving the v0.11.7 detector weights and operating thresholds.
Williamsburg uses the city's official address points, assessor-enriched tax parcels, building
footprints, and 2021 municipal orthophoto. Parcel use, tax class, business/parcel name, owner, zoning,
and raw classifications remain in the audit path. The broad Williamsburg "Commercial-Industrial"
tax class is normalized to Commercial for prescreen context so a small office is not falsely treated
as an industrial priority; the exact source class remains in the audit fields.

Production-size orthophoto frames at City Hall and the Williamsburg Lodge retained individual rooftop
units, fan tops, curbs, and equipment clusters. A live 0.5-mile discovery centered at 401 Lafayette St
returned 490 parcels and 1,087 official building footprints, joined 1,036 footprints, and produced 22
prescreen-passing properties with no candidate truncation.

Suffolk is now paused after a blind field test produced three major high-value false negatives among
the first five reviewed sites and only three REVIEW results across 107 candidates. Chesapeake and
Newport News remain paused for the same underlying deployment concern: their available imagery is not
dependable enough for blind HVAC prospecting. All three adapters remain in source for diagnostics and
future imagery replacements, but they are hidden from the city selector.

Williamsburg safeguards
-----------------------
  * Search centers use the normalized official full-address field and prefer nonresidential named points.
  * Parcel assessment context comes from the same official polygon record; no secondary scrape or
    approximate assessment join is required.
  * City building footprints are required; discovery stops before prescreening if neither the
    Williamsburg layer nor the statewide fallback returns usable footprints.
  * Orthophoto exports are checked for JSON errors, exact dimensions, readable image data, and blank frames.
  * The existing context-only manual-review route for medical campuses with a building at least
    100,000 ft2 includes Williamsburg. It does not claim that equipment was detected.
  * A new REVIEW-only safeguard covers the two confirmed Portsmouth public-site misses: one 60–95 ft
    seam-suppressed packaged-mechanical candidate must be centered on a >=50,000-ft2 institutional
    building and meet explicit verifier gates. It cannot produce STRONG and does not loosen detection.

All prior Hampton, Norfolk, and Virginia Beach controls remain unchanged.

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

Recommended Williamsburg blind test
-----------------------------------
1. Build and extract the Windows artifact, keeping the entire folder together.
2. Select Williamsburg. The default center is 401 Lafayette St and the default radius is 0.5 mile.
3. Leave the minimum building size at 10,000 ft2 for the first run.
4. Click Discover + Prescreen. Confirm Williamsburg addresses, WILLIAMSBURG CITY footprints, and
   Williamsburg municipal orthophoto 2021 imagery. Reduce the radius if prescreen-passing rows are omitted.
5. Analyze the passing properties. Review every STRONG and REVIEW result and spot-check QUIET sites.
6. Send prospecting_results.csv first. Send individual property folders only for definite misses,
   confusing false positives, or unusually useful controls; the full scan archive is not required.

Use a genuinely new Williamsburg area rather than the City Hall/Lodge preflight sites for the first blind test.

City behavior
-------------
The app starts with Norfolk selected. Available cities are Hampton, Norfolk, Portsmouth, Virginia Beach,
and Williamsburg.
Changing the city clears discovered rows so data sources cannot be mixed. Each scan covers only the
selected city's parcel inventory, even when its radius crosses a municipal boundary.

Virginia Beach uses its 2025 ImageServer imagery and existing parcel/building services. Norfolk
uses its 2025 MapServer imagery, city parcel/building services, and FY27 assessment join. Hampton
uses official address/parcel/building/assessment layers and 2026 municipal aerial imagery. Portsmouth
uses official city address/parcel/building layers and 2022 municipal aerial tiles. Williamsburg uses
official city address/parcel/building layers and 2021 municipal orthophoto exports.

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

  HVAC_Territory_Discovery_v01116_Windows.zip

Extract it and run HVAC_Territory_Discovery_v01116.exe. Keep the bundled files together.

Source validation (Python 3.12)
-------------------------------
  pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
  pip install -r requirements.txt
  python -m unittest -v test_detection_logic.py test_territories.py test_release_contract.py
  python app.py

The offline tests mock GIS requests and do not perform a full detector scan. GitHub Actions performs
the source/bundled model loading and Windows packaging checks.

Official source references (verified 2026-09-21)
------------------------------------------------
https://gis.williamsburgva.gov/server/rest/services/Property_Addressing_Service/FeatureServer/1
https://gis.williamsburgva.gov/server/rest/services/Tax_Parcels/MapServer/0
https://gis.williamsburgva.gov/server/rest/services/Property_Information_Lookup/FeatureServer/1
https://gis.williamsburgva.gov/server/rest/services/DBO_wburg_orthoimagery_2021/MapServer
https://portsmouthgis.maps.arcgis.com/apps/webappviewer/index.html?id=2e16d709ed954e76b5b9828d79110bd4
https://services1.arcgis.com/nGsguNiHLn7MU4R4/arcgis/rest/services/Portsmouth_Addresses/FeatureServer/0
https://services1.arcgis.com/nGsguNiHLn7MU4R4/arcgis/rest/services/Parcels_new/FeatureServer/0
https://services1.arcgis.com/nGsguNiHLn7MU4R4/arcgis/rest/services/StandardLayers/FeatureServer/3
https://tiles.arcgis.com/tiles/nGsguNiHLn7MU4R4/arcgis/rest/services/Aerials_2022/MapServer
https://suffolkgis.suffolk-va.net/hosting/rest/services/Parcel_Viewer/Parcels_and_Zoning/FeatureServer/0
https://suffolkgis.suffolk-va.net/hosting/rest/services/Parcel_Viewer/Parcels_and_Zoning/FeatureServer/2
https://suffolkgis.suffolk-va.net/hosting/rest/services/Parcel_Viewer/Parcels_and_Zoning/FeatureServer/4
https://suffolkgis.suffolk-va.net/hosting/rest/services/Parcel_Viewer/Parcels_and_Zoning/FeatureServer/10
https://www.suffolkva.us/369/Mapping-Resources
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
