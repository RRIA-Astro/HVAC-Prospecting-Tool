HVAC Territory Discovery v0.11.7 — Diagnostic Calibration
==========================================================

Purpose
-------
Desktop prospecting triage for commercial HVAC opportunities in Virginia Beach aerial imagery.
The application discovers parcels, applies a precision-weighted GIS prescreen, downloads parcel/building
views, and runs the bundled two-stage detector locally. Results are STRONG, REVIEW, or QUIET.

This is a prospecting filter, not an engineering survey or equipment inventory. A REVIEW result
means investigate further. QUIET means no rankable evidence was observed in the available imagery;
it does not prove that valuable equipment is absent.

What v0.11.7 changes
--------------------
This build converts the 250-property September 13 field review and its 11-property diagnostic subset
into bounded ranking changes while leaving the v0.0.12 detector, verifier, image acquisition, model
thresholds, rescue thresholds, and v0.11.6 prescreen frozen.

1. Package boxes from overview/parcel-tile views more than 5 ft from a mapped building are rejected,
   except for an established very-high-certainty close-footprint control. Weak package hypotheses
   below both p=0.55 and best class=0.35 are also rejected. These rules remove the loading canopy at
   2682 Dean, emergency/generator equipment at 1243 Bayne, the Hobby Lobby semi-trailer, and yard
   clutter at 189 Rosemont.
2. A seam-cut package can rank only when a strong non-seam raw observation corroborates the same
   machine. An all-seam package result is REVIEW-only. This recovers the two real 50-100 ton units at
   484 Viking without reopening ordinary seam false positives.
3. One on-building package at least 25 ft with p>=0.65 and best class>=0.55 can create REVIEW. This
   narrowly surfaces the approximately 26 ft AHU at 777 Seahawk.
4. Rescue-only thermal boxes are rejected when they are more than 45 ft from a building on a site
   below 8,000 ft2, or when a compact review-only box below 22 ft has both p<0.70 and best class<0.40.
   These remove the 2856 Crusader yard debris and 2697 International residential condenser controls.
5. A compact rooftop tower label below 30 ft on a Commercial building of at least 100,000 ft2 remains
   visible but cannot create STRONG alone. Hobby Lobby therefore becomes REVIEW, not STRONG.
6. When all verified equipment paths are empty, a military/federal site with at least a 30,000 ft2
   building and one normal Stage-1 proposal can receive REVIEW. Its evidence text explicitly says
   "Strategic-site unverified proposal" and does not claim recognized equipment. This catches NAS
   Oceana - NEXCOM HQ while preserving the known fanless-equipment limitation.

The diagnostic replay keeps 509 Viking and 477 Viking STRONG; moves 2682 Dean, 2697 International,
2856 Crusader, 1243 Bayne, and 189 Rosemont to QUIET; moves 777 Seahawk, NEXCOM HQ, and 484 Viking to
REVIEW; and downgrades Hobby Lobby from STRONG to REVIEW. See REGRESSION_NOTES_v0117.txt for exact
evidence and limitations.

Inherited v0.11.5 perimeter recall
----------------------------------
5925 Thurston was still QUIET in the completed v0.11.4 field scan. The probable side-yard
heat-rejection unit is visible in F02_138944sf.jpg, but neither the normal tiles nor the shifted
1024-pixel rescue tiles produced a Stage-1 proposal on it.

v0.11.5 adds a final, tightly gated zoomed perimeter pass:

1. It runs only on an eligible priority property with no normal tower/chiller hypothesis.
2. The existing shifted 1024-pixel rescue runs first.
3. If that rescue has no rankable thermal evidence, each selected focus view is covered by a 3 x 3
   grid of 512-pixel crops enlarged to 1024 pixels for inference.
4. Stage 1 uses a rescue-only 0.008 proposal floor. Only physically plausible 7-130 ft proposals
   are verified, with bounded proposal counts per tile.
5. A retained zoomed proposal must have total thermal probability >=0.55 and best thermal-class
   probability >=0.50.
6. Every zoomed result is REVIEW-only. It cannot create STRONG by itself.

Direct inference with the bundled frozen models now produces:

- 5925 Thurston F02: cooling-tower REVIEW evidence on the actual side-yard fan bank
  (p=0.7965, best class=0.6976, Stage-1=0.00819, approximately 14.5 ft).
- 1444 Diamond Springs B01: cooling-tower REVIEW evidence on the rooftop target
  (p=0.6444, best class=0.5937, Stage-1=0.01171, approximately 9.8 ft).
- 5770 Thurston B01: no zoomed evidence.
- 2377 Ferry B01: the known scrap lookalike is retained in raw audit evidence but rejected from
  ranking at approximately 108 ft from the nearest mapped building.

