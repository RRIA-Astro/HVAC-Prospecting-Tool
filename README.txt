HVAC Territory Discovery v0.11.11 — Chesapeake Expansion
========================================================

Purpose
-------
Commercial-HVAC prospecting triage from public GIS and aerial imagery. The app discovers parcels,
applies a precision-first GIS prescreen, and analyzes passing sites locally as STRONG, REVIEW, or
QUIET. It is a prospecting filter, not an engineering survey. QUIET does not prove that valuable
equipment is absent, and REVIEW still requires a salesperson to inspect the imagery.

What changed
------------
v0.11.11 adds Chesapeake as the third selectable city while preserving the v0.11.7 detector
weights and primary thresholds. Chesapeake uses:

  * City address points for exact search-center matching.
  * City parcel polygons plus the official Real Estate Parcel Class table for prescreen context.
  * City Building Outlines, including government, medical, education, hospitality, industrial,
    commercial, airport, apartment, and other coded building types.
  * Virginia Geographic Information Network's VBMP most-recent orthophoto service. Its current
    service combines 2022, 2023, and 2025 Virginia imagery, with the newest available area on top.

Official Chesapeake project names and building names are retained as facility hints. Raw property
class, class description, source URLs, imagery label, and footprint source are preserved in scan
audit output. Chesapeake discovery stops before prescreening if its parcel-class table or both
building-footprint sources fail, preventing a service outage from producing misleading QUIET rows.

Transient network handling
--------------------------
ArcGIS, VGIN, and other HTTP reads now retry transient 429/500/502/503/504, connection, and timeout
failures up to three total attempts with short bounded backoff. Permanent errors are returned
immediately. Image validation still rejects JSON error pages, unreadable data, blank exports, and
wrong-sized exports before inference.

Bounded Norfolk controls
------------------------
Two field-review findings are encoded without changing model weights or global thresholds:

  * 830 Poplar Hall: one isolated zoom-rescue thermal hypothesis smaller than 10 x 7.5 ft, more
    than 30 ft from the only building on a sub-15,000-ft2 Norfolk warehouse, no longer ranks.
    Normal detections, larger/closer machines, multiple hypotheses, other property types, and other
    cities are unaffected.
  * Large medical campuses in Norfolk or Chesapeake with a building at least 100,000 ft2 remain
    REVIEW even when CV has no rankable evidence. The evidence text explicitly says manual HVAC
    review and does not claim a detected tower or chiller. This covers fanless/obscured heat
    rejection such as the Lake Taylor miss.

All v0.11.10 Norfolk behavior remains, including the overlapping perimeter-rescue grid, 50,000-ft2
priority focus floor, urban/dense hotel rule, small-site rescue attribution check, split-parcel
building ownership, distinct-building rescue selection, and public/institutional near-miss review.
Virginia Beach stays on its preserved v0.11.7 branch.

Detector contract
-----------------
No model was retrained. The v0.0.12 model assets and primary operating points remain:

  Stage 1 candidate:             0.07
  Tower/chiller verifier:       0.35
  Large packaged verifier:      0.45
  Shifted rescue candidate:     0.015
  Zoomed perimeter candidate:   0.008

FROZEN_DETECTION_CONTRACT.json protects model hashes, operating points, preserved detector logic,
and the bounded territory rules. The complete ResNet18 checkpoint is 22,410,981 bytes with SHA256
7dbdd679df66598a8d9e63f983507eb7900af9553595a3bb250ee6e4795e6ffd.

Recommended Chesapeake blind test
---------------------------------
1. Build and extract the Windows artifact, keeping the entire folder together.
2. Select Chesapeake. The default center is 306 Cedar Rd and the default radius is 1.0 mile.
3. Leave the minimum building size at 10,000 ft2 for the first run.
4. Click Discover + Prescreen. Confirm Chesapeake addresses, CHESAPEAKE CITY footprints, and the
   VGIN imagery label. If more than 250 candidates are reported, reduce the radius.
5. Analyze the passing properties. Review all STRONG and REVIEW sites and spot-check QUIET sites.
6. Send prospecting_results.csv first. Send individual property folders only for definite misses,
   confusing false positives, or unusually good controls; the full scan archive is not required.

Use a genuinely new Chesapeake area for the first blind test. Avoid beginning at known controls,
because the goal is to measure whether the existing detector generalizes to the new city's imagery.

City behavior
-------------
The app starts with Norfolk selected. Changing the city clears discovered rows so data sources
cannot be mixed. Each scan covers only the selected city's parcel inventory, even when its radius
crosses a municipal boundary.

Virginia Beach uses its 2025 ImageServer imagery and existing parcel/building services.
Norfolk uses its 2025 MapServer imagery, city parcel/building services, and FY27 assessment join.
Chesapeake uses city OpenData address/parcel/building/class layers and VGIN VBMP imagery.

All cities retain the Virginia Civil Reference building-footprint fallback. The actual footprint
source is recorded. Shadows, roof displacement, imagery age, tree cover, screened equipment,
fanless towers, and incomplete GIS geometry can affect results.

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

  HVAC_Territory_Discovery_v01111_Windows.zip

Extract it and run HVAC_Territory_Discovery_v01111.exe. Keep the bundled files together.

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
https://gis.cityofchesapeake.net/mapping/rest/services/OpenData/OpenData/MapServer/1
https://gis.cityofchesapeake.net/mapping/rest/services/OpenData/OpenData/MapServer/4
https://gis.cityofchesapeake.net/mapping/rest/services/OpenData/OpenData/MapServer/15
https://gis.cityofchesapeake.net/mapping/rest/services/OpenData/OpenData/MapServer/30
https://vginmaps.vdem.virginia.gov/arcgis/rest/services/VBMP_Imagery/MostRecentImagery_WGS/MapServer
https://www.norfolk.gov/1596/Geographic-Information-Systems
https://data.norfolk.gov/Real-Estate/Property-Assessment-and-Sales-FY27/qva7-tzrf
