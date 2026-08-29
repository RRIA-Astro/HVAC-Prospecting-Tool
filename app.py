import json,math,threading,tkinter as tk,urllib.parse,urllib.request
from tkinter import ttk,messagebox
from pathlib import Path
ADDR="https://geo.vbgov.com/mapservices/rest/services/Business_Systems/Pictometry_Online/MapServer/0/query"
PARCEL="https://geo.vbgov.com/mapservices/rest/services/Basemaps/Property_Information/MapServer/12/query"
AERIAL="https://geo.vbgov.com/imageservices/rest/services/Imagery/Aerial2025/ImageServer/exportImage"
BLDGS="https://dsfmportal.dcr.virginia.gov/server/rest/services/CivilReference/Civil_Reference_Layers/MapServer/2/query"
def gj(u,p):
 q=urllib.parse.urlencode(p);req=urllib.request.Request(u+"?"+q,headers={"User-Agent":"HVAC-Territory/0.7.2"})
 with urllib.request.urlopen(req,timeout=90) as r:return json.loads(r.read().decode())
def geocode(t):
 m=gj(ADDR.rsplit("/query",1)[0],{"f":"json"});fs=[f["name"] for f in m.get("fields",[]) if f.get("type")=="esriFieldTypeString"];fs=([x for x in fs if any(k in x.lower() for k in ("address","full","street","site"))] or fs)[:8];s=t.replace("'","''")
 d=gj(ADDR,{"f":"json","where":" OR ".join(f"UPPER({f}) LIKE UPPER('%{s}%')" for f in fs),"outFields":"*","returnGeometry":"true","outSR":"4326","resultRecordCount":10})
 if not d.get("features"):raise RuntimeError("Search-center address not found.")
 g=d["features"][0]["geometry"];return float(g["x"]),float(g["y"])
def bb(x,y,m):
 dy=m/69;dx=m/(69*max(.2,math.cos(math.radians(y))));return x-dx,y-dy,x+dx,y+dy
def dist(x,y,a,b):return math.hypot((a-x)*69.172*math.cos(math.radians(y)),(b-y)*69)
def area(rs):
 vals=[]
 for r in rs or []:
  if not r:continue
  la=sum(p[1] for p in r)/len(r);c=math.cos(math.radians(la));q=[(p[0]*69.172*c*5280,p[1]*69*5280) for p in r];vals.append(abs(sum(q[i][0]*q[(i+1)%len(q)][1]-q[(i+1)%len(q)][0]*q[i][1] for i in range(len(q)))/2))
 return max(vals) if vals else 0
def cent(rs):
 p=[q for r in rs or [] for q in r];return (sum(x[0] for x in p)/len(p),sum(x[1] for x in p)/len(p)) if p else (None,None)
def page_query(url,base):
 out=[];off=0
 while True:
  p=dict(base);p["resultOffset"]=off;p["resultRecordCount"]=1000
  d=gj(url,p);fs=d.get("features",[]);out+=fs
  if len(fs)<1000 and not d.get("exceededTransferLimit"):break
  off+=len(fs)
  if not fs:break
 return out
def footprints(x,y,mi):
 a,b,c,d=bb(x,y,mi);base={"f":"json","where":"1=1","geometry":f"{a},{b},{c},{d}","geometryType":"esriGeometryEnvelope","inSR":"4326","spatialRel":"esriSpatialRelIntersects","outFields":"OBJECTID","returnGeometry":"true","outSR":"4326"}
 out=[]
 for f in page_query(BLDGS,base):
  rs=f.get("geometry",{}).get("rings",[]);cx,cy=cent(rs)
  if cx is not None and dist(x,y,cx,cy)<=mi:out.append({"lon":cx,"lat":cy,"sqft":round(area(rs))})
 return out
