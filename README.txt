HVAC Territory Discovery v0.11.3 — Recall Rescue + Context Cleanup
===================================================================

v0.11.3 keeps the frozen v0.0.12 local detector and its primary recall-oriented thresholds unchanged while incorporating the field lessons from the v0.11.2 Virginia Beach A/B run.

PRIMARY DETECTOR OPERATING POINT — UNCHANGED
- Stage 1 candidate: 0.07
- Tower/chiller verifier: 0.35
- Large packaged HVAC verifier: 0.45
- No OpenAI API key required.

NEW THERMAL REVIEW RESCUE
- Tower/chiller recall is treated as the primary KPI.
- Very large buildings receive higher-resolution MECH FOCUS views around the building and immediate perimeter.
- If a high-value property has no accepted tower/chiller after the normal scan, up to two focus/building views receive a shifted-center Stage-1 rescue pass.
- A rescue tower/chiller candidate that still clears 0.35 is normal retained evidence.
- A plausible rescue candidate between 0.22 and 0.35 can produce REVIEW only. It cannot produce STRONG.
- This deliberately accepts some additional review workload to reduce the chance of silently missing a real tower/fluid cooler/chiller.

WHY THIS WAS ADDED
The v0.11.2 targeted quiet audit was strong overall, but 5925 Thurston contained a small tower/fluid-cooler-like object beside a large industrial building that should have been bubbled up. The normal scan had Stage-1 activity but retained no high-value evidence. v0.11.3 improves both image scale and tile/context coverage for that failure mode without globally lowering the frozen tower/chiller threshold.

PACKAGED-EQUIPMENT CONTEXT CLEANUP
Large packaged HVAC is useful but secondary to tower/chiller recall. Field review found recurring truck/trailer/loading-area false positives.

v0.11.3 therefore prevents a packaged-only detection from driving ranking when:
- the detection is clipped by an internal 1024-pixel inference-tile seam, or
- its center is more than 45 ft from the nearest mapped building footprint.

The detection is still preserved in cv_result.json for auditability and the evidence text reports context-rejected packaged evidence. This intentionally favors precision for packaged equipment while leaving tower/chiller sensitivity alone.

THERMAL TRIAGE
- Direct tower/chiller evidence with physical long dimension >=22 ft can drive STRONG.
- Smaller direct tower/chiller evidence is still surfaced, but as REVIEW.
- Campus-adjacent tower/chiller evidence remains REVIEW.
- Below-0.35 rescue evidence remains REVIEW only.
- Multiple/large packaged units can still drive STRONG/REVIEW when they pass package context checks.

PRESCREEN SANITATION
v0.11.3 adds a repeated-small-building-complex filter to catch townhouse-style developments even when the parcel is mislabeled Public/Semi Public or otherwise non-residential.

A property can be filtered when it has:
- 40+ building footprints,
- at least 85% of footprints under 15,000 ft2,
- largest building under 30,000 ft2,
- average building size under 12,000 ft2,
- and no protected institutional/industrial context.

University, college, Virginia Tech, military, hospital/medical, industrial/manufacturing, utility, government, school, pump-station, and substation contexts are protected from this morphology filter.

PROPERTY/CAMPUS LOGIC RETAINED FROM v0.11.2
- Parcel-centered overview and high-resolution parcel tiles.
- Broader but explicitly labeled campus-adjacent search for true institutional campuses.
- Detection-to-parcel geographic attribution.
- Ordinary parcel tolerance: 30 ft.
- Outside-property detections logged but excluded from ranking.
- Geographic cross-view de-duplication.
- Approximate physical equipment sizing.
- STRONG / REVIEW / QUIET triage.
- Persistent user review status/notes.
- Open Existing Scan after restart.

NEW DIAGNOSTICS
Each detection can now record:
- approximate width/height/long dimension in feet,
- distance from parcel,
- distance from nearest mapped building,
- source view kind,
- internal-tile-edge flag,
- rescue flag,
- REVIEW-only rescue flag.

cv_result.json adds:
- stage1_rescue_proposals
- thermal_rescue_evidence
- thermal_review_only_evidence

If rescue evidence is found, the annotated folder also includes RESCUE_*.jpg overlays in yellow.

HOW TO USE
1. Enter a Virginia Beach center address, radius, and size threshold.
2. Click 1. Discover + Prescreen.
3. Review the PRESCREEN REASON column if a property looks unexpected.
4. Click 2. Analyze Prescreened.
5. STRONG and REVIEW properties rise above QUIET properties.
6. Double-click a row for details or open the saved scan folder for imagery.
7. Use Mark STRONG / REVIEW / QUIET and Edit Note during field review.
8. After a restart, click Open Existing Scan and choose the HVAC_Prospecting_Scan_* folder.

OUTPUT
Downloads\HVAC_Prospecting_Scan_YYYYMMDD_HHMMSS\
- prospecting_results.csv
- SCAN_SUMMARY.txt
- one folder per analyzed property
  - source aerials
  - source\view_manifest.json
  - annotated views
  - annotated\RESCUE_*.jpg when rescue evidence exists
  - cv_result.json

IMPORTANT
This is a sales-prospecting filter, not an engineering survey. A QUIET result is not proof that valuable mechanical equipment is absent. The operating philosophy remains asymmetric: false positives cost review time, while a missed cooling tower or chiller can hide a valuable opportunity.

WINDOWS BUILD
Upload this source tree to GitHub, preserving .github/workflows/build-windows.yml and models/. Run the Build Windows EXE workflow. The artifact will be HVAC_Territory_Discovery_v0113_Windows.zip.

The build remains PyInstaller --onedir because PyTorch/Ultralytics is more reliable this way. The FP16 ResNet18 state remains below GitHub's browser per-file upload limit.

Keep v0.10.1 as the dedicated Training-Safe labeling app. v0.11.3 remains a prospecting/field-validation build.
