import base64, json, math, threading, tkinter as tk, urllib.parse, urllib.request
from tkinter import ttk, messagebox
from pathlib import Path
from PIL import Image, ImageTk
from openai import OpenAI

MODEL="gpt-5.4-mini"

# Virginia Beach public GIS services
ADDR_LAYER="https://geo.vbgov.com/mapservices/rest/services/Business_Systems/Pictometry_Online/MapServer/0/query"
PROP_LAYER="https://geo.vbgov.com/mapservices/rest/services/Business_Systems/Pictometry_Online/MapServer/4/query"
AERIAL="https://geo.vbgov.com/imageservices/rest/services/Imagery/Aerial2025/ImageServer/exportImage"
VGIN_BUILDINGS="https://dsfmportal.dcr.virginia.gov/server/rest/services/CivilReference/Civil_Reference_Layers/MapServer/2/query"

def get_json(url, params):
    q=urllib.parse.urlencode(params)
    req=urllib.request.Request(url+"?"+q,headers={"User-Agent":"HVAC-Territory-Discovery/0.7"})
    with urllib.request.urlopen(req,timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

def geocode_address(text):
    # VB GIS address point search; deliberately VB-only for first territory-discovery build.
    # Query common text fields without assuming a single exact schema.
    meta=get_json(ADDR_LAYER.rsplit("/query",1)[0],{"f":"json"})
    fields=[f["name"] for f in meta.get("fields",[]) if f.get("type")=="esriFieldTypeString"]
    preferred=[x for x in fields if any(k in x.lower() for k in ("address","full","street","site"))]
    use=(preferred or fields)[:8]
    safe=text.replace("'","''")
    where=" OR ".join([f"UPPER({f}) LIKE UPPER('%{safe}%')" for f in use]) if use else "1=0"
    d=get_json(ADDR_LAYER,{"f":"json","where":where,"outFields":"*","returnGeometry":"true","outSR":"4326","resultRecordCount":10})
    feats=d.get("features",[])
    if not feats: raise RuntimeError("Virginia Beach GIS could not find that address/place. Try a street address for v0.7.0.")
    g=feats[0]["geometry"]
    return float(g["x"]),float(g["y"]),feats[0].get("attributes",{})

def bbox_for_radius(lon,lat,miles):
    dy=miles/69.0
    dx=miles/(69.0*max(.2,math.cos(math.radians(lat))))
    return lon-dx,lat-dy,lon+dx,lat+dy

def polygon_area_sqft(rings):
    # Local equirectangular approximation; adequate for discovery/ranking.
    pts=[]
    for ring in rings or []:
        if not ring: continue
        lat0=sum(p[1] for p in ring)/len(ring)
        c=math.cos(math.radians(lat0))
        xy=[(p[0]*69.172*c*5280,p[1]*69.0*5280) for p in ring]
        a=abs(sum(xy[i][0]*xy[(i+1)%len(xy)][1]-xy[(i+1)%len(xy)][0]*xy[i][1] for i in range(len(xy)))/2)
        pts.append(a)
    return max(pts) if pts else 0

def centroid(rings):
    pts=[p for ring in (rings or []) for p in ring]
    if not pts:return None,None
    return sum(p[0] for p in pts)/len(pts),sum(p[1] for p in pts)/len(pts)

def discover(center,radius,min_sqft,max_results=400):
    lon,lat=center
    xmin,ymin,xmax,ymax=bbox_for_radius(lon,lat,radius)
    geom=f"{xmin},{ymin},{xmax},{ymax}"
    params={"f":"json","where":"1=1","geometry":geom,"geometryType":"esriGeometryEnvelope",
            "inSR":"4326","spatialRel":"esriSpatialRelIntersects","outFields":"*",
            "returnGeometry":"true","outSR":"4326","resultRecordCount":max_results}
    d=get_json(VGIN_BUILDINGS,params)
    rows=[]
    for ft in d.get("features",[]):
        rings=ft.get("geometry",{}).get("rings",[])
        area=polygon_area_sqft(rings)
        if area<min_sqft: continue
        x,y=centroid(rings)
        if x is None: continue
        dist=math.hypot((x-lon)*69.172*math.cos(math.radians(lat)),(y-lat)*69.0)
        if dist>radius*1.08: continue
        rows.append({"lon":x,"lat":y,"sqft":round(area),"distance":round(dist,2),
                     "oid":ft.get("attributes",{}).get("OBJECTID","")})
    rows.sort(key=lambda z:(-z["sqft"],z["distance"]))
    return rows

def nearest_address(lon,lat):
    # nearest address point within ~300 ft
    d=get_json(ADDR_LAYER,{"f":"json","where":"1=1","geometry":f"{lon},{lat}",
        "geometryType":"esriGeometryPoint","inSR":"4326","spatialRel":"esriSpatialRelIntersects",
        "distance":"300","units":"esriSRUnit_Foot","outFields":"*","returnGeometry":"true",
        "outSR":"4326","resultRecordCount":8})
    feats=d.get("features",[])
    if not feats:return ""
    def label(a):
        for k,v in a.items():
            if v and any(t in k.lower() for t in ("address","full","site")): return str(v)
        vals=[str(v) for v in a.values() if v not in (None,"")]
        return " ".join(vals[:4])
    return label(feats[0].get("attributes",{}))

def export_aerial(lon,lat,sqft,outfile):
    # Scale frame to footprint size, but keep enough perimeter to expose ground equipment.
    side=max(550,min(1800,math.sqrt(max(sqft,1))*3.2))
    half_m=(side*.3048)/2
    # Web Mercator
    R=6378137.0
    x=R*math.radians(lon)
    y=R*math.log(math.tan(math.pi/4+math.radians(lat)/2))
    bbox=f"{x-half_m},{y-half_m},{x+half_m},{y+half_m}"
    q=urllib.parse.urlencode({"f":"image","bbox":bbox,"bboxSR":"3857","imageSR":"3857",
                              "size":"1800,1800","format":"jpg","pixelType":"U8",
                              "interpolation":"+RSP_BilinearInterpolation"})
    req=urllib.request.Request(AERIAL+"?"+q,headers={"User-Agent":"HVAC-Territory-Discovery/0.7"})
    with urllib.request.urlopen(req,timeout=120) as r: Path(outfile).write_bytes(r.read())

class App:
    def __init__(self,r):
        self.r=r; self.rows=[]; self.center=None
        r.title("HVAC Territory Discovery v0.7.0 — Candidate Finder"); r.geometry("1180x780")
        top=ttk.Frame(r,padding=10);top.pack(fill="x")
        ttk.Label(top,text="Virginia Beach address / search center:").grid(row=0,column=0,sticky="w")
        self.q=tk.StringVar(value="717 General Booth Blvd")
        ttk.Entry(top,textvariable=self.q,width=44).grid(row=0,column=1,padx=5)
        ttk.Label(top,text="Radius (mi):").grid(row=0,column=2)
        self.rad=tk.StringVar(value="1.0");ttk.Entry(top,textvariable=self.rad,width=7).grid(row=0,column=3,padx=5)
        ttk.Label(top,text="Min footprint ft²:").grid(row=0,column=4)
        self.mins=tk.StringVar(value="10000");ttk.Entry(top,textvariable=self.mins,width=9).grid(row=0,column=5,padx=5)
        self.go=ttk.Button(top,text="Discover Candidates",command=self.start);self.go.grid(row=0,column=6,padx=8)
        self.status=tk.StringVar(value="Ready — v0.7.0 discovers and ranks building candidates; deep vision remains a separate validated engine.")
        ttk.Label(r,textvariable=self.status).pack(fill="x",padx=10)
        cols=("rank","address","sqft","miles","status")
        self.tree=ttk.Treeview(r,columns=cols,show="headings")
        for c,w in zip(cols,(55,430,120,90,280)):
            self.tree.heading(c,text=c.upper());self.tree.column(c,width=w,anchor="w")
        self.tree.pack(fill="both",expand=True,padx=10,pady=8)
        bar=ttk.Frame(r,padding=(10,0,10,10));bar.pack(fill="x")
        ttk.Button(bar,text="Download Aerial for Selected",command=self.aerial).pack(side="left")
        ttk.Button(bar,text="Copy Selected Address",command=self.copy_addr).pack(side="left",padx=8)
        ttk.Label(bar,text="v0.7.0 deliberately does not auto-run 11-call deep vision on every building.").pack(side="right")

    def start(self):
        self.go.config(state="disabled"); self.status.set("Finding search center and querying building footprints...")
        threading.Thread(target=self.work,daemon=True).start()

    def work(self):
        try:
            lon,lat,_=geocode_address(self.q.get().strip())
            radius=float(self.rad.get()); mins=float(self.mins.get())
            rows=discover((lon,lat),radius,mins)
            # Address only the top 100 candidates to avoid hammering the public service.
            for i,z in enumerate(rows[:100]):
                self.r.after(0,lambda i=i,n=len(rows[:100]):self.status.set(f"Resolving candidate addresses {i+1}/{n}..."))
                try:z["address"]=nearest_address(z["lon"],z["lat"])
                except:z["address"]=""
                z["status"]="UNCLASSIFIED — ready for property/business filter"
            self.rows=rows[:100];self.center=(lon,lat)
            self.r.after(0,self.show)
        except Exception as e:self.r.after(0,lambda e=e:self.fail(e))

    def show(self):
        for x in self.tree.get_children():self.tree.delete(x)
        for i,z in enumerate(self.rows,1):
            self.tree.insert("", "end", iid=str(i-1), values=(i,z.get("address",""),f'{z["sqft"]:,}',z["distance"],z["status"]))
        self.status.set(f"{len(self.rows)} candidate buildings shown. Largest footprints ranked first. Select one to download centered 2025 aerial imagery.")
        self.go.config(state="normal")

    def fail(self,e):
        self.status.set("Failed: "+repr(e));self.go.config(state="normal")

    def selected(self):
        s=self.tree.selection()
        if not s: messagebox.showinfo("Select candidate","Select a building first.");return None
        return self.rows[int(s[0])]

    def aerial(self):
        z=self.selected()
        if not z:return
        out=Path.home()/"Downloads"/f'HVAC_candidate_{z["lat"]:.5f}_{z["lon"]:.5f}.jpg'
        self.status.set("Downloading centered 2025 Virginia Beach aerial...")
        def w():
            try:
                export_aerial(z["lon"],z["lat"],z["sqft"],out)
                self.r.after(0,lambda:self.status.set("Saved: "+str(out)))
            except Exception as e:self.r.after(0,lambda:self.status.set("Aerial download failed: "+repr(e)))
        threading.Thread(target=w,daemon=True).start()

    def copy_addr(self):
        z=self.selected()
        if not z:return
        self.r.clipboard_clear();self.r.clipboard_append(z.get("address",""))
        self.status.set("Address copied.")

r=tk.Tk();App(r);r.mainloop()
