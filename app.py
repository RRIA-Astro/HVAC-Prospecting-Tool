import json,math,threading,tkinter as tk,urllib.parse,urllib.request
from tkinter import ttk,messagebox
from pathlib import Path
ADDR="https://geo.vbgov.com/mapservices/rest/services/Business_Systems/Pictometry_Online/MapServer/0/query"
PARCEL="https://geo.vbgov.com/mapservices/rest/services/Business_Systems/Pictometry_Online/MapServer/4/query"
BLDGS="https://dsfmportal.dcr.virginia.gov/server/rest/services/CivilReference/Civil_Reference_Layers/MapServer/2/query"
AERIAL="https://geo.vbgov.com/imageservices/rest/services/Imagery/Aerial2025/ImageServer/exportImage"
def gj(u,p):
 q=urllib.parse.urlencode(p);req=urllib.request.Request(u+"?"+q,headers={"User-Agent":"HVAC-Territory/0.7.3"})
 with urllib.request.urlopen(req,timeout=90) as r:return json.loads(r.read().decode())
def geocode(t):
 m=gj(ADDR.rsplit("/query",1)[0],{"f":"json"});fs=[f["name"] for f in m.get("fields",[]) if f.get("type")=="esriFieldTypeString"];fs=([x for x in fs if any(k in x.lower() for k in ("address","full","street","site"))] or fs)[:8];s=t.replace("'","''")
 d=gj(ADDR,{"f":"json","where":" OR ".join(f"UPPER({f}) LIKE UPPER('%{s}%')" for f in fs),"outFields":"*","returnGeometry":"true","outSR":"4326","resultRecordCount":10})
 if not d.get("features"):raise RuntimeError("Search-center address not found.")
 g=d["features"][0]["geometry"];return float(g["x"]),float(g["y"])
def bb(x,y,m):
 dy=m/69;dx=m/(69*max(.2,math.cos(math.radians(y))));return x-dx,y-dy,x+dx,y+dy
def distance(x,y,a,b):return math.hypot((a-x)*69.172*math.cos(math.radians(y)),(b-y)*69)
def ring_area(r):
 if len(r)<3:return 0
 la=sum(p[1] for p in r)/len(r);c=math.cos(math.radians(la));q=[(p[0]*69.172*c*5280,p[1]*69*5280) for p in r]
 return abs(sum(q[i][0]*q[(i+1)%len(q)][1]-q[(i+1)%len(q)][0]*q[i][1] for i in range(len(q)))/2)
def poly_area(rs):return sum(ring_area(r) for r in (rs or []))
def centroid(rs):
 p=[q for r in (rs or []) for q in r]
 return (sum(a[0] for a in p)/len(p),sum(a[1] for a in p)/len(p)) if p else (None,None)
def point_in_ring(x,y,r):
 inside=False;j=len(r)-1
 for i in range(len(r)):
  xi,yi=r[i];xj,yj=r[j]
  if ((yi>y)!=(yj>y)) and x < (xj-xi)*(y-yi)/(yj-yi+1e-30)+xi:inside=not inside
  j=i
 return inside
def point_in_poly(x,y,rs):
 # adequate for local tax parcels; first containing ring wins
 return any(point_in_ring(x,y,r) for r in (rs or []))
def pages(u,p):
 out=[];off=0
 while True:
  q=dict(p);q["resultOffset"]=off;q["resultRecordCount"]=1000;d=gj(u,q);fs=d.get("features",[]);out.extend(fs)
  if not d.get("exceededTransferLimit") and len(fs)<1000:break
  if not fs:break
  off+=len(fs)
 return out
