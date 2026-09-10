import base64,json,math,threading,tkinter as tk,urllib.parse,urllib.request,tempfile,time,shutil,sys,os,subprocess,csv
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
    req=urllib.request.Request(u+"?"+q,headers={"User-Agent":"HVAC-Territory/0.11.0"})
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


from datetime import datetime
from PIL import Image,ImageTk,ImageDraw
import numpy as np

APP_VERSION='0.11.0'
CANDIDATE_THRESHOLD=0.07
TOWER_CHILLER_THRESHOLD=0.35
LARGE_PACKAGED_THRESHOLD=0.45
DISPLAY={'COOLING_TOWER':'Tower','AIR_COOLED_CHILLER':'Chiller','LARGE_PACKAGED_HVAC':'Large pkg'}

def safe_name(s):
    s=''.join(c if c.isalnum() or c in '-_' else '_' for c in (s or 'candidate'))
    while '__' in s:s=s.replace('__','_')
    return s.strip('_') or 'candidate'

def resource_path(*parts):
    return Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent)).joinpath(*parts)

def box_iou(a,b):
    x1=max(a[0],b[0]);y1=max(a[1],b[1]);x2=min(a[2],b[2]);y2=min(a[3],b[3])
    inter=max(0,x2-x1)*max(0,y2-y1)
    if inter<=0:return 0.0
    aa=max(0,a[2]-a[0])*max(0,a[3]-a[1]);bb=max(0,b[2]-b[0])*max(0,b[3]-b[1])
    return inter/max(aa+bb-inter,1e-9)

def square_crop(box,w,h,scale=1.8,min_side=96,max_side=1024):
    x1,y1,x2,y2=box;cx=(x1+x2)/2;cy=(y1+y2)/2
    side=max(x2-x1,y2-y1)*scale;side=max(side,min_side);side=min(side,max_side,w,h)
    a=cx-side/2;b=cy-side/2;c=cx+side/2;d=cy+side/2
    if a<0:c-=a;a=0
    if b<0:d-=b;b=0
    if c>w:a-=c-w;c=w
    if d>h:b-=d-h;d=h
    return int(max(0,a)),int(max(0,b)),int(min(w,c)),int(min(h,d))

def softmax(x):
    x=x-np.max(x);e=np.exp(x);return e/np.sum(e)

