HVAC Territory Discovery v0.9.7 — Deterministic Sales Scoring

ARCHITECTURE CHANGE
GPT identifies visible equipment. Code, not GPT, sets a minimum sales-opportunity score from those observations.

WHY
The exact 912 Birdneck image repeatedly produced a chiller-like observation but GPT downgraded the property because it could not prove a water loop. For prospecting, that is the wrong veto.

RULES
- Credible large air-cooled/process chiller morphology establishes a sales-score floor even without visible piping.
- Cooling-tower/heat-rejection morphology does the same.
- Strong/probable hydronic/process piping independently raises the floor.
- Large packaged HVAC gets a smaller floor.
- Piping corroborates high-value equipment but its absence never subtracts.
- GPT's original synthesis score is retained as model_score for diagnostics.
- Final building score = max(model_score, deterministic rule floor).
- Campus non-dilution remains unchanged: best physical building cannot be diluted by poor/accessory buildings.

UI DIAGNOSTIC
After analysis, the building trace shows:
B1: GOOD 68 [model 42, rule 68]
This makes it clear whether the result came from GPT synthesis or the deterministic sales rules.

FIRST REGRESSION SET
1. 912 Birdneck — should be elevated if the detector again reports the large chiller-like anomaly.
2. 717 General Booth — should remain GOOD.
3. 949 Birdneck — should remain at least review-worthy if tower/heat-rejection evidence is detected.
4. 589 Birdneck — should remain low/poor if it only shows ordinary light-industrial HVAC.
