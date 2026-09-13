import base64,json,math,threading,tkinter as tk,urllib.parse,urllib.request,tempfile,time,shutil,sys,os,subprocess,csv,traceback
from tkinter import ttk,messagebox,filedialog,simpledialog
from pathlib import Path

ADDR="https://geo.vbgov.com/mapservices/rest/services/Business_Systems/Pictometry_Online/MapServer/0/query"
PARCEL="https://geo.vbgov.com/mapservices/rest/services/Business_Systems/Pictometry_Online/MapServer/4/query"
# City of Virginia Beach authoritative planimetric Building Footprints
CITY_BLDGS="https://geo.vbgov.com/mapservices/rest/services/Basemaps/Structures_and_Physical_Features/MapServer/6/query"
FALLBACK_BLDGS="https://dsfmportal.dcr.virginia.gov/server/rest/services/CivilReference/Civil_Reference_Layers/MapServer/2/query"
AERIAL="https://geo.vbgov.com/imageservices/rest/services/Imagery/Aerial2025/ImageServer/exportImage"

def gj(u,p):
    q=urllib.parse.urlencode(p)
    req=urllib.request.Request(u+"?"+q,headers={"User-Agent":"HVAC-Territory/0.11.6"})
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
            out.append({"lon":cx,"lat":cy,"sq":round(area(rs)),"rings":rs,
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
        p["facility"]="";p["facility_kind"]=""
        inside=[n for n in names if pinpoly(n["lon"],n["lat"],p["rings"])]
        if inside:
            inside.sort(key=lambda n:(0 if n["kind"] else 1,miles(p["lon"],p["lat"],n["lon"],n["lat"])))
            p["facility"]=inside[0]["name"];p["facility_kind"]=inside[0].get("kind","")
        else:
            near=sorted(names,key=lambda n:miles(p["lon"],p["lat"],n["lon"],n["lat"]))
            if near and miles(p["lon"],p["lat"],near[0]["lon"],near[0]["lat"])<=0.04:
                p["facility"]=near[0]["name"];p["facility_kind"]=near[0].get("kind","")

def classify(land,zone,largest,avg,count,fcodes):
    s=(land+" "+zone+" "+" ".join(fcodes)).upper()
    very_high=("HOSP","MEDICAL","UNIVERS","COLLEGE","INDUSTR","MANUFACTUR","UTILITY","PUMP STATION","SUBSTATION")
    high=("GOVERN","SCHOOL","PUBLIC/SEMI PUBLIC","WAREHOUSE","DISTRIBUT")
    low=("APART","CONDO","MULTI FAMILY","MULTIFAMILY","TOWN HOUSE","TOWNHOUSE","TOWNHOME","RESTAUR","RETAIL","SHOPPING","STORE","SINGLE FAMILY","DUPLEX")
    medium=("OFFICE","HOTEL","MOTEL","CHURCH","RELIG","ASSEMBLY","ENTERTAIN","AUTO","COMMERCIAL","MILITARY")
    if any(k in s for k in very_high): tier,score="HIGH",82
    elif any(k in s for k in high): tier,score="HIGH",74
    elif any(k in s for k in low): tier,score="LOW",18
    elif any(k in s for k in medium): tier,score="MEDIUM",52
    else:tier,score="UNKNOWN",42

    if largest:
        score += 16 if largest>=100000 else 13 if largest>=75000 else 9 if largest>=40000 else 5 if largest>=20000 else 2 if largest>=10000 else 0
    if avg:
        score += 5 if avg>=40000 else 3 if avg>=20000 else 0
    if count>=20 and avg and avg<10000:score-=28
    elif count>=10 and avg and avg<10000:score-=20
    elif count>=6 and avg and avg<7000:score-=14
    if largest is None:score-=10
    return tier,max(0,min(99,score))

def property_context(p):
    return " ".join(str(x or "") for x in (p.get("land"),p.get("zone"),p.get("facility"),p.get("facility_kind")," ".join(p.get("fcodes",[])))).upper()

def campus_buffer_ft(p):
    """Small ordinary parcel tolerance; broader only for true institutional/industrial campuses.
    Broader campus detections are surfaced as adjacent evidence, not blindly attributed as in-parcel equipment.
    """
    ctx=property_context(p);count=p.get("count",0) or 0
    if p.get("storage_like") or any(k in ctx for k in ("PUBLIC STORAGE","SELF STORAGE","MINI STORAGE","TOWN HOUSE","TOWNHOUSE","TOWNHOME","APART","CONDO")):
        return PARCEL_BUFFER_FT
    if any(k in ctx for k in ("UNIVERS","COLLEGE","VIRGINIA TECH","HOSP","MEDICAL CENTER","MILITARY","SCHOOL CAMPUS")):
        return 180.0
    if count>=4 and any(k in ctx for k in ("INDUSTR","MANUFACTUR","UTILITY","GOVERN","SCHOOL")):
        return 75.0
    return PARCEL_BUFFER_FT

def building_elongation(b):
    """Rotation-independent footprint elongation from the building's longest ring."""
    rings=b.get("rings") or []
    if not rings:return 1.0
    ring=max(rings,key=len);pts=ring[:-1] if len(ring)>2 and ring[0]==ring[-1] else ring
    if len(pts)<3:return 1.0
    lat=sum(q[1] for q in pts)/len(pts);c=math.cos(math.radians(lat))
    xy=[(q[0]*69.172*c*5280,q[1]*69*5280) for q in pts]
    mx=sum(q[0] for q in xy)/len(xy);my=sum(q[1] for q in xy)/len(xy)
    xx=sum((q[0]-mx)**2 for q in xy)/len(xy);yy=sum((q[1]-my)**2 for q in xy)/len(xy)
    xyv=sum((q[0]-mx)*(q[1]-my) for q in xy)/len(xy)
    disc=math.sqrt(max(0.0,(xx-yy)**2+4*xyv*xyv));hi=(xx+yy+disc)/2;lo=(xx+yy-disc)/2
    return math.sqrt(max(hi,1e-9)/max(lo,1e-9))

def repetitive_storage_like(p):
    """Identify self-storage morphology without sacrificing real campuses.

    Explicit storage coding is decisive. Otherwise require a dense, highly repetitive set of
    small elongated footprints. Institutional, industrial and public/semi-public sites are
    protected because laboratories, greenhouses and military campuses can share that geometry.
    """
    ctx=property_context(p)
    if any(k in ctx for k in ("PUBLIC STORAGE","SELF STORAGE","MINI STORAGE")):return True
    protected=any(k in ctx for k in ("UNIVERS","COLLEGE","VIRGINIA TECH","MILITARY","HOSP","MEDICAL",
                                      "PUBLIC/SEMI PUBLIC","MANUFACTUR","UTILITY","GOVERN","SCHOOL",
                                      "PUMP STATION","SUBSTATION"))
    if protected:return False
    bs=p.get("buildings") or [];count=len(bs) or (p.get("count",0) or 0)
    largest=p.get("largest");avg=p.get("avg")
    if count<8 or largest is None or largest>=18000 or (avg is not None and avg>=11000):return False
    if not bs:return False
    small=sum((b.get("sq") or 0)<15000 for b in bs)/max(1,len(bs))
    elongated=sum(building_elongation(b)>=2.4 for b in bs)/max(1,len(bs))
    return small>=0.85 and elongated>=0.65

def ambiguous_small_public_site(p):
    """Reject small residential-scale parcels hidden behind a generic public-use code.

    Virginia Beach parcel data can label whole residential common-interest areas Public/Semi
    Public.  A nearby road/court name may then be attached as the facility name.  Preserve small
    sites only when the name, OSM kind, or building code identifies a real institutional or utility
    use; otherwise there is not enough nonresidential evidence to spend an imagery scan on them.
    """
    land=str(p.get("land") or "").upper();largest=p.get("largest");count=p.get("count",0) or 0
    if "PUBLIC/SEMI PUBLIC" not in land or largest is None or largest>=8000 or count>2:return False
    identity=" ".join(str(x or "") for x in (p.get("facility"),p.get("facility_kind")," ".join(p.get("fcodes",[])))).upper()
    identified=any(k in identity for k in (
        "HOSP","MEDICAL","CLINIC","UNIVERS","COLLEGE","SCHOOL","ACADEMY","DAYCARE",
        "CHURCH","RELIG","WORSHIP","MOSQUE","SYNAGOG","GOVERN","MUNICIPAL","CITY OF",
        "COUNTY","FIRE","POLICE","LIBRARY","UTILITY","PUMP","SUBSTATION","WATER TREATMENT",
        "WASTEWATER","MILITARY"))
    return not identified

def prescreen(p,mn):
    """Cheap precision-first non-vision gate with campus protection."""
    ctx=property_context(p);largest=p.get("largest");avg=p.get("avg");count=p.get("count",0)
    residential=any(k in ctx for k in ("SINGLE FAMILY","DUPLEX","MULTI FAMILY","MULTIFAMILY","APART","CONDO","TOWN HOUSE","TOWNHOUSE","TOWNHOME"))
    poor_use=any(k in ctx for k in ("RESTAUR","RETAIL","SHOPPING","STORE","PUBLIC STORAGE","SELF STORAGE","MINI STORAGE"))
    strong_priority=any(k in ctx for k in ("HOSP","MEDICAL","UNIVERS","COLLEGE","INDUSTR","MANUFACTUR","UTILITY",
                                            "PUMP STATION","SUBSTATION","GOVERN","SCHOOL","MILITARY","WAREHOUSE","DISTRIBUT",
                                            "VIRGINIA TECH","PUBLIC/SEMI PUBLIC"))
    if residential:return False,"RESIDENTIAL / TOWNHOME"
    if repetitive_storage_like(p):return False,"REPETITIVE STORAGE-LIKE COMPLEX"
    if largest is None:return False,"NO FOOTPRINT"
    if ambiguous_small_public_site(p):return False,"AMBIGUOUS SMALL PUBLIC PARCEL"
    if largest>=max(mn,20000):return True,f"SIZE: largest {largest:,} ft2"
    if strong_priority and largest>=2500:return True,f"PRIORITY: {largest:,} ft2"
    if not poor_use and largest>=10000:return True,f"COMMERCIAL SIZE: {largest:,} ft2"
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
        p["storage_like"]=repetitive_storage_like(p)
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

def lonlat_offset(lon,lat,dx_ft,dy_ft):
    return (lon+dx_ft/(69.172*5280*max(.2,math.cos(math.radians(lat)))),lat+dy_ft/(69*5280))

def local_xy_ft(lon,lat,ref_lon,ref_lat):
    return ((lon-ref_lon)*69.172*math.cos(math.radians(ref_lat))*5280,(lat-ref_lat)*69*5280)

def parcel_extent(z):
    pts=[pt for r in (z.get("rings") or []) for pt in r]
    if not pts:return z["lon"],z["lat"],700.0,700.0,(-350,-350,350,350)
    ref_lon,ref_lat=centroid(z.get("rings"))
    if ref_lon is None:ref_lon,ref_lat=z["lon"],z["lat"]
    xy=[local_xy_ft(a,b,ref_lon,ref_lat) for a,b in pts]
    xs=[q[0] for q in xy];ys=[q[1] for q in xy];xmin,xmax=min(xs),max(xs);ymin,ymax=min(ys),max(ys)
    cx=(xmin+xmax)/2;cy=(ymin+ymax)/2;lon,lat=lonlat_offset(ref_lon,ref_lat,cx,cy)
    return lon,lat,max(1,xmax-xmin),max(1,ymax-ymin),(xmin,ymin,xmax,ymax)

def _point_segment_distance(px,py,ax,ay,bx,by):
    vx=bx-ax;vy=by-ay;wx=px-ax;wy=py-ay;vv=vx*vx+vy*vy
    if vv<=1e-9:return math.hypot(px-ax,py-ay)
    t=max(0.0,min(1.0,(wx*vx+wy*vy)/vv));qx=ax+t*vx;qy=ay+t*vy
    return math.hypot(px-qx,py-qy)

def point_poly_distance_ft(lon,lat,rings):
    if not rings:return 0.0
    if pinpoly(lon,lat,rings):return 0.0
    best=1e30
    for r in rings:
        if len(r)<2:continue
        xy=[local_xy_ft(a,b,lon,lat) for a,b in r]
        for i in range(len(xy)):
            a=xy[i];b=xy[(i+1)%len(xy)]
            best=min(best,_point_segment_distance(0,0,a[0],a[1],b[0],b[1]))
    return best if best<1e29 else 0.0

def meaningful_buildings(z,maxn=6):
    bs=sorted(z.get("buildings",[]),key=lambda b:b.get("sq",0),reverse=True)
    if not bs:return []
    largest=z.get("largest") or bs[0].get("sq",0) or 0
    floor=max(2500,min(6000,largest*0.03))
    keep=[b for b in bs if b.get("sq",0)>=floor]
    if not keep and bs:keep=[bs[0]]
    return keep[:maxn]

def building_focus_centers(b,ground_tile=620.0,margin=70.0,max_tiles=4):
    """Higher-resolution coverage for very large buildings and their immediate perimeter.
    This targets side-yard/edge heat-rejection equipment that can be too small in a whole-building image.
    """
    rings=b.get('rings') or []
    if not rings:return []
    ref_lon,ref_lat=centroid(rings)
    if ref_lon is None:return []
    pts=[local_xy_ft(a,c,ref_lon,ref_lat) for r in rings for a,c in r]
    if not pts:return []
    xs=[q[0] for q in pts];ys=[q[1] for q in pts];xmin,xmax=min(xs)-margin,max(xs)+margin;ymin,ymax=min(ys)-margin,max(ys)+margin
    def axis(lo,hi):
        span=hi-lo
        if span<=ground_tile*.90:return [(lo+hi)/2]
        n=max(2,int(math.ceil(span/(ground_tile*.78))))
        n=min(3,n)
        return [lo+ground_tile*.45+(max(0,span-ground_tile*.90))*i/max(1,n-1) for i in range(n)]
    cand=[(xx,yy) for yy in axis(ymin,ymax) for xx in axis(xmin,xmax)]
    if len(cand)>max_tiles:
        # Prefer perimeter-spread positions rather than repeatedly sampling the center.
        cand=sorted(cand,key=lambda q:(q[1],q[0]));idx=[round(i*(len(cand)-1)/(max_tiles-1)) for i in range(max_tiles)];cand=[cand[i] for i in sorted(set(idx))]
    return [lonlat_offset(ref_lon,ref_lat,xx,yy) for xx,yy in cand]

def _coverage_centers(z,tile_side=1100.0,max_tiles=9):
    """High-resolution parcel coverage for campuses. Overview + these tiles prevents missing a plant because footprint GIS is incomplete."""
    lon,lat,w,h,b=parcel_extent(z);xmin,ymin,xmax,ymax=b
    margin=max(0.0,campus_buffer_ft(z)-PARCEL_BUFFER_FT);xmin-=margin;xmax+=margin;ymin-=margin;ymax+=margin
    w=xmax-xmin;h=ymax-ymin
    # Only add parcel tiles when the property has campus-like morphology or a broad parcel extent.
    if z.get("count",0)<4 and max(w,h)<900 and (z.get("psq") or 0)<250000:return []
    step=tile_side*0.82
    def centers(lo,hi):
        span=hi-lo
        if span<=tile_side:return [(lo+hi)/2]
        n=max(2,int(math.ceil((span-tile_side)/step))+2)
        first=lo+tile_side/2;last=hi-tile_side/2
        if n==2:return [first,last]
        return [first+(last-first)*i/(n-1) for i in range(n)]
    xs=centers(xmin,xmax);ys=centers(ymin,ymax);cand=[]
    ref_lon,ref_lat=centroid(z.get("rings"))
    if ref_lon is None:ref_lon,ref_lat=z["lon"],z["lat"]
    for yy in ys:
        for xx in xs:
            qlon,qlat=lonlat_offset(ref_lon,ref_lat,xx,yy)
            # Retain tiles centered in/near the parcel; 0.45 tile allowance handles irregular parcels and edge buildings.
            dist=point_poly_distance_ft(qlon,qlat,z.get("rings") or [])
            if dist<=tile_side*.45:cand.append((qlon,qlat,math.hypot(xx,yy)))
    if len(cand)>max_tiles:
        # Spread selections across the full candidate list instead of only taking central tiles.
        cand=sorted(cand,key=lambda q:(q[1],q[0]))
        idx=[round(i*(len(cand)-1)/(max_tiles-1)) for i in range(max_tiles)]
        cand=[cand[i] for i in sorted(set(idx))]
    return [(a,b) for a,b,_ in cand]

def campus_images(z,root):
    root=Path(root);root.mkdir(parents=True,exist_ok=True);bs=meaningful_buildings(z);views=[]
    plon,plat,pw,ph,_=parcel_extent(z)
    campus_margin=max(0.0,campus_buffer_ft(z)-PARCEL_BUFFER_FT)
    overview_ground=max(700,max(pw+2*campus_margin,ph+2*campus_margin)*1.15+220)
    overview_side=max(700,min(2400,overview_ground/max(.72,math.cos(math.radians(plat)))))
    q=root/"00_CAMPUS_OVERVIEW.jpg";aerial_side(plon,plat,overview_side,q)
    views.append({"label":"CAMPUS OVERVIEW","path":str(q),"building":None,"lon":plon,"lat":plat,"side_ft":overview_side,"pixels":1800,"kind":"overview"})

    # Parcel-wide high-resolution coverage catches central plants on campuses even when building footprints are absent/wrong.
    for j,(lon,lat) in enumerate(_coverage_centers(z),1):
        side=min(2400,1100.0/max(.72,math.cos(math.radians(lat))));q=root/f"P{j:02d}_PARCEL_TILE.jpg";aerial_side(lon,lat,side,q)
        views.append({"label":f"PARCEL TILE {j}","path":str(q),"building":None,"lon":lon,"lat":lat,"side_ft":side,"pixels":1800,"kind":"parcel_tile"})

    # Large-building focus views trade some field of view for much better equipment scale. The added 70-ft
    # perimeter specifically targets towers/fluid coolers/chillers beside warehouse/industrial walls.
    fj=0
    for b in bs:
        if (b.get('sq') or 0)<75000:continue
        for lon,lat in building_focus_centers(b):
            fj+=1;ground=620.0;side=min(1200,ground/max(.72,math.cos(math.radians(lat))))
            q=root/f"F{fj:02d}_{int(b.get('sq',0))}sf.jpg";aerial_side(lon,lat,side,q)
            views.append({"label":f"MECH FOCUS {fj} — {int(b.get('sq',0)):,} ft2","path":str(q),"building":b,"lon":lon,"lat":lat,"side_ft":side,"pixels":1800,"kind":"building_focus"})

    for i,b in enumerate(bs,1):
        side=max(420,min(1100,math.sqrt(max(b.get("sq") or 3000,1))*3.4))
        q=root/f"B{i:02d}_{int(b.get('sq',0))}sf.jpg";aerial_side(b["lon"],b["lat"],side,q)
        views.append({"label":f"BUILDING {i} — {int(b.get('sq',0)):,} ft2","path":str(q),"building":b,"lon":b["lon"],"lat":b["lat"],"side_ft":side,"pixels":1800,"kind":"building"})

    manifest={"app_version":APP_VERSION,"address":z.get("address","")+"","facility":z.get("facility","")+"","parcel_area_ft2":round(z.get("psq") or 0),
              "parcel_extent_ft":[round(pw),round(ph)],"attribution_buffer_ft":campus_buffer_ft(z),"prescreen_reason":z.get("pre_reason",""),
              "views":[{k:v.get(k) for k in ("label","path","lon","lat","side_ft","pixels","kind")} for v in views]}
    (root/'view_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return views


from datetime import datetime
from PIL import Image,ImageTk,ImageDraw
import numpy as np

APP_VERSION='0.11.6'
CANDIDATE_THRESHOLD=0.07
TOWER_CHILLER_THRESHOLD=0.35
LARGE_PACKAGED_THRESHOLD=0.45
# Recall-rescue operating point: only used on a shifted center crop after a high-value property has no tower/chiller hit.
# Rescue evidence below the frozen 0.35 verifier threshold can only produce REVIEW, never STRONG.
THERMAL_REVIEW_THRESHOLD=0.22
THERMAL_REVIEW_CLASS_MIN=0.10
# Deep rescue deliberately lowers only Stage-1 proposal confidence. Any candidate below the frozen
# 0.07 operating point is REVIEW-only even if the Stage-2 verifier likes it.
DEEP_RESCUE_CANDIDATE_THRESHOLD=0.015
DEEP_RESCUE_MAX_DET=32
DEEP_RESCUE_MAX_VERIFY_PER_TILE=14
# Zoomed perimeter rescue makes a small side-yard machine occupy more inference pixels after the
# normal and shifted 1024px passes produce no usable thermal proposal. 512px was selected by direct
# inference on 5925 Thurston and 1444 Diamond Springs. It remains REVIEW-only.
PERIMETER_RESCUE_TILE_PX=512
PERIMETER_RESCUE_CANDIDATE_THRESHOLD=0.008
PERIMETER_RESCUE_MAX_DET=40
PERIMETER_RESCUE_MAX_VERIFY_PER_TILE=12
PERIMETER_RESCUE_MIN_P=0.55
PERIMETER_RESCUE_MIN_BEST=0.50
THERMAL_RESCUE_MAX_BUILDING_DISTANCE_FT=75.0
# STRONG thermal evidence now requires either high verifier confidence or both useful physical scale
# and reasonable class confidence. This promotes compact real chillers (1245 Miller) while demoting
# low-confidence lookalikes such as landscaping/clutter at 1400 Air Rail and 1609 Diamond Springs.
THERMAL_STRONG_HIGH_P=0.78
THERMAL_STRONG_HIGH_BEST=0.40
THERMAL_STRONG_SIZED_P=0.60
THERMAL_STRONG_SIZED_BEST=0.30
THERMAL_STRONG_MIN_FT=22.0
PACKAGE_MAX_BUILDING_DISTANCE_FT=45.0
DISPLAY={'COOLING_TOWER':'Tower','AIR_COOLED_CHILLER':'Chiller','LARGE_PACKAGED_HVAC':'Large pkg'}
PARCEL_BUFFER_FT=30.0

def safe_name(s):
    s=''.join(c if c.isalnum() or c in '-_' else '_' for c in (s or 'candidate'))
    while '__' in s:s=s.replace('__','_')
    return s.strip('_') or 'candidate'

def resource_path(*parts):
    bases=[]
    if getattr(sys,'_MEIPASS',None):
        bases.append(Path(sys._MEIPASS))
    bases.extend([
        Path(__file__).resolve().parent,
        Path(sys.executable).resolve().parent,
        Path(sys.executable).resolve().parent/'_internal',
    ])
    for base in bases:
        p=base.joinpath(*parts)
        if p.exists():
            return p
    return bases[0].joinpath(*parts)

def required_asset(*parts):
    p=resource_path(*parts)
    if p.exists():
        return p
    searched=[]
    if getattr(sys,'_MEIPASS',None):
        searched.append(str(Path(sys._MEIPASS).joinpath(*parts)))
    searched.extend([
        str(Path(__file__).resolve().parent.joinpath(*parts)),
        str(Path(sys.executable).resolve().parent.joinpath(*parts)),
        str((Path(sys.executable).resolve().parent/'_internal').joinpath(*parts)),
    ])
    raise FileNotFoundError(
        "Required model asset is missing: "+str(Path(*parts))+
        "\n\nSearched:\n- "+"\n- ".join(dict.fromkeys(searched))
    )

def box_iou(a,b):
    x1=max(a[0],b[0]);y1=max(a[1],b[1]);x2=min(a[2],b[2]);y2=min(a[3],b[3])
    inter=max(0,x2-x1)*max(0,y2-y1)
    if inter<=0:return 0.0
    aa=max(0,a[2]-a[0])*max(0,a[3]-a[1]);bb=max(0,b[2]-b[0])*max(0,b[3]-b[1])
    return inter/max(aa+bb-inter,1e-9)

def box_overlap_min(a,b):
    """Intersection divided by the smaller box area; useful for cross-class nested boxes."""
    x1=max(a[0],b[0]);y1=max(a[1],b[1]);x2=min(a[2],b[2]);y2=min(a[3],b[3])
    inter=max(0,x2-x1)*max(0,y2-y1)
    if inter<=0:return 0.0
    aa=max(0,a[2]-a[0])*max(0,a[3]-a[1]);bb=max(0,b[2]-b[0])*max(0,b[3]-b[1])
    return inter/max(min(aa,bb),1e-9)

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

def nearest_building_distance_ft(lon,lat,z):
    bs=z.get('buildings') or []
    if not bs:return None
    best=1e30
    for b in bs:
        rings=b.get('rings') or []
        if rings:
            best=min(best,point_poly_distance_ft(lon,lat,rings))
    return None if best>=1e29 else best

def thermal_rescue_eligible(z):
    ctx=property_context(z);largest=z.get('largest') or 0
    poor=any(k in ctx for k in ('SINGLE FAMILY','DUPLEX','MULTI FAMILY','MULTIFAMILY','APART','CONDO','TOWN HOUSE','TOWNHOUSE',
                                 'TOWNHOME','RESTAUR','RETAIL','SHOPPING','STORE','PUBLIC STORAGE','SELF STORAGE','MINI STORAGE'))
    priority=any(k in ctx for k in ('INDUSTR','MANUFACTUR','UTILITY','HOSP','MEDICAL','UNIVERS','COLLEGE','VIRGINIA TECH',
                                     'MILITARY','GOVERN','SCHOOL','WAREHOUSE','DISTRIBUT','PUBLIC/SEMI PUBLIC'))
    return priority and not poor and largest>=2500 and not repetitive_storage_like(z)

def thermal_rescue_views(views,z):
    """Choose focus views by value without excluding smaller priority properties."""
    bviews=[v for v in views if v.get('kind') in ('building_focus','building')]
    bviews=sorted(bviews,key=lambda v:(0 if v.get('kind')=='building_focus' else 1,-(v.get('building') or {}).get('sq',0)))
    limit=2 if (z.get('largest') or 0)>=75000 else 1
    if bviews:return bviews[:limit]
    return [v for v in views if v.get('kind') in ('parcel_tile','overview')][:1]

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
        candidate_path=required_asset('models','candidate.pt')
        if progress:progress('Loading Stage-1 candidate model...')
        self.candidate=YOLO(str(candidate_path))
        self.embedder=resnet18(weights=None);self.embedder.fc=nn.Identity()
        embedder_path=required_asset('models','resnet18_embedder_state_fp16.pt')
        if progress:progress('Loading Stage-2 embedder model...')
        embed_state=torch.load(embedder_path,map_location='cpu')
        self.embedder.load_state_dict(embed_state)
        self.embedder.eval()
        self.tf=transforms.Compose([transforms.Resize((224,224)),transforms.ToTensor(),transforms.Normalize([0.485,0.456,0.406],[0.229,0.224,0.225])])
        verifier_path=required_asset('models','verifier_runtime.json')
        if progress:progress('Loading Stage-2 verifier parameters...')
        v=json.loads(verifier_path.read_text())
        self.mean=np.asarray(v['scaler_mean'],dtype=np.float32);self.scale=np.asarray(v['scaler_scale'],dtype=np.float32)
        self.coef=np.asarray(v['coef'],dtype=np.float32);self.intercept=np.asarray(v['intercept'],dtype=np.float32)
        self.idname={int(k):v for k,v in v['class_names_by_id'].items()}
        if progress:progress('Local CV ready.')

    def positions(self,n):
        return [0] if n<=1024 else [0,n-1024]

    def rescue_tile_origins(self,w,h):
        """Return shifted 1024px tiles not used by the normal corner scan.

        On an 1800px focus image the normal pass sees an object near a side wall close to a
        tile edge in both corner tiles. 5925 Thurston exposed that failure mode. These five
        overlap tiles put the same perimeter equipment nearer a tile center, where Stage 1
        has materially different context.
        """
        if w<=1024 and h<=1024:return [(0,0)]
        ex=max(0,w-1024);ey=max(0,h-1024);mx=ex//2;my=ey//2
        normal={(0,0),(ex,0),(0,ey),(ex,ey)}
        cand=[(mx,0),(mx,ey),(0,my),(ex,my),(mx,my)]
        out=[]
        for q in cand:
            if q not in normal and q not in out:out.append(q)
        return out or [(mx,my)]

    def perimeter_rescue_tile_origins(self,w,h):
        """Overlapping zoom crops; 1800px imagery becomes a 3x3 grid at 0/644/1288."""
        t=PERIMETER_RESCUE_TILE_PX
        def axes(n):
            if n<=t:return [0]
            return list(dict.fromkeys((0,(n-t)//2,n-t)))
        return [(x,y) for x in axes(w) for y in axes(h)]

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
        probs=softmax(xs@self.coef.T+self.intercept);target=probs[1:];pid=int(np.argmax(target))+1;p=float(np.sum(target));best=float(probs[pid])
        thr=LARGE_PACKAGED_THRESHOLD if pid==3 else TOWER_CHILLER_THRESHOLD
        return self.idname[pid],p,float(probs[0]),p>=thr,best

    def _geo_detection(self,d,view,image_w,image_h,z):
        x1,y1,x2,y2=d['box'];cx=(x1+x2)/2;cy=(y1+y2)/2;side=float(view.get('side_ft') or 700)
        ground_side=side*math.cos(math.radians(float(view['lat'])))
        dx=(cx-image_w/2)*ground_side/image_w;dy=(image_h/2-cy)*ground_side/image_h
        lon,lat=lonlat_offset(float(view['lon']),float(view['lat']),dx,dy)
        d['lon']=lon;d['lat']=lat;d['width_ft']=abs(x2-x1)*ground_side/image_w;d['height_ft']=abs(y2-y1)*ground_side/image_h
        d['long_ft']=max(d['width_ft'],d['height_ft']);d['short_ft']=min(d['width_ft'],d['height_ft'])
        d['parcel_distance_ft']=point_poly_distance_ft(lon,lat,z.get('rings') or [])
        d['building_distance_ft']=nearest_building_distance_ft(lon,lat,z)
        d['view_kind']=view.get('kind','')
        allowed=campus_buffer_ft(z);d['parcel_ok']=d['parcel_distance_ft']<=allowed
        d['attribution_scope']='PARCEL' if d['parcel_distance_ft']<=PARCEL_BUFFER_FT else ('CAMPUS ADJACENT' if d['parcel_ok'] else 'OUTSIDE')
        return d

    def scan_image(self,view,tile_dir,z):
        path=view['path'];im=Image.open(path).convert('RGB');w,h=im.size;dets=[];outside=[];props=0
        for x0 in self.positions(w):
            for y0 in self.positions(h):
                tw=min(1024,w-x0);th=min(1024,h-y0);tile=im.crop((x0,y0,x0+tw,y0+th)).convert('RGB')
                tp=Path(tile_dir)/f'{Path(path).stem}__x{x0}_y{y0}.jpg';tile.save(tp,quality=92)
                r=self.candidate.predict(source=str(tp),imgsz=1024,conf=CANDIDATE_THRESHOLD,iou=.50,verbose=False,device='cpu')[0]
                if r.boxes is None:continue
                xy=r.boxes.xyxy.detach().cpu().numpy();cf=r.boxes.conf.detach().cpu().numpy();props+=len(xy)
                for bb,cc in zip(xy,cf):
                    pb=tuple(map(float,bb.tolist()));typ,p,rej,keep,best=self.verify(tile,pb,float(cc),Path(path).name)
                    if not keep:continue
                    edge=4.0
                    internal_edge=(pb[0]<=edge and x0>0) or (pb[1]<=edge and y0>0) or (pb[2]>=tw-edge and x0+tw<w) or (pb[3]>=th-edge and y0+th<h)
                    d={'box':(pb[0]+x0,pb[1]+y0,pb[2]+x0,pb[3]+y0),'type':typ,'p':p,'best_class_prob':best,'candidate':float(cc),'reject':rej,
                       'internal_tile_edge':bool(internal_edge),'rescue':False,'review_only':False}
                    self._geo_detection(d,view,w,h,z)
                    (dets if d['parcel_ok'] else outside).append(d)
        def nms(q):
            q.sort(key=lambda d:(d['p'],d['candidate']),reverse=True);keep=[]
            for d in q:
                if any(box_iou(d['box'],k['box'])>=.45 for k in keep):continue
                keep.append(d)
            return keep
        return im,nms(dets),props,nms(outside)

    def scan_rescue_image(self,view,tile_dir,z):
        """Deep tower/chiller rescue for high-value properties with no accepted thermal evidence.

        v0.11.4 differs from the normal scan in two intentionally asymmetric ways:
        1) shifted overlap tiles move side-yard equipment away from 1024px inference seams;
        2) Stage-1 confidence is lowered only here to recover weak proposals.

        A proposal below the frozen 0.07 Stage-1 operating point can never create STRONG evidence.
        It is scored by Stage 2 with the Stage-1 numeric feature floored at 0.07, then retained only
        as REVIEW evidence when the visual verifier is plausible. This protects recall without
        globally changing the frozen detector operating point.
        """
        path=view['path'];im=Image.open(path).convert('RGB');w,h=im.size;out=[];props=0;tiles_run=0;verified=0
        ground_side=float(view.get('side_ft') or 700)*math.cos(math.radians(float(view['lat'])))
        ft_per_px=ground_side/max(w,1)
        for x0,y0 in self.rescue_tile_origins(w,h):
            tw=min(1024,w-x0);th=min(1024,h-y0)
            if tw<256 or th<256:continue
            tile=im.crop((x0,y0,x0+tw,y0+th)).convert('RGB')
            tp=Path(tile_dir)/f'{Path(path).stem}__DEEPRESCUE_x{x0}_y{y0}.jpg';tile.save(tp,quality=92)
            r=self.candidate.predict(source=str(tp),imgsz=1024,conf=DEEP_RESCUE_CANDIDATE_THRESHOLD,iou=.50,
                                     max_det=DEEP_RESCUE_MAX_DET,verbose=False,device='cpu')[0]
            tiles_run+=1
            if r.boxes is None:continue
            xy=r.boxes.xyxy.detach().cpu().numpy();cf=r.boxes.conf.detach().cpu().numpy();props+=len(xy)
            # Cheap physical-size gate before ResNet verification. This is intentionally broad and only
            # removes proposals that cannot plausibly be commercial heat-rejection equipment at this scale.
            candidates=[]
            for bb,cc in zip(xy,cf):
                pb=tuple(map(float,bb.tolist()));long_px=max(pb[2]-pb[0],pb[3]-pb[1]);long_ft=long_px*ft_per_px
                if long_ft<7.0 or long_ft>130.0:continue
                candidates.append((float(cc),pb))
            candidates.sort(reverse=True,key=lambda q:q[0]);candidates=candidates[:DEEP_RESCUE_MAX_VERIFY_PER_TILE]
            for cc,pb in candidates:
                verified+=1
                # Stage 2 was trained around normal Stage-1 candidates. Flooring only the numeric confidence
                # feature lets the visual embedding judge a weak proposal, but weak Stage-1 evidence remains
                # REVIEW-only below.
                scored_conf=max(cc,CANDIDATE_THRESHOLD)
                typ,p,rej,keep,best=self.verify(tile,pb,scored_conf,Path(path).name)
                if typ not in ('COOLING_TOWER','AIR_COOLED_CHILLER'):continue
                if not keep and (p<THERMAL_REVIEW_THRESHOLD or best<THERMAL_REVIEW_CLASS_MIN):continue
                edge=4.0
                internal_edge=(pb[0]<=edge and x0>0) or (pb[1]<=edge and y0>0) or (pb[2]>=tw-edge and x0+tw<w) or (pb[3]>=th-edge and y0+th<h)
                if internal_edge:continue
                weak_stage1=cc<CANDIDATE_THRESHOLD
                d={'box':(pb[0]+x0,pb[1]+y0,pb[2]+x0,pb[3]+y0),'type':typ,'p':p,'best_class_prob':best,
                   'candidate':cc,'candidate_scored_as':scored_conf,'reject':rej,'internal_tile_edge':False,
                   'rescue':True,'deep_rescue':True,'review_only':bool(weak_stage1 or not keep)}
                self._geo_detection(d,view,w,h,z)
                if d['parcel_ok'] and 7.0<=d.get('long_ft',0)<=130.0:out.append(d)
        out.sort(key=lambda d:(d['p'],d['candidate']),reverse=True);keep=[]
        for d in out:
            if any(box_iou(d['box'],k['box'])>=.35 for k in keep):continue
            keep.append(d)
        return keep,props,tiles_run,verified

    def scan_perimeter_rescue_image(self,view,tile_dir,z):
        """Zoomed REVIEW-only fallback for small side-yard heat-rejection equipment.

        Each 512px source crop is enlarged to 1024px before Stage 1. This is deliberately
        property- and view-gated and runs only after the normal plus shifted rescue pass has
        produced no rankable thermal evidence.
        """
        path=view['path'];im=Image.open(path).convert('RGB');w,h=im.size;out=[];props=0;tiles_run=0;verified=0
        ground_side=float(view.get('side_ft') or 700)*math.cos(math.radians(float(view['lat'])))
        ft_per_px=ground_side/max(w,1)
        for x0,y0 in self.perimeter_rescue_tile_origins(w,h):
            tw=min(PERIMETER_RESCUE_TILE_PX,w-x0);th=min(PERIMETER_RESCUE_TILE_PX,h-y0)
            if tw<256 or th<256:continue
            crop=im.crop((x0,y0,x0+tw,y0+th)).convert('RGB')
            tile=crop.resize((1024,1024),Image.Resampling.LANCZOS)
            tp=Path(tile_dir)/f'{Path(path).stem}__PERIMETER_x{x0}_y{y0}.jpg';tile.save(tp,quality=93)
            r=self.candidate.predict(source=str(tp),imgsz=1024,conf=PERIMETER_RESCUE_CANDIDATE_THRESHOLD,iou=.50,
                                     max_det=PERIMETER_RESCUE_MAX_DET,verbose=False,device='cpu')[0]
            tiles_run+=1
            if r.boxes is None:continue
            xy=r.boxes.xyxy.detach().cpu().numpy();cf=r.boxes.conf.detach().cpu().numpy();props+=len(xy)
            candidates=[]
            for bb,cc in zip(xy,cf):
                pb=tuple(map(float,bb.tolist()))
                source_long=max((pb[2]-pb[0])*tw/1024.0,(pb[3]-pb[1])*th/1024.0)
                long_ft=source_long*ft_per_px
                if 7.0<=long_ft<=130.0:candidates.append((float(cc),pb))
            candidates.sort(reverse=True,key=lambda q:q[0]);candidates=candidates[:PERIMETER_RESCUE_MAX_VERIFY_PER_TILE]
            for cc,pb in candidates:
                verified+=1
                scored_conf=max(cc,CANDIDATE_THRESHOLD)
                typ,p,rej,keep,best=self.verify(tile,pb,scored_conf,Path(path).name)
                if typ not in ('COOLING_TOWER','AIR_COOLED_CHILLER'):continue
                if p<PERIMETER_RESCUE_MIN_P or best<PERIMETER_RESCUE_MIN_BEST:continue
                mapped=(x0+pb[0]*tw/1024.0,y0+pb[1]*th/1024.0,x0+pb[2]*tw/1024.0,y0+pb[3]*th/1024.0)
                d={'box':mapped,'type':typ,'p':p,'best_class_prob':best,'candidate':cc,
                   'candidate_scored_as':scored_conf,'reject':rej,'internal_tile_edge':False,
                   'rescue':True,'deep_rescue':False,'perimeter_rescue':True,'review_only':True}
                self._geo_detection(d,view,w,h,z)
                if d['parcel_ok'] and 7.0<=d.get('long_ft',0)<=130.0:out.append(d)
        out.sort(key=lambda d:(d['p'],d['candidate']),reverse=True);keep=[]
        for d in out:
            if any(box_iou(d['box'],k['box'])>=.35 for k in keep):continue
            keep.append(d)
        return keep,props,tiles_run,verified

    def _world_box(self,d,ref_lon,ref_lat):
        x,y=local_xy_ft(d['lon'],d['lat'],ref_lon,ref_lat);w=d.get('width_ft',0);h=d.get('height_ft',0)
        return (x-w/2,y-h/2,x+w/2,y+h/2)

    def _same_physical(self,a,b,ref_lon,ref_lat):
        A=self._world_box(a,ref_lon,ref_lat);B=self._world_box(b,ref_lon,ref_lat)
        iou=box_iou(A,B);dist=miles(a['lon'],a['lat'],b['lon'],b['lat'])*5280
        maxdim=max(a.get('long_ft',0),b.get('long_ft',0),1)
        if a['type']==b['type']:
            return iou>=.24 or dist<=max(6.0,min(16.0,maxdim*.22))
        # Different labels can still describe one machine. Same-view partial/nested boxes are
        # especially common in tower/chiller ambiguity (for example 965 Baker).
        same_image=a.get('image') and a.get('image')==b.get('image')
        return iou>=.30 or (same_image and (iou>=.12 or box_overlap_min(A,B)>=.30))

    def scan_property(self,views,site_dir,z,progress=None):
        site_dir=Path(site_dir);ann=site_dir/'annotated';tiles=site_dir/'_tiles';ann.mkdir(parents=True,exist_ok=True);tiles.mkdir(parents=True,exist_ok=True)
        raw=[];outside=[];props=0;viewrows=[];rescue_props=0;rescue_tiles=0;rescue_verified=0;rescue_dets=[]
        perimeter_props=0;perimeter_tiles=0;perimeter_verified=0;perimeter_dets=[]
        try:
            for i,view in enumerate(views,1):
                label=view['label'];path=view['path']
                if progress:progress(f'{label} ({i}/{len(views)})')
                im,dets,np_,out_=self.scan_image(view,tiles,z);props+=np_
                for d in dets:d['view']=label;d['image']=Path(path).name
                for d in out_:d['view']=label;d['image']=Path(path).name
                raw.extend(dets);outside.extend(out_);viewrows.append({'view':label,'image':Path(path).name,'kind':view.get('kind',''),'side_ft':round(float(view.get('side_ft') or 0),1),'stage1_proposals':np_,'retained_attributed':len(dets),'campus_adjacent':sum(d.get('attribution_scope')=='CAMPUS ADJACENT' for d in dets),'outside_parcel':len(out_)})
                if dets or out_:
                    dr=ImageDraw.Draw(im)
                    for d in dets:
                        x1,y1,x2,y2=d['box'];adj=d.get('attribution_scope')=='CAMPUS ADJACENT';prefix='ADJ ' if adj else ''
                        txt=f"{prefix}{DISPLAY.get(d['type'],d['type'])} {d['p']:.2f} {d.get('long_ft',0):.0f}ft";color='orange' if adj else 'red'
                        dr.rectangle((x1,y1,x2,y2),outline=color,width=5);dr.rectangle((x1,max(0,y1-24),x1+max(140,len(txt)*8),y1),fill=color);dr.text((x1+3,max(0,y1-21)),txt,fill='white')
                    for d in out_:
                        x1,y1,x2,y2=d['box'];txt=f"OUTSIDE PARCEL {DISPLAY.get(d['type'],d['type'])}"
                        dr.rectangle((x1,y1,x2,y2),outline='orange',width=4);dr.text((x1+3,max(0,y1-20)),txt,fill='orange')
                    im.save(ann/Path(path).name,quality=93)

            # Any normal thermal hypothesis stops the expensive fallbacks, including a context-rejected
            # one: rescanning dock/roof clutter at more scales would only multiply the same false lead.
            have_tc=any(d.get('type') in ('COOLING_TOWER','AIR_COOLED_CHILLER') for d in raw)
            if not have_tc and thermal_rescue_eligible(z):
                bviews=thermal_rescue_views(views,z)
                for view in bviews:
                    if progress:progress(f"THERMAL RESCUE — {view['label']}")
                    rd,np_,ntiles,nverify=self.scan_rescue_image(view,tiles,z);rescue_props+=np_;rescue_tiles+=ntiles;rescue_verified+=nverify
                    for d in rd:
                        d['view']='THERMAL RESCUE — '+view['label'];d['image']=Path(view['path']).name
                    if rd:
                        rescue_dets.extend(rd);raw.extend(rd)
                        # Preserve normal annotation and create a separate rescue overlay for auditability.
                        ap=ann/Path(view['path']).name;rim=Image.open(ap if ap.exists() else view['path']).convert('RGB');dr=ImageDraw.Draw(rim)
                        for d in rd:
                            x1,y1,x2,y2=d['box'];tag='REVIEW ' if d.get('review_only') else ''
                            txt=f"RESCUE {tag}{DISPLAY.get(d['type'],d['type'])} {d['p']:.2f} {d.get('long_ft',0):.0f}ft"
                            dr.rectangle((x1,y1,x2,y2),outline='yellow',width=5);dr.rectangle((x1,max(0,y1-24),x1+max(180,len(txt)*8),y1),fill='yellow');dr.text((x1+3,max(0,y1-21)),txt,fill='black')
                        rim.save(ann/('RESCUE_'+Path(view['path']).name),quality=93)

                # If shifted 1024px tiles still supply no rankable thermal evidence, zoom overlapping
                # 512px perimeter crops to 1024px. All evidence from this fallback is REVIEW-only.
                if not any(thermal_detection_rankable(z,d) for d in rescue_dets):
                    for view in bviews:
                        if progress:progress(f"PERIMETER RESCUE — {view['label']}")
                        rd,np_,ntiles,nverify=self.scan_perimeter_rescue_image(view,tiles,z)
                        perimeter_props+=np_;perimeter_tiles+=ntiles;perimeter_verified+=nverify
                        for d in rd:
                            d['view']='PERIMETER RESCUE — '+view['label'];d['image']=Path(view['path']).name
                        if rd:
                            perimeter_dets.extend(rd);raw.extend(rd)
                            ap=ann/Path(view['path']).name;rim=Image.open(ap if ap.exists() else view['path']).convert('RGB');dr=ImageDraw.Draw(rim)
                            for d in rd:
                                x1,y1,x2,y2=d['box'];txt=f"PERIMETER REVIEW {DISPLAY.get(d['type'],d['type'])} {d['p']:.2f} {d.get('long_ft',0):.0f}ft"
                                dr.rectangle((x1,y1,x2,y2),outline='cyan',width=5);dr.rectangle((x1,max(0,y1-24),x1+max(220,len(txt)*8),y1),fill='cyan');dr.text((x1+3,max(0,y1-21)),txt,fill='black')
                            rim.save(ann/('PERIMETER_RESCUE_'+Path(view['path']).name),quality=93)

            # Cross-view geographic de-duplication: repeated views of one machine count as one evidence object.
            raw.sort(key=lambda d:(d['p'],d['candidate']),reverse=True);uniq=[];ref_lon=z.get('lon');ref_lat=z.get('lat')
            for d in raw:
                if any(self._same_physical(d,k,ref_lon,ref_lat) for k in uniq):continue
                uniq.append(d)
            hits={k:0 for k in DISPLAY};maxp=0.0
            for d in uniq:
                if d['type'] in hits:hits[d['type']]+=1
                maxp=max(maxp,d['p'])
            out={'detector_status':'EVIDENCE' if uniq else 'QUIET','hits':hits,'max_prob':maxp,'stage1_proposals':props,
                 'stage1_rescue_proposals':rescue_props,'deep_rescue_tiles':rescue_tiles,'deep_rescue_verified':rescue_verified,
                 'perimeter_rescue_proposals':perimeter_props,'perimeter_rescue_tiles':perimeter_tiles,
                 'perimeter_rescue_verified':perimeter_verified,'perimeter_rescue_evidence':sum(bool(d.get('perimeter_rescue')) for d in uniq),
                 'thermal_rescue_evidence':sum(bool(d.get('rescue')) for d in uniq),
                 'thermal_review_only_evidence':sum(bool(d.get('rescue') and d.get('review_only')) for d in uniq),
                 'raw_retained_evidence':len(raw),'retained_evidence':len(uniq),'attribution_rejected':len(outside),
                 'cross_property_rejected':0,'cross_property_rejected_detections':[],
                 'views':viewrows,'detections':uniq,'raw_detections':raw,'outside_parcel_detections':outside}
            (site_dir/'cv_result.json').write_text(json.dumps(out,indent=2,default=float),encoding='utf-8')
            return out
        finally:shutil.rmtree(tiles,ignore_errors=True)

def package_rankable(z,d):
    if d.get('type')!='LARGE_PACKAGED_HVAC' or d.get('attribution_scope')=='CAMPUS ADJACENT':return False
    if z.get('storage_like') or repetitive_storage_like(z):return False
    # A detection cut by an internal inference-tile seam is too fragile to drive a packaged-only prospect.
    if d.get('internal_tile_edge'):return False
    # Trucks/trailers and dock clutter are recurring large-package false positives. Real rooftop/package equipment
    # is normally on or close to a mapped building. Packaged equipment is secondary to tower/chiller recall, so
    # we deliberately require stronger building context here.
    bd=d.get('building_distance_ft')
    if bd is not None and bd>PACKAGE_MAX_BUILDING_DISTANCE_FT:
        # Permit a narrow high-certainty side-yard exception. 1569 Diamond Springs is the
        # motivating fixed four-fan unit; trailers and trucks do not meet these verifier gates.
        side_yard=(bd<=70 and d.get('view_kind') in ('building_focus','building') and
                   float(d.get('p') or 0)>=.82 and float(d.get('best_class_prob') or 0)>=.70)
        if not side_yard:return False
    # Wide low-certainty rectangles in an overview are usually a roof span, trailer bank or
    # self-storage row rather than one packaged HVAC unit.
    if d.get('view_kind')=='overview' and (d.get('long_ft') or 0)>=90 and (d.get('short_ft') or 0)>=50 and float(d.get('p') or 0)<.90:return False
    return True

def packaged_bands(cv,z):
    allpkg=[d for d in cv.get('detections',[]) if d.get('type')=='LARGE_PACKAGED_HVAC' and d.get('attribution_scope')!='CAMPUS ADJACENT']
    ds=[d for d in allpkg if package_rankable(z,d)]
    very_large=sum((d.get('long_ft') or 0)>=36 for d in ds)
    largeish=sum((d.get('long_ft') or 0)>=28 for d in ds)
    mid=sum((d.get('long_ft') or 0)>=18 for d in ds)
    return ds,very_large,largeish,mid

def thermal_detection_rankable(z,d):
    if d.get('type') not in ('COOLING_TOWER','AIR_COOLED_CHILLER'):return False
    if z.get('storage_like') or repetitive_storage_like(z):return False
    p=float(d.get('p') or 0);best=float(d.get('best_class_prob') or 0)
    if d.get('rescue'):
        if best<.22:return False
        bd=d.get('building_distance_ft')
        if bd is not None and bd>THERMAL_RESCUE_MAX_BUILDING_DISTANCE_FT:return False
    # Keep high-confidence seam detections such as 5649 Bayside, while removing the weak
    # overview seam lookalike at 1400 Air Rail.
    if d.get('view_kind')=='overview' and d.get('internal_tile_edge') and p<.60 and best<.25:return False
    if d.get('view_kind')=='overview' and (d.get('long_ft') or 0)>=80 and (d.get('short_ft') or 0)>=45 and p<.70:return False
    # Broad, near-square, low-certainty normal boxes are commonly debris piles or roof clutter.
    # This deliberately suppresses weak shapes such as 1609 Diamond Springs while retaining the
    # stronger 5580 Shell review and every established side-yard rescue case.
    if not d.get('rescue') and (d.get('long_ft') or 0)>=32 and (d.get('short_ft') or 0)>=28 and p<.55 and best<.30:return False
    return True

def thermal_evidence(cv,z):
    alltc=[d for d in cv.get('detections',[]) if d.get('type') in ('COOLING_TOWER','AIR_COOLED_CHILLER')]
    tc=[d for d in alltc if thermal_detection_rankable(z,d)]
    direct=[d for d in tc if d.get('attribution_scope')!='CAMPUS ADJACENT']
    strong=[]
    for d in direct:
        if d.get('review_only'):continue
        p=float(d.get('p') or 0);best=float(d.get('best_class_prob') or 0);long=float(d.get('long_ft') or 0)
        high_conf=(p>=THERMAL_STRONG_HIGH_P and best>=THERMAL_STRONG_HIGH_BEST)
        sized_conf=(long>=THERMAL_STRONG_MIN_FT and p>=THERMAL_STRONG_SIZED_P and best>=THERMAL_STRONG_SIZED_BEST)
        if high_conf or sized_conf:strong.append(d)
    return tc,direct,strong

def triage_status(z,cv):
    tc,direct,strong=thermal_evidence(cv,z)
    if strong:return 'STRONG'
    # Small direct tower/chiller evidence, campus-adjacent evidence, and below-threshold thermal-rescue evidence
    # are still intentionally surfaced, but as REVIEW rather than STRONG.
    if tc:return 'REVIEW'
    ds,very_large,largeish,mid=packaged_bands(cv,z)
    if very_large>=1 or largeish>=2 or mid>=10:return 'STRONG'
    if largeish>=1 or mid>=5 or (mid>=3 and max([d.get('long_ft',0) for d in ds]+[0])>=23):return 'REVIEW'
    return 'QUIET'

def hit_text(cv,z):
    q=[]
    tc,direct,strong=thermal_evidence(cv,z)
    for typ,label in (('COOLING_TOWER','Tower'),('AIR_COOLED_CHILLER','Chiller')):
        reg=sum(d.get('type')==typ and not d.get('review_only') for d in tc)
        rev=sum(d.get('type')==typ and d.get('review_only') for d in tc)
        if reg:q.append(f"{label} evidence {reg}")
        if rev:q.append(f"{label} review {rev}")
    alltc=[d for d in cv.get('detections',[]) if d.get('type') in ('COOLING_TOWER','AIR_COOLED_CHILLER')]
    rejected=max(0,len(alltc)-len(tc))
    if rejected:q.append(f"Thermal context-rejected {rejected}")
    ds,very_large,largeish,mid=packaged_bands(cv,z)
    allpkg=[d for d in cv.get('detections',[]) if d.get('type')=='LARGE_PACKAGED_HVAC' and d.get('attribution_scope')!='CAMPUS ADJACENT']
    if ds:
        mx=max(d.get('long_ft',0) for d in ds);q.append(f"Pkg evidence {len(ds)} (max ~{mx:.0f} ft)")
    suppressed=max(0,len(allpkg)-len(ds))
    if suppressed:q.append(f"Pkg context-rejected {suppressed}")
    adj=sum(d.get('attribution_scope')=='CAMPUS ADJACENT' for d in cv.get('detections',[]))
    if adj:q.append(f"Campus-adjacent {adj}")
    rescue_review=sum(bool(d.get('rescue') and d.get('review_only')) for d in tc)
    if rescue_review:q.append(f"Thermal rescue review {rescue_review}")
    if cv.get('attribution_rejected'):q.append(f"Outside parcel {cv['attribution_rejected']}")
    if cv.get('cross_property_rejected'):q.append(f"Neighbor-assigned {cv['cross_property_rejected']}")
    return ' | '.join(q)

def opportunity_score(z,cv,status=None):
    status=status or triage_status(z,cv);tc,direct,strong=thermal_evidence(cv,z)
    ds,very_large,largeish,mid=packaged_bands(cv,z)
    towers=sum(d.get('type')=='COOLING_TOWER' for d in tc);chillers=sum(d.get('type')=='AIR_COOLED_CHILLER' for d in tc)
    if strong:
        if any(d.get('type')=='COOLING_TOWER' for d in strong):base=96
        else:base=94
    elif tc:base=78 if any(d.get('review_only') for d in tc) else 82
    elif status=='STRONG':base=86
    elif status=='REVIEW':base=70
    else:return 0
    if towers and chillers:base+=2
    if towers+chillers>=2:base+=1
    if largeish:base+=min(3,largeish)
    base+=min(1,int((z.get('score') or 0)/60))
    return min(99,int(base))

def cross_property_same_machine(a,b):
    """Conservative cross-parcel duplicate test for one thermal machine seen twice."""
    thermal=('COOLING_TOWER','AIR_COOLED_CHILLER')
    if a.get('type') not in thermal or b.get('type') not in thermal:return False
    if a.get('attribution_scope')!='PARCEL' or b.get('attribution_scope')!='PARCEL':return False
    if None in (a.get('lon'),a.get('lat'),b.get('lon'),b.get('lat')):return False
    dist=miles(a['lon'],a['lat'],b['lon'],b['lat'])*5280
    maxdim=max(float(a.get('long_ft') or 0),float(b.get('long_ft') or 0),1.0)
    return dist<=max(6.0,min(14.0,maxdim*.28))

def _cross_property_owner_key(record,d):
    """Prefer an actual containing parcel, then the closest parcel/building context."""
    z=record['z'];pd=d.get('parcel_distance_ft');bd=d.get('building_distance_ft')
    pd=float(pd) if pd is not None else 1e9;bd=float(bd) if bd is not None else 1e9
    mapped_inside=bool(z.get('rings')) and pd<=.5
    return (0 if mapped_inside else 1,pd,bd,-float(d.get('best_class_prob') or 0),
            -float(d.get('p') or 0),int(record.get('scan_index') or 0))

def refresh_cv_summary(cv):
    """Refresh retained-evidence counters after cross-property ownership is resolved."""
    ds=cv.get('detections',[]);hits={k:0 for k in DISPLAY};maxp=0.0
    for d in ds:
        if d.get('type') in hits:hits[d['type']]+=1
        maxp=max(maxp,float(d.get('p') or 0))
    cv['detector_status']='EVIDENCE' if ds else 'QUIET';cv['hits']=hits;cv['max_prob']=maxp
    cv['retained_evidence']=len(ds)
    cv['perimeter_rescue_evidence']=sum(bool(d.get('perimeter_rescue')) for d in ds)
    cv['thermal_rescue_evidence']=sum(bool(d.get('rescue')) for d in ds)
    cv['thermal_review_only_evidence']=sum(bool(d.get('rescue') and d.get('review_only')) for d in ds)

def reconcile_cross_property_detections(records):
    """Assign a thermal detection seen from multiple property scans to one best owner.

    Campus-adjacent evidence is intentionally excluded because broad institutional parcels use a
    different attribution contract.  Raw evidence remains in each site's audit JSON.
    """
    nodes=[]
    for ri,r in enumerate(records):
        z=r['z']
        for di,d in enumerate(r['cv'].get('detections',[])):
            if d.get('attribution_scope')=='PARCEL' and thermal_detection_rankable(z,d):nodes.append((ri,di,d))
    parent=list(range(len(nodes)))
    def find(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]];i=parent[i]
        return i
    def union(a,b):
        a=find(a);b=find(b)
        if a!=b:parent[b]=a
    for i,(ri,_,a) in enumerate(nodes):
        for j in range(i+1,len(nodes)):
            rj,_,b=nodes[j]
            if ri!=rj and cross_property_same_machine(a,b):union(i,j)
    groups={}
    for i,node in enumerate(nodes):groups.setdefault(find(i),[]).append(node)
    removals={}
    for members in groups.values():
        if len({ri for ri,_,_ in members})<2:continue
        owner=min(members,key=lambda q:_cross_property_owner_key(records[q[0]],q[2]));owner_ri=owner[0]
        owner_z=records[owner_ri]['z']
        for ri,di,d in members:
            if ri==owner_ri:continue
            audit=dict(d);audit['assigned_to_address']=owner_z.get('address','');audit['assigned_to_facility']=owner_z.get('facility','')
            removals.setdefault(ri,{})[di]=audit
    for ri,by_index in removals.items():
        cv=records[ri]['cv'];cv['detections']=[d for di,d in enumerate(cv.get('detections',[])) if di not in by_index]
        audit=cv.setdefault('cross_property_rejected_detections',[]);audit.extend(by_index[i] for i in sorted(by_index))
        cv['cross_property_rejected']=len(audit);refresh_cv_summary(cv)
    for r in records:
        r['cv'].setdefault('cross_property_rejected',0);r['cv'].setdefault('cross_property_rejected_detections',[])
    return sum(len(v) for v in removals.values())

class DetailWindow:
    def __init__(self,parent,z):
        w=tk.Toplevel(parent);w.title(f"Prospect Detail — {z.get('facility') or z.get('address')}");w.geometry('900x650')
        txt=tk.Text(w,wrap='word',font=('Segoe UI',10));txt.pack(fill='both',expand=True,padx=10,pady=10)
        lines=[f"FACILITY: {z.get('facility','')}",f"ADDRESS: {z.get('address','')}",f"CV: {z.get('cv_status','NOT SCANNED')}",
               f"OPPORTUNITY SCORE: {z.get('cv_score','')}",f"MODEL EVIDENCE HITS: {z.get('cv_equipment','')}",
               f"MAX HIGH-VALUE PROBABILITY: {'' if z.get('cv_max_prob') is None else str(round(100*z['cv_max_prob']))+'%'}",
               f"GIS TIER / SCORE: {z.get('tier','')} / {z.get('score','')}",f"LAND USE: {z.get('land','')}",f"PRESCREEN: {z.get('pre_reason','')}",
               f"LARGEST BUILDING: {z.get('largest') or 'UNKNOWN'} ft²",f"AVG BUILDING: {z.get('avg') or 'UNKNOWN'} ft²",f"BUILDINGS: {z.get('count',0)}",f"DISTANCE: {z.get('distance','')} mi",f"USER REVIEW: {z.get('review_status','')}",f"NOTE: {z.get('review_note','')}",
               '',"Model evidence is geographically de-duplicated across views, but remains prospecting evidence rather than an engineering inventory.",
               "QUIET does not prove no valuable mechanical opportunity exists."]
        txt.insert('1.0','\n'.join(lines));txt.config(state='disabled')

class App:
    def __init__(self,r):
        self.r=r;self.rows=[];self.cv=None;self.scan_running=False;self.last_scan_root=None;self.review_csv_path=None
        r.title('HVAC Territory Discovery v0.11.6 — Precision Ownership');r.geometry('1820x930')
        t=ttk.Frame(r,padding=10);t.pack(fill='x')
        ttk.Label(t,text='Virginia Beach center:').grid(row=0,column=0);self.q=tk.StringVar(value='717 General Booth Blvd');ttk.Entry(t,textvariable=self.q,width=36).grid(row=0,column=1,padx=5)
        ttk.Label(t,text='Radius mi:').grid(row=0,column=2);self.rad=tk.StringVar(value='1.0');ttk.Entry(t,textvariable=self.rad,width=6).grid(row=0,column=3)
        ttk.Label(t,text='Size threshold ft²:').grid(row=0,column=4);self.mn=tk.StringVar(value='10000');ttk.Entry(t,textvariable=self.mn,width=8).grid(row=0,column=5)
        self.discb=ttk.Button(t,text='1. Discover + Prescreen',command=self.start);self.discb.grid(row=0,column=6,padx=8)
        self.scanb=ttk.Button(t,text='2. Analyze Prescreened',command=self.analyze_prescreened);self.scanb.grid(row=0,column=7,padx=5)
        ttk.Button(t,text='Open Existing Scan',command=self.load_existing_scan).grid(row=0,column=8,padx=8)
        self.st=tk.StringVar(value='v0.11.6 precision ownership — frozen v0.0.12 CV.');ttk.Label(r,textvariable=self.st).pack(fill='x',padx=10)
        cols=('rank','facility','address','cv','opp','evidence','maxp','review','note','largest','bldgs','mi','land','tier','pre','prewhy','gis','source')
        heads={'rank':'#','facility':'FACILITY','address':'ADDRESS','cv':'TRIAGE','opp':'OPP','evidence':'MECHANICAL EVIDENCE','maxp':'MAX P','review':'USER','note':'NOTE','largest':'LARGEST','bldgs':'BLDGS','mi':'MI','land':'LAND USE','tier':'GIS TIER','pre':'PRE','prewhy':'PRESCREEN REASON','gis':'GIS','source':'FOOTPRINT'}
        widths=(42,205,170,72,52,245,55,72,150,82,48,48,145,65,42,170,48,85)
        self.tree=ttk.Treeview(r,columns=cols,show='headings')
        for c,w in zip(cols,widths):self.tree.heading(c,text=heads[c]);self.tree.column(c,width=w,anchor='w')
        self.tree.pack(fill='both',expand=True,padx=10,pady=8);self.tree.bind('<Double-1>',lambda e:self.details())
        f=ttk.Frame(r,padding=10);f.pack(fill='x')
        self.selb=ttk.Button(f,text='Analyze Selected',command=self.analyze_selected);self.selb.pack(side='left')
        ttk.Button(f,text='Prospect Details',command=self.details).pack(side='left',padx=6);ttk.Button(f,text='Open Scan Folder',command=self.open_folder).pack(side='left',padx=6)
        ttk.Separator(f,orient='vertical').pack(side='left',fill='y',padx=6)
        ttk.Button(f,text='Mark STRONG',command=lambda:self.mark_review('STRONG')).pack(side='left',padx=3)
        ttk.Button(f,text='Mark REVIEW',command=lambda:self.mark_review('REVIEW')).pack(side='left',padx=3)
        ttk.Button(f,text='Mark QUIET',command=lambda:self.mark_review('QUIET')).pack(side='left',padx=3)
        ttk.Button(f,text='Edit Note',command=self.edit_note).pack(side='left',padx=5)
        ttk.Separator(f,orient='vertical').pack(side='left',fill='y',padx=6);ttk.Button(f,text='Download Aerial',command=self.download_aerial).pack(side='left')
        ttk.Button(f,text='Save Campus Images',command=self.save_campus).pack(side='left',padx=6);ttk.Button(f,text='Copy Address',command=self.copy_address).pack(side='left',padx=6)

    def start(self):
        if self.scan_running:return
        self.discb.config(state='disabled');self.st.set('Querying GIS and applying precision-weighted prescreen...');threading.Thread(target=self.work,daemon=True).start()
    def work(self):
        try:
            x,y=geocode(self.q.get().strip());self.rows,np_,nb,nj,src,errs=discover(x,y,float(self.rad.get()),float(self.mn.get()));self.diag=(np_,nb,nj,src,errs)
            for z in self.rows:z.update(cv_status='',cv_score=None,cv_equipment='',cv_max_prob=None,cv_folder='',review_status='',review_note='')
            self.r.after(0,self.show)
        except Exception as e:self.r.after(0,lambda e=e:self.fail(e))
    def show(self):
        self.refresh();pre=sum(bool(z.get('pre')) for z in self.rows);np_,nb,nj,src,errs=self.diag;warn=(' | fallback: '+errs[0][:70]) if errs and src!='VB CITY' else ''
        self.st.set(f'{len(self.rows)} discovered | {pre} pass prescreen | parcels {np_} | footprints {nb} | joined {nj} | {src}{warn}');self.discb.config(state='normal')
    def refresh(self):
        def k(z):
            s=z.get('cv_status','');rank={'STRONG':0,'REVIEW':1,'SURFACE':1,'QUIET':2,'ERROR':3,'':4}.get(s,4)
            return (rank,-(z.get('cv_score') or 0),0 if z.get('pre') else 1,-(z.get('score') or 0),-(z.get('largest') or 0))
        self.rows.sort(key=k)
        for x in self.tree.get_children():self.tree.delete(x)
        for n,z in enumerate(self.rows,1):
            mp='' if z.get('cv_max_prob') is None else f"{100*z['cv_max_prob']:.0f}%";opp='' if z.get('cv_score') is None else z['cv_score'];largest='UNKNOWN' if z.get('largest') is None else f"{int(z['largest']):,}"
            self.tree.insert('', 'end', iid=str(n-1), values=(z.get('scan_index') or n,z.get('facility',''),z.get('address',''),z.get('cv_status',''),opp,z.get('cv_equipment',''),mp,z.get('review_status',''),z.get('review_note',''),largest,z.get('count',0),z.get('distance',''),z.get('land',''),z.get('tier',''),'YES' if z.get('pre') else 'NO',z.get('pre_reason',''),z.get('score',''),z.get('source','')))
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
    def _finalize_scan_record(self,record):
        z=record['z'];cv=record['cv'];folder=record['folder'];n=record['scan_index']
        z['cv_status']=triage_status(z,cv);z['cv_score']=opportunity_score(z,cv,z['cv_status']);z['cv_equipment']=hit_text(cv,z);z['cv_max_prob']=cv['max_prob'];z['cv_folder']=str(folder);z['scan_index']=n
        cv['triage_status']=z['cv_status'];cv['opportunity_score']=z['cv_score'];cv['evidence_text']=z['cv_equipment'];cv['prescreen_reason']=z.get('pre_reason','');cv['attribution_buffer_ft']=campus_buffer_ft(z)
        (folder/'cv_result.json').write_text(json.dumps(cv,indent=2,default=float),encoding='utf-8')
        return {'scan_index':n,'facility':z.get('facility',''),'address':z.get('address',''),'cv_status':z['cv_status'],'opportunity_score':z['cv_score'],'model_evidence_hits':z['cv_equipment'],'max_high_value_probability':round(cv['max_prob'],4),'stage1_proposals':cv['stage1_proposals'],'stage1_rescue_proposals':cv.get('stage1_rescue_proposals',0),'deep_rescue_tiles':cv.get('deep_rescue_tiles',0),'deep_rescue_verified':cv.get('deep_rescue_verified',0),'perimeter_rescue_proposals':cv.get('perimeter_rescue_proposals',0),'perimeter_rescue_tiles':cv.get('perimeter_rescue_tiles',0),'perimeter_rescue_verified':cv.get('perimeter_rescue_verified',0),'perimeter_rescue_evidence':cv.get('perimeter_rescue_evidence',0),'thermal_rescue_evidence':cv.get('thermal_rescue_evidence',0),'thermal_review_only_evidence':cv.get('thermal_review_only_evidence',0),'raw_retained_evidence':cv.get('raw_retained_evidence',cv['retained_evidence']),'retained_evidence':cv['retained_evidence'],'outside_parcel_rejected':cv.get('attribution_rejected',0),'neighbor_assigned_evidence':cv.get('cross_property_rejected',0),'gis_score':z.get('score',''),'gis_tier':z.get('tier',''),'prescreen':z.get('pre',False),'prescreen_reason':z.get('pre_reason',''),'largest_building_ft2':z.get('largest',''),'avg_building_ft2':z.get('avg',''),'building_count':z.get('count',0),'land_use':z.get('land',''),'distance_miles':z.get('distance',''),'user_review':z.get('review_status',''),'user_note':z.get('review_note',''),'reviewed_at':'','result_folder':str(folder)}
    def scan_worker(self,sites):
        stamp=datetime.now().strftime('%Y%m%d_%H%M%S');root=Path.home()/'Downloads'/f'HVAC_Prospecting_Scan_{stamp}';root.mkdir(parents=True,exist_ok=True);self.last_scan_root=root;self.review_csv_path=root/'prospecting_results.csv';rows=[];records=[]
        try:
            eng=self.engine()
            for n,z in enumerate(sites,1):
                fac=z.get('facility') or z.get('address') or f'site_{n}';folder=root/f"{n:03d}_{safe_name(fac+'_'+(z.get('address') or ''))[:100]}"
                self.r.after(0,lambda n=n,fac=fac:self.st.set(f'Scanning {n}/{len(sites)} — {fac}'))
                views=campus_images(z,folder/'source');cv=eng.scan_property(views,folder,z,lambda m,n=n,fac=fac:self.r.after(0,lambda m=m,n=n,fac=fac:self.st.set(f'{n}/{len(sites)} {fac}: {m}')))
                record={'z':z,'cv':cv,'folder':folder,'scan_index':n};records.append(record);rows.append(self._finalize_scan_record(record))
                self.write_csv(root,rows);self.r.after(0,self.refresh)
            reassigned=reconcile_cross_property_detections(records);rows=[self._finalize_scan_record(r) for r in records];self.write_csv(root,rows);self.r.after(0,self.refresh)
            strong=sum(r['cv_status']=='STRONG' for r in rows);review=sum(r['cv_status']=='REVIEW' for r in rows);surf=strong+review;quiet=sum(r['cv_status']=='QUIET' for r in rows);(root/'SCAN_SUMMARY.txt').write_text(f'HVAC Territory Discovery v0.11.6\nFrozen detector pipeline v0.0.12\nPrimary thresholds 0.07 / 0.35 / 0.45\nParcel buffer: {PARCEL_BUFFER_FT:.0f} ft\n\nProperties analyzed: {len(rows)}\nSTRONG: {strong}\nREVIEW: {review}\nSurfaced total: {surf}\nQUIET: {quiet}\nNeighbor-assigned duplicate evidence: {reassigned}\n\nMechanical evidence is geographically de-duplicated across views and properties. Outside-parcel and context-rejected detections do not rank the property. v0.11.6 adds a conservative small-public-parcel prescreen, rejects broad weak thermal debris shapes, and assigns duplicated boundary equipment to the best-supported parcel while retaining raw audit evidence.\n',encoding='utf-8')
            self.r.after(0,lambda:self.st.set(f'Scan complete: {strong} STRONG + {review} REVIEW / {len(rows)} | {root}'));self.r.after(0,lambda:messagebox.showinfo('Scan Complete',f'Analyzed {len(rows)} properties.\nSTRONG {strong} | REVIEW {review} | QUIET {quiet}.\n\nResults:\n{root}'))
        except Exception as e:
            detail=traceback.format_exc()
            try:
                diag=Path.home()/'Downloads'/'HVAC_CV_ERROR.txt'
                diag.write_text(
                    'HVAC Territory Discovery v0.11.6\n\n'+detail+
                    '\nExecutable: '+str(sys.executable)+
                    '\n_MEIPASS: '+str(getattr(sys,'_MEIPASS',None))+
                    '\nCandidate asset: '+str(resource_path('models','candidate.pt'))+
                    '\nEmbedder asset: '+str(resource_path('models','resnet18_embedder_state_fp16.pt'))+
                    '\nVerifier asset: '+str(resource_path('models','verifier_runtime.json')),
                    encoding='utf-8'
                )
                popup=str(e)+'\n\nFull diagnostic saved to:\n'+str(diag)
            except Exception:
                popup=str(e)+'\n\n'+detail
            self.r.after(0,lambda popup=popup:self.st.set('CV scan failed. See HVAC_CV_ERROR.txt in Downloads.'))
            self.r.after(0,lambda popup=popup:messagebox.showerror('CV Scan Failed',popup))
        finally:self.scan_running=False;self.r.after(0,lambda:self.scanb.config(state='normal'));self.r.after(0,lambda:self.selb.config(state='normal'))
    def _num(self,v,kind=float):
        try:return kind(v) if str(v).strip() else None
        except:return None
    def load_existing_scan(self):
        root=filedialog.askdirectory(title='Select HVAC_Prospecting_Scan folder')
        if not root:return
        root=Path(root);csvp=root/'prospecting_results.csv'
        if not csvp.exists():messagebox.showerror('Open Existing Scan','prospecting_results.csv was not found in that folder.');return
        try:
            with csvp.open('r',newline='',encoding='utf-8-sig') as f:rr=list(csv.DictReader(f))
            rows=[]
            for i,r in enumerate(rr,1):
                folder=Path(r.get('result_folder') or '')
                if not folder.exists() and folder.name and (root/folder.name).exists():folder=root/folder.name
                rows.append({'scan_index':self._num(r.get('scan_index'),int) or i,'facility':r.get('facility',''),'address':r.get('address',''),
                             'cv_status':r.get('cv_status',''),'cv_score':self._num(r.get('opportunity_score'),int),'cv_equipment':r.get('model_evidence_hits',''),
                             'cv_max_prob':self._num(r.get('max_high_value_probability')),'cv_folder':str(folder) if folder else '',
                             'score':self._num(r.get('gis_score'),int) or 0,'tier':r.get('gis_tier',''),'pre':str(r.get('prescreen','')).lower() in ('true','1','yes'),
                             'pre_reason':r.get('prescreen_reason',''),'largest':self._num(r.get('largest_building_ft2'),int),'avg':self._num(r.get('avg_building_ft2'),int),'count':self._num(r.get('building_count'),int) or 0,
                             'land':r.get('land_use',''),'distance':self._num(r.get('distance_miles')) or '','source':'SAVED SCAN',
                             'review_status':r.get('user_review',''),'review_note':r.get('user_note','')})
            self.rows=rows;self.last_scan_root=root;self.review_csv_path=csvp;self.refresh()
            done=sum(bool(z.get('review_status')) for z in rows);self.st.set(f'Loaded existing scan: {len(rows)} properties | {done} reviewed | {root}')
        except Exception as e:messagebox.showerror('Open Existing Scan',repr(e))
    def _save_review(self,z):
        if not self.review_csv_path or not Path(self.review_csv_path).exists():return
        csvp=Path(self.review_csv_path)
        with csvp.open('r',newline='',encoding='utf-8-sig') as f:rows=list(csv.DictReader(f));fields=list(rows[0].keys()) if rows else []
        for f in ('user_review','user_note','reviewed_at'):
            if f not in fields:fields.append(f)
        target=str(z.get('scan_index') or '')
        for i,r in enumerate(rows,1):
            if (r.get('scan_index') or str(i))==target:
                r['user_review']=z.get('review_status','');r['user_note']=z.get('review_note','');r['reviewed_at']=datetime.now().isoformat(timespec='seconds');break
        tmp=csvp.with_suffix('.tmp')
        with tmp.open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
        tmp.replace(csvp)
    def mark_review(self,status):
        z=self.sel()
        if not z:return
        z['review_status']=status;self._save_review(z);self.refresh();self.st.set(f"Saved review: {status} — {z.get('address') or z.get('facility')}")
    def edit_note(self):
        z=self.sel()
        if not z:return
        note=simpledialog.askstring('Review Note','Short note for this property:',initialvalue=z.get('review_note',''),parent=self.r)
        if note is None:return
        z['review_note']=note.strip();self._save_review(z);self.refresh();self.st.set(f"Saved note — {z.get('address') or z.get('facility')}")
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
        if z.get('lon') is None or z.get('lat') is None:messagebox.showinfo('Saved Scan','Map coordinates are not stored in older scan CSVs. Use Open Scan Folder for the saved aerials.');return
        out=Path.home()/'Downloads'/f"HVAC_{safe_name(z.get('address') or 'candidate')}.jpg";self.st.set('Downloading aerial...')
        def w():
            try:aerial(z['lon'],z['lat'],z.get('largest'),out);self.r.after(0,lambda:self.st.set('Saved '+str(out)))
            except Exception as e:self.r.after(0,lambda e=e:self.st.set('Download failed: '+repr(e)))
        threading.Thread(target=w,daemon=True).start()
    def save_campus(self):
        z=self.sel()
        if not z:return
        if z.get('lon') is None or z.get('lat') is None or not z.get('rings'):messagebox.showinfo('Saved Scan','Parcel geometry is not stored in the scan CSV. Use Open Scan Folder for the saved campus images.');return
        out=Path.home()/'Downloads'/f"HVAC_CAMPUS_{safe_name(z.get('address') or 'candidate')}";self.st.set('Generating campus images...')
        def w():
            try:
                q=campus_images(z,out);self.r.after(0,lambda:self.st.set(f'Saved {len(q)} images to {out}'))
            except Exception as e:self.r.after(0,lambda e=e:self.st.set('Campus image failed: '+repr(e)))
        threading.Thread(target=w,daemon=True).start()
    def copy_address(self):
        z=self.sel()
        if z:self.r.clipboard_clear();self.r.clipboard_append(z.get('address',''));self.st.set('Address copied.')

if __name__=='__main__':
    r=tk.Tk();App(r);r.mainloop()