class LocalCV:
    def __init__(self,progress=None):
        if progress:progress('Loading frozen v0.0.12 local models...')
        os.environ.setdefault('YOLO_CONFIG_DIR',str(Path.home()/'.hvac_territory_ultralytics'))
        import torch
        import torch.nn as nn
        from torchvision import transforms
        from torchvision.models import resnet18
        from ultralytics import YOLO
        self.torch=torch
        try:torch.set_num_threads(max(1,min(8,(os.cpu_count() or 4)-1)))
        except:pass
        self.candidate=YOLO(str(resource_path('models','candidate.pt')))
        self.embedder=resnet18(weights=None);self.embedder.fc=nn.Identity()
        self.embedder.load_state_dict(torch.load(resource_path('models','resnet18_embedder_state.pt'),map_location='cpu'))
        self.embedder.eval()
        self.tf=transforms.Compose([transforms.Resize((224,224)),transforms.ToTensor(),transforms.Normalize([0.485,0.456,0.406],[0.229,0.224,0.225])])
        v=json.loads(resource_path('models','verifier_runtime.json').read_text())
        self.mean=np.asarray(v['scaler_mean'],dtype=np.float32);self.scale=np.asarray(v['scaler_scale'],dtype=np.float32)
        self.coef=np.asarray(v['coef'],dtype=np.float32);self.intercept=np.asarray(v['intercept'],dtype=np.float32)
        self.idname={int(k):v for k,v in v['class_names_by_id'].items()}
        if progress:progress('Local CV ready.')

    def positions(self,n):
        return [0] if n<=1024 else [0,n-1024]

    def verify(self,tile,pb,conf,source_name):
        crop=tile.crop(square_crop(pb,tile.width,tile.height)).convert('RGB')
        x=self.tf(crop).unsqueeze(0)
        with self.torch.no_grad():f=self.embedder(x).cpu().numpy()
        f=f/np.maximum(np.linalg.norm(f,axis=1,keepdims=True),1e-9)
        x1,y1,x2,y2=pb;T=1024.0;bw=max(x2-x1,1);bh=max(y2-y1,1);wf=bw/T;hf=bh/T;area=wf*hf
        num=np.array([[float(conf),wf,hf,area,math.log(max(wf,1e-6)/max(hf,1e-6)),(x1+x2)/2/T,(y1+y2)/2/T,
                       max(0,min(x1,y1,T-x2,T-y2))/T,1.0 if 'CAMPUS_OVERVIEW' in source_name.upper() else 0.0]],dtype=np.float32)
        for col in (1,2,3):num[:,col]=np.log(np.maximum(num[:,col],1e-6))
        feat=np.concatenate([f,num],axis=1)[0];xs=(feat-self.mean)/self.scale
        probs=softmax(xs@self.coef.T+self.intercept);target=probs[1:];pid=int(np.argmax(target))+1;p=float(np.sum(target))
        thr=LARGE_PACKAGED_THRESHOLD if pid==3 else TOWER_CHILLER_THRESHOLD
        return self.idname[pid],p,float(probs[0]),p>=thr

    def scan_image(self,path,tile_dir):
        im=Image.open(path).convert('RGB');w,h=im.size;dets=[];props=0
        for x0 in self.positions(w):
            for y0 in self.positions(h):
                tw=min(1024,w-x0);th=min(1024,h-y0);tile=im.crop((x0,y0,x0+tw,y0+th)).convert('RGB')
                tp=Path(tile_dir)/f'{Path(path).stem}__x{x0}_y{y0}.jpg';tile.save(tp,quality=92)
                r=self.candidate.predict(source=str(tp),imgsz=1024,conf=CANDIDATE_THRESHOLD,iou=.50,verbose=False,device='cpu')[0]
                if r.boxes is None:continue
                xy=r.boxes.xyxy.detach().cpu().numpy();cf=r.boxes.conf.detach().cpu().numpy();props+=len(xy)
                for bb,cc in zip(xy,cf):
                    pb=tuple(map(float,bb.tolist()));typ,p,rej,keep=self.verify(tile,pb,float(cc),Path(path).name)
                    if keep:dets.append({'box':(pb[0]+x0,pb[1]+y0,pb[2]+x0,pb[3]+y0),'type':typ,'p':p,'candidate':float(cc),'reject':rej})
        dets.sort(key=lambda d:(d['p'],d['candidate']),reverse=True);keep=[]
        for d in dets:
            if any(box_iou(d['box'],k['box'])>=.45 for k in keep):continue
            keep.append(d)
        return im,keep,props

    def scan_property(self,views,site_dir,progress=None):
        site_dir=Path(site_dir);ann=site_dir/'annotated';tiles=site_dir/'_tiles';ann.mkdir(parents=True,exist_ok=True);tiles.mkdir(parents=True,exist_ok=True)
        all_d=[];props=0;viewrows=[]
        try:
            for i,(label,path,b) in enumerate(views,1):
                if progress:progress(f'{label} ({i}/{len(views)})')
                im,dets,np_=self.scan_image(path,tiles);props+=np_
                for d in dets:d['view']=label;d['image']=Path(path).name
                all_d.extend(dets);viewrows.append({'view':label,'image':Path(path).name,'stage1_proposals':np_,'retained':len(dets)})
                if dets:
                    dr=ImageDraw.Draw(im)
                    for d in dets:
                        x1,y1,x2,y2=d['box'];txt=f"{DISPLAY.get(d['type'],d['type'])} {d['p']:.2f}"
                        dr.rectangle((x1,y1,x2,y2),outline='red',width=5);dr.rectangle((x1,max(0,y1-24),x1+max(120,len(txt)*8),y1),fill='red');dr.text((x1+3,max(0,y1-21)),txt,fill='white')
                    im.save(ann/Path(path).name,quality=93)
            hits={k:0 for k in DISPLAY};maxp=0.0
            for d in all_d:
                if d['type'] in hits:hits[d['type']]+=1
                maxp=max(maxp,d['p'])
            out={'status':'SURFACE' if all_d else 'QUIET','hits':hits,'max_prob':maxp,'stage1_proposals':props,'retained_evidence':len(all_d),'views':viewrows,'detections':all_d}
            (site_dir/'cv_result.json').write_text(json.dumps(out,indent=2,default=float))
            return out
        finally:shutil.rmtree(tiles,ignore_errors=True)

def hit_text(cv):
    h=cv['hits'];q=[]
    if h['COOLING_TOWER']:q.append(f"Tower {h['COOLING_TOWER']}")
    if h['AIR_COOLED_CHILLER']:q.append(f"Chiller {h['AIR_COOLED_CHILLER']}")
    if h['LARGE_PACKAGED_HVAC']:q.append(f"Large pkg {h['LARGE_PACKAGED_HVAC']}")
    return ' | '.join(q)