def load_parcels(x,y,mi):
 a,b,c,d=bb(x,y,mi);p={"f":"json","where":"1=1","geometry":f"{a},{b},{c},{d}","geometryType":"esriGeometryEnvelope","inSR":"4326","spatialRel":"esriSpatialRelIntersects","outFields":"PAR_GPIN,FULL_ADDR,PROP_ADDRESS,LAND_USE,ZONING,PROP_CLASS,LATITUDE,LONGITUDE","returnGeometry":"true","outSR":"4326"}
 out=[]
 for f in pages(PARCEL,p):
  at=f.get("attributes",{});rs=f.get("geometry",{}).get("rings",[]);cx,cy=centroid(rs)
  try:lon=float(at.get("LONGITUDE") or cx);lat=float(at.get("LATITUDE") or cy)
  except:continue
  if distance(x,y,lon,lat)>mi*1.15 and not point_in_poly(x,y,rs):continue
  out.append({"gpin":str(at.get("PAR_GPIN") or ""),"address":at.get("FULL_ADDR") or at.get("PROP_ADDRESS") or "","land_use":at.get("LAND_USE") or "","zoning":at.get("ZONING") or "","prop_class":at.get("PROP_CLASS") or "","lon":lon,"lat":lat,"rings":rs,"parcel_sqft":round(poly_area(rs))})
 return out
def load_buildings(x,y,mi):
 a,b,c,d=bb(x,y,mi);p={"f":"json","where":"1=1","geometry":f"{a},{b},{c},{d}","geometryType":"esriGeometryEnvelope","inSR":"4326","spatialRel":"esriSpatialRelIntersects","outFields":"OBJECTID","returnGeometry":"true","outSR":"4326"}
 out=[]
 for f in pages(BLDGS,p):
  rs=f.get("geometry",{}).get("rings",[]);cx,cy=centroid(rs)
  if cx is not None and distance(x,y,cx,cy)<=mi*1.05:out.append({"lon":cx,"lat":cy,"sqft":round(poly_area(rs)),"assigned":False})
 return out
def classify(l,z,sf):
 s=(l+" "+z).upper();hi=("HOSP","MEDICAL","UNIVERS","COLLEGE","INDUSTR","MANUFACTUR","GOVERN","SCHOOL","WAREHOUSE","DISTRIBUT","UTILITY","PUBLIC/SEMI PUBLIC","MILITARY");lo=("APART","CONDO","MULTI FAMILY","MULTIFAMILY","RESTAUR","RETAIL","SHOPPING","STORE","SINGLE FAMILY","DUPLEX");md=("OFFICE","HOTEL","MOTEL","CHURCH","RELIG","ASSEMBLY","ENTERTAIN","AUTO","COMMERCIAL")
 t="HIGH" if any(k in s for k in hi) else "LOW" if any(k in s for k in lo) else "MEDIUM" if any(k in s for k in md) else "UNKNOWN";sc={"HIGH":75,"MEDIUM":55,"UNKNOWN":50,"LOW":20}[t]
 if sf:sc+=10 if sf>=75000 else 6 if sf>=40000 else 3 if sf>=20000 else 0
 return t,min(95,sc)
def discover(x,y,mi,mn):
 ps=load_parcels(x,y,mi);bs=load_buildings(x,y,mi)
 # exact spatial join: building centroid must fall inside parcel polygon
 for b in bs:
  hits=[p for p in ps if point_in_poly(b["lon"],b["lat"],p["rings"])]
  if hits:
   # if overlapping parcel polygons exist, choose smallest containing parcel
   p=min(hits,key=lambda z:z["parcel_sqft"] or 10**30);p.setdefault("buildings",[]).append(b);b["assigned"]=True
 rows=[]
 for p in ps:
  allb=p.get("buildings",[]);qual=[b for b in allb if b["sqft"]>=mn]
  largest=max((b["sqft"] for b in allb),default=None);total=sum(b["sqft"] for b in allb) if allb else None
  lu=(p["land_use"]+" "+p["zoning"]).upper()
  obviously_small=largest is not None and largest<mn and not any(k in lu for k in ("PUBLIC","MILITARY","HOSP","MEDICAL","INDUSTR","MANUFACTUR","UNIVERS","COLLEGE","SCHOOL","GOVERN"))
  if obviously_small:continue
  # Missing footprints stay for high-recall unless clearly single-family/duplex.
  if largest is None and any(k in lu for k in ("SINGLE FAMILY","DUPLEX")):continue
  p["largest"]=largest;p["total"]=total;p["bcount"]=len(allb);p["qcount"]=len(qual)
  p["source"]="SPATIAL JOIN" if allb else "FOOTPRINT MISSING"
  p["distance"]=round(distance(x,y,p["lon"],p["lat"]),2);p["tier"],p["score"]=classify(p["land_use"],p["zoning"],largest);rows.append(p)
 # GPIN is property identity; one row per parcel
 ded={}
 for p in rows:
  k=p["gpin"] or "ADDR:"+p["address"].upper().strip()
  if k not in ded:ded[k]=p
 out=list(ded.values());out.sort(key=lambda z:(-z["score"],-(z["largest"] or 0),z["distance"]));return out[:200]
