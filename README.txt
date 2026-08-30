HVAC Territory Discovery v0.7.4

Changes
- Uses VGIN/VBMP locality-submitted building footprints instead of Microsoft computer-vision footprints.
- Retains exact building-centroid-inside-Virginia-Beach-parcel spatial join.
- Adds average building footprint to largest/total/count.
- Penalizes many-small-building properties to reduce townhome/housing false positives.
- Adds two discovery paths:
    SIZE: largest building meets selected threshold.
    ANOMALY: smaller non-residential site retained for later mechanical-equipment screening.
- Small residential properties do not enter the ANOMALY path.
- No OpenAI/API calls yet.

Suggested regression test
Center: 717 General Booth Blvd
Radius: 1.0 mile
Size path: 10,000 ft2

Check 717, 912, 927/949 Birdneck area, Corning military/townhome properties, and Bell Avenue.
