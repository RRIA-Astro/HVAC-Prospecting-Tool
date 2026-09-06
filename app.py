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
    req=urllib.request.Request(u+"?"+q,headers={"User-Agent":"HVAC-Territory/0.10.0"})
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

# ---------------- Human Review + Training Dataset ----------------
import csv,os,zipfile
from datetime import datetime,timezone
from PIL import Image,ImageTk

APP_VERSION="0.10.0"
DATASET_NAME="HVAC_Training_Dataset"
EQUIPMENT_CLASSES=[
    ("cooling_tower","Cooling tower / fluid cooler / evaporative heat rejection"),
    ("air_cooled_chiller","Air-cooled / process chiller"),
    ("large_packaged_hvac","Genuinely large packaged RTU / AHU"),
    ("process_hydronic_piping","Substantial hydronic / process piping"),
    ("mechanical_yard_process","Mechanical yard / process-cooling area"),
    ("other_high_value_mechanical","Other clearly high-value mechanical equipment"),
]
CLASS_IDS={k:i for i,(k,_) in enumerate(EQUIPMENT_CLASSES)}


def dataset_root():
    p=Path.home()/"Downloads"/DATASET_NAME
    (p/"images").mkdir(parents=True,exist_ok=True)
    (p/"labels").mkdir(parents=True,exist_ok=True)
    return p


def safe_name(s):
    s="".join(c if c.isalnum() or c in "-_" else "_" for c in (s or "candidate"))
    while "__" in s:s=s.replace("__","_")
    return s.strip("_") or "candidate"


def site_key(z):
    return z.get("gpin") or (z.get("address") or f'{z.get("lon",0):.6f}_{z.get("lat",0):.6f}')


def labels_json_path():return dataset_root()/"annotations.json"


def load_dataset_labels():
    p=labels_json_path()
    if not p.exists():return {"version":1,"classes":[k for k,_ in EQUIPMENT_CLASSES],"sites":{}}
    try:
        d=json.loads(p.read_text())
        d.setdefault("version",1);d.setdefault("classes",[k for k,_ in EQUIPMENT_CLASSES]);d.setdefault("sites",{})
        return d
    except Exception:
        return {"version":1,"classes":[k for k,_ in EQUIPMENT_CLASSES],"sites":{}}


def save_dataset_labels(d):
    root=dataset_root();p=root/"annotations.json";tmp=root/"annotations.tmp.json"
    tmp.write_text(json.dumps(d,indent=2));tmp.replace(p)
    write_site_csv(d)
    (root/"classes.txt").write_text("\n".join(k for k,_ in EQUIPMENT_CLASSES)+"\n")


def write_site_csv(d):
    p=dataset_root()/"site_labels.csv"
    with p.open("w",newline="",encoding="utf-8") as f:
        w=csv.writer(f)
        w.writerow(["site_key","facility","address","rating","land_use","zoning","largest_ft2","building_count","notes","updated_utc"])
        for k,s in d.get("sites",{}).items():
            meta=s.get("meta",{})
            w.writerow([k,meta.get("facility",""),meta.get("address",""),s.get("rating","UNRATED"),
                        meta.get("land",""),meta.get("zone",""),meta.get("largest",""),meta.get("count",""),
                        s.get("notes",""),s.get("updated_utc","")])


def ensure_yolo_label(image_record):
    """Write normalized YOLO boxes. Empty files are valid negative examples."""
    root=dataset_root();img_name=image_record.get("dataset_image")
    if not img_name:return
    w=float(image_record.get("width") or 1);h=float(image_record.get("height") or 1)
    lines=[]
    for a in image_record.get("annotations",[]):
        if a.get("class") not in CLASS_IDS:continue
        x1,y1,x2,y2=[float(a.get(k,0)) for k in ("x1","y1","x2","y2")]
        x1,x2=sorted((max(0,min(w,x1)),max(0,min(w,x2))));y1,y2=sorted((max(0,min(h,y1)),max(0,min(h,y2))))
        if x2-x1<2 or y2-y1<2:continue
        xc=(x1+x2)/(2*w);yc=(y1+y2)/(2*h);bw=(x2-x1)/w;bh=(y2-y1)/h
        lines.append(f"{CLASS_IDS[a['class']]} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}")
    (root/"labels"/(Path(img_name).stem+".txt")).write_text("\n".join(lines)+("\n" if lines else ""))


