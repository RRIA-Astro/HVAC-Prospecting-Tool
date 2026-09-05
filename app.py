import base64,json,math,threading,tkinter as tk,urllib.parse,urllib.request,tempfile,time,shutil
from tkinter import ttk,messagebox
from pathlib import Path

ADDR="https://geo.vbgov.com/mapservices/rest/services/Business_Systems/Pictometry_Online/MapServer/0/query"
PARCEL="https://geo.vbgov.com/mapservices/rest/services/Business_Systems/Pictometry_Online/MapServer/4/query"
# City of Virginia Beach authoritative planimetric Building Footprints
CITY_BLDGS="https://geo.vbgov.com/mapservices/rest/services/Basemaps/Structures_and_Physical_Features/MapServer/6/query"
FALLBACK_BLDGS="https://dsfmportal.dcr.virginia.gov/server/rest/services/CivilReference/Civil_Reference_Layers/MapServer/2/query"
AERIAL="https://geo.vbgov.com/imageservices/rest/services/Imagery/Aerial2025/ImageServer/exportImage"

def gj(u,p):
    q=urllib.parse.urlencode(p)
    req=urllib.request.Request(u+"?"+q,headers={"User-Agent":"HVAC-Territory/0.9.8"})
    with urllib.request.urlopen(req,timeout=90) as r:
        d=json.loads(r.read().decode())
    if "error" in d: raise RuntimeError(d["error"].get("message",str(d["error"])))
    return d

def geocode(t):
    m=gj(ADDR.rsplit("/query",1)[0],{"f":"json"})
    fs=[f["name"] for f in m.get("fields",[]) if f.get("type")=="esriFieldTypeString"]
    fs=([x for x in fs if any(k in x.lower() for k in ("address","full","street","site"))] or fs)[:8]
    s=t.replace("'","''")
    d=gj(ADDR,{"f":"json","where":" OR ".join(f"UPPER({f}) LIKE UPPER('%{s}%')" for f in fs),
               "outFields":"*","returnGeometry":"true","outSR":"4326","resultRecordCount":10})
    if not d.get("features"):raise RuntimeError("Search-center address not found.")
    g=d["features"][0]["geometry"];return float(g["x"]),float(g["y"])

def bbox(x,y,m):
    dy=m/69;dx=m/(69*max(.2,math.cos(math.radians(y))))
    return x-dx,y-dy,x+dx,y+dy
def miles(x,y,a,b):return math.hypot((a-x)*69.172*math.cos(math.radians(y)),(b-y)*69)

def ring_area(r):
    if len(r)<3:return 0
    la=sum(p[1] for p in r)/len(r);c=math.cos(math.radians(la))
    q=[(p[0]*69.172*c*5280,p[1]*69*5280) for p in r]
    return abs(sum(q[i][0]*q[(i+1)%len(q)][1]-q[(i+1)%len(q)][0]*q[i][1] for i in range(len(q)))/2)
def area(rs):return sum(ring_area(r) for r in (rs or []))
def centroid(rs):
    pts=[q for r in (rs or []) for q in r]
    return (sum(p[0] for p in pts)/len(pts),sum(p[1] for p in pts)/len(pts)) if pts else (None,None)

def pinring(x,y,r):
    inside=False;j=len(r)-1
    for i in range(len(r)):
        xi,yi=r[i];xj,yj=r[j]
        if ((yi>y)!=(yj>y)) and x<(xj-xi)*(y-yi)/(yj-yi+1e-30)+xi:inside=not inside
        j=i
    return inside
def pinpoly(x,y,rs):return any(pinring(x,y,r) for r in (rs or []))

def pages(u,p,chunk=1800):
    out=[];off=0
    while True:
        q=dict(p);q["resultOffset"]=off;q["resultRecordCount"]=chunk
        d=gj(u,q);fs=d.get("features",[]);out.extend(fs)
        if not d.get("exceededTransferLimit") and len(fs)<chunk:break
        if not fs:break
        off+=len(fs)
    return out

def load_parcels(x,y,mi):
    a,b,c,d=bbox(x,y,mi)
    p={"f":"json","where":"1=1","geometry":f"{a},{b},{c},{d}","geometryType":"esriGeometryEnvelope",
       "inSR":"4326","spatialRel":"esriSpatialRelIntersects",
       "outFields":"PAR_GPIN,FULL_ADDR,PROP_ADDRESS,LAND_USE,ZONING,PROP_CLASS,LATITUDE,LONGITUDE",
       "returnGeometry":"true","outSR":"4326"}
    out=[]
    for f in pages(PARCEL,p):
        at=f.get("attributes",{});rs=f.get("geometry",{}).get("rings",[]);cx,cy=centroid(rs)
        try:lon=float(at.get("LONGITUDE") or cx);lat=float(at.get("LATITUDE") or cy)
        except:continue
        # Strict user radius on the property's representative point.
        if miles(x,y,lon,lat)>mi:continue
        out.append({"gpin":str(at.get("PAR_GPIN") or ""),"address":at.get("FULL_ADDR") or at.get("PROP_ADDRESS") or "",
                    "land":at.get("LAND_USE") or "","zone":at.get("ZONING") or "",
                    "lon":lon,"lat":lat,"rings":rs,"psq":area(rs)})
    return out

def _query_buildings(url,x,y,mi,outfields):
    a,b,c,d=bbox(x,y,mi)
    p={"f":"json","where":"1=1","geometry":f"{a},{b},{c},{d}","geometryType":"esriGeometryEnvelope",
       "inSR":"4326","spatialRel":"esriSpatialRelIntersects","outFields":outfields,
       "returnGeometry":"true","outSR":"4326"}
    out=[]
    for f in pages(url,p):
        rs=f.get("geometry",{}).get("rings",[]);cx,cy=centroid(rs)
        if cx is None:continue
        if miles(x,y,cx,cy)<=mi*1.03:
            at=f.get("attributes",{})
            out.append({"lon":cx,"lat":cy,"sq":round(area(rs)),
                        "fcode":at.get("fcode") or at.get("FCODE") or "",
                        "height":at.get("height_highest")})
    return out