def opportunity_score(z,cv):
    h=cv['hits'];t=h['COOLING_TOWER'];c=h['AIR_COOLED_CHILLER'];p=h['LARGE_PACKAGED_HVAC']
    if t:base=94
    elif c:base=91
    elif p>=3:base=84
    elif p:base=76
    else:return 0
    if sum(x>0 for x in (t,c,p))>=2:base+=3
    base+=min(2,int(round(cv['max_prob']*2)));base+=min(2,int((z.get('score') or 0)/45))
    return min(99,int(base))

class DetailWindow:
    def __init__(self,parent,z):
        w=tk.Toplevel(parent);w.title(f"Prospect Detail — {z.get('facility') or z.get('address')}");w.geometry('900x650')
        txt=tk.Text(w,wrap='word',font=('Segoe UI',10));txt.pack(fill='both',expand=True,padx=10,pady=10)
        lines=[f"FACILITY: {z.get('facility','')}",f"ADDRESS: {z.get('address','')}",f"CV: {z.get('cv_status','NOT SCANNED')}",
               f"OPPORTUNITY SCORE: {z.get('cv_score','')}",f"MODEL EVIDENCE HITS: {z.get('cv_equipment','')}",
               f"MAX HIGH-VALUE PROBABILITY: {'' if z.get('cv_max_prob') is None else str(round(100*z['cv_max_prob']))+'%'}",
               f"GIS TIER / SCORE: {z.get('tier','')} / {z.get('score','')}",f"LAND USE: {z.get('land','')}",
               f"LARGEST BUILDING: {z.get('largest') or 'UNKNOWN'} ft²",f"BUILDINGS: {z.get('count',0)}",f"DISTANCE: {z.get('distance','')} mi",
               '',"Model evidence hits are not guaranteed physical unit counts because campus and building views can overlap.",
               "QUIET does not prove no valuable mechanical opportunity exists."]
        txt.insert('1.0','\n'.join(lines));txt.config(state='disabled')