def aerial(x,y,sf,out):
 side=max(650,min(1800,math.sqrt(max(sf or 30000,1))*3.2));h=side*.3048/2;R=6378137;X=R*math.radians(x);Y=R*math.log(math.tan(math.pi/4+math.radians(y)/2));q=urllib.parse.urlencode({"f":"image","bbox":f"{X-h},{Y-h},{X+h},{Y+h}","bboxSR":"3857","imageSR":"3857","size":"1800,1800","format":"jpg"})
 with urllib.request.urlopen(AERIAL+"?"+q,timeout=120) as r:Path(out).write_bytes(r.read())
class App:
 def __init__(self,r):
  self.r=r;self.rows=[];r.title("HVAC Territory Discovery v0.7.3 — Parcel Spatial Join");r.geometry("1500x830");t=ttk.Frame(r,padding=10);t.pack(fill="x");ttk.Label(t,text="Virginia Beach search center:").grid(row=0,column=0);self.q=tk.StringVar(value="717 General Booth Blvd");ttk.Entry(t,textvariable=self.q,width=40).grid(row=0,column=1,padx=5);ttk.Label(t,text="Radius mi:").grid(row=0,column=2);self.rad=tk.StringVar(value="1.0");ttk.Entry(t,textvariable=self.rad,width=6).grid(row=0,column=3);ttk.Label(t,text="Min building ft²:").grid(row=0,column=4);self.mn=tk.StringVar(value="10000");ttk.Entry(t,textvariable=self.mn,width=8).grid(row=0,column=5);self.b=ttk.Button(t,text="Discover + Spatial Join",command=self.start);self.b.grid(row=0,column=6,padx=8);self.st=tk.StringVar(value="Ready");ttk.Label(r,textvariable=self.st).pack(fill="x",padx=10)
  cs=("rank","address","largest","total","bldgs","miles","landuse","zoning","tier","score","source");self.tree=ttk.Treeview(r,columns=cs,show="headings")
  for c,w in zip(cs,(45,260,95,95,60,65,220,70,80,65,135)):self.tree.heading(c,text=c.upper());self.tree.column(c,width=w,anchor="w")
  self.tree.pack(fill="both",expand=True,padx=10,pady=8);f=ttk.Frame(r,padding=10);f.pack(fill="x");ttk.Button(f,text="Download Aerial",command=self.dl).pack(side="left");ttk.Button(f,text="Copy Address",command=self.copy).pack(side="left",padx=8);ttk.Label(f,text="FOOTPRINT MISSING = parcel retained for recall; no building polygon was spatially joined.").pack(side="right")
 def start(self):self.b.config(state="disabled");self.st.set("Loading parcel polygons + building polygons and performing exact spatial join...");threading.Thread(target=self.work,daemon=True).start()
 def work(self):
  try:x,y=geocode(self.q.get().strip());self.rows=discover(x,y,float(self.rad.get()),float(self.mn.get()));self.r.after(0,self.show)
  except Exception as e:self.r.after(0,lambda e=e:self.fail(e))
 def show(self):
  for i in self.tree.get_children():self.tree.delete(i)
  for n,z in enumerate(self.rows,1):self.tree.insert("","end",iid=str(n-1),values=(n,z["address"],f'{z["largest"]:,}' if z["largest"] else "UNKNOWN",f'{z["total"]:,}' if z["total"] else "UNKNOWN",z["bcount"],z["distance"],z["land_use"],z["zoning"],z["tier"],z["score"],z["source"]))
  self.st.set(f"{len(self.rows)} property prospects. Building sizes now come only from footprints whose centroid lies inside the actual parcel polygon.");self.b.config(state="normal")
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