def parcels(x,y,mi):
 a,b,c,d=bb(x,y,mi);base={"f":"json","where":"1=1","geometry":f"{a},{b},{c},{d}","geometryType":"esriGeometryEnvelope","inSR":"4326","spatialRel":"esriSpatialRelIntersects","outFields":"PAR_GPIN,FULL_ADDR,PROP_ADDRESS,LAND_USE,ZONING,PROP_CLASS,LATITUDE,LONGITUDE","returnGeometry":"true","outSR":"4326"}
 out=[]
 for f in page_query(PARCEL,base):
  at=f.get("attributes",{});g=f.get("geometry",{});cx,cy=cent(g.get("rings",[]))
  lon=at.get("LONGITUDE") or cx;lat=at.get("LATITUDE") or cy
  try:lon=float(lon);lat=float(lat)
  except:continue
  if dist(x,y,lon,lat)>mi:continue
  out.append({"gpin":str(at.get("PAR_GPIN") or ""),"address":at.get("FULL_ADDR") or at.get("PROP_ADDRESS") or "","land_use":at.get("LAND_USE") or "","zoning":at.get("ZONING") or "","prop_class":at.get("PROP_CLASS") or "","lon":lon,"lat":lat})
 return out
def classify(l,z,sf):
 s=(l+" "+z).upper();hi=("HOSP","MEDICAL","UNIVERS","COLLEGE","INDUSTR","MANUFACTUR","GOVERN","SCHOOL","WAREHOUSE","DISTRIBUT","UTILITY","PUBLIC/SEMI PUBLIC","MILITARY");lo=("APART","CONDO","MULTI FAMILY","MULTIFAMILY","RESTAUR","RETAIL","SHOPPING","STORE","RESIDENTIAL");md=("OFFICE","HOTEL","MOTEL","CHURCH","RELIG","ASSEMBLY","ENTERTAIN","AUTO")
 t="HIGH" if any(k in s for k in hi) else "LOW" if any(k in s for k in lo) else "MEDIUM" if any(k in s for k in md) else "UNKNOWN";sc={"HIGH":75,"MEDIUM":55,"UNKNOWN":50,"LOW":20}[t]
 if sf:sc+=10 if sf>=75000 else 6 if sf>=40000 else 3 if sf>=20000 else 0
 return t,min(95,sc)
def discover(x,y,mi,mn):
 ps=parcels(x,y,mi);fs=footprints(x,y,mi);rows=[]
 # Property-first discovery: every non-residential/unknown parcel is eligible even if Microsoft footprint data is missing.
 for p in ps:
  matches=[f for f in fs if dist(p["lon"],p["lat"],f["lon"],f["lat"])<=0.18]
  # Prefer nearby qualifying footprints; aggregate same-property candidates to one prospect.
  qs=[f for f in matches if f["sqft"]>=mn]
  sf=max((f["sqft"] for f in qs),default=None)
  lu=(p["land_use"]+" "+p["zoning"]).upper()
  residential=any(k in lu for k in ("SINGLE FAMILY","RESIDENTIAL")) and not any(k in lu for k in ("MULTI","PUBLIC","OFFICE","INDUSTR","MILITARY"))
  if sf is None and residential:continue
  if sf is None and not p["land_use"] and not p["address"]:continue
  p["sqft"]=sf;p["source"]="FOOTPRINT+PARCEL" if sf else "PARCEL ONLY";p["distance"]=round(dist(x,y,p["lon"],p["lat"]),2);p["tier"],p["prescore"]=classify(p["land_use"],p["zoning"],sf);rows.append(p)
 # Deduplicate on parcel GPIN; fallback normalized address.
 seen={};out=[]
 for z in rows:
  key=("G",z["gpin"]) if z["gpin"] else ("A"," ".join(z["address"].upper().split()))
  if key in seen:
   old=seen[key]
   if (z["sqft"] or 0)>(old["sqft"] or 0):old["sqft"]=z["sqft"]
   continue
  seen[key]=z;out.append(z)
 out.sort(key=lambda z:(-z["prescore"],-(z["sqft"] or 0),z["distance"]));return out[:150]