def load_buildings(x,y,mi):
    errors=[]
    try:
        b=_query_buildings(CITY_BLDGS,x,y,mi,"*")
        if b:return b,"VB CITY",errors
        errors.append("VB CITY returned 0 footprints")
    except Exception as e:
        errors.append("VB CITY: "+str(e))
    try:
        b=_query_buildings(FALLBACK_BLDGS,x,y,mi,"*")
        if b:return b,"VA CIVILREF",errors
        errors.append("VA CIVILREF returned 0 footprints")
    except Exception as e:
        errors.append("VA CIVILREF: "+str(e))
    return [],"NONE",errors

def load_osm_names(x,y,mi):
    a,b,c,d=bbox(x,y,mi)
    query=f'[out:json][timeout:25];(nwr["name"]({b},{a},{d},{c}););out center tags;'
    try:data=gj("https://overpass-api.de/api/interpreter",{"data":query})
    except Exception:return []
    out=[]
    for e in data.get("elements",[]):
        t=e.get("tags",{});name=(t.get("name") or "").strip()
        if not name:continue
        lon=e.get("lon");lat=e.get("lat")
        if lon is None or lat is None:
            ce=e.get("center") or {};lon=ce.get("lon");lat=ce.get("lat")
        if lon is None or lat is None:continue
        kind=t.get("amenity") or t.get("office") or t.get("shop") or t.get("industrial") or t.get("building") or t.get("man_made") or ""
        out.append({"name":name,"lon":float(lon),"lat":float(lat),"kind":kind})
    return out

def assign_facility_names(ps,names):
    for p in ps:
        inside=[n for n in names if pinpoly(n["lon"],n["lat"],p["rings"])]
        if inside:
            inside.sort(key=lambda n:(0 if n["kind"] else 1,miles(p["lon"],p["lat"],n["lon"],n["lat"])))
            p["facility"]=inside[0]["name"]
        else:
            near=sorted(names,key=lambda n:miles(p["lon"],p["lat"],n["lon"],n["lat"]))
            p["facility"]=near[0]["name"] if near and miles(p["lon"],p["lat"],near[0]["lon"],near[0]["lat"])<=0.04 else ""

def classify(land,zone,largest,avg,count,fcodes):
    s=(land+" "+zone+" "+" ".join(fcodes)).upper()
    very_high=("HOSP","MEDICAL","UNIVERS","COLLEGE","INDUSTR","MANUFACTUR","UTILITY","PUMP STATION","SUBSTATION")
    high=("GOVERN","SCHOOL","PUBLIC/SEMI PUBLIC","WAREHOUSE","DISTRIBUT")
    low=("APART","CONDO","MULTI FAMILY","MULTIFAMILY","RESTAUR","RETAIL","SHOPPING","STORE","SINGLE FAMILY","DUPLEX")
    medium=("OFFICE","HOTEL","MOTEL","CHURCH","RELIG","ASSEMBLY","ENTERTAIN","AUTO","COMMERCIAL","MILITARY")
    if any(k in s for k in very_high): tier,score="HIGH",82
    elif any(k in s for k in high): tier,score="HIGH",74
    elif any(k in s for k in low): tier,score="LOW",18
    elif any(k in s for k in medium): tier,score="MEDIUM",52
    else:tier,score="UNKNOWN",42

    # One/few substantial buildings matter more than aggregate campus area.
    if largest:
        score += 16 if largest>=100000 else 13 if largest>=75000 else 9 if largest>=40000 else 5 if largest>=20000 else 2 if largest>=10000 else 0
    if avg:
        score += 5 if avg>=40000 else 3 if avg>=20000 else 0
    # Penalize townhome / many-small-building morphology.
    if count>=20 and avg and avg<10000:score-=28
    elif count>=10 and avg and avg<10000:score-=20
    elif count>=6 and avg and avg<7000:score-=14
    # Missing footprints are retained in discovery but should not consume Deep Vision budget first.
    if largest is None:score-=10
    return tier,max(0,min(99,score))

def prescreen(p,mn):
    """Cheap non-vision gate. High recall for central/process HVAC opportunities."""
    land=(p["land"]+" "+p["zone"]+" "+" ".join(p.get("fcodes",[]))).upper()
    largest=p.get("largest");avg=p.get("avg");count=p.get("count",0)
    residential=any(k in land for k in ("SINGLE FAMILY","DUPLEX","MULTI FAMILY","MULTIFAMILY","APART","CONDO"))
    poor_use=any(k in land for k in ("RESTAUR","RETAIL","SHOPPING","STORE"))
    priority=any(k in land for k in ("HOSP","MEDICAL","UNIVERS","COLLEGE","INDUSTR","MANUFACTUR","UTILITY",
                                     "PUMP STATION","SUBSTATION","GOVERN","SCHOOL","PUBLIC/SEMI PUBLIC","MILITARY",
                                     "WAREHOUSE","DISTRIBUT"))
    many_small=count>=10 and avg and avg<10000

    if residential:return False,"RESIDENTIAL"
    if many_small and not priority:return False,"MANY SMALL"
    if largest is None:return False,"NO FOOTPRINT"
    if largest>=max(mn,20000):return True,"SIZE"
    if priority and largest>=2500:return True,"PRIORITY EXCEPTION"
    if not poor_use and largest>=10000:return True,"COMMERCIAL SIZE"
    return False,"FILTERED"

