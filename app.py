import json,math,threading,tkinter as tk,urllib.parse,urllib.request
from tkinter import ttk,messagebox,simpledialog
from pathlib import Path

ADDR="https://geo.vbgov.com/mapservices/rest/services/Business_Systems/Pictometry_Online/MapServer/0/query"
PARCEL="https://geo.vbgov.com/mapservices/rest/services/Business_Systems/Pictometry_Online/MapServer/4/query"
# City of Virginia Beach authoritative planimetric Building Footprints
CITY_BLDGS="https://geo.vbgov.com/mapservices/rest/services/Basemaps/Structures_and_Physical_Features/MapServer/6/query"
FALLBACK_BLDGS="https://dsfmportal.dcr.virginia.gov/server/rest/services/CivilReference/Civil_Reference_Layers/MapServer/2/query"
AERIAL="https://geo.vbgov.com/imageservices/rest/services/Imagery/Aerial2025/ImageServer/exportImage"
OPENAI_URL="https://api.openai.com/v1/responses"
SCREEN_MODEL="gpt-5.4-mini"

def gj(u,p):
    q=urllib.parse.urlencode(p)
    req=urllib.request.Request(u+"?"+q,headers={"User-Agent":"HVAC-Territory/0.8.1"})
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
    high=("HOSP","MEDICAL","UNIVERS","COLLEGE","INDUSTR","MANUFACTUR","GOVERN","SCHOOL",
          "WAREHOUSE","DISTRIBUT","UTILITY","PUBLIC/SEMI PUBLIC","PUMP STATION","SUBSTATION")
    low=("APART","CONDO","MULTI FAMILY","MULTIFAMILY","RESTAUR","RETAIL","SHOPPING","STORE",
         "SINGLE FAMILY","DUPLEX")
    med=("OFFICE","HOTEL","MOTEL","CHURCH","RELIG","ASSEMBLY","ENTERTAIN","AUTO","COMMERCIAL","MILITARY")
    t="HIGH" if any(k in s for k in high) else "LOW" if any(k in s for k in low) else "MEDIUM" if any(k in s for k in med) else "UNKNOWN"
    score={"HIGH":75,"MEDIUM":55,"UNKNOWN":50,"LOW":20}[t]
    if largest:score+=10 if largest>=75000 else 6 if largest>=40000 else 3 if largest>=20000 else 0
    if count>=12 and avg and avg<10000:score-=20
    elif count>=6 and avg and avg<7000:score-=12
    return t,max(0,min(95,score))

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
        sizepass=largest is not None and largest>=mn
        residential=any(k in land for k in ("SINGLE FAMILY","DUPLEX","MULTI FAMILY","MULTIFAMILY","APART","CONDO"))
        anomaly_eligible=not residential
        if not sizepass and not anomaly_eligible:continue
        p.update(largest=largest,total=total,count=count,avg=avg,fcodes=fcodes,buildings=bl,
                 distance=round(miles(x,y,p["lon"],p["lat"]),2))
        p["tier"],p["score"]=classify(p["land"],p["zone"],largest,avg,count,fcodes)
        p["path"]="SIZE" if sizepass else "ANOMALY"
        p["source"]=bsource if bl else "FOOTPRINT MISSING"
        rows.append(p)
    ded={}
    for p in rows:
        k=p["gpin"] or "A:"+p["address"].upper().strip()
        if k not in ded:ded[k]=p
    out=list(ded.values())
    out.sort(key=lambda z:(-z["score"],0 if z["path"]=="SIZE" else 1,-(z["largest"] or 0),z["distance"]))
    return out[:250],len(ps),len(bs),joined,bsource,berrors

def aerial(x,y,sf,out):
    side=max(650,min(1800,math.sqrt(max(sf or 30000,1))*3.2));h=side*.3048/2;R=6378137
    X=R*math.radians(x);Y=R*math.log(math.tan(math.pi/4+math.radians(y)/2))
    q=urllib.parse.urlencode({"f":"image","bbox":f"{X-h},{Y-h},{X+h},{Y+h}","bboxSR":"3857",
                              "imageSR":"3857","size":"1800,1800","format":"jpg"})
    with urllib.request.urlopen(AERIAL+"?"+q,timeout=120) as r:Path(out).write_bytes(r.read())

