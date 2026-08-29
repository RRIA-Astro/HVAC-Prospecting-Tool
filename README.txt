HVAC Territory Discovery v0.7.3 — Parcel Spatial Join

Core fix:
Building footprints are no longer matched to nearby parcel reference points. Each building centroid must geometrically fall inside the actual Virginia Beach Property_Polygons parcel polygon.

Per property the app reports:
- largest building footprint
- total building footprint
- building count
- parcel land use/zoning
- prospect tier/score
- SPATIAL JOIN or FOOTPRINT MISSING

One prospect row is retained per GPIN. Multi-building campuses therefore remain one sales property while retaining their building counts/areas.

Regression:
- 928 Birdneck should no longer inherit neighboring building areas or appear as duplicate property rows.
- 927 and 1096 Birdneck can remain through FOOTPRINT MISSING if the external footprint dataset lacks their structures.