def export_dataset_zip():
    root=dataset_root();stamp=datetime.now().strftime("%Y%m%d_%H%M")
    out=Path.home()/"Downloads"/f"{DATASET_NAME}_{stamp}.zip"
    with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as z:
        for p in root.rglob("*"):
            if p.is_file():z.write(p,p.relative_to(root.parent))
    return out


class ReviewWindow:
    def __init__(self,app,z,raw_imgs):
        self.app=app;self.z=z;self.root=dataset_root();self.data=app.label_data;self.key=site_key(z)
        self.site=self.data["sites"].setdefault(self.key,{"rating":"UNRATED","notes":"","meta":{},"images":[]})
        self.site["meta"]={"facility":z.get("facility","") or "","address":z.get("address","") or "","gpin":z.get("gpin","") or "",
                           "land":z.get("land","") or "","zone":z.get("zone","") or "","largest":z.get("largest"),"count":z.get("count",0),
                           "lon":z.get("lon"),"lat":z.get("lat"),"source":z.get("source","")}
        self.images=self.prepare_images(raw_imgs);self.idx=0;self.current_pil=None;self.tkimg=None;self.scale=1;self.offset=(0,0);self.drag_start=None;self.temp_rect=None
        self.win=tk.Toplevel(app.r);self.win.title(f"Review & Label — {z.get('facility') or z.get('address')}");self.win.geometry("1500x900")
        self.win.protocol("WM_DELETE_WINDOW",self.close)
        self.build_ui();self.load_image()

    def prepare_images(self,imgs):
        safe=safe_name((self.z.get("facility") or "")+"_"+(self.z.get("address") or ""))
        existing={x.get("label"):x for x in self.site.get("images",[])}
        out=[]
        for label,p,b in imgs:
            im=Image.open(p);w,h=im.size
            dataset_name=f"{safe}_{safe_name(label)}.jpg"
            dst=self.root/"images"/dataset_name
            if not dst.exists():shutil.copy2(p,dst)
            rec=existing.get(label,{"label":label,"annotations":[],"negative":False,"image_notes":"","rating":"UNRATED"})
            rec.update({"dataset_image":dataset_name,"width":w,"height":h,"building_sqft":b.get("sq") if b else None,
                        "building_lon":b.get("lon") if b else None,"building_lat":b.get("lat") if b else None})
            out.append(rec)
        self.site["images"]=out
        return out

    def build_ui(self):
        top=ttk.Frame(self.win,padding=8);top.pack(fill="x")
        ttk.Label(top,text=f"{self.z.get('facility') or ''}   {self.z.get('address') or ''}",font=("Segoe UI",11,"bold")).pack(side="left")
        self.imgtitle=tk.StringVar();ttk.Label(top,textvariable=self.imgtitle).pack(side="left",padx=20)
        ttk.Button(top,text="Save",command=self.save).pack(side="right",padx=4)
        ttk.Button(top,text="Save & Close",command=self.close).pack(side="right",padx=4)

        body=ttk.Frame(self.win);body.pack(fill="both",expand=True,padx=8,pady=4)
        left=ttk.Frame(body);left.pack(side="left",fill="both",expand=True)
        right=ttk.Frame(body,width=360,padding=8);right.pack(side="right",fill="y")

        self.canvas=tk.Canvas(left,bg="#202020",cursor="crosshair",highlightthickness=0)
        self.canvas.pack(fill="both",expand=True)
        self.canvas.bind("<ButtonPress-1>",self.on_press);self.canvas.bind("<B1-Motion>",self.on_drag);self.canvas.bind("<ButtonRelease-1>",self.on_release)
        self.canvas.bind("<Configure>",lambda e:self.render())

        nav=ttk.Frame(left,padding=6);nav.pack(fill="x")
        ttk.Button(nav,text="◀ Previous",command=self.prev).pack(side="left")
        ttk.Button(nav,text="Next ▶",command=self.next).pack(side="left",padx=8)
        ttk.Label(nav,text="Drag a box around equipment. Boxes are saved in original-image coordinates.").pack(side="left",padx=15)

        ttk.Label(right,text="SITE RATING",font=("Segoe UI",10,"bold")).pack(anchor="w")
        self.rating=tk.StringVar(value=self.site.get("rating","UNRATED"))
        for v in ("GOOD","MAYBE","POOR","UNRATED"):
            ttk.Radiobutton(right,text=v,value=v,variable=self.rating).pack(anchor="w")

        ttk.Separator(right).pack(fill="x",pady=8)
        ttk.Label(right,text="BOX CLASS",font=("Segoe UI",10,"bold")).pack(anchor="w")
        self.class_var=tk.StringVar(value=EQUIPMENT_CLASSES[0][0])
        self.class_box=ttk.Combobox(right,textvariable=self.class_var,state="readonly",width=36,
                                    values=[k for k,_ in EQUIPMENT_CLASSES]);self.class_box.pack(fill="x",pady=3)
        self.class_desc=tk.StringVar();ttk.Label(right,textvariable=self.class_desc,wraplength=330).pack(anchor="w")
        self.class_box.bind("<<ComboboxSelected>>",lambda e:self.update_class_desc());self.update_class_desc()

        self.negative=tk.BooleanVar();ttk.Checkbutton(right,text="Negative image: no target equipment",variable=self.negative,command=self.neg_changed).pack(anchor="w",pady=(8,3))
        ttk.Label(right,text="Use Negative when no HIGH-VALUE target class is present. Ordinary small RTUs, splits and residential-style condensers are background and should NOT be boxed.",wraplength=330).pack(anchor="w")

        ttk.Label(right,text="IMAGE / BUILDING RATING",font=("Segoe UI",10,"bold")).pack(anchor="w",pady=(10,2))
        self.image_rating=tk.StringVar(value="UNRATED")
        br=ttk.Frame(right);br.pack(fill="x")
        for v in ("GOOD","MAYBE","POOR","UNRATED"):
            ttk.Radiobutton(br,text=v,value=v,variable=self.image_rating).pack(side="left")

        ttk.Label(right,text="ANNOTATIONS",font=("Segoe UI",10,"bold")).pack(anchor="w",pady=(10,2))
        self.listbox=tk.Listbox(right,height=12);self.listbox.pack(fill="x")
        b=ttk.Frame(right);b.pack(fill="x",pady=4)
        ttk.Button(b,text="Delete Selected",command=self.delete_box).pack(side="left")
        ttk.Button(b,text="Clear Image",command=self.clear_boxes).pack(side="left",padx=4)

        ttk.Label(right,text="SITE NOTES",font=("Segoe UI",10,"bold")).pack(anchor="w",pady=(10,2))
        self.notes=tk.Text(right,width=38,height=7,wrap="word");self.notes.pack(fill="x");self.notes.insert("1.0",self.site.get("notes","") or "")
        ttk.Label(right,text="IMAGE NOTES",font=("Segoe UI",10,"bold")).pack(anchor="w",pady=(10,2))
        self.image_notes=tk.Text(right,width=38,height=5,wrap="word");self.image_notes.pack(fill="x")

    def update_class_desc(self):
        d=dict(EQUIPMENT_CLASSES);self.class_desc.set(d.get(self.class_var.get(),""))

    def persist_current_fields(self):
        if not self.images:return
        rec=self.images[self.idx];rec["negative"]=bool(self.negative.get());rec["image_notes"]=self.image_notes.get("1.0","end").strip();rec["rating"]=self.image_rating.get()
        self.site["rating"]=self.rating.get();self.site["notes"]=self.notes.get("1.0","end").strip();self.site["updated_utc"]=datetime.now(timezone.utc).isoformat()

    def load_image(self):
        if not self.images:return
        rec=self.images[self.idx];p=self.root/"images"/rec["dataset_image"]
        self.current_pil=Image.open(p).convert("RGB")
        self.imgtitle.set(f"{self.idx+1}/{len(self.images)} — {rec['label']} — {rec.get('building_sqft') or 'campus'}")
        self.negative.set(bool(rec.get("negative",False)));self.image_rating.set(rec.get("rating","UNRATED"))
        self.image_notes.delete("1.0","end");self.image_notes.insert("1.0",rec.get("image_notes","") or "")
        self.refresh_list();self.render()

    def render(self):
        if not self.current_pil:return
        cw=max(100,self.canvas.winfo_width());ch=max(100,self.canvas.winfo_height())
        iw,ih=self.current_pil.size;self.scale=min(cw/iw,ch/ih);rw,rh=max(1,int(iw*self.scale)),max(1,int(ih*self.scale))
        ox=(cw-rw)//2;oy=(ch-rh)//2;self.offset=(ox,oy)
        view=self.current_pil.resize((rw,rh),Image.LANCZOS);self.tkimg=ImageTk.PhotoImage(view)
        self.canvas.delete("all");self.canvas.create_image(ox,oy,anchor="nw",image=self.tkimg)
        for n,a in enumerate(self.images[self.idx].get("annotations",[]),1):
            x1=ox+a["x1"]*self.scale;y1=oy+a["y1"]*self.scale;x2=ox+a["x2"]*self.scale;y2=oy+a["y2"]*self.scale
            self.canvas.create_rectangle(x1,y1,x2,y2,outline="#ffcc00",width=2)
            self.canvas.create_text(x1+3,y1+3,anchor="nw",text=f"{n} {a['class']}",fill="#ffcc00",font=("Segoe UI",9,"bold"))

    def canvas_to_image(self,x,y):
        ox,oy=self.offset
        if self.scale<=0:return None
        ix=(x-ox)/self.scale;iy=(y-oy)/self.scale
        w,h=self.current_pil.size
        return max(0,min(w,ix)),max(0,min(h,iy))

    def on_press(self,e):
        if self.negative.get():return
        self.drag_start=(e.x,e.y);self.temp_rect=self.canvas.create_rectangle(e.x,e.y,e.x,e.y,outline="#00ff99",width=2,dash=(4,2))
    def on_drag(self,e):
        if self.drag_start and self.temp_rect:self.canvas.coords(self.temp_rect,self.drag_start[0],self.drag_start[1],e.x,e.y)
    def on_release(self,e):
        if not self.drag_start:return
        a=self.canvas_to_image(*self.drag_start);b=self.canvas_to_image(e.x,e.y);self.drag_start=None
        if self.temp_rect:self.canvas.delete(self.temp_rect);self.temp_rect=None
        if not a or not b:return
        x1,x2=sorted((a[0],b[0]));y1,y2=sorted((a[1],b[1]))
        if x2-x1<8 or y2-y1<8:return
        self.images[self.idx].setdefault("annotations",[]).append({"class":self.class_var.get(),"x1":round(x1,1),"y1":round(y1,1),"x2":round(x2,1),"y2":round(y2,1)})
        self.negative.set(False);self.refresh_list();self.render()

    def refresh_list(self):
        self.listbox.delete(0,"end")
        for n,a in enumerate(self.images[self.idx].get("annotations",[]),1):
            self.listbox.insert("end",f"{n}. {a['class']}  ({int(a['x1'])},{int(a['y1'])})-({int(a['x2'])},{int(a['y2'])})")
    def delete_box(self):
        s=self.listbox.curselection()
        if not s:return
        del self.images[self.idx]["annotations"][s[0]];self.refresh_list();self.render()
    def clear_boxes(self):
        if messagebox.askyesno("Clear annotations","Delete all boxes on this image?",parent=self.win):
            self.images[self.idx]["annotations"]=[];self.refresh_list();self.render()
    def neg_changed(self):
        if self.negative.get() and self.images[self.idx].get("annotations"):
            if messagebox.askyesno("Negative image","Marking this image negative will delete its equipment boxes. Continue?",parent=self.win):
                self.images[self.idx]["annotations"]=[];self.refresh_list();self.render()
            else:self.negative.set(False)
    def prev(self):
        self.persist_current_fields()
        if self.idx>0:self.idx-=1;self.load_image()
    def next(self):
        self.persist_current_fields()
        if self.idx<len(self.images)-1:self.idx+=1;self.load_image()
    def save(self):
        self.persist_current_fields()
        for rec in self.images:ensure_yolo_label(rec)
        save_dataset_labels(self.data);self.app.apply_human_labels();self.app.refresh()
        self.app.st.set(f"Saved labels for {self.z.get('facility') or self.z.get('address')} to {dataset_root()}")
    def close(self):
        self.save();self.win.destroy()