def aerial_at(x,y,side_ft,pixels,out):
    h=side_ft*.3048/2;R=6378137
    X=R*math.radians(x);Y=R*math.log(math.tan(math.pi/4+math.radians(y)/2))
    q=urllib.parse.urlencode({"f":"image","bbox":f"{X-h},{Y-h},{X+h},{Y+h}","bboxSR":"3857",
                              "imageSR":"3857","size":f"{pixels},{pixels}","format":"jpg"})
    with urllib.request.urlopen(AERIAL+"?"+q,timeout=120) as r:Path(out).write_bytes(r.read())

def screen_images(z):
    import base64,tempfile
    td=Path(tempfile.gettempdir()); imgs=[]
    overview_side=max(900,min(2200,math.sqrt(max(z.get("total") or z.get("largest") or 30000,1))*4.0))
    p=td/f"hvac_v081_{abs(hash((z['lon'],z['lat'])))}_overview.jpg"
    aerial_at(z["lon"],z["lat"],overview_side,1600,p)
    imgs.append(("PROPERTY OVERVIEW",base64.b64encode(p.read_bytes()).decode("ascii")))
    bs=sorted(z.get("buildings",[]),key=lambda b:b.get("sq",0),reverse=True); chosen=[]
    for b in bs:
        if any(miles(b["lon"],b["lat"],q["lon"],q["lat"])<0.025 for q in chosen):continue
        chosen.append(b)
        if len(chosen)>=4:break
    if not chosen:
        d=0.0016
        chosen=[{"lon":z["lon"]-d,"lat":z["lat"],"sq":25000},{"lon":z["lon"]+d,"lat":z["lat"],"sq":25000},
                {"lon":z["lon"],"lat":z["lat"]-d,"sq":25000},{"lon":z["lon"],"lat":z["lat"]+d,"sq":25000}]
    for i,b in enumerate(chosen,1):
        side=max(500,min(1050,math.sqrt(max(b.get("sq") or 25000,1))*3.0))
        p=td/f"hvac_v081_{abs(hash((z['lon'],z['lat'])))}_b{i}.jpg"
        aerial_at(b["lon"],b["lat"],side,1400,p)
        imgs.append((f"BUILDING/PERIMETER VIEW {i}",base64.b64encode(p.read_bytes()).decode("ascii")))
    return imgs