def aerial(x,y,sf,out):
 side=max(650,min(1800,math.sqrt(max(sf or 30000,1))*3.2));h=side*.3048/2;R=6378137;X=R*math.radians(x);Y=R*math.log(math.tan(math.pi/4+math.radians(y)/2));q=urllib.parse.urlencode({"f":"image","bbox":f"{X-h},{Y-h},{X+h},{Y+h}","bboxSR":"3857","imageSR":"3857","size":"1800,1800","format":"jpg"})
 with urllib.request.urlopen(AERIAL+"?"+q,timeout=120) as r:Path(out).write_bytes(r.read())
class A:
 def __init__(self,r):
  self.r=r;self.rows=[];r.title("HVAC Territory Discovery v0.7.2 — High Recall");r.geometry("1390x820");t=ttk.Frame(r,padding=10);t.pack(fill="x");ttk.Label(t,text="Virginia Beach search center:").grid(row=0,column=0);self.q=tk.StringVar(value="717 General Booth Blvd");ttk.Entry(t,textvariable=self.q,width=40).grid(row=0,column=1,padx=5);ttk.Label(t,text="Radius mi:").grid(row=0,column=2);self.rad=tk.StringVar(value="1.0");ttk.Entry(t,textvariable=self.rad,width=6).grid(row=0,column=3);ttk.Label(t,text="Min footprint ft²:").grid(row=0,column=4);self.mn=tk.StringVar(value="10000");ttk.Entry(t,textvariable=self.mn,width=8).grid(row=0,column=5);self.b=ttk.Button(t,text="Discover + Pre-Filter",command=self.start);self.b.grid(row=0,column=6,padx=8);self.st=tk.StringVar(value="Ready — property-first discovery preserves candidates when footprint data is missing.");ttk.Label(r,textvariable=self.st).pack(fill="x",padx=10)
  cs=("rank","address","sqft","miles","landuse","zoning","tier","score","source");self.tree=ttk.Treeview(r,columns=cs,show="headings")
  for c,w in zip(cs,(45,300,95,65,230,75,85,70,150)):self.tree.heading(c,text=c.upper());self.tree.column(c,width=w,anchor="w")
  self.tree.pack(fill="both",expand=True,padx=10,pady=8);f=ttk.Frame(r,padding=10);f.pack(fill="x");ttk.Button(f,text="Download Aerial",command=self.dl).pack(side="left");ttk.Button(f,text="Copy Address",command=self.copy).pack(side="left",padx=8);ttk.Label(f,text="PARCEL ONLY = retained because footprint source did not supply a qualifying building match.").pack(side="right")
 def start(self):self.b.config(state="disabled");self.st.set("Querying all parcels and all building-footprint pages...");threading.Thread(target=self.work,daemon=True).start()
 def work(self):
  try:x,y=geocode(self.q.get().strip());self.rows=discover(x,y,float(self.rad.get()),float(self.mn.get()));self.r.after(0,self.show)
  except Exception as e:self.r.after(0,lambda e=e:self.fail(e))
 def show(self):
  for i in self.tree.get_children():self.tree.delete(i)
  for n,z in enumerate(self.rows,1):self.tree.insert("","end",iid=str(n-1),values=(n,z["address"],f'{z["sqft"]:,}' if z["sqft"] else "UNKNOWN",z["distance"],z["land_use"],z["zoning"],z["tier"],z["prescore"],z["source"]))
  self.st.set(f"{len(self.rows)} property prospects. Duplicates grouped by parcel/address; missing footprint records retained.");self.b.config(state="normal")
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
   try:aerial(z["lon"],z["lat"],z["sqft"],out);self.r.after(0,lambda:self.st.set("Saved "+str(out)))
   except Exception as e:self.r.after(0,lambda:self.st.set("Download failed: "+repr(e)))
  threading.Thread(target=w,daemon=True).start()
 def copy(self):
  z=self.sel()
  if z:self.r.clipboard_clear();self.r.clipboard_append(z["address"]);self.st.set("Address copied.")
r=tk.Tk();A(r);r.mainloop()
