HVAC Territory Discovery v0.7.5

Key correction:
v0.7.4 pointed at the wrong VGIN derivative layer. v0.7.5 instead uses the City of Virginia Beach's own
Basemaps/Structures_and_Physical_Features/MapServer/6 Building Footprints layer.

The city layer contains actual planimetric building polygons plus FCODE classifications such as:
Building Commercial, Building School, Building Government, Building Church, Pump Station,
Substation, Parking Garage, Airplane Hangar, etc.

Other changes:
- strict requested-radius cutoff restored for parcel representative points
- diagnostic counts displayed: parcels fetched, city footprints fetched, footprints spatially joined
- FCODE shown in result table
- two-path SIZE / ANOMALY logic retained
- many-small-building penalty retained
- no OpenAI/API calls yet

Regression:
717 General Booth / 1.0 mi / 10,000 ft2.
The diagnostic line MUST show nonzero city footprints and nonzero spatial joins.
717 and 912 should have populated building areas rather than FOOTPRINT MISSING.
