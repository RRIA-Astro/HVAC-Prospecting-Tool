import json,math,threading,tkinter as tk,urllib.parse,urllib.request
from tkinter import ttk,messagebox
from pathlib import Path

ADDR="https://geo.vbgov.com/mapservices/rest/services/Business_Systems/Pictometry_Online/MapServer/0/query"
PARCEL="https://geo.vbgov.com/mapservices/rest/services/Business_Systems/Pictometry_Online/MapServer/4/query"
# City of Virginia Beach authoritative planimetric Building Footprints
BLDGS="https://geo.vbgov.com/mapservices/rest/services/Basemaps/Structures_and_Physical_Features/MapServer/6/query"
AERIAL="https://geo.vbgov.com/imageservices/rest/services/Imagery/Aerial2025/ImageServer/exportImage"

def gj(u,p):
    q=urllib.parse.urlencode(p)
    req=urllib.request.Request(u+"?"+q,headers={"User-Agent":"HVAC-Territory/0.7.5"})
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

def load_buildings(x,y,mi):
    a,b,c,d=bbox(x,y,mi)
    p={"f":"json","where":"1=1","geometry":f"{a},{b},{c},{d}","geometryType":"esriGeometryEnvelope",
       "inSR":"4326","spatialRel":"esriSpatialRelIntersects","outFields":"OBJECTID,fcode,height_highest",
       "returnGeometry":"true","outSR":"4326"}
    out=[]
    for f in pages(BLDGS,p):
        rs=f.get("geometry",{}).get("rings",[]);cx,cy=centroid(rs)
        if cx is None:continue
        if miles(x,y,cx,cy)<=mi*1.03:
            at=f.get("attributes",{})
            out.append({"lon":cx,"lat":cy,"sq":round(area(rs)),
                        "fcode":at.get("fcode") or "","height":at.get("height_highest")})
    return out

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
    ps=load_parcels(x,y,mi);bs=load_buildings(x,y,mi)
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
        p.update(largest=largest,total=total,count=count,avg=avg,fcodes=fcodes,
                 distance=round(miles(x,y,p["lon"],p["lat"]),2))
        p["tier"],p["score"]=classify(p["land"],p["zone"],largest,avg,count,fcodes)
        p["path"]="SIZE" if sizepass else "ANOMALY"
        p["source"]="VB CITY" if bl else "FOOTPRINT MISSING"
        rows.append(p)
    ded={}
    for p in rows:
        k=p["gpin"] or "A:"+p["address"].upper().strip()
        if k not in ded:ded[k]=p
    out=list(ded.values())
    out.sort(key=lambda z:(-z["score"],0 if z["path"]=="SIZE" else 1,-(z["largest"] or 0),z["distance"]))
    return out[:250],len(ps),len(bs),joined

def aerial(x,y,sf,out):
    side=max(650,min(1800,math.sqrt(max(sf or 30000,1))*3.2));h=side*.3048/2;R=6378137
    X=R*math.radians(x);Y=R*math.log(math.tan(math.pi/4+math.radians(y)/2))
    q=urllib.parse.urlencode({"f":"image","bbox":f"{X-h},{Y-h},{X+h},{Y+h}","bboxSR":"3857",
                              "imageSR":"3857","size":"1800,1800","format":"jpg"})
    with urllib.request.urlopen(AERIAL+"?"+q,timeout=120) as r:Path(out).write_bytes(r.read())

class App:
    def __init__(self,r):
        self.r=r;self.rows=[];r.title("HVAC Territory Discovery v0.7.5 — Virginia Beach City Footprints");r.geometry("1600x850")
        t=ttk.Frame(r,padding=10);t.pack(fill="x")
        ttk.Label(t,text="Virginia Beach search center:").grid(row=0,column=0)
        self.q=tk.StringVar(value="717 General Booth Blvd");ttk.Entry(t,textvariable=self.q,width=40).grid(row=0,column=1,padx=5)
        ttk.Label(t,text="Radius mi:").grid(row=0,column=2);self.rad=tk.StringVar(value="1.0");ttk.Entry(t,textvariable=self.rad,width=6).grid(row=0,column=3)
        ttk.Label(t,text="Size path min ft²:").grid(row=0,column=4);self.mn=tk.StringVar(value="10000");ttk.Entry(t,textvariable=self.mn,width=8).grid(row=0,column=5)
        self.b=ttk.Button(t,text="Discover",command=self.start);self.b.grid(row=0,column=6,padx=8)
        self.st=tk.StringVar(value="Uses City of Virginia Beach planimetric building footprints.")
        ttk.Label(r,textvariable=self.st).pack(fill="x",padx=10)
        cs=("rank","address","largest","total","avg","bldgs","miles","land","zone","fcode","tier","score","path","source")
        self.tree=ttk.Treeview(r,columns=cs,show="headings")
        for c,w in zip(cs,(45,220,80,85,75,50,55,180,55,175,70,50,70,90)):
            self.tree.heading(c,text=c.upper());self.tree.column(c,width=w,anchor="w")
        self.tree.pack(fill="both",expand=True,padx=10,pady=8)
        f=ttk.Frame(r,padding=10);f.pack(fill="x")
        ttk.Button(f,text="Download Aerial",command=self.dl).pack(side="left")
        ttk.Button(f,text="Copy Address",command=self.copy).pack(side="left",padx=8)
    def start(self):
        self.b.config(state="disabled");self.st.set("Querying Virginia Beach parcels + city building footprints...")
        threading.Thread(target=self.work,daemon=True).start()
    def work(self):
        try:
            x,y=geocode(self.q.get().strip())
            self.rows,np,nb,nj=discover(x,y,float(self.rad.get()),float(self.mn.get()))
            self.diag=(np,nb,nj);self.r.after(0,self.show)
        except Exception as e:self.r.after(0,lambda e=e:self.fail(e))
    def show(self):
        for i in self.tree.get_children():self.tree.delete(i)
        for n,z in enumerate(self.rows,1):
            fmt=lambda v:f"{v:,}" if v is not None else "UNKNOWN"
            self.tree.insert("","end",iid=str(n-1),values=(n,z["address"],fmt(z["largest"]),fmt(z["total"]),fmt(z["avg"]),
                z["count"],z["distance"],z["land"],z["zone"],", ".join(z["fcodes"]),z["tier"],z["score"],z["path"],z["source"]))
        sz=sum(z["path"]=="SIZE" for z in self.rows);np,nb,nj=self.diag
        self.st.set(f"{len(self.rows)} prospects — SIZE {sz}, ANOMALY {len(self.rows)-sz} | parcels {np} | city footprints {nb} | spatially joined {nj}")
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
    def copy(self):
        z=self.sel()
        if z:self.r.clipboard_clear();self.r.clipboard_append(z["address"]);self.st.set("Address copied.")

r=tk.Tk();App(r);r.mainloop()
