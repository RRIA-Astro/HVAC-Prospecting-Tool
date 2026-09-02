HVAC Territory Discovery v0.9.0

ARCHITECTURE
GIS/property/building data -> non-vision prescreen -> Deep Vision -> ranked leads.

The unreliable v0.8 cheap one-call vision screen has been removed.

NON-VISION PRESCREEN
- Residential / apartment / condo / duplex properties are rejected.
- Many-small-building morphology is penalized to reduce townhome/campus false positives.
- Large buildings advance by size.
- Smaller priority properties can advance through PRIORITY EXCEPTION:
  hospital/medical, university/college, industrial/manufacturing, utilities,
  government/public, schools, military, warehouse/distribution.
- Missing-footprint parcels remain visible but do not automatically consume Deep Vision budget.
- Building size is a signal, not an absolute rule.

DEEP VISION
- Integrated 10-view + synthesis architecture (11 calls/property).
- GPT-5.4-mini.
- Connection-tracing rules from the successful v0.6.6 development:
  hydronic/process evidence is weighted; visible valves/flanges are not mandatory;
  large diameter + paired/complex routing + building termination matters;
  white pipe is not automatically PVC;
  exact chiller-vs-tower identity is secondary to correctly flagging the prospect.
- Buttons: Deep Analyze Selected, Top 10, Top 25.
- Batch only analyzes candidates marked PRE=YES.
- Completed Deep Vision results rerank GOOD -> MAYBE -> POOR.

FIRST TEST
Use 717 General Booth / 1 mile / 10,000 ft².
Before running a batch, inspect the PRE=YES shortlist.
Important checks:
- 912 Birdneck should pass prescreen and Deep Vision should return GOOD.
- 717 General Booth should pass and return GOOD.
- 949 Birdneck should pass because it is Public/Semi Public even though parcel/building association remains imperfect.
- Bell Avenue small military/institutional candidates with footprints >=2,500 ft² should survive via PRIORITY EXCEPTION.
- Residential/townhome-like properties should be pushed out before vision.

NOTE
Virginia Beach remains the regression/test data source in v0.9.0. Geographic generalization is a later architecture step.
