HVAC Deep Vision v0.6.5 — HVAC Forensic Discrimination

Adds domain rules learned from the benchmark:

- A large multi-fan box is NOT enough to call something a chiller.
- Suspected chillers must be checked for substantial hydronic/process-water connections.
- Valves, flanges, paired larger pipes, insulation, headers, fittings and similar connections strengthen chiller evidence.
- Visible PVC condensate drainage is POSITIVE evidence for direct-expansion packaged HVAC and AGAINST classifying that unit as an air-cooled water chiller.
- PVC condensate drains MUST NOT create central-plant evidence.
- Generic conduit, drains, rails, seams, shadows and roof lines must not be treated as hydronic piping.
- Strong piping triggers a trace-the-pipe / reconsider-connected-equipment pass.
- Cooling-tower search now includes screened, low-profile, closed-circuit, evaporative and process heat-rejection equipment.
- Mechanical complexity alone no longer establishes a central plant.
- Large-tonnage packaged RTUs can still be worthwhile prospects.

v0.6.4 multi-crop geometry and robust token/retry handling are retained.

REGRESSION TESTS:
1. 1632 Corporate Landing: should favor large packaged DX RTUs, with no central plant based merely on PVC drains/roof lines.
2. 912 S Birdneck: should retain probable air-cooled chiller when substantial water connections are visible.
3. 717 General Booth: should use strong piping to reconsider atypical process chillers and cooling towers.

GitHub: replace app.py, requirements.txt and .github/workflows/build-windows.yml, commit, then download HVAC-Deep-Vision-v065-Windows.