def discover(x,y,mi,mn):
    ps=load_parcels(x,y,mi);assign_facility_names(ps,load_osm_names(x,y,mi));bs,bsource,berrors=load_buildings(x,y,mi)
    joined=0
    for b in bs:
        hits=[p for p in ps if pinpoly(b["lon"],b["lat"],p["rings"])]
        if hits:
            min(hits,key=lambda p:p["psq"] or 1e99).setdefault("bs",[]).append(b);joined+=1
    rows=[]
    for p in ps:
        bl=p.get("bs",[]);largest=max((b["sq"] for b in bl),default=None)
        total=sum(b["sq"] for b in bl) if bl else None;count=len(bl);avg=round(total/count) if count else None
        fcodes=sorted(set(b["fcode"] for b in bl if b["fcode"]))
        land=(p["land"]+" "+p["zone"]).upper()
        if any(k in land for k in ("SINGLE FAMILY","DUPLEX")):continue
        p.update(largest=largest,total=total,count=count,avg=avg,fcodes=fcodes,buildings=bl,
                 distance=round(miles(x,y,p["lon"],p["lat"]),2))
        p["tier"],p["score"]=classify(p["land"],p["zone"],largest,avg,count,fcodes)
        p["pre"],p["pre_reason"]=prescreen(p,mn)
        p["source"]=bsource if bl else "FOOTPRINT MISSING"
        rows.append(p)
    ded={}
    for p in rows:
        k=p["gpin"] or "A:"+p["address"].upper().strip()
        if k not in ded or p["score"]>ded[k]["score"]:ded[k]=p
    out=list(ded.values())
    out.sort(key=lambda z:(0 if z["pre"] else 1,-z["score"],-(z["largest"] or 0),z["distance"]))
    return out[:250],len(ps),len(bs),joined,bsource,berrors


def aerial(x,y,sf,out):
    side=max(650,min(1800,math.sqrt(max(sf or 30000,1))*3.2));h=side*.3048/2;R=6378137
    X=R*math.radians(x);Y=R*math.log(math.tan(math.pi/4+math.radians(y)/2))
    q=urllib.parse.urlencode({"f":"image","bbox":f"{X-h},{Y-h},{X+h},{Y+h}","bboxSR":"3857",
                              "imageSR":"3857","size":"1800,1800","format":"jpg"})
    with urllib.request.urlopen(AERIAL+"?"+q,timeout=120) as r:Path(out).write_bytes(r.read())


def aerial_side(x,y,side_ft,out,pixels=1800):
    side=max(250,min(2400,float(side_ft)));h=side*.3048/2;R=6378137
    X=R*math.radians(x);Y=R*math.log(math.tan(math.pi/4+math.radians(y)/2))
    q=urllib.parse.urlencode({"f":"image","bbox":f"{X-h},{Y-h},{X+h},{Y+h}","bboxSR":"3857","imageSR":"3857","size":f"{pixels},{pixels}","format":"jpg"})
    with urllib.request.urlopen(AERIAL+"?"+q,timeout=120) as r:Path(out).write_bytes(r.read())

def meaningful_buildings(z,maxn=6):
    """Buildings worth an independent 11-call Deep Vision inspection.
    Accessory footprints should not consume budget or dilute a real process building.
    """
    bs=sorted(z.get("buildings",[]),key=lambda b:b.get("sq",0),reverse=True)
    if not bs:return []
    largest=z.get("largest") or bs[0].get("sq",0) or 0
    # Absolute accessory floor plus a modest relative floor for very large campuses.
    floor=max(2500,min(6000,largest*0.03))
    keep=[b for b in bs if b.get("sq",0)>=floor]
    # Always retain the largest physical building if footprint data exists.
    if not keep and bs:keep=[bs[0]]
    return keep[:maxn]

def campus_images(z,root):
    root=Path(root);root.mkdir(parents=True,exist_ok=True);bs=meaningful_buildings(z);paths=[]
    if bs:
        lon=sum(b["lon"] for b in bs)/len(bs);lat=sum(b["lat"] for b in bs)/len(bs)
        span=max([math.hypot((b["lon"]-lon)*69.172*math.cos(math.radians(lat)),(b["lat"]-lat)*69)*5280 for b in bs]+[0])
        side=max(700,min(2400,span*2.6+350))
    else:lon,lat,side=z["lon"],z["lat"],max(700,math.sqrt(max(z.get("largest") or 30000,1))*3.2)
    q=root/"00_CAMPUS_OVERVIEW.jpg";aerial_side(lon,lat,side,q);paths.append(("CAMPUS OVERVIEW",str(q),None))
    for i,b in enumerate(bs,1):
        side=max(420,min(1100,math.sqrt(max(b.get("sq") or 3000,1))*3.4))
        q=root/f"B{i:02d}_{int(b.get('sq',0))}sf.jpg";aerial_side(b["lon"],b["lat"],side,q)
        paths.append((f"BUILDING {i} — {int(b.get('sq',0)):,} ft2",str(q),b))
    return paths

# ---------------- Deep Vision v0.6.6 Connection Tracing engine ----------------
from PIL import Image
from openai import OpenAI
MODEL="gpt-5.4-mini"
OBS={"type":"object","additionalProperties":False,"properties":{k:{"type":"object","additionalProperties":False,
"properties":{"status":{"type":"string","enum":["strong","probable","possible","not_observed"]},
"quantity":{"type":"string","enum":["none","one","few","several","many","unknown"]},
"confidence":{"type":"integer"},"evidence":{"type":"string"}},
"required":["status","quantity","confidence","evidence"]} for k in
["cooling_towers","air_cooled_chillers","large_packaged_hvac","small_packaged_hvac","condensers","piping","mechanical_yard"]},
"required":["cooling_towers","air_cooled_chillers","large_packaged_hvac","small_packaged_hvac","condensers","piping","mechanical_yard"]}
FINAL={"type":"object","additionalProperties":False,"properties":{
"class":{"type":"string","enum":["GOOD","MAYBE","POOR"]},"score":{"type":"integer"},"confidence":{"type":"integer"},
"cooling_towers":{"type":"string"},"air_cooled_chillers":{"type":"string"},"large_packaged_hvac":{"type":"string"},
"small_packaged_hvac":{"type":"string"},"piping":{"type":"string"},"central_system_evidence":{"type":"string"},
"ambiguities":{"type":"array","items":{"type":"string"}},"summary":{"type":"string"}},
"required":["class","score","confidence","cooling_towers","air_cooled_chillers","large_packaged_hvac","small_packaged_hvac",
"piping","central_system_evidence","ambiguities","summary"]}

