HVAC Territory Discovery v0.7.0 — Candidate Finder

PURPOSE
First territory-discovery milestone. This build finds large building footprints around a Virginia Beach search-center address, ranks them by footprint size, resolves nearby address data, and can download centered 2025 Virginia Beach aerial imagery for a selected candidate.

WHY THIS IS SEPARATE FROM DEEP VISION
v0.6.6 is the validated HVAC forensic engine. It uses 11 model calls/property and should not be run blindly on every structure. v0.7.0 establishes the upstream discovery layer first.

DEFAULTS
Radius: 1 mile
Minimum building footprint: 10,000 ft²
Results: up to 100 qualifying candidates, ranked by footprint size.

CURRENT LIMITATIONS
- Virginia Beach only.
- Candidate filtering is footprint-based in this milestone. Business/property-type scoring is the next layer.
- Nearby address matching may occasionally choose an adjacent address on dense parcels.
- Deep vision is intentionally not automatically invoked yet.

DATA
Uses public Virginia Beach address/aerial GIS services and Virginia statewide/VGIN building footprints.