class App:
    def __init__(self,r):
        self.r=r;self.rows=[];self.label_data=load_dataset_labels();r.title("HVAC Territory Discovery v0.10.0 — Review & Label");r.geometry("1600x900")
        t=ttk.Frame(r,padding=10);t.pack(fill="x")
        ttk.Label(t,text="Virginia Beach test center:").grid(row=0,column=0)
        self.q=tk.StringVar(value="717 General Booth Blvd");ttk.Entry(t,textvariable=self.q,width=36).grid(row=0,column=1,padx=5)
        ttk.Label(t,text="Radius mi:").grid(row=0,column=2);self.rad=tk.StringVar(value="1.0");ttk.Entry(t,textvariable=self.rad,width=6).grid(row=0,column=3)
        ttk.Label(t,text="Size threshold ft²:").grid(row=0,column=4);self.mn=tk.StringVar(value="10000");ttk.Entry(t,textvariable=self.mn,width=8).grid(row=0,column=5)
        self.b=ttk.Button(t,text="Discover + Prescreen",command=self.start);self.b.grid(row=0,column=6,padx=8)
        self.st=tk.StringVar(value="GIS discovery + human review. Labels build a reusable HVAC aerial training dataset.")
        ttk.Label(r,textvariable=self.st).pack(fill="x",padx=10)

        cs=("rank","facility","address","largest","bldgs","inspect","miles","land","tier","pre","gis","human","boxes","source")
        self.tree=ttk.Treeview(r,columns=cs,show="headings")
        widths=(45,230,190,80,55,60,60,170,70,55,55,80,60,95)
        for c,w in zip(cs,widths):self.tree.heading(c,text=c.upper());self.tree.column(c,width=w,anchor="w")
        self.tree.pack(fill="both",expand=True,padx=10,pady=8)
        self.tree.bind("<Double-1>",lambda e:self.review_selected())

        f=ttk.Frame(r,padding=10);f.pack(fill="x")
        ttk.Button(f,text="Download Aerial",command=self.dl).pack(side="left")
        ttk.Button(f,text="Save Campus Images",command=self.save_campus).pack(side="left",padx=8)
        ttk.Button(f,text="Review / Label Selected",command=self.review_selected).pack(side="left",padx=8)
        ttk.Button(f,text="Export Dataset ZIP",command=self.export_zip).pack(side="left",padx=8)
        ttk.Button(f,text="Copy Address",command=self.copy).pack(side="left",padx=8)
        ttk.Button(f,text="Dataset Summary",command=self.dataset_summary).pack(side="right",padx=8)

    def start(self):
        self.b.config(state="disabled");self.st.set("Querying GIS and applying non-vision prescreen...");threading.Thread(target=self.work,daemon=True).start()
    def work(self):
        try:
            x,y=geocode(self.q.get().strip());mn=float(self.mn.get());self.rows,np,nb,nj,src,errs=discover(x,y,float(self.rad.get()),mn)
            self.diag=(np,nb,nj,src,errs);self.apply_human_labels();self.r.after(0,self.show)
        except Exception as e:self.r.after(0,lambda e=e:self.fail(e))
    def apply_human_labels(self):
        sites=self.label_data.get("sites",{})
        for z in self.rows:
            s=sites.get(site_key(z),{});z["human_rating"]=s.get("rating","") if s.get("rating")!="UNRATED" else ""
            z["human_boxes"]=sum(len(x.get("annotations",[])) for x in s.get("images",[]))
    def rowvals(self,n,z):
        fmt=lambda v:f"{v:,}" if v is not None else "UNKNOWN"
        return (n,z.get("facility","") or "",z.get("address","") or "",fmt(z.get("largest")),z.get("count",0),len(meaningful_buildings(z)),
                z.get("distance",""),z.get("land",""),z.get("tier",""),"YES" if z.get("pre") else "NO",z.get("score",""),
                z.get("human_rating",""),z.get("human_boxes",0),z.get("source",""))
    def show(self):
        for i in self.tree.get_children():self.tree.delete(i)
        for n,z in enumerate(self.rows,1):self.tree.insert("","end",iid=str(n-1),values=self.rowvals(n,z))
        pre=sum(bool(z.get("pre")) for z in self.rows);np,nb,nj,src,errs=self.diag;warn=(" | fallback: "+errs[0][:70]) if errs and src!="VB CITY" else ""
        self.st.set(f"{len(self.rows)} discovered | {pre} pass prescreen | parcels {np} | footprints {nb} | joined {nj} | {src}{warn}");self.b.config(state="normal")
    def refresh(self):
        self.apply_human_labels();self.rows.sort(key=lambda z:(0 if z.get("human_rating")=="GOOD" else 1 if z.get("human_rating")=="MAYBE" else 2 if z.get("human_rating")=="POOR" else 3,
                                                          0 if z.get("pre") else 1,-z.get("score",0),-(z.get("largest") or 0)))
        for i in self.tree.get_children():self.tree.delete(i)
        for n,z in enumerate(self.rows,1):self.tree.insert("","end",iid=str(n-1),values=self.rowvals(n,z))
    def fail(self,e):self.st.set("Failed: "+repr(e));self.b.config(state="normal")
    def selidx(self):
        s=self.tree.selection()
        if not s:messagebox.showinfo("Select","Select a candidate.");return None
        return int(s[0])
    def dl(self):
        i=self.selidx()
        if i is None:return
        z=self.rows[i];out=Path.home()/"Downloads"/f'HVAC_{safe_name(z.get("address") or "candidate")}.jpg';self.st.set("Downloading aerial...")
        def w():
            try:aerial(z["lon"],z["lat"],z.get("largest"),out);self.r.after(0,lambda:self.st.set("Saved "+str(out)))
            except Exception as e:self.r.after(0,lambda:self.st.set("Download failed: "+repr(e)))
        threading.Thread(target=w,daemon=True).start()
    def save_campus(self):
        i=self.selidx()
        if i is None:return
        z=self.rows[i];out=Path.home()/"Downloads"/f"HVAC_CAMPUS_{safe_name(z.get('address') or 'candidate')}";self.st.set("Generating campus/building images...")
        def w():
            try:
                imgs=campus_images(z,out);(out/"README.txt").write_text("00 is campus overview. B images are centered on meaningful associated buildings and include perimeter.\n\n"+"\n".join(f"{label}: {Path(p).name}" for label,p,_ in imgs))
                self.r.after(0,lambda:self.st.set(f"Saved {len(imgs)} campus images to {out}"))
            except Exception as e:self.r.after(0,lambda e=e:self.st.set("Save campus images failed: "+repr(e)))
        threading.Thread(target=w,daemon=True).start()
    def review_selected(self):
        i=self.selidx()
        if i is None:return
        self.st.set("Generating review images...")
        z=self.rows[i]
        def w():
            try:
                safe=safe_name((z.get("facility") or "")+"_"+(z.get("address") or ""))
                work=Path(tempfile.gettempdir())/f"hvac_label_{safe}_{abs(hash((z.get('lon'),z.get('lat'))))}"
                imgs=campus_images(z,work)
                self.r.after(0,lambda imgs=imgs:ReviewWindow(self,z,imgs))
                self.r.after(0,lambda:self.st.set("Review images ready. Draw boxes around known equipment."))
            except Exception as e:self.r.after(0,lambda e=e:self.st.set("Review failed: "+repr(e)))
        threading.Thread(target=w,daemon=True).start()
    def export_zip(self):
        try:save_dataset_labels(self.label_data);out=export_dataset_zip();self.st.set(f"Dataset exported: {out}")
        except Exception as e:self.st.set("Dataset export failed: "+repr(e))
    def dataset_summary(self):
        sites=self.label_data.get("sites",{});ratings={k:0 for k in ("GOOD","MAYBE","POOR","UNRATED")};boxes=neg=images=0;counts={k:0 for k,_ in EQUIPMENT_CLASSES}
        for s in sites.values():
            ratings[s.get("rating","UNRATED")]=ratings.get(s.get("rating","UNRATED"),0)+1
            for rec in s.get("images",[]):
                images+=1;neg+=1 if rec.get("negative") else 0
                for a in rec.get("annotations",[]):boxes+=1;counts[a.get("class")]=counts.get(a.get("class"),0)+1
        txt=f"Sites: {len(sites)}\nGOOD {ratings.get('GOOD',0)} | MAYBE {ratings.get('MAYBE',0)} | POOR {ratings.get('POOR',0)} | UNRATED {ratings.get('UNRATED',0)}\nImages: {images} | negative images: {neg} | boxes: {boxes}\n\n"
        txt+="\n".join(f"{k}: {counts.get(k,0)}" for k,_ in EQUIPMENT_CLASSES);messagebox.showinfo("Training Dataset Summary",txt)
    def copy(self):
        i=self.selidx()
        if i is not None:
            z=self.rows[i];self.r.clipboard_clear();self.r.clipboard_append(z.get("address","") or "");self.st.set("Address copied.")

if __name__=="__main__":
    r=tk.Tk();App(r);r.mainloop()