IP="""BLIND COMMERCIAL HVAC FORENSIC AERIAL INSPECTION. Inspect ALL visible roof AND ground/perimeter areas.

Identify candidate equipment AND trace visible piping to discriminate equipment types.

HYDRONIC / PROCESS-WATER PIPING uses WEIGHTED evidence. Valves/flanges are NOT required. Strong clues include:
- substantial diameter relative to condensate/drain piping;
- paired supply/return-style runs;
- multiple 90-degree turns or complex purposeful routing;
- elevation changes/supports;
- direct equipment-to-building or equipment-to-penthouse termination;
- insulation;
- valves, flanges, headers, strainers, gauges, pumps and fittings WHEN visible.
White pipe is not automatically PVC. Large insulated white piping can be hydronic/process-water piping.

CONDENSATE / DX:
- A small PVC condensate drain is POSITIVE evidence for direct-expansion packaged HVAC and AGAINST interpreting that unit as an air-cooled water chiller.
- Condensate drainage is generally small and comparatively simple/gravity-routed.
- Do not confuse a drain with a substantial paired circuit having multiple turns and purposeful routing.

CONNECTION TRACING:
- Whenever credible substantial or complex piping is visible, trace it in BOTH directions as far as the view permits.
- Determine whether it appears equipment-to-building, equipment-to-penthouse, equipment-to-equipment, or unresolved.
- If piping reaches an ambiguous fan-topped object, RECONSIDER that object's identity using the connection.
- Strong equipment-to-building paired water piping can support a chiller/process-cooling interpretation even when valves/flanges are indoors or obscured.

AIR-COOLED / PROCESS CHILLERS — PROSPECTING STANDARD:
- This is a SALES-PROSPECT screen, not a requirement to prove equipment identity beyond doubt.
- Strong chiller morphology is independently valuable evidence even when water piping cannot be traced from aerial imagery.
- Look for large ground/pad-mounted or perimeter equipment with a long rectangular chassis, repeated axial condenser-fan array, finned heat-exchanger sections, substantial overall scale, and placement beside a commercial/institutional/process building.
- A large multi-fan machine that is strongly consistent with an air-cooled chiller should be preserved as PROBABLE/POSSIBLE high-value equipment even if its hydronic connections disappear indoors, underground, under insulation, or are below image resolution.
- Hydronic/process-water piping remains powerful corroboration and should raise confidence substantially when visible, but it is NOT a mandatory gate for a promising chiller-like machine.
- Distinguish against ordinary condenser banks, VRF arrays, and packaged RTUs using scale, single-machine chassis continuity, fan-array organization, finned sections, pad/perimeter placement, roof-curb/duct evidence, and visible connections.
- Process chillers may look different from typical comfort-cooling chillers; morphology and connection evidence should be combined rather than requiring either one alone.

PACKAGED RTU / AHU:
- Favor packaged DX when cabinet/curb/duct morphology is present, especially with a small condensate drain and no substantial water circuit.
- Do not classify prominent exhaust, make-up-air, kitchen-hood, or ventilation equipment as a large RTU solely because it is physically large.

COOLING TOWERS / HEAT REJECTION:
- Search for conventional towers AND screened, partly enclosed, low-profile, closed-circuit, evaporative, induced-draft, and process heat-rejection equipment.
- Do not require a visible plume.
- Atypical fan-array/tower morphology PLUS substantial condenser/process-water piping is meaningful combined evidence.
- If credible large water piping terminates at a tower-like/fan-array object, raise heat-rejection probability even if the form factor is unfamiliar.

CENTRAL SYSTEM CAUTION:
- Mechanical complexity alone does NOT establish a central plant.
- Generic conduit, roof drains, seams, rails, shadows, gas piping, or isolated lines do NOT establish hydronic piping.
- Conversely, do not reject a central system merely because valves/flanges are not visible when pipe size, pairing, routing geometry, and termination strongly support a pumped water circuit.

Do not infer address, occupant, company, or building type. Use not_observed rather than claiming absence from one crop. Use quantity bands, not exact counts. Preserve plausible high-value equipment for synthesis."""

SP="""Synthesize the independent overlapping observations from ONE property and deduplicate them. Use HVAC forensic CONNECTION EVIDENCE.

WEIGHTED PIPING RULE:
Do NOT require visible valves/flanges for hydronic/process-water piping. Strong evidence can arise from substantial diameter + paired runs + multiple 90-degree turns/complex routing + direct equipment-to-building/penthouse termination. Insulation, valves, flanges, headers, pumps and fittings strengthen the conclusion but are not mandatory. White pipe is not automatically PVC.

DX RULE:
Small simple PVC condensate drainage is positive DX evidence and MUST NOT create central-plant evidence. Large paired complex routed piping is fundamentally different.

MORPHOLOGY + CONNECTIONS BEFORE CLASSIFYING:
- Evaluate high-value equipment using TWO independent evidence channels: (A) equipment morphology/scale/location and (B) connection/piping evidence.
- Strong evidence from BOTH channels gives high confidence.
- Strong chiller-like morphology alone can still justify a GOOD or upper-MAYBE SALES PROSPECT when piping is hidden, buried, indoors, obscured, or below image resolution.
- Strong traceable hydronic/process-water connections can likewise elevate an ambiguous machine.
- If any crop reports credible substantial or complex piping, use the reported endpoints and geometry to reconsider connected equipment.
- Large fan-topped equipment connected by a substantial paired routed circuit to a building/penthouse may be an air-cooled or process chiller despite atypical morphology.
- Tower-like/fan-array equipment connected to substantial condenser/process-water piping may be cooling-tower/heat-rejection equipment even if screened, low-profile, enclosed, or nonstandard.
- Do not collapse a visually compelling large chiller candidate to ordinary packaged DX solely because the water circuit cannot be proven from overhead imagery.

PACKAGED DX CHECK:
Favor packaged RTU/AHU when cabinet/curb/duct evidence exists AND no substantial water circuit connects to the unit. A small condensate drain supports DX. Mechanical complexity alone does NOT establish a central plant.

SCORING — SALES-PROSPECT OBJECTIVE:
- Score whether a salesperson should investigate the property, NOT whether the aerial image proves a complete central-plant schematic.
- Confirmed/probable chiller, cooling tower, or strong traceable pumped central/process-water circuit should materially raise prospect score.
- A visually compelling LARGE air-cooled/process-chiller candidate may independently support GOOD/upper-MAYBE even without confirmed piping, because human review is the intended next step.
- Strong morphology + strong connection evidence should score higher than morphology alone.
- A credible unresolved large chiller/tower candidate with strong connection evidence should generally keep the property GOOD or upper-MAYBE for human review.
- Genuinely large packaged RTUs can be worthwhile.
- Numerous small packaged units alone are weak.
- Not_observed is not proof of absence.

In central_system_evidence and summary, explicitly explain the evidence chain, for example: substantial paired piping + multiple routed turns + equipment-to-building termination -> probable pumped hydronic/process-water circuit. Do not infer property identity or building type."""

