HVAC Territory Discovery v0.7.6

Resilience update:
- Tries City of Virginia Beach Building Footprints first.
- If the city service is stopped/errors/returns zero, automatically falls back to Virginia CivilReference Building_Footprints.
- The fallback is the source used successfully in v0.7.3 and is currently published by Virginia DCR/VGIN.
- A footprint-source outage no longer aborts the entire search.
- Status line reports active footprint source, footprint count, spatial joins, and fallback reason.
- Parcel/address/land-use data remains Virginia Beach Pictometry Property_Polygons.
- SIZE / ANOMALY paths and many-small-building penalty retained.
- No OpenAI calls.

Regression:
717 General Booth Blvd / 1.0 mi / 10,000 ft2.
Expected during current city-service outage: source VA CIVILREF, with nonzero footprints and joins.