Recall routing
--------------
Rescue eligibility now includes smaller priority sites down to a 2,500 ft2 largest footprint,
including Public/Semi Public property. This gives 1444 Diamond Springs a rescue view despite its
10,018 ft2 largest building. Residential, restaurant, retail, shopping, and storage contexts remain
excluded. Sites at or above 75,000 ft2 use up to two focus views; smaller eligible sites use one.

False-positive controls
-----------------------
The completed 135-property v0.11.4 scan exposed recurring vehicles, scrap, roof spans, and repetitive
self-storage layouts. v0.11.5 keeps raw detections in cv_result.json for audit while excluding these
patterns from ranking:

- Weak overview detections cut by an inference seam.
- Rescue thermal detections with best class probability below 0.22 or more than 75 ft from a mapped
  building.
- Low-confidence overview thermal boxes at least 80 x 45 ft.
- Overview packaged boxes at least 90 x 50 ft unless total probability is at least 0.90.
- Packaged evidence more than 45 ft from a building, except a narrow high-certainty side-yard rule
  (building/focus view, <=70 ft, p>=0.82, best class>=0.70).
- Explicit self-storage parcels and non-protected complexes dominated by small elongated footprints.

University, college, Virginia Tech, military, hospital/medical, Public/Semi Public, manufacturing,
utility, government, school, pump-station, and substation contexts are protected from the geometric
storage heuristic.

The cross-class geographic de-duplicator also merges nested or partially overlapping tower/chiller
boxes from the same image so one machine does not count twice (the 965 Baker case).

Saved-scan ranking replay
-------------------------
Replaying the 135 saved v0.11.4 cv_result.json files through the new ranking logic yields 16 STRONG,
6 REVIEW, and 113 QUIET. Four saved statuses change:

- 1569 Diamond Springs: QUIET -> STRONG (high-certainty fixed side-yard packaged unit).
- 1400 Air Rail: REVIEW -> QUIET (weak overview seam/trailer lookalike).
- 5770 Thurston: REVIEW -> QUIET (weak rescue vehicle/debris lookalikes).
- 2377 Ferry: REVIEW -> QUIET (rescue scrap lookalike too far from a building).

5925 Thurston and 1444 Diamond Springs require fresh inference to receive the new zoomed evidence;
their old JSON files cannot contain detections from a path that did not yet exist. Fresh discovery is
also required for the new footprint-morphology storage filter because old scan CSVs omit building rings.
With current footprints, 1409 Diamond Springs is correctly classified as a repetitive storage-like
complex (12 of 12 elongated small footprints), while 1444 Diamond Springs remains protected by its
Public/Semi Public context and passes the prescreen.

The zoomed path was also executed across all 70 saved properties that would reach it under v0.11.5,
using current parcel polygons and building footprints. Ten properties retained any raw zoom evidence;
eight had rankable evidence after attribution and building-context checks. The bounded fallback therefore
adds targeted REVIEW recall rather than broadly reclassifying the territory.

Frozen model contract
---------------------
The bundled v0.0.12 model weights are byte-for-byte unchanged. Normal operating points remain:

- Stage-1 candidate: 0.07
- Cooling tower / air-cooled chiller verifier: 0.35
- Large packaged HVAC verifier: 0.45

The 0.015 shifted-rescue and 0.008 zoomed-rescue Stage-1 floors apply only inside their bounded rescue
paths. Low-Stage-1 rescue evidence is REVIEW-only.

Output and audit fields
-----------------------
Each site folder retains source imagery, annotated evidence, cv_result.json, and a view manifest.
The scan CSV/JSON includes:

- stage1_rescue_proposals, deep_rescue_tiles, deep_rescue_verified
- perimeter_rescue_proposals, perimeter_rescue_tiles, perimeter_rescue_verified
- perimeter_rescue_evidence, thermal_rescue_evidence, thermal_review_only_evidence
- context-rejected evidence summaries while preserving raw detections
- neighbor_assigned_evidence in CSV plus cross_property_rejected and the rejected detection audit
  records in cv_result.json

Run from source
---------------
Use Python 3.12 on Windows:

  pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
  pip install -r requirements.txt
  python app.py

Build the portable Windows app
------------------------------
Upload this source tree to GitHub with .github/workflows/build-windows.yml and models/ intact. Run
the Build Windows EXE workflow. The artifact will be:

  HVAC_Territory_Discovery_v0117_Windows.zip

Extract that ZIP before running the EXE. Keep the generated folder together because PyInstaller
onedir dependencies and model assets are required at runtime.

Validation
----------
Run:

  python -m unittest -v test_v0117_logic.py

The suite checks frozen thresholds, 5925 zoom coverage, zoom coordinate mapping, smaller-priority
rescue routing, known package/thermal context cases, the 1609 debris rejection, ambiguous-small-
public prescreening, cross-view and cross-property fusion, and storage morphology.

Keep v0.10.1 as the dedicated Training-Safe labeling app. v0.11.7 remains the prospecting and
field-validation build.
