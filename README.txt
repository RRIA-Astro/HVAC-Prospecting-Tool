HVAC Territory Discovery v0.9.5 — Non-Diluting Campus

Core business rule:
ONE GOOD BUILDING = GOOD CAMPUS.

Changes from v0.9.4:
1. Frozen v0.6.6 building-recognition engine remains unchanged.
2. Campus score is deterministically floored at the strongest physical-building score.
3. Campus class cannot be lower than the strongest physical-building class.
4. Poor/ordinary buildings cannot subtract from a stronger building.
5. Additional MAYBE/GOOD buildings may add scope through campus synthesis.
6. Accessory structures below the meaningful-building floor are no longer given an independent 11-call Deep Vision analysis.
   Default floor is at least 2,500 ft², rising modestly on very large campuses.
7. The selected-analysis status line now exposes individual building results, e.g.:
   B1: GOOD 78 | B2: MAYBE 42

Regression:
- 912 Birdneck should now inspect the ~83,743 ft² school and skip the ~1,099 ft² accessory footprint.
- This test will tell us the raw B1 result directly. If B1 itself is only MAYBE, campus dilution was not the remaining cause.
- 949 Birdneck should retain its multiple meaningful buildings.
- 717 General Booth should remain strong.

Do not retune the v0.6.6 HVAC recognition prompt in this build.
