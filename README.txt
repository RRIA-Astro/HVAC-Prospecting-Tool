HVAC Territory Discovery v0.9.1 — Campus-Aware Deep Vision

WHAT CHANGED
- Campus/property is now the opportunity unit, not the mailing-address building.
- Discovery retains all joined building footprints for each parcel.
- New INSPECT column shows how many meaningful buildings will receive Deep Vision.
- Up to 6 meaningful buildings per property are inspected, largest first; tiny accessory structures are skipped.
- Each inspected building gets its own high-resolution aerial centered on that footprint with perimeter context.
- Each building then receives the proven v0.6.6-style 10-view + synthesis analysis (11 calls/building).
- One additional low-cost campus-overview vision call provides context for detached equipment and inter-building infrastructure.
- Final campus synthesis does NOT average away a strong process building: one strong building can make the campus GOOD.
- New Save Campus Images button saves the campus overview plus every exact building-centered source aerial before API analysis.
- FACILITY column adds best-effort nearby facility/business names from OpenStreetMap/Overpass. Blank or imperfect names are possible; address/GIS remains authoritative for geometry.
- Batch failures are now written to Downloads/HVAC_v091_batch_errors.txt instead of being silently counted.

IMPORTANT COST NOTE
Campus-aware analysis can use substantially more API calls than v0.9.0 on multi-building properties.
Example: 6 inspected buildings = about 67 calls (6 x 11 building calls + 1 campus overview context), plus final campus synthesis.
Use Deep Analyze Selected while validating 949 Birdneck before running a large batch.

FIRST REGRESSION TEST — 949 BIRDNECK
1. Discover + Prescreen around 717 General Booth.
2. Select 949 Birdneck.
3. Check BLDGS and INSPECT. The app should no longer inspect only the address-centered fire station.
4. Click Save Campus Images BEFORE spending API credits.
5. Confirm one of the Bxx images centers the lower-right building where the cooling tower is visible.
6. Then Deep Analyze Selected.
7. The campus result should be allowed to become GOOD even if the fire-station building itself is POOR.

SECOND REGRESSION TEST — 912 BIRDNECK
Save Campus Images and confirm the building image includes the side-mounted chiller and perimeter at useful resolution, then run Deep Analyze Selected.
