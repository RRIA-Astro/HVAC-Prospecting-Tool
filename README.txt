HVAC Territory Discovery v0.10.0 — Review & Label

PURPOSE
v0.10.0 stops trying to make a generic vision model definitively identify HVAC equipment.
It preserves the GIS/campus discovery work and turns the application into a human-in-the-loop
prospecting and training-data tool.

NO OPENAI API KEY IS REQUIRED IN THIS VERSION.

PRIMARY WORKFLOW
1. Discover + Prescreen an area.
2. Select a property.
3. Click Review / Label Selected (or double-click the row).
4. Review the campus overview and each meaningful building image.
5. Give the SITE a GOOD / MAYBE / POOR rating.
6. On each image, select a high-value equipment class and drag a box around known equipment.
7. Mark an image Negative when none of the high-value target classes is present.
8. Add notes if useful and Save.
9. Repeat. The tool is now creating a reusable labeled aerial dataset from expert review.

TARGET OBJECT CLASSES
0 cooling_tower
1 air_cooled_chiller
2 large_packaged_hvac
3 process_hydronic_piping
4 mechanical_yard_process
5 other_high_value_mechanical

IMPORTANT NEGATIVE-EXAMPLE RULE
Small residential/light-commercial condensers, mini-splits, ordinary small RTUs, vents and similar
low-value equipment are BACKGROUND, not target classes. If an image contains only that kind of
mechanical equipment, mark the image Negative instead of drawing boxes around it.

This design directly teaches a future detector the difference between:
- 912-type high-value chiller opportunities, and
- 589/928-type ordinary low-value HVAC sites.

LABELING WINDOW
- Campus overview + building-centered images.
- Site GOOD/MAYBE/POOR rating.
- Image/building GOOD/MAYBE/POOR rating.
- Draw equipment bounding boxes with click-drag.
- Delete individual boxes or clear an image.
- Mark clean/low-value images as Negative.
- Site notes and image notes.

DATASET LOCATION
The app writes persistent data under:
  Downloads/HVAC_Training_Dataset/

FILES CREATED
- annotations.json        Full metadata, site labels, image labels, boxes and notes.
- site_labels.csv         Easy-to-review site-level ratings.
- classes.txt             Detector class order.
- images/                 The exact aerial images that were labeled.
- labels/                 YOLO-format bounding-box files. Empty files are valid negative images.

EXPORT
Click Export Dataset ZIP to create a timestamped ZIP in Downloads.
This makes it easy to upload the growing dataset later for model training.

DATASET SUMMARY
Shows number of sites, site ratings, images, negative images, total bounding boxes and class counts.
Use this to see where the training set is thin.

DISCOVERY
This build intentionally keeps the existing Virginia Beach GIS/aerial pipeline so labeling can begin
immediately. Geographic portability should be handled separately after the labeling workflow is stable.
