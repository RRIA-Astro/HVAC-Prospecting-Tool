HVAC Territory Discovery v0.11.2 — Property/Campus Cleanup
===========================================================

v0.11.2 keeps the frozen v0.0.12 local detector and its recall-oriented thresholds unchanged, while fixing property-side issues found during the 185-property Virginia Beach field run.

FROZEN DETECTOR OPERATING POINT
- Stage 1 candidate: 0.07
- Tower/chiller verifier: 0.35
- Large packaged HVAC verifier: 0.45
- No OpenAI API key required.

WHY v0.11.2
The field run showed that the detector itself was generally functioning well, but several errors were caused upstream/downstream by GIS, image framing, cross-view duplication, and ranking:
- 1444 Diamond Springs (Virginia Tech) was a critical false negative because the useful building/towers were not adequately covered by the generated campus views.
- Several false positives were real equipment on neighboring properties that happened to be in-frame.
- Generic Public/Semi Public land use allowed many small residential properties through the old 2,500-ft2 priority exception.
- Town House was not treated as residential.
- Repeated views of one machine could inflate evidence counts.
- Mid-sized packaged HVAC needed to remain detectable but should usually be additive rather than a strong prospect by itself.

WHAT CHANGED
1. Parcel/campus coverage
   - Campus overview is centered on the parcel extent, not only selected building-footprint centroids.
   - Campus-like properties receive overlapping high-resolution parcel coverage tiles.
   - Institutional campuses can use a broader adjacent-campus search buffer so a central plant is not missed solely because parcel GIS splits a real campus.
   - Each source folder now includes view_manifest.json with view centers, extents, and attribution settings.

2. Property attribution
   - Accepted detections are geolocated from image pixels back to approximate ground coordinates.
   - Ordinary properties use a 30-ft parcel tolerance.
   - True institutional campuses may retain farther campus-adjacent tower/chiller evidence, but it is explicitly labeled ADJ and ranks as REVIEW rather than being blindly treated as target-parcel equipment.
   - Equipment beyond the allowed attribution buffer is logged in cv_result.json and annotated orange, but does not rank the property.

3. Cross-view de-duplication
   - Repeated detections of the same physical object in overlapping campus/building views are geographically de-duplicated.
   - CSV evidence is therefore closer to physical evidence than the v0.11.1 raw hit count, though it is still not an engineering inventory.

4. Prescreen sanitation
   - Town House / Townhouse / Townhome are residential and do not pass.
   - Generic Public/Semi Public no longer receives the 2,500-ft2 priority exception.
   - Public Storage / Self Storage / Mini Storage are not granted an industrial priority exception merely because parcel land use says Industrial.
   - Prescreen reason is shown in the table and written to prospecting_results.csv.

5. Packaged-equipment triage
   - Approximate equipment dimensions are derived from aerial scale.
   - A few mid-sized packaged units can remain QUIET.
   - Multiple/large packaged units can move a property to REVIEW or STRONG.
   - Towers/chillers remain the highest priority and dominate ranking.
   - This is intentionally approximate; dimensions are used as ranking evidence, not claimed tonnage.

6. STRONG / REVIEW / QUIET
   - STRONG: direct high-value evidence or convincing large packaged-equipment concentration.
   - REVIEW: worthwhile ambiguity, including mid-sized cumulative capacity or campus-adjacent tower/chiller evidence.
   - QUIET: no retained high-value evidence after attribution/ranking.

7. Persistent manual review
   - Mark a selected row STRONG / REVIEW / QUIET and add a note.
   - Review status is written immediately into prospecting_results.csv.
   - Open Existing Scan reloads a prior scan folder after a restart so review progress is not lost.

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
  - cv_result.json

IMPORTANT
This is a sales-prospecting filter, not an engineering survey. A QUIET result is not proof that valuable mechanical equipment is absent. The operating philosophy is deliberately asymmetric: false positives cost review time, while a missed cooling tower or chiller can hide a valuable opportunity.

WINDOWS BUILD
Upload this source tree to GitHub, preserving .github/workflows/build-windows.yml and models/. Run the Build Windows EXE workflow. The artifact will be HVAC_Territory_Discovery_v0112_Windows.zip.

The build remains PyInstaller --onedir because PyTorch/Ultralytics is more reliable this way. The FP16 ResNet18 state remains below GitHub's browser per-file upload limit.

Keep v0.10.1 as the dedicated Training-Safe labeling app. v0.11.2 remains a prospecting/field-validation build.
