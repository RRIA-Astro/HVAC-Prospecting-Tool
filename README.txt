v0.6.3 MULTI-CROP TEST

Creates 9 overlapping high-resolution crops plus the overview. GPT-5.4 mini inspects each view independently, including building perimeter/ground areas, then an 11th call synthesizes the observations.

Uses quantity bands instead of exact equipment counts and 'not observed' instead of claiming absence.

This intentionally costs more per property; it is an accuracy experiment.

First tests:
- 912 S Birdneck: can it find the ground-mounted 300-ton air-cooled chiller?
- 717 General Booth: can it find the cooling towers and piping?
- 1632 Corporate Landing: does it avoid gross overcounting?

GitHub: replace app.py, requirements.txt, and .github/workflows/build-windows.yml, commit, then download HVAC-Deep-Vision-v063-Windows.