def dv_url(p):
    return "data:image/jpeg;base64,"+base64.b64encode(Path(p).read_bytes()).decode()
def dv_ask(c,prompt,content,schema,name,tok=5000,effort="low"):
    last=None
    for attempt in range(2):
        budget=tok if attempt==0 else max(tok,8000)
        r=c.responses.create(model=MODEL,reasoning={"effort":effort},
          input=[{"role":"user","content":[{"type":"input_text","text":prompt}]+content}],
          text={"format":{"type":"json_schema","name":name,"strict":True,"schema":schema},"verbosity":"low"},
          max_output_tokens=budget)
        last=r
        if r.status=="completed" and (r.output_text or "").strip():return json.loads(r.output_text),r
        reason=getattr(getattr(r,"incomplete_details",None),"reason",None)
        if attempt==0 and reason=="max_output_tokens":continue
        raise RuntimeError(f"response {r.status}: {getattr(r,'incomplete_details',None)}")
    raise RuntimeError(f"No usable response: {getattr(last,'status',None)}")
def dv_crops(path):
    im=Image.open(path).convert("RGB");w,h=im.size
    d=Path(tempfile.gettempdir())/("hvac_dv_"+Path(path).stem);d.mkdir(exist_ok=True)
    out=[("overview",str(path))];tw,th=int(w*.5),int(h*.5);n=0
    for cy in (.25,.5,.75):
        for cx in (.25,.5,.75):
            x=max(0,min(w-tw,int(w*cx-tw/2)));y=max(0,min(h-th,int(h*cy-th/2)));n+=1
            p=d/f"crop_{n}.jpg";im.crop((x,y,x+tw,y+th)).save(p,quality=96)
            out.append((f"crop {n}",str(p)))
    return out

STATUS_RANK={"not_observed":0,"possible":1,"probable":2,"strong":3}

def _best_signal(obs, field):
    """Return strongest repeated visual signal for one equipment family."""
    hits=[]
    for item in obs:
        try:
            d=item["observations"][field]
            st=d.get("status","not_observed")
            cf=int(d.get("confidence",0) or 0)
            if st!="not_observed":
                hits.append((STATUS_RANK.get(st,0),cf,item.get("view",""),d.get("evidence","")))
        except Exception:
            pass
    hits.sort(reverse=True)
    if not hits:
        return {"status":"not_observed","confidence":0,"views":0,"best_view":"","evidence":""}
    rank,conf,view,evidence=hits[0]
    status={1:"possible",2:"probable",3:"strong"}.get(rank,"not_observed")
    return {"status":status,"confidence":conf,"views":len(hits),"best_view":view,"evidence":evidence}

def deterministic_sales_score(obs, model_result):
    """
    v0.9.8 conservative deterministic scoring.

    912 Birdneck is the positive control: a genuinely large, multi-fan,
    ground-mounted chiller candidate must be able to surface even when piping
    cannot be proven.

    589 Birdneck is the negative control: an ordinary small side-mounted
    packaged unit / weak large-equipment hallucination must NOT become GOOD.

    Core rule: weak morphology alone can request REVIEW, but cannot create GOOD.
    """
    ch=_best_signal(obs,"air_cooled_chillers")
    tw=_best_signal(obs,"cooling_towers")
    pp=_best_signal(obs,"piping")
    lg=_best_signal(obs,"large_packaged_hvac")
    my=_best_signal(obs,"mechanical_yard")

    raw=int(model_result.get("score",0) or 0)
    floors=[]
    reasons=[]

    def corroborated(sig):
        # Independent visual corroboration. Absence never subtracts.
        return (
            pp["status"] in ("probable","strong") or
            my["status"] in ("probable","strong")
        )

    def high_value_floor(sig,name):
        st,cf,n=sig["status"],sig["confidence"],sig["views"]
        cor=corroborated(sig)

        if st=="strong":
            # Strong high-value equipment can stand on morphology alone.
            val=78
            if cf>=80: val=84
            if n>=2: val+=4
            floors.append(min(94,val))
            reasons.append(f"{name} strong {cf}% in {n} view(s)")
            return

        if st=="probable":
            # One probable view is review-worthy, not automatically GOOD.
            # Multiple views or independent process/hydronic-yard evidence
            # are required for a GOOD deterministic floor.
            if n>=2 or cor:
                val=68
                if cf>=70: val+=5
                if n>=3: val+=4
            else:
                val=58 if cf>=60 else 54
            floors.append(min(90,val))
            reasons.append(
                f"{name} probable {cf}% in {n} view(s)"
                + (" with corroboration" if cor else "")
            )
            return

        if st=="possible":
            # This is the key 589 safeguard. "Possible" is never enough to
            # manufacture GOOD. Repetition/corroboration can only create MAYBE.
            if n>=3 and cor:
                val=58
            elif n>=2 or cor:
                val=52
            else:
                val=0
            if val:
                floors.append(val)
                reasons.append(
                    f"{name} possible {cf}% in {n} view(s)"
                    + (" with corroboration" if cor else "")
                )

    high_value_floor(ch,"air-cooled/process chiller")
    high_value_floor(tw,"cooling tower/heat rejection")

    # Piping is independently useful, but weak piping is not a substitute
    # for actual high-value equipment.
    if pp["status"]=="strong":
        floors.append(70)
        reasons.append(f"piping strong {pp['confidence']}%")
    elif pp["status"]=="probable":
        floors.append(60)
        reasons.append(f"piping probable {pp['confidence']}%")

    # Large packaged HVAC alone is a MAYBE signal. Never create GOOD.
    if lg["status"]=="strong":
        floors.append(58)
        reasons.append(f"large packaged HVAC strong {lg['confidence']}%")
    elif lg["status"]=="probable":
        floors.append(52)
        reasons.append(f"large packaged HVAC probable {lg['confidence']}%")
    elif lg["status"]=="possible" and lg["views"]>=3:
        floors.append(46)
        reasons.append(f"large packaged HVAC possible across {lg['views']} views")

    # Multiple INDEPENDENT high-value channels can strengthen the floor.
    # Do not count packaged HVAC here.
    independent=sum(
        1 for s in (ch,tw,pp)
        if s["status"] in ("probable","strong")
    )
    floor=max(floors) if floors else 0
    if independent>=2 and floor>=60:
        floor=min(94,floor+5)

    # Deterministic logic is a floor, not a penalty. It cannot lower GPT.
    final=max(raw,floor)
    cls="GOOD" if final>=65 else "MAYBE" if final>=40 else "POOR"

    return final,cls,{
        "model_score":raw,
        "rule_floor":floor,
        "air_cooled_chiller":ch,
        "cooling_tower":tw,
        "piping":pp,
        "large_packaged_hvac":lg,
        "mechanical_yard":my,
        "reasons":reasons
    }


