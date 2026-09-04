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
    req=urllib.request.Request(u+"?"+q,headers={"User-Agent":"HVAC-Territory/0.9.3"})
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
    bs=sorted(z.get("buildings",[]),key=lambda b:b.get("sq",0),reverse=True)
    if not bs:return []
    floor=max(1800,min(6000,(z.get("largest") or 6000)*0.04))
    keep=[b for b in bs if b.get("sq",0)>=floor]
    if len(keep)<min(2,len(bs)):keep=bs[:min(2,len(bs))]
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

The prospecting objective is HIGH RECALL for expensive/complex mechanical opportunities. Exact inventory is secondary.

BALANCED HIGH-VALUE SEARCH — evaluate EACH category independently before deciding the site is ordinary:
1. AIR-COOLED CHILLERS / PROCESS CHILLERS
2. COOLING TOWERS / FLUID COOLERS / EVAPORATIVE HEAT REJECTION
3. SUBSTANTIAL HYDRONIC OR PROCESS PIPING
4. LARGE-TONNAGE PACKAGED HVAC
5. MECHANICAL YARDS / CENTRAL-PLANT INFRASTRUCTURE
Do not let strong or weak evidence in one category anchor the inspection of the others. In particular, do not focus on cooling towers at the expense of air-cooled chillers.

AIR-COOLED CHILLER RECOGNITION:
- Deliberately search roof edges, side yards, narrow service alleys, pads immediately beside buildings, and perimeter mechanical areas.
- A large air-cooled chiller can look from above like a long rectangular bank of condensers or a packaged unit. Fan count alone is NOT diagnostic.
- Favor a chiller/process-chiller interpretation when scale is substantial and morphology shows a long integrated machine with multiple axial condenser fans, especially when substantial piping leaves the machine and enters the building.
- Large-diameter paired supply/return piping, insulation, purposeful multiple 90-degree turns, elevation changes/supports, and direct equipment-to-building routing are strong hydronic evidence.
- Visible pumps, valves, flanges and headers are SUPPORTING evidence, not requirements; these components may be indoors.
- White insulated hydronic piping can resemble PVC from aerial imagery. Judge diameter, paired routing, complexity and destination rather than color.
- Do not dismiss a large fan-array machine as ordinary condensers merely because valves/flanges are not visible. Explicitly compare: integrated air-cooled chiller vs condenser bank vs packaged DX/RTU.
- A credible large chiller or process chiller is independently high-value prospecting evidence even if no cooling tower is present.

CONNECTION-TRACING RULES:
- Large fan equipment alone does not prove a chiller. Inspect what connects to it.
- Hydronic/process evidence is WEIGHTED, not gated on visible valves/flanges. Valves and specialties may be indoors.
- Strong evidence can include substantial pipe diameter; paired supply/return; multiple 90-degree turns or complex purposeful routing;
  elevation changes/supports; direct equipment-to-building or penthouse termination; insulation; and, when visible, valves/flanges/headers/pumps.
- Large-diameter piping with several purposeful bends that enters a building can be strong water-system evidence even when valves are not visible.
- White pipe is NOT automatically PVC. Color is not diagnostic.
- Small simple PVC condensate drainage remains positive evidence for packaged DX and against a water chiller interpretation.
- Trace credible piping in BOTH directions and reconsider ambiguous equipment based on what the piping connects.
- Search for conventional cooling towers plus SMALL SINGLE-CELL cooling towers, low-profile/screened towers,
  closed-circuit fluid coolers, evaporative condensers, induced-draft heat rejection, and atypical process chillers.
- A small single-cell cooling tower / fluid cooler may appear from above as a compact square or rectangular outdoor enclosure
  with ONE large axial top fan. Look for louvered/air-intake side structure, a fan opening/shroud, equipment base/enclosure,
  and placement immediately beside a building or process area.
- IMPORTANT: cooling-tower piping may disappear underground almost immediately or enter the building below grade. Lack of
  long visible above-ground piping does NOT rule out a cooling tower or evaporative heat-rejection device.
- Credible cooling-tower / evaporative heat-rejection morphology is independently high-value prospecting evidence. Do NOT
  require visible valves, pumps, long hydronic pipe runs, or a separately visible chiller before treating it as important.
- When a compact one-fan outdoor structure could reasonably be a cooling tower/fluid cooler, explicitly compare that
  interpretation against ordinary exhaust fan, rooftop unit, condenser, dumpster/enclosure, or other non-HVAC alternatives.
  If tower/fluid-cooler morphology is credible, report at least POSSIBLE/PROBABLE rather than dismissing it solely for weak piping visibility.
