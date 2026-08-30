HVAC Territory Discovery v0.8.0

MAJOR MILESTONE: Cheap Mechanical Vision Screen

Adds:
- One-image, one-call GPT-5.4-mini first-pass aerial screening.
- Low reasoning and 700 max output tokens to keep screening much cheaper than v0.6.6 Deep Vision.
- Screen Selected button for controlled regression testing.
- Screen Top 25 button; intentionally capped at 25 per click to control API spend.
- Mechanical score 0-100 and PROMISING / REVIEW / LOW result columns.
- Screened candidates are re-ranked by mechanical opportunity.
- Prompt emphasizes high recall for cooling towers, chillers/chiller-like equipment, substantial piping,
  mechanical yards, large packaged equipment and complex rooftop systems.
- Small buildings are explicitly allowed to score highly.
- Large building size alone is explicitly NOT mechanical evidence.
- Exact chiller-vs-tower identification is not required.
- GIS fallback architecture from v0.7.6 retained.
- API key is entered at runtime and is not saved to disk.

FIRST TEST RECOMMENDATION:
Do NOT Screen Top 25 initially.
1. Discover around 717 General Booth.
2. Screen Selected on known cases individually:
   - 717 General Booth (should PROMISING)
   - 912 Birdneck (should PROMISING)
   - a known poor/ordinary property (should LOW or REVIEW)
   - Bell Avenue candidate if visible in search (important small-building anomaly test)
3. Only after those look reasonable, try Screen Top 25.

This is intentionally a screening model, not detailed equipment inventory.
v0.6.6 Deep Vision remains the intended later-stage analyzer for promising/ambiguous properties.
