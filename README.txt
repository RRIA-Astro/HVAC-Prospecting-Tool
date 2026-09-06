HVAC Territory Discovery v0.10.1 — Training-Safe Review & Label

PURPOSE
Prevent unreviewed aerial images from silently becoming negative detector-training examples.

IMAGE REVIEW STATES

POSITIVE
- The image has been fully inspected.
- At least one high-value target is present.
- ALL visible target-class equipment should be boxed.
- A Positive image without a valid box is automatically treated as UNREVIEWED.

NEGATIVE
- The image has been fully inspected.
- No target-class equipment is present.
- Ordinary small RTUs, splits, residential/light-commercial condensers and vents are background.
- An explicit empty YOLO label file is created.

UNREVIEWED
- Not safe for detector training.
- No YOLO label file is kept.
- Excluded from Training-Safe export.

MIGRATION FROM v0.10.0
Conservative migration is automatic:
- Existing image with target boxes -> POSITIVE.
- Existing image explicitly marked Negative -> NEGATIVE.
- Everything else -> UNREVIEWED, even if it had a GOOD/MAYBE/POOR image or site rating.

NEW UI
- Explicit Positive / Negative / Unreviewed state for every image.
- Progress counter: Reviewed X/Y | Positive X | Negative X | Unreviewed X.
- Discovery table shows reviewed-image progress for saved sites.
- Drawing a target box automatically marks the image Positive.
- Marking an annotated image Negative asks before deleting its target boxes.

EXPORT TRAINING-SAFE ZIP
- Includes ONLY reviewed Positive and Negative images.
- Positive images include YOLO boxes.
- Negative images include explicit empty YOLO label files.
- Unreviewed images are absent.
- Positive images without a valid box are excluded.
- Includes classes.txt, dataset.yaml, review_manifest.csv and README.txt.

FULL DATASET BACKUP
- Copies the entire working HVAC_Training_Dataset folder, including unreviewed material.
- Use for backup/transfer only, not direct model training.

IMPORTANT
For a Positive image, box every visible instance of every target class. An unboxed visible target can otherwise be learned as background.
