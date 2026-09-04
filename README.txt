HVAC Territory Discovery v0.9.4

ARCHITECTURE
GIS/property prescreen -> campus-aware building selection -> frozen v0.6.6 Connection-Tracing analyzer on each meaningful building -> campus opportunity synthesis.

IMPORTANT CHANGE
v0.9.4 removes the v0.9.2/v0.9.3 building-recognition prompt modifications.
The per-building inspection prompt and per-building 10-view synthesis prompt are restored verbatim from HVAC Deep Vision v0.6.6.

PRESERVED FROM NEWER VERSIONS
- Campus-aware multi-building coverage
- Facility/business-name lookup
- GIS prescreen
- Save Campus Images
- Batch error logging
- Opportunity/max campus synthesis

WHY
v0.6.6 previously recognized the known side-mounted chiller/hydronic opportunity at 912 Birdneck much better than later prompt revisions. v0.9.4 treats v0.6.6 as a frozen building analyzer and puts campus logic around it instead of continually retuning equipment recognition.

REGRESSION ORDER
1. 912 Birdneck
2. 949 Birdneck
3. 717 General Booth

Do not run a large batch until these three are checked.