def cheap_screen(api_key,z):
    imgs=screen_images(z)
    prompt="""FAST HIGH-RECALL aerial screen for commercial HVAC sales prospecting. You have a PROPERTY OVERVIEW and close BUILDING/PERIMETER VIEWS. Inspect EVERY image and the ground immediately beside every building. Do not stop after seeing ordinary rooftop units.

Actively search for cooling towers or tower-like heat rejection equipment; air-cooled chillers or large fan-array equipment beside walls; substantial hydronic/process piping; paired large pipes; complex purposeful piping with multiple 90-degree turns; mechanical yards/central plants; unusually large packaged HVAC; and dense complex rooftop systems.

Critical rules: side-mounted equipment may be much more important than rooftop equipment. A small building with towers/chillers/process piping can be a great prospect. Large building size alone is not mechanical evidence. Exact chiller-vs-cooling-tower identification is not required: if substantial high-value equipment is visible but ambiguous, score the SITE highly. White insulated hydronic pipe can resemble PVC; large diameter plus multiple bends and purposeful routing into a building is meaningful. Ordinary small RTUs/condensers alone remain LOW. Prefer a false positive over missing credible central/process equipment.

Return ONLY JSON:
{"mechanical_score":0-100,"decision":"PROMISING"|"REVIEW"|"LOW","high_value_evidence":true|false,"best_view":"overview or building/perimeter view number","signals":["short visible signal"],"summary":"one concise sentence"}
80-100 strong central/process/large mechanical evidence; 60-79 credible promising evidence; 40-59 ambiguous/review; 0-39 ordinary/light mechanical evidence."""
    content=[{"type":"input_text","text":prompt}]
    for label,b64 in imgs:
        content += [{"type":"input_text","text":label},{"type":"input_image","image_url":"data:image/jpeg;base64,"+b64}]
    body={"model":SCREEN_MODEL,"reasoning":{"effort":"low"},"max_output_tokens":850,"input":[{"role":"user","content":content}]}
    req=urllib.request.Request(OPENAI_URL,data=json.dumps(body).encode(),headers={"Authorization":"Bearer "+api_key,"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=240) as r:d=json.loads(r.read().decode())
    text=""
    for o in d.get("output",[]):
        for c in o.get("content",[]):
            if c.get("type")=="output_text":text+=c.get("text","")
    text=text.strip()
    if text.startswith("```"):text=text.split("\\n",1)[1].rsplit("```",1)[0].strip()
    ans=json.loads(text);ans["_views"]=len(imgs);return ans


class App:
    def __init__(self,r):
        self.r=r;self.rows=[];r.title("HVAC Territory Discovery v0.8.1 — Building-Aware Mechanical Screen");r.geometry("1600x850")
        t=ttk.Frame(r,padding=10);t.pack(fill="x")
        ttk.Label(t,text="Virginia Beach search center:").grid(row=0,column=0)
        self.q=tk.StringVar(value="717 General Booth Blvd");ttk.Entry(t,textvariable=self.q,width=40).grid(row=0,column=1,padx=5)
        ttk.Label(t,text="Radius mi:").grid(row=0,column=2);self.rad=tk.StringVar(value="1.0");ttk.Entry(t,textvariable=self.rad,width=6).grid(row=0,column=3)
        ttk.Label(t,text="Size path min ft²:").grid(row=0,column=4);self.mn=tk.StringVar(value="10000");ttk.Entry(t,textvariable=self.mn,width=8).grid(row=0,column=5)
        self.b=ttk.Button(t,text="Discover",command=self.start);self.b.grid(row=0,column=6,padx=8)
        ttk.Label(t,text="OpenAI key:").grid(row=0,column=7)
        self.key=tk.StringVar();ttk.Entry(t,textvariable=self.key,width=22,show="*").grid(row=0,column=8,padx=4)
        self.st=tk.StringVar(value="Footprints: Virginia Beach city service first; Virginia CivilReference fallback automatically.")
        ttk.Label(r,textvariable=self.st).pack(fill="x",padx=10)
        cs=("rank","address","largest","total","avg","bldgs","miles","land","zone","tier","score","path","mech","vision","source")
        self.tree=ttk.Treeview(r,columns=cs,show="headings")
        for c,w in zip(cs,(45,210,75,80,70,50,55,165,50,65,50,70,55,90,90)):
            self.tree.heading(c,text=c.upper());self.tree.column(c,width=w,anchor="w")
        self.tree.pack(fill="both",expand=True,padx=10,pady=8)
        f=ttk.Frame(r,padding=10);f.pack(fill="x")
        ttk.Button(f,text="Download Aerial",command=self.dl).pack(side="left")
        ttk.Button(f,text="Screen Selected",command=self.screen_selected).pack(side="left",padx=8)
        ttk.Button(f,text="Screen Top 25",command=self.screen_top).pack(side="left",padx=8)
        ttk.Button(f,text="Copy Address",command=self.copy).pack(side="left",padx=8)
    def start(self):
        self.b.config(state="disabled");self.st.set("Querying parcels + building footprints (automatic fallback enabled)...")
        threading.Thread(target=self.work,daemon=True).start()
    def work(self):
        try:
            x,y=geocode(self.q.get().strip())
            self.rows,np,nb,nj,src,errs=discover(x,y,float(self.rad.get()),float(self.mn.get()))
            self.diag=(np,nb,nj,src,errs);self.r.after(0,self.show)
        except Exception as e:self.r.after(0,lambda e=e:self.fail(e))
    def show(self):
        for i in self.tree.get_children():self.tree.delete(i)
        for n,z in enumerate(self.rows,1):
            fmt=lambda v:f"{v:,}" if v is not None else "UNKNOWN"
            self.tree.insert("","end",iid=str(n-1),values=(n,z["address"],fmt(z["largest"]),fmt(z["total"]),fmt(z["avg"]),
                z["count"],z["distance"],z["land"],z["zone"],z["tier"],z["score"],z["path"],
                z.get("mech",""),z.get("vision",""),z["source"]))
        sz=sum(z["path"]=="SIZE" for z in self.rows);np,nb,nj,src,errs=self.diag
        warn=(" | fallback reason: "+errs[0][:80]) if errs and src!="VB CITY" else ""
        self.st.set(f"{len(self.rows)} prospects — SIZE {sz}, ANOMALY {len(self.rows)-sz} | parcels {np} | footprints {nb} | joined {nj} | source {src}{warn}")
        self.b.config(state="normal")
    def fail(self,e):self.st.set("Failed: "+repr(e));self.b.config(state="normal")
    def sel(self):
        s=self.tree.selection()
        if not s:messagebox.showinfo("Select","Select a candidate.");return
        return self.rows[int(s[0])]
    def dl(self):
        z=self.sel()
        if not z:return
        out=Path.home()/"Downloads"/f'HVAC_{z["address"].replace(" ","_") or "candidate"}.jpg';self.st.set("Downloading aerial...")
        def w():
            try:aerial(z["lon"],z["lat"],z["largest"],out);self.r.after(0,lambda:self.st.set("Saved "+str(out)))
            except Exception as e:self.r.after(0,lambda:self.st.set("Download failed: "+repr(e)))
        threading.Thread(target=w,daemon=True).start()
    def getkey(self):
        k=self.key.get().strip()
        if not k:messagebox.showinfo("OpenAI key","Paste your OpenAI API key first.");return None
        return k
    def screen_one(self,i,k):
        z=self.rows[i]
        try:
            r=cheap_screen(k,z)
            z["mech"]=int(r.get("mechanical_score",0))
            z["vision"]=r.get("decision","")
            z["vision_summary"]=r.get("summary","")
            z["signals"]=r.get("signals",[])
            z["best_view"]=r.get("best_view","");z["screen_views"]=r.get("_views",0)
            return None
        except Exception as e:return str(e)
    def refresh_row(self,i):
        z=self.rows[i];fmt=lambda v:f"{v:,}" if v is not None else "UNKNOWN"
        self.tree.item(str(i),values=(i+1,z["address"],fmt(z["largest"]),fmt(z["total"]),fmt(z["avg"]),
            z["count"],z["distance"],z["land"],z["zone"],z["tier"],z["score"],z["path"],
            z.get("mech",""),z.get("vision",""),z["source"]))
    def screen_selected(self):
        k=self.getkey();s=self.tree.selection()
        if not k:return
        if not s:messagebox.showinfo("Select","Select a candidate.");return
        i=int(s[0]);self.st.set("Cheap visual screen running for "+self.rows[i]["address"]+"...")
        def w():
            e=self.screen_one(i,k)
            self.r.after(0,lambda:self.after_screen(i,e))
        threading.Thread(target=w,daemon=True).start()
    def after_screen(self,i,e):
        self.refresh_row(i)
        z=self.rows[i]
        if e:self.st.set("Screen failed: "+e)
        else:self.st.set(f'{z["address"]}: mechanical {z["mech"]}/100 — {z["vision"]} — {z.get("vision_summary","")} | {z.get("screen_views",0)} images | best: {z.get("best_view","")}')
    def screen_top(self):
        k=self.getkey()
        if not k:return
        # Default batch deliberately limited to 25 to control API spend.
        ids=list(range(min(25,len(self.rows))))
        self.st.set(f"Screening {len(ids)} candidates with building-aware views...")
        def w():
            errs=0
            for n,i in enumerate(ids,1):
                if self.screen_one(i,k):errs+=1
                self.r.after(0,lambda i=i:self.refresh_row(i))
                self.r.after(0,lambda n=n:self.st.set(f"Cheap visual screen {n}/{len(ids)}..."))
            self.r.after(0,lambda:self.finish_batch(errs))
        threading.Thread(target=w,daemon=True).start()
    def finish_batch(self,errs):
        # Re-rank screened candidates by mechanical score first; unscreened retain GIS score.
        self.rows.sort(key=lambda z:(0 if "mech" in z else 1,-z.get("mech",0),-z["score"],z["distance"]))
        for i in self.tree.get_children():self.tree.delete(i)
        for n,z in enumerate(self.rows,1):
            fmt=lambda v:f"{v:,}" if v is not None else "UNKNOWN"
            self.tree.insert("","end",iid=str(n-1),values=(n,z["address"],fmt(z["largest"]),fmt(z["total"]),fmt(z["avg"]),
                z["count"],z["distance"],z["land"],z["zone"],z["tier"],z["score"],z["path"],z.get("mech",""),z.get("vision",""),z["source"]))
        self.st.set(f"Visual screening complete. {errs} errors. Screened candidates re-ranked by mechanical opportunity.")
    def copy(self):
        z=self.sel()
        if z:self.r.clipboard_clear();self.r.clipboard_append(z["address"]);self.st.set("Address copied.")

r=tk.Tk();App(r);r.mainloop()
