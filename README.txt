HVAC Territory Discovery v0.8.2

Perimeter-focused visual screening.
For up to two largest distinct buildings, one API call now receives:
- property overview
- roof/context view
- north perimeter
- south perimeter
- east perimeter
- west perimeter

Purpose: fix false negatives where high-value chillers/cooling towers sit beside buildings.
First regression: 912 Birdneck only. If it still returns LOW, stop batch testing; the next build should save/show
the exact generated crops so we can debug aerial targeting directly.
