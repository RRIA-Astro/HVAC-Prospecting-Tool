HVAC Deep Vision v0.6.6 — Connection Tracing

Built directly from the supplied v0.6.5 app.py.

MAIN CHANGE
Hydronic/process-water identification is now based on a weighted evidence hierarchy rather than requiring visible valves/flanges.

Strong evidence:
- substantial pipe diameter
- paired supply/return-style runs
- multiple 90-degree turns / complex purposeful routing
- direct equipment-to-building or penthouse termination
- insulation
- valves/flanges/headers/pumps/fittings when visible

Valves/flanges are supporting evidence, not mandatory; they may be indoors.
White piping is not automatically PVC.
Small, simple PVC condensate drainage remains positive DX evidence.
Credible complex piping triggers trace-both-directions reasoning and reconsideration of connected equipment.

Cooling-tower logic also uses piping relationships for screened, low-profile, closed-circuit, evaporative, and process heat-rejection equipment.

Regression tests:
1. 1632 Corporate Landing — should remain packaged DX / no invented central plant.
2. 912 S Birdneck — should recover the air-cooled chiller from pipe size, geometry, and building termination.
3. 717 General Booth — should use piping relationships to reconsider the process chillers and cooling towers.
