HVAC Territory Discovery v0.9.10 — Calibrated Sales Scoring

PURPOSE
Calibrate deterministic scoring using:
- 912 Birdneck as a positive control (large ground-mounted multi-fan chiller)
- 589 Birdneck as a negative control (ordinary light-industrial building with small side-mounted packaged HVAC)

CHANGES FROM v0.9.7
1. POSSIBLE chiller/tower evidence can no longer create a GOOD score.
2. A single PROBABLE chiller/tower view normally creates MAYBE, not GOOD.
3. GOOD from deterministic rules requires stronger evidence:
   - STRONG high-value equipment morphology, OR
   - PROBABLE evidence repeated across views, OR
   - PROBABLE evidence plus independent piping/mechanical-yard corroboration.
4. Large packaged HVAC alone is capped at a MAYBE rule floor.
5. Missing piping still never subtracts from a credible chiller/tower candidate.
6. Vision instructions now emphasize physical scale using cars, parking stalls,
   doors, roof curbs and building dimensions, and explicitly warn against
   confusing small side-mounted packaged units with large chillers.
7. Existing campus non-dilution behavior remains intact.

FIRST TEST
Run 912 Birdneck and 589 Birdneck before broader testing.
Desired behavior:
- 912: GOOD or strong MAYBE that clearly identifies the large chiller candidate.
- 589: POOR/MAYBE, but NOT promoted to GOOD by the deterministic rule.


v0.9.10 calibration: suppresses low-value-only small/local HVAC false positives; weak MAYBE buildings no longer accumulate into a stronger campus. High-value chiller/tower/process evidence remains recall-biased.
