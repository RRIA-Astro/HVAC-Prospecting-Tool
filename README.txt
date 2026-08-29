v0.7.2 HIGH-RECALL DISCOVERY

Changes:
- Property-first discovery using Virginia Beach parcel data plus Microsoft/VGIN building footprints.
- Paginates ArcGIS queries instead of assuming a single response is complete.
- A parcel can remain a candidate even when the footprint source has no qualifying match.
- Such rows display SQFT=UNKNOWN and SOURCE=PARCEL ONLY.
- Prospects are deduplicated by GPIN, with normalized address fallback.
- Public/Semi Public and Military are promoted to HIGH rather than UNKNOWN.
- Strict requested radius remains.
- Deep Vision is still not invoked.

Regression targets:
927 S Birdneck Rd and 1096 S Birdneck Rd should now have a path into discovery even if Microsoft's footprint layer omitted them.
928 Birdneck should not appear twice merely because multiple footprint geometries map to the same parcel.
