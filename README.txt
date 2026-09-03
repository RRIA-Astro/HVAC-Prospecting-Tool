HVAC Territory Discovery v0.9.2

Recognition refinement based on the known 949 Birdneck regression case.

UNCHANGED
- v0.9.1 campus-aware building selection/coverage
- GIS prescreen
- facility-name lookup
- multi-building analysis
- batch error logging

CHANGED
- Deep Vision explicitly searches for small single-cell cooling towers / fluid coolers.
- One large axial top fan on a compact ground-level tower-like enclosure is now a recognized morphology.
- Louvered/air-intake enclosure morphology and location beside a building are explicit evidence.
- Cooling-tower piping may disappear underground immediately; long visible piping is NOT required.
- Credible cooling-tower / evaporative heat-rejection morphology is independently high-value.
- Building synthesis must compare compact tower-like equipment against ordinary exhaust/condenser/non-HVAC alternatives.
- Campus synthesis uses opportunity/max logic: one strong process/mechanical building can make the whole campus GOOD.

FIRST REGRESSION
949 Birdneck only.
The known cooling-tower building is Building 1 in the saved campus set.
Expected behavior: Building 1 should receive materially stronger cooling-tower/fluid-cooler evidence and the campus should rise above the v0.9.1 MAYBE 48 result.

Do not batch Top 10/25 until 949 is retested.
