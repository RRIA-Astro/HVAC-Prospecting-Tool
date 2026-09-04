HVAC Territory Discovery v0.9.3 — Balanced High-Value Recognition

Goal
Preserve v0.9.2 cooling-tower improvements while restoring equal emphasis on air-cooled/process chillers and hydronic/process systems.

Changes
- Every crop must independently search five high-value categories: chillers, towers/fluid coolers, hydronic/process piping, large packaged HVAC, and mechanical yards/central plants.
- Explicit air-cooled chiller morphology: long integrated multi-fan equipment, scale, side-yard/perimeter placement, and equipment-to-building connections.
- Fan count alone is not diagnostic.
- Large paired piping, purposeful 90-degree routing, insulation and building termination support chiller/hydronic identification.
- Visible valves/flanges/pumps are supporting evidence, not required.
- White insulated hydronic pipe must not be dismissed as PVC based on color.
- Cooling towers and chillers are independent, equally important prospecting paths.
- v0.9.1 campus-aware coverage and v0.9.2 single-cell cooling-tower recognition remain intact.

Regression set
1. 912 Birdneck: known large air-cooled chiller beside building. Target: materially stronger than v0.9.2 MAYBE 45, ideally recognition of chiller/hydronic evidence.
2. 949 Birdneck: retain useful high-MAYBE behavior for possible single-cell heat rejection; do not force GOOD.
3. 717 General Booth: retain GOOD behavior and high-value process/mechanical-yard detection.

Recommended test order: 912 -> 949 -> 717. Run individually before another batch.
