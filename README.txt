HVAC Territory Discovery v0.8.3 — Visual Debug Control

Purpose: isolate the 912 Birdneck false-negative.

Changes:
- The FIRST image sent to GPT is now generated with EXACTLY the same aerial() function and framing as the GUI's Download Aerial button.
- Existing overview + roof/context + N/S/E/W perimeter images remain.
- New "Save Screening Images" button writes every exact image generated for screening to:
  Downloads/HVAC_SCREEN_DEBUG_<address>/
- The folder includes numbered JPGs and a README identifying each view.
- Saving images makes NO OpenAI API call.

TEST:
1. Discover 912 Birdneck.
2. Select it and click Save Screening Images.
3. Open image 01. It should match the useful Download Aerial framing where the chiller is easily visible.
4. Inspect the other images and note which image(s) clearly show the chiller.
5. Then run Screen Selected once.

If GPT still returns LOW while image 01 clearly shows the chiller, we have isolated a model-recognition/attention problem rather than a GIS/crop-targeting problem.
