import base64,json,math,threading,tkinter as tk,urllib.parse,urllib.request,tempfile
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
    req=urllib.request.Request(u+"?"+q,headers={"User-Agent":"HVAC-Territory/0.9.0"})
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
    ps=load_parcels(x,y,mi);bs,bsource,berrors=load_buildings(x,y,mi)
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

CONNECTION-TRACING RULES:
- Large fan equipment alone does not prove a chiller. Inspect what connects to it.
- Hydronic/process evidence is WEIGHTED, not gated on visible valves/flanges. Valves and specialties may be indoors.
- Strong evidence can include substantial pipe diameter; paired supply/return; multiple 90-degree turns or complex purposeful routing;
  elevation changes/supports; direct equipment-to-building or penthouse termination; insulation; and, when visible, valves/flanges/headers/pumps.
- Large-diameter piping with several purposeful bends that enters a building can be strong water-system evidence even when valves are not visible.
- White pipe is NOT automatically PVC. Color is not diagnostic.
- Small simple PVC condensate drainage remains positive evidence for packaged DX and against a water chiller interpretation.
- Trace credible piping in BOTH directions and reconsider ambiguous equipment based on what the piping connects.
- Search for conventional cooling towers plus low-profile/screened towers, closed-circuit fluid coolers, evaporative condensers,
  induced-draft heat rejection, and atypical process chillers.
- Mechanical complexity alone does not establish a central plant.
- Large-tonnage packaged RTUs can still make a property worthwhile, but numerous small RTUs alone are weak.
- Never treat not_observed in one crop as proof of absence. Use quantity bands rather than exact counts.
Do not infer occupant, address, or business identity."""

SP="""Synthesize overlapping observations for ONE property and deduplicate them.
Prioritize the sales question: is there credible visible evidence of high-value central/process HVAC, cooling towers, chillers,
substantial hydronic/process piping, mechanical yards, or unusually large packaged equipment?

Use connection evidence as a WEIGHTED chain:
substantial diameter + paired runs + multiple purposeful 90-degree turns + building/equipment termination + insulation/supports
can establish strong hydronic/process evidence even without visible valves/flanges. Valves may be indoors.
White pipe is not automatically PVC. Small simple drain routing is DX evidence.
If credible piping exists, trace its reported endpoints and reconsider connected equipment, including atypical process chillers
and nonstandard heat rejection. Do not invent a central plant merely from many RTUs.
Favor recall for prospecting: false negatives on major central/process equipment are worse than small RTU count errors or
chiller-vs-tower ambiguity. Exact tower-vs-chiller identity is less important than correctly flagging the property as worth pursuing."""

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
def deep_run(key,path,progress):
    c=OpenAI(api_key=key,timeout=180);views=dv_crops(path);obs=[];use=[0,0]
    for i,(label,p) in enumerate(views):
        progress(f"Deep Vision: {label} {i+1}/10")
        x,r=dv_ask(c,IP,[{"type":"input_image","image_url":dv_url(p),"detail":"high"}],OBS,"crop_inspection")
        obs.append({"view":label,"observations":x})
        try:use[0]+=r.usage.input_tokens;use[1]+=r.usage.output_tokens
        except:pass
    progress("Deep Vision: synthesizing...")
    x,r=dv_ask(c,SP,[{"type":"input_text","text":json.dumps(obs,separators=(",",":"))}],FINAL,"property_synthesis",6000,"medium")
    try:use[0]+=r.usage.input_tokens;use[1]+=r.usage.output_tokens
    except:pass
    return x,obs,use

class App:
    def __init__(self,r):
        self.r=r;self.rows=[];r.title("HVAC Territory Discovery v0.9.0 — Prescreen + Deep Vision");r.geometry("1600x880")
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
        cs=("rank","address","largest","avg","bldgs","miles","land","tier","pre","reason","gis","deep","dvscore","source")
        self.tree=ttk.Treeview(r,columns=cs,show="headings")
        widths=(45,210,80,75,50,55,175,65,55,120,50,65,60,90)
        for c,w in zip(cs,widths):
            self.tree.heading(c,text=c.upper());self.tree.column(c,width=w,anchor="w")
        self.tree.pack(fill="both",expand=True,padx=10,pady=8)
        f=ttk.Frame(r,padding=10);f.pack(fill="x")
        ttk.Button(f,text="Download Aerial",command=self.dl).pack(side="left")
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
        return (n,z["address"],fmt(z["largest"]),fmt(z["avg"]),z["count"],z["distance"],z["land"],z["tier"],
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
    def getkey(self):
        k=self.key.get().strip()
        if not k:messagebox.showinfo("OpenAI key","Paste your OpenAI API key first.");return None
        return k
    def run_deep_one(self,i,k,batchpos=None,total=None):
        z=self.rows[i]
        tmp=Path(tempfile.gettempdir())/f"hvac_deep_{i}_{abs(hash((z['lon'],z['lat'])))}.jpg"
        aerial(z["lon"],z["lat"],z["largest"],tmp)
        def prog(x):
            prefix=f"[{batchpos}/{total}] " if batchpos else ""
            self.r.after(0,lambda:self.st.set(prefix+x+" — "+(z["address"] or "candidate")))
        result,obs,use=deep_run(k,tmp,prog)
        z["deep_class"]=result["class"];z["deep_score"]=result["score"];z["deep_conf"]=result["confidence"]
        z["deep_summary"]=result["summary"];z["deep_result"]=result;z["tokens"]=sum(use)
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
            errors=0
            for pos,i in enumerate(ids,1):
                try:self.run_deep_one(i,k,pos,len(ids))
                except Exception:errors+=1
            self.r.after(0,self.refresh)
            self.r.after(0,lambda:self.st.set(f"Deep Vision batch complete: {len(ids)-errors} analyzed, {errors} errors."))
        threading.Thread(target=w,daemon=True).start()
    def copy(self):
        i=self.selidx()
        if i is not None:
            z=self.rows[i];self.r.clipboard_clear();self.r.clipboard_append(z["address"]);self.st.set("Address copied.")

r=tk.Tk();App(r);r.mainloop()
