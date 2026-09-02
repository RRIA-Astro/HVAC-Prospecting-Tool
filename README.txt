HVAC Territory Discovery v0.8.1

Building-aware mechanical screen.

One API call per property now includes a property overview plus up to four close aerial views centered on the largest distinct building footprints, with generous perimeter context. This directly targets the v0.8.0 false negatives at 912 Birdneck, 717 General Booth, and 949 Birdneck, where important chillers/cooling towers sit beside buildings.

Regression before batch use:
- 912 Birdneck: should materially exceed 22 and preferably PROMISING
- 717 General Booth: should materially exceed 58 and preferably PROMISING
- 949 Birdneck: should notice high-value side equipment
- 1008 Bells: should remain LOW
- 589 Birdneck: should remain LOW

Do not Screen Top 25 until those five discriminate acceptably.