def deep_run_building(c,path,label,progress):
    views=dv_crops(path);obs=[];use=[0,0]
    for i,(vlabel,p) in enumerate(views):
        progress(f"{label}: {vlabel} {i+1}/10")
        x,r=dv_ask(c,IP,[{"type":"input_image","image_url":dv_url(p),"detail":"high"}],OBS,"crop_inspection")
        obs.append({"view":vlabel,"observations":x})
        try:use[0]+=r.usage.input_tokens;use[1]+=r.usage.output_tokens
        except:pass
    progress(f"{label}: synthesizing")
    x,r=dv_ask(c,SP,[{"type":"input_text","text":json.dumps(obs,separators=(",",":"))}],FINAL,"property_synthesis",6000,"medium")
    try:use[0]+=r.usage.input_tokens;use[1]+=r.usage.output_tokens
    except:pass

    # v0.9.8: GPT performs equipment recognition; deterministic business rules
    # establish the minimum sales-prospect score. This prevents "no visible
    # water loop" from vetoing a credible large chiller/tower anomaly.
    sales_score,sales_class,sales_trace=deterministic_sales_score(obs,x)
    x["model_score"]=int(x.get("score",0) or 0)
    x["model_class"]=x.get("class","POOR")
    x["score"]=sales_score
    x["class"]=sales_class
    x["sales_trace"]=sales_trace
    if sales_trace["rule_floor"] > sales_trace["model_score"]:
        why="; ".join(sales_trace["reasons"][:3])
        x["summary"]=f'{x.get("summary","")} SALES RULE FLOOR {sales_trace["rule_floor"]}: {why}.'
    return x,obs,use

CAMPUS_FINAL={"type":"object","additionalProperties":False,"properties":{"class":{"type":"string","enum":["GOOD","MAYBE","POOR"]},"score":{"type":"integer"},"confidence":{"type":"integer"},"best_building":{"type":"integer"},"high_value_buildings":{"type":"array","items":{"type":"integer"}},"key_evidence":{"type":"string"},"summary":{"type":"string"}},"required":["class","score","confidence","best_building","high_value_buildings","key_evidence","summary"]}
CAMPUS_PROMPT="""Synthesize building-level commercial HVAC inspections for ONE campus/property. The sales opportunity is the CAMPUS, not an average building.
Each physical building was independently analyzed by the frozen v0.6.6 Connection-Tracing engine.

NON-DILUTION RULE — MANDATORY:
- Anchor the campus to the BEST physical-building opportunity.
- A POOR or mediocre building can NEVER reduce/dilute the score or class earned by a stronger building.
- Additional MAYBE/GOOD buildings may INCREASE the campus opportunity because they add service scope.
- One GOOD physical building means the campus is GOOD.
- Think MAXIMUM + POSITIVE ADDITIONS, never averaging.

Building 0 is campus-overview context only and is NOT a physical building. It may add corroborating evidence but may not lower the campus.
Accessory/support structures should not influence the opportunity merely because they are ordinary.
Return the physical building number carrying the strongest opportunity and identify other high-value buildings when present.
Favor recall for high-value central/process HVAC."""