- Mechanical complexity alone does not establish a central plant.
- Large-tonnage packaged RTUs can still make a property worthwhile, but numerous small RTUs alone are weak.
- Never treat not_observed in one crop as proof of absence. Use quantity bands rather than exact counts.
Do not infer occupant, address, or business identity."""

SP="""Synthesize overlapping observations for ONE property and deduplicate them.
Prioritize the sales question: is there credible visible evidence of high-value central/process HVAC, air-cooled/process chillers, cooling towers/fluid coolers,
substantial hydronic/process piping, mechanical yards, or unusually large packaged equipment?

SYNTHESIZE BALANCED EVIDENCE. Independently review the observations for (a) air-cooled/process chillers, (b) cooling towers/fluid coolers,
(c) hydronic/process piping, (d) large packaged HVAC, and (e) mechanical-yard/central-plant evidence before assigning the class.
Do not require one high-value category to corroborate another: a credible air-cooled chiller can make the building valuable without a cooling tower,
and a credible cooling tower can make it valuable without a separately visible chiller.
For possible air-cooled chillers, explicitly reconsider long rectangular multi-fan equipment beside the building using scale + integrated-machine morphology + connection routing.
Fan count alone is not diagnostic. Substantial paired piping with purposeful bends and building termination strongly supports hydronic service even when valves/flanges are indoors or invisible.

Use connection evidence as a WEIGHTED chain:
substantial diameter + paired runs + multiple purposeful 90-degree turns + building/equipment termination + insulation/supports
can establish strong hydronic/process evidence even without visible valves/flanges. Valves may be indoors.
White pipe is not automatically PVC. Small simple drain routing is DX evidence.
If credible piping exists, trace its reported endpoints and reconsider connected equipment, including atypical process chillers
and nonstandard heat rejection. However, do NOT require visible piping to validate credible cooling-tower morphology: tower piping
can enter the ground or building almost immediately.
A compact single-cell tower/fluid cooler with one large top axial fan, plausible louvered/air-intake enclosure, and appropriate
ground-level placement beside a building is itself important evidence. If multiple crops support that morphology, a building may
be GOOD even when the associated piping is buried or visually obscure.
Do not invent a central plant merely from many RTUs.
Favor recall for prospecting: false negatives on major central/process equipment are worse than small RTU count errors or
chiller-vs-tower ambiguity. Exact tower-vs-chiller/fluid-cooler identity is less important than correctly flagging the property as worth pursuing."""

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
    return x,obs,use

CAMPUS_FINAL={"type":"object","additionalProperties":False,"properties":{"class":{"type":"string","enum":["GOOD","MAYBE","POOR"]},"score":{"type":"integer"},"confidence":{"type":"integer"},"best_building":{"type":"integer"},"high_value_buildings":{"type":"array","items":{"type":"integer"}},"key_evidence":{"type":"string"},"summary":{"type":"string"}},"required":["class","score","confidence","best_building","high_value_buildings","key_evidence","summary"]}
CAMPUS_PROMPT="""Synthesize building-level commercial HVAC inspections for ONE campus/property. The sales opportunity is the CAMPUS, not the mailing-address building.
Use an OPPORTUNITY/MAXIMUM philosophy, not an average: one building with credible high-value mechanical equipment can make the entire campus GOOD even when every other building is ordinary.
Credible cooling-tower / fluid-cooler / evaporative heat-rejection evidence BY ITSELF is a strong sales signal and does not require separately visible chillers, pumps, or long piping. Piping may go underground immediately.
Likewise, credible AIR-COOLED OR PROCESS CHILLERS, substantial hydronic/process piping, mechanical yards, or unusually large equipment can independently make the campus valuable. Do not require a cooling tower for a chiller-based opportunity. Treat chiller evidence and cooling-tower evidence as equal, independent high-value paths.
Do not average away a strong process/utility building because office/admin/support buildings are poor.
Building 0 is campus-overview context and is not a physical building; use it as supporting evidence only.
Return the physical building number(s) carrying the strongest opportunity when identifiable. Favor recall for high-value equipment."""

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
    return final,results,use,errors,imgs

class App:
    def __init__(self,r):
        self.r=r;self.rows=[];r.title("HVAC Territory Discovery v0.9.3 — Balanced High-Value Recognition");r.geometry("1600x880")
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
                self.r.after(0,lambda:self.st.set(f'{z["address"]}: {z["deep_class"]} {z["deep_score"]}/100 — {z["deep_summary"]} | {z["tokens"]:,} tokens'))
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
