HVAC Territory Discovery v0.9.6 — Prospect-Oriented Chiller Recognition

WHAT STAYS FROZEN
- v0.9.5 campus discovery/coverage
- meaningful-building filter
- non-dilution rule: one GOOD building = GOOD campus
- cooling-tower/process-water logic
- GIS prescreen and facility lookup

WHAT CHANGES
The building-level Deep Vision decision standard for air-cooled/process chillers.

A/B test finding:
The exact 912 Birdneck B1 image run through standalone v0.6.6 returned MAYBE 42.
It DID notice the long ground-level rectangular unit as chiller-like, but refused to elevate it because a traceable water circuit could not be proven.

v0.9.6 changes that business rule:
- This is a SALES-PROSPECT screen, not definitive equipment verification.
- Strong large-chiller morphology is independently valuable.
- Piping is a confidence amplifier, not a mandatory gate.
- Large ground/pad/perimeter multi-fan machines are evaluated using chassis continuity, fan-array organization, finned sections, scale, placement, roof-curb/duct evidence, and connections.
- Hidden/buried/indoor/low-resolution piping must not automatically collapse a compelling chiller candidate to ordinary packaged DX.
- Strong morphology + piping remains higher confidence than morphology alone.

FIRST TEST
912 Birdneck only.
We want the model to recognize that a compelling large chiller-like machine is enough to cue salesperson review without falsely claiming that the chilled-water circuit is proven.