def deep_run_campus(key,z,root,progress):
    c=OpenAI(api_key=key,timeout=240);imgs=campus_images(z,root);results=[];use=[0,0];errors=[]
    # One inexpensive campus-wide context call helps catch detached mechanical equipment / inter-building infrastructure.
    try:
        progress("Campus overview context...")
        ov,r=dv_ask(c,IP,[{"type":"input_image","image_url":dv_url(imgs[0][1]),"detail":"high"}],OBS,"campus_overview")
        results.append({"building":0,"sqft":None,"result":{"class":"MAYBE","score":50,"confidence":50,"cooling_towers":json.dumps(ov["cooling_towers"]),"air_cooled_chillers":json.dumps(ov["air_cooled_chillers"]),"large_packaged_hvac":json.dumps(ov["large_packaged_hvac"]),"small_packaged_hvac":json.dumps(ov["small_packaged_hvac"]),"piping":json.dumps(ov["piping"]),"central_system_evidence":json.dumps(ov["mechanical_yard"]),"ambiguities":[],"summary":"Campus overview context only."}})
        try:use[0]+=r.usage.input_tokens;use[1]+=r.usage.output_tokens
        except:pass
    except Exception as e:errors.append(f"Campus overview: {type(e).__name__}: {e}")
    for n,(label,path,b) in enumerate(imgs[1:],1):
        try:
            r,obs,u=deep_run_building(c,path,f"Building {n}/{len(imgs)-1}",progress)
            results.append({"building":n,"sqft":b.get("sq"),"result":r});use[0]+=u[0];use[1]+=u[1]
        except Exception as e:errors.append(f"Building {n}: {type(e).__name__}: {e}")
    if not results:raise RuntimeError("All building analyses failed: "+" | ".join(errors))
    progress("Campus synthesis...")
    final,r=dv_ask(c,CAMPUS_PROMPT,[{"type":"input_text","text":json.dumps(results,separators=(",",":"))}],CAMPUS_FINAL,"campus_synthesis",5000,"medium")
    try:use[0]+=r.usage.input_tokens;use[1]+=r.usage.output_tokens
    except:pass

    # Hard business rule: weak buildings never dilute the strongest physical-building opportunity.
    physical=[x for x in results if x.get("building",0)>0 and isinstance(x.get("result"),dict)]
    if physical:
        best=max(physical,key=lambda x:int(x["result"].get("score",0) or 0))
        best_score=int(best["result"].get("score",0) or 0)
        best_class=best["result"].get("class","POOR")
        rank={"POOR":0,"MAYBE":1,"GOOD":2}
        final["score"]=max(int(final.get("score",0) or 0),best_score)
        if rank.get(best_class,0)>rank.get(final.get("class","POOR"),0):
            final["class"]=best_class
        final["best_building"]=best["building"]
        # Other non-poor physical buildings are positive scope, never negative evidence.
        positive=[x["building"] for x in physical if x["result"].get("class") in ("GOOD","MAYBE")]
        final["high_value_buildings"]=sorted(set(final.get("high_value_buildings",[])+positive))
    return final,results,use,errors,imgs