class App:
    def __init__(self,r):
        self.r=r;self.rows=[];self.cv=None;self.scan_running=False;self.last_scan_root=None
        r.title('HVAC Territory Discovery v0.11.0 — Local CV Prospecting');r.geometry('1720x900')
        t=ttk.Frame(r,padding=10);t.pack(fill='x')
        ttk.Label(t,text='Virginia Beach center:').grid(row=0,column=0);self.q=tk.StringVar(value='717 General Booth Blvd');ttk.Entry(t,textvariable=self.q,width=36).grid(row=0,column=1,padx=5)
        ttk.Label(t,text='Radius mi:').grid(row=0,column=2);self.rad=tk.StringVar(value='1.0');ttk.Entry(t,textvariable=self.rad,width=6).grid(row=0,column=3)
        ttk.Label(t,text='Size threshold ft²:').grid(row=0,column=4);self.mn=tk.StringVar(value='10000');ttk.Entry(t,textvariable=self.mn,width=8).grid(row=0,column=5)
        self.discb=ttk.Button(t,text='1. Discover + Prescreen',command=self.start);self.discb.grid(row=0,column=6,padx=8)
        self.scanb=ttk.Button(t,text='2. Analyze Prescreened',command=self.analyze_prescreened);self.scanb.grid(row=0,column=7,padx=5)
        self.st=tk.StringVar(value='Frozen local v0.0.12 CV — 0.07 / 0.35 / 0.45. No API key required.');ttk.Label(r,textvariable=self.st).pack(fill='x',padx=10)
        cols=('rank','facility','address','cv','opp','evidence','maxp','largest','bldgs','mi','land','tier','pre','gis','source')
        heads={'rank':'RANK','facility':'FACILITY','address':'ADDRESS','cv':'CV','opp':'OPP','evidence':'MODEL EVIDENCE HITS','maxp':'MAX P','largest':'LARGEST','bldgs':'BLDGS','mi':'MI','land':'LAND USE','tier':'GIS TIER','pre':'PRE','gis':'GIS','source':'FOOTPRINT'}
        widths=(45,220,180,75,55,230,60,85,55,55,155,70,50,55,95)
        self.tree=ttk.Treeview(r,columns=cols,show='headings')
        for c,w in zip(cols,widths):self.tree.heading(c,text=heads[c]);self.tree.column(c,width=w,anchor='w')
        self.tree.pack(fill='both',expand=True,padx=10,pady=8);self.tree.bind('<Double-1>',lambda e:self.details())
        f=ttk.Frame(r,padding=10);f.pack(fill='x')
        self.selb=ttk.Button(f,text='Analyze Selected',command=self.analyze_selected);self.selb.pack(side='left')
        ttk.Button(f,text='Prospect Details',command=self.details).pack(side='left',padx=7);ttk.Button(f,text='Open Scan Folder',command=self.open_folder).pack(side='left',padx=7)
        ttk.Separator(f,orient='vertical').pack(side='left',fill='y',padx=6);ttk.Button(f,text='Download Aerial',command=self.download_aerial).pack(side='left')
        ttk.Button(f,text='Save Campus Images',command=self.save_campus).pack(side='left',padx=7);ttk.Button(f,text='Copy Address',command=self.copy_address).pack(side='left',padx=7)

    def start(self):
        if self.scan_running:return
        self.discb.config(state='disabled');self.st.set('Querying GIS and applying high-recall prescreen...');threading.Thread(target=self.work,daemon=True).start()
    def work(self):
        try:
            x,y=geocode(self.q.get().strip());self.rows,np_,nb,nj,src,errs=discover(x,y,float(self.rad.get()),float(self.mn.get()));self.diag=(np_,nb,nj,src,errs)
            for z in self.rows:z.update(cv_status='',cv_score=None,cv_equipment='',cv_max_prob=None,cv_folder='')
            self.r.after(0,self.show)
        except Exception as e:self.r.after(0,lambda e=e:self.fail(e))
    def show(self):
        self.refresh();pre=sum(bool(z.get('pre')) for z in self.rows);np_,nb,nj,src,errs=self.diag;warn=(' | fallback: '+errs[0][:70]) if errs and src!='VB CITY' else ''
        self.st.set(f'{len(self.rows)} discovered | {pre} pass prescreen | parcels {np_} | footprints {nb} | joined {nj} | {src}{warn}');self.discb.config(state='normal')
    def refresh(self):
        def k(z):
            s=z.get('cv_status','');rank={'SURFACE':0,'QUIET':1,'ERROR':2,'':3}.get(s,3)
            return (rank,-(z.get('cv_score') or 0),0 if z.get('pre') else 1,-(z.get('score') or 0),-(z.get('largest') or 0))
        self.rows.sort(key=k)
        for x in self.tree.get_children():self.tree.delete(x)
        for n,z in enumerate(self.rows,1):
            mp='' if z.get('cv_max_prob') is None else f"{100*z['cv_max_prob']:.0f}%";opp='' if z.get('cv_score') is None else z['cv_score'];largest='UNKNOWN' if z.get('largest') is None else f"{z['largest']:,}"
            self.tree.insert('', 'end', iid=str(n-1), values=(n,z.get('facility',''),z.get('address',''),z.get('cv_status',''),opp,z.get('cv_equipment',''),mp,largest,z.get('count',0),z.get('distance',''),z.get('land',''),z.get('tier',''),'YES' if z.get('pre') else 'NO',z.get('score',''),z.get('source','')))
    def fail(self,e):self.st.set('Failed: '+repr(e));self.discb.config(state='normal')
    def sel(self):
        s=self.tree.selection()
        if not s:messagebox.showinfo('Select','Select a candidate.');return None
        return self.rows[int(s[0])]
    def engine(self):
        if self.cv is None:self.cv=LocalCV(lambda msg:self.r.after(0,lambda msg=msg:self.st.set(msg)))
        return self.cv
    def analyze_prescreened(self):
        if self.scan_running:return
        q=[z for z in self.rows if z.get('pre')]
        if not q:messagebox.showinfo('Analyze','Run discovery first; no prescreened properties are available.');return
        self.begin_scan(q)
    def analyze_selected(self):
        if self.scan_running:return
        z=self.sel()
        if z:self.begin_scan([z])
    def begin_scan(self,sites):
        self.scan_running=True;self.scanb.config(state='disabled');self.selb.config(state='disabled');threading.Thread(target=self.scan_worker,args=(list(sites),),daemon=True).start()
    def scan_worker(self,sites):
        stamp=datetime.now().strftime('%Y%m%d_%H%M%S');root=Path.home()/'Downloads'/f'HVAC_Prospecting_Scan_{stamp}';root.mkdir(parents=True,exist_ok=True);self.last_scan_root=root;rows=[]
        try:
            eng=self.engine()
            for n,z in enumerate(sites,1):
                fac=z.get('facility') or z.get('address') or f'site_{n}';folder=root/f"{n:03d}_{safe_name(fac+'_'+(z.get('address') or ''))[:100]}"
                self.r.after(0,lambda n=n,fac=fac:self.st.set(f'Scanning {n}/{len(sites)} — {fac}'))
                views=campus_images(z,folder/'source');cv=eng.scan_property(views,folder,lambda m,n=n,fac=fac:self.r.after(0,lambda m=m,n=n,fac=fac:self.st.set(f'{n}/{len(sites)} {fac}: {m}')))
                z['cv_status']=cv['status'];z['cv_score']=opportunity_score(z,cv);z['cv_equipment']=hit_text(cv);z['cv_max_prob']=cv['max_prob'];z['cv_folder']=str(folder)
                rows.append({'facility':z.get('facility',''),'address':z.get('address',''),'cv_status':z['cv_status'],'opportunity_score':z['cv_score'],'model_evidence_hits':z['cv_equipment'],'max_high_value_probability':round(cv['max_prob'],4),'stage1_proposals':cv['stage1_proposals'],'retained_evidence':cv['retained_evidence'],'gis_score':z.get('score',''),'gis_tier':z.get('tier',''),'prescreen':z.get('pre',False),'largest_building_ft2':z.get('largest',''),'building_count':z.get('count',0),'land_use':z.get('land',''),'distance_miles':z.get('distance',''),'result_folder':str(folder)})
                self.write_csv(root,rows);self.r.after(0,self.refresh)
            surf=sum(r['cv_status']=='SURFACE' for r in rows);(root/'SCAN_SUMMARY.txt').write_text(f'HVAC Territory Discovery v0.11.0\nFrozen pipeline v0.0.12\nThresholds 0.07 / 0.35 / 0.45\n\nProperties analyzed: {len(rows)}\nSurfaced: {surf}\nQuiet: {len(rows)-surf}\n\nEvidence hits are not exact unit counts.\n')
            self.r.after(0,lambda:self.st.set(f'Scan complete: {surf}/{len(rows)} surfaced | {root}'));self.r.after(0,lambda:messagebox.showinfo('Scan Complete',f'Analyzed {len(rows)} properties.\nSurfaced {surf}.\n\nResults:\n{root}'))
        except Exception as e:self.r.after(0,lambda e=e:messagebox.showerror('CV Scan Failed',repr(e)))
        finally:self.scan_running=False;self.r.after(0,lambda:self.scanb.config(state='normal'));self.r.after(0,lambda:self.selb.config(state='normal'))
    def write_csv(self,root,rows):
        with (root/'prospecting_results.csv').open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(rows[0].keys()));w.writeheader();w.writerows(rows)
    def details(self):
        z=self.sel()
        if z:DetailWindow(self.r,z)
    def open_folder(self):
        z=self.sel();p=Path(z['cv_folder']) if z and z.get('cv_folder') else self.last_scan_root
        if not p or not Path(p).exists():messagebox.showinfo('Scan Folder','No completed scan folder is available.');return
        p=Path(p)
        try:
            if sys.platform.startswith('win'):os.startfile(p)
            elif sys.platform=='darwin':subprocess.Popen(['open',str(p)])
            else:subprocess.Popen(['xdg-open',str(p)])
        except Exception as e:self.st.set('Open folder failed: '+repr(e))
    def download_aerial(self):
        z=self.sel()
        if not z:return
        out=Path.home()/'Downloads'/f"HVAC_{safe_name(z.get('address') or 'candidate')}.jpg";self.st.set('Downloading aerial...')
        def w():
            try:aerial(z['lon'],z['lat'],z.get('largest'),out);self.r.after(0,lambda:self.st.set('Saved '+str(out)))
            except Exception as e:self.r.after(0,lambda:self.st.set('Download failed: '+repr(e)))
        threading.Thread(target=w,daemon=True).start()
    def save_campus(self):
        z=self.sel()
        if not z:return
        out=Path.home()/'Downloads'/f"HVAC_CAMPUS_{safe_name(z.get('address') or 'candidate')}";self.st.set('Generating campus images...')
        def w():
            try:
                q=campus_images(z,out);self.r.after(0,lambda:self.st.set(f'Saved {len(q)} images to {out}'))
            except Exception as e:self.r.after(0,lambda:self.st.set('Campus image failed: '+repr(e)))
        threading.Thread(target=w,daemon=True).start()
    def copy_address(self):
        z=self.sel()
        if z:self.r.clipboard_clear();self.r.clipboard_append(z.get('address',''));self.st.set('Address copied.')

if __name__=='__main__':
    r=tk.Tk();App(r);r.mainloop()
