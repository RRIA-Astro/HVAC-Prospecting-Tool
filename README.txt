HVAC Deep Vision v0.6.4

Fixes the max_output_tokens failure seen in v0.6.3.

Changes:
- Individual crop inspections now use LOW reasoning effort.
- Initial crop output allowance increased from 2,200 to 5,000 tokens.
- If a crop still hits max_output_tokens, it automatically retries once with 8,000 tokens.
- Final multi-view synthesis retains MEDIUM reasoning with a 6,000-token allowance.
- Multi-crop geometry, blind inspection rubric, quantity bands, and per-view reporting remain unchanged.

This is intentionally still an accuracy experiment using 10 visual inspections plus one synthesis call.

TEST FIRST:
912 S Birdneck — determine whether any crop detects the ground-mounted 300-ton air-cooled chiller.

GitHub:
Replace app.py, requirements.txt, and .github/workflows/build-windows.yml, then commit.
Download the HVAC-Deep-Vision-v064-Windows artifact.