class App:
    def __init__(self,r):
        self.r=r;self.rows=[];r.title("HVAC Territory Discovery v0.9.8 — Calibrated Sales Scoring");r.geometry("1600x880")
        t=ttk.Frame(r,padding=10);t.pack(fill="x")
        ttk.Label(t,text="Virginia Beach test center:").grid(row=0,column=0)
        self.q=tk.StringVar(value="717 General Booth Blvd");ttk.Entry(t,textvariable=self.q,width=36).grid(row=0,column=1,padx=5)
        ttk.Label(t,text="Radius mi:").grid(row=0,column=2);self.rad=tk.StringVar(value="1.0");ttk.Entry(t,textvariable=self.rad,width=6).grid(row=0,column=3)
        ttk.Label(t,text="Size threshold ft²:").grid(row=0,column=4);self.mn=tk.StringVar(value="10000");ttk.Entry(t,textvariable=self.mn,width=8).grid(row=0,column=5)
        self.b=ttk.Button(t,text="Discover + Prescreen",command=self.start);self.b.grid(row=0,column=6,padx=8)
        ttk.Label(t,text="OpenAI key:").grid(row=0,column=7);self.key=tk.StringVar()
        ttk.Entry(t,textvariable=self.key,width=22,show="*").grid(row=0,column=8,padx=4)
        self.st=tk.StringVar(value="Non-vision prescreen first. Deep Vision only on shortlisted candidates.")
        ttk.Label(r,textvariable=self.st).pack(fill="x",padx=10)
        cs=("rank","facility","address","largest","avg","bldgs","inspect","miles","land","tier","pre","reason","gis","deep","dvscore","source")
        self.tree=ttk.Treeview(r,columns=cs,show="headings")
        widths=(45,210,190,80,75,50,55,55,160,65,55,120,50,65,60,90)
        for c,w in zip(cs,widths):
            self.tree.heading(c,text=c.upper());self.tree.column(c,width=w,anchor="w")
        self.tree.pack(fill="both",expand=True,padx=10,pady=8)
        f=ttk.Frame(r,padding=10);f.pack(fill="x")
        ttk.Button(f,text="Download Aerial",command=self.dl).pack(side="left")
        ttk.Button(f,text="Save Campus Images",command=self.save_campus).pack(side="left",padx=8)
        ttk.Button(f,text="Deep Analyze Selected",command=self.deep_selected).pack(side="left",padx=8)
        ttk.Button(f,text="Deep Analyze Top 10",command=lambda:self.deep_batch(10)).pack(side="left",padx=8)
        ttk.Button(f,text="Deep Analyze Top 25",command=lambda:self.deep_batch(25)).pack(side="left",padx=8)
        ttk.Button(f,text="Copy Address",command=self.copy).pack(side="left",padx=8)

    def start(self):
        self.b.config(state="disabled");self.st.set("Querying GIS and applying non-vision prescreen...")
        threading.Thread(target=self.work,daemon=True).start()
    def work(self):
        try:
            x,y=geocode(self.q.get().strip());mn=float(self.mn.get())
            self.rows,np,nb,nj,src,errs=discover(x,y,float(self.rad.get()),mn)
            self.diag=(np,nb,nj,src,errs);self.r.after(0,self.show)
        except Exception as e:self.r.after(0,lambda e=e:self.fail(e))
    def rowvals(self,n,z):
        fmt=lambda v:f"{v:,}" if v is not None else "UNKNOWN"
        return (n,z.get("facility","") or "",z["address"],fmt(z["largest"]),fmt(z["avg"]),z["count"],len(meaningful_buildings(z)),z["distance"],z["land"],z["tier"],
                "YES" if z["pre"] else "NO",z["pre_reason"],z["score"],z.get("deep_class",""),z.get("deep_score",""),z["source"])
    def show(self):
        for i in self.tree.get_children():self.tree.delete(i)
        for n,z in enumerate(self.rows,1):self.tree.insert("","end",iid=str(n-1),values=self.rowvals(n,z))
        pre=sum(z["pre"] for z in self.rows);np,nb,nj,src,errs=self.diag
        warn=(" | fallback: "+errs[0][:70]) if errs and src!="VB CITY" else ""
        self.st.set(f"{len(self.rows)} discovered | {pre} pass prescreen | parcels {np} | footprints {nb} | joined {nj} | {src}{warn}")
        self.b.config(state="normal")
    def fail(self,e):self.st.set("Failed: "+repr(e));self.b.config(state="normal")
    def selidx(self):
        s=self.tree.selection()
        if not s:messagebox.showinfo("Select","Select a candidate.");return None
        return int(s[0])
    def dl(self):
        i=self.selidx()
        if i is None:return
        z=self.rows[i];out=Path.home()/"Downloads"/f'HVAC_{z["address"].replace(" ","_") or "candidate"}.jpg'
        self.st.set("Downloading aerial...")
        def w():
            try:aerial(z["lon"],z["lat"],z["largest"],out);self.r.after(0,lambda:self.st.set("Saved "+str(out)))
            except Exception as e:self.r.after(0,lambda:self.st.set("Download failed: "+repr(e)))
        threading.Thread(target=w,daemon=True).start()
    def save_campus(self):
        i=self.selidx()
        if i is None:return
        z=self.rows[i];safe="".join(c if c.isalnum() or c in "-_" else "_" for c in (z["address"] or "candidate"));out=Path.home()/"Downloads"/f"HVAC_CAMPUS_{safe}"
        self.st.set("Generating campus/building inspection images...")
        def w():
            try:
                imgs=campus_images(z,out);(out/"README.txt").write_text("Campus-aware inspection set. 00 is campus overview. Each B image is centered on one meaningful associated building and includes perimeter.\n\n"+"\n".join(f"{label}: {Path(p).name}" for label,p,_ in imgs))
                self.r.after(0,lambda:self.st.set(f"Saved {len(imgs)} campus images to {out}"))
            except Exception as e:self.r.after(0,lambda e=e:self.st.set("Save campus images failed: "+repr(e)))
        threading.Thread(target=w,daemon=True).start()
    def getkey(self):
        k=self.key.get().strip()
        if not k:messagebox.showinfo("OpenAI key","Paste your OpenAI API key first.");return None
        return k
    def run_deep_one(self,i,k,batchpos=None,total=None):
        z=self.rows[i];safe="".join(c if c.isalnum() or c in "-_" else "_" for c in (z["address"] or str(i)));root=Path(tempfile.gettempdir())/f"hvac_campus_{safe}_{abs(hash((z['lon'],z['lat'])))}"
        def prog(x):
            prefix=f"[{batchpos}/{total}] " if batchpos else "";self.r.after(0,lambda:self.st.set(prefix+x+" — "+(z.get("facility") or z["address"] or "candidate")))
        result,buildings,use,errs,imgs=deep_run_campus(k,z,root,prog)
        z["deep_class"]=result["class"];z["deep_score"]=result["score"];z["deep_conf"]=result["confidence"];z["deep_summary"]=result["summary"];z["deep_result"]=result;z["building_results"]=buildings;z["tokens"]=sum(use);z["deep_errors"]=errs;z["best_building"]=result["best_building"]
        parts=[]
        for br in buildings:
            if br.get("building",0)>0:
                rr=br.get("result",{})
                ms=rr.get("model_score")
                rf=(rr.get("sales_trace") or {}).get("rule_floor")
                extra=f" [model {ms}, rule {rf}]" if ms is not None else ""
                parts.append(f'B{br["building"]}: {rr.get("class","?")} {rr.get("score","?")}{extra}')
        z["building_score_trace"]=" | ".join(parts)
    def refresh(self):
        self.rows.sort(key=lambda z:(0 if z.get("deep_class")=="GOOD" else 1 if z.get("deep_class")=="MAYBE" else 2 if z.get("deep_class")=="POOR" else 3,
                                     -z.get("deep_score",0),0 if z["pre"] else 1,-z["score"],-(z["largest"] or 0)))
        for x in self.tree.get_children():self.tree.delete(x)
        for n,z in enumerate(self.rows,1):self.tree.insert("","end",iid=str(n-1),values=self.rowvals(n,z))
    def deep_selected(self):
        k=self.getkey();i=self.selidx()
        if not k or i is None:return
        self.st.set("Starting Deep Vision...")
        def w():
            try:
                self.run_deep_one(i,k);z=self.rows[i]
                self.r.after(0,self.refresh)
                self.r.after(0,lambda:self.st.set(f'{z["address"]}: {z["deep_class"]} {z["deep_score"]}/100 — {z.get("building_score_trace","")} — {z["deep_summary"]} | {z["tokens"]:,} tokens'))
            except Exception as e:self.r.after(0,lambda e=e:self.st.set("Deep Vision failed: "+repr(e)))
        threading.Thread(target=w,daemon=True).start()
    def deep_batch(self,n):
        k=self.getkey()
        if not k:return
        ids=[i for i,z in enumerate(self.rows) if z["pre"] and not z.get("deep_class")][:n]
        if not ids:messagebox.showinfo("Deep Vision","No unscreened prescreen candidates.");return
        self.st.set(f"Deep Vision batch starting: {len(ids)} candidates...")
        def w():
            errors=[]
            for pos,i in enumerate(ids,1):
                try:self.run_deep_one(i,k,pos,len(ids))
                except Exception as e:
                    msg=f"{self.rows[i]['address']}: {type(e).__name__}: {e}";self.rows[i]["deep_error"]=msg;errors.append(msg)
            self.r.after(0,self.refresh)
            if errors:
                log=Path.home()/"Downloads"/"HVAC_v091_batch_errors.txt";log.write_text("\n".join(errors))
                self.r.after(0,lambda:self.st.set(f"Campus Deep Vision complete: {len(ids)-len(errors)} analyzed, {len(errors)} errors. Log: {log}"))
            else:self.r.after(0,lambda:self.st.set(f"Campus Deep Vision complete: {len(ids)} analyzed, 0 errors."))
        threading.Thread(target=w,daemon=True).start()
    def copy(self):
        i=self.selidx()
        if i is not None:
            z=self.rows[i];self.r.clipboard_clear();self.r.clipboard_append(z["address"]);self.st.set("Address copied.")

r=tk.Tk();App(r);r.mainloop()
