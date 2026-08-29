import json,math,threading,tkinter as tk,urllib.parse,urllib.request
from tkinter import ttk,messagebox
from pathlib import Path
ADDR="https://geo.vbgov.com/mapservices/rest/services/Business_Systems/Pictometry_Online/MapServer/0/query"
PARCEL="https://geo.vbgov.com/mapservices/rest/services/Basemaps/Property_Information/MapServer/12/query"
AERIAL="https://geo.vbgov.com/imageservices/rest/services/Imagery/Aerial2025/ImageServer/exportImage"
BLDGS="https://dsfmportal.dcr.virginia.gov/server/rest/services/CivilReference/Civil_Reference_Layers/MapServer/2/query"
def gj(u,p):
 q=urllib.parse.urlencode(p);r=urllib.request.Request(u+"?"+q,headers={"User-Agent":"HVAC-Territory/0.7.1"})
 with urllib.request.urlopen(r,timeout=60) as x:return json.loads(x.read().decode())
def geocode(t):
 m=gj(ADDR.rsplit("/query",1)[0],{"f":"json"});fs=[f["name"] for f in m.get("fields",[]) if f.get("type")=="esriFieldTypeString"];fs=([x for x in fs if any(k in x.lower() for k in ("address","full","street","site"))] or fs)[:8];s=t.replace("'","''")
 d=gj(ADDR,{"f":"json","where":" OR ".join(f"UPPER({f}) LIKE UPPER('%{s}%')" for f in fs),"outFields":"*","returnGeometry":"true","outSR":"4326","resultRecordCount":10})
 if not d.get("features"):raise RuntimeError("Search-center address not found.")
 g=d["features"][0]["geometry"];return float(g["x"]),float(g["y"])
def bb(x,y,m):
 dy=m/69;dx=m/(69*max(.2,math.cos(math.radians(y))));return x-dx,y-dy,x+dx,y+dy
def area(rs):
 a=[]
 for r in rs or []:
  if not r:continue
  la=sum(p[1] for p in r)/len(r);c=math.cos(math.radians(la));q=[(p[0]*69.172*c*5280,p[1]*69*5280) for p in r];a.append(abs(sum(q[i][0]*q[(i+1)%len(q)][1]-q[(i+1)%len(q)][0]*q[i][1] for i in range(len(q)))/2))
 return max(a) if a else 0
def cent(rs):
 p=[q for r in rs or [] for q in r];return (sum(x[0] for x in p)/len(p),sum(x[1] for x in p)/len(p)) if p else (None,None)
def discover(x,y,mi,mn):
 a1,b1,a2,b2=bb(x,y,mi);d=gj(BLDGS,{"f":"json","where":"1=1","geometry":f"{a1},{b1},{a2},{b2}","geometryType":"esriGeometryEnvelope","inSR":"4326","spatialRel":"esriSpatialRelIntersects","outFields":"*","returnGeometry":"true","outSR":"4326","resultRecordCount":500});out=[]
 for f in d.get("features",[]):
  rs=f.get("geometry",{}).get("rings",[]);sf=area(rs)
  if sf<mn:continue
  a,b=cent(rs)
  if a is None:continue
  dist=math.hypot((a-x)*69.172*math.cos(math.radians(y)),(b-y)*69)
  if dist<=mi:out.append({"lon":a,"lat":b,"sqft":round(sf),"distance":round(dist,2)})
 out.sort(key=lambda z:(-z["sqft"],z["distance"]));return out[:100]
def parcel(x,y):
 d=gj(PARCEL,{"f":"json","where":"1=1","geometry":f"{x},{y}","geometryType":"esriGeometryPoint","inSR":"4326","spatialRel":"esriSpatialRelIntersects","outFields":"FULL_ADDR,PROP_ADDRESS,LAND_USE,ZONING,PROP_CLASS,PAR_GPIN","returnGeometry":"false","resultRecordCount":5});fs=d.get("features",[])
 if not fs:return {"address":"","land_use":"","zoning":"","prop_class":""}
 a=fs[0].get("attributes",{});return {"address":a.get("FULL_ADDR") or a.get("PROP_ADDRESS") or "","land_use":a.get("LAND_USE") or "","zoning":a.get("ZONING") or "","prop_class":a.get("PROP_CLASS") or ""}
def classify(l,z,sf):
 s=(l+" "+z).upper();hi=("HOSP","MEDICAL","UNIVERS","COLLEGE","INDUSTR","MANUFACTUR","GOVERN","SCHOOL","WAREHOUSE","DISTRIBUT","UTILITY");lo=("APART","CONDO","MULTI FAMILY","MULTIFAMILY","RESTAUR","RETAIL","SHOPPING","STORE","RESIDENTIAL");md=("OFFICE","HOTEL","MOTEL","CHURCH","RELIG","ASSEMBLY","ENTERTAIN","AUTO")
 t="HIGH" if any(k in s for k in hi) else "LOW" if any(k in s for k in lo) else "MEDIUM" if any(k in s for k in md) else "UNKNOWN";sc={"HIGH":75,"MEDIUM":55,"UNKNOWN":50,"LOW":20}[t]+(10 if sf>=75000 else 6 if sf>=40000 else 3 if sf>=20000 else 0);return t,min(95,sc)
def aerial(x,y,sf,out):
 side=max(550,min(1800,math.sqrt(max(sf,1))*3.2));h=side*.3048/2;R=6378137;X=R*math.radians(x);Y=R*math.log(math.tan(math.pi/4+math.radians(y)/2));q=urllib.parse.urlencode({"f":"image","bbox":f"{X-h},{Y-h},{X+h},{Y+h}","bboxSR":"3857","imageSR":"3857","size":"1800,1800","format":"jpg"})
 with urllib.request.urlopen(AERIAL+"?"+q,timeout=120) as r:Path(out).write_bytes(r.read())
class A:
 def __init__(self,r):
  self.r=r;self.rows=[];r.title("HVAC Territory Discovery v0.7.1 — Property Pre-Filter");r.geometry("1300x800");t=ttk.Frame(r,padding=10);t.pack(fill="x");ttk.Label(t,text="Virginia Beach search center:").grid(row=0,column=0);self.q=tk.StringVar(value="717 General Booth Blvd");ttk.Entry(t,textvariable=self.q,width=40).grid(row=0,column=1,padx=5);ttk.Label(t,text="Radius mi:").grid(row=0,column=2);self.rad=tk.StringVar(value="1.0");ttk.Entry(t,textvariable=self.rad,width=6).grid(row=0,column=3);ttk.Label(t,text="Min ft²:").grid(row=0,column=4);self.mn=tk.StringVar(value="10000");ttk.Entry(t,textvariable=self.mn,width=8).grid(row=0,column=5);self.b=ttk.Button(t,text="Discover + Pre-Filter",command=self.start);self.b.grid(row=0,column=6,padx=8);self.st=tk.StringVar(value="Ready");ttk.Label(r,textvariable=self.st).pack(fill="x",padx=10)
  cs=("rank","address","sqft","miles","landuse","zoning","tier","prescore");self.tree=ttk.Treeview(r,columns=cs,show="headings")
  for c,w in zip(cs,(50,310,100,70,260,90,100,100)):self.tree.heading(c,text=c.upper());self.tree.column(c,width=w,anchor="w")
  self.tree.pack(fill="both",expand=True,padx=10,pady=8);f=ttk.Frame(r,padding=10);f.pack(fill="x");ttk.Button(f,text="Download Aerial",command=self.dl).pack(side="left");ttk.Button(f,text="Copy Address",command=self.copy).pack(side="left",padx=8);ttk.Label(f,text="LOW is de-prioritized, not deleted. UNKNOWN stays in pipeline.").pack(side="right")
 def start(self):self.b.config(state="disabled");self.st.set("Discovering...");threading.Thread(target=self.work,daemon=True).start()
 def work(self):
  try:
   x,y=geocode(self.q.get().strip());rows=discover(x,y,float(self.rad.get()),float(self.mn.get()))
   for i,z in enumerate(rows):
    self.r.after(0,lambda i=i,n=len(rows):self.st.set(f"Reading parcel metadata {i+1}/{n}..."))
    try:p=parcel(z["lon"],z["lat"])
    except:p={"address":"","land_use":"","zoning":"","prop_class":""}
    z.update(p);z["tier"],z["prescore"]=classify(z["land_use"],z["zoning"],z["sqft"])
   rows.sort(key=lambda z:(-z["prescore"],-z["sqft"]));self.rows=rows;self.r.after(0,self.show)
  except Exception as e:self.r.after(0,lambda e=e:self.fail(e))
 def show(self):
  for i in self.tree.get_children():self.tree.delete(i)
  for n,z in enumerate(self.rows,1):self.tree.insert("","end",iid=str(n-1),values=(n,z["address"],f'{z["sqft"]:,}',z["distance"],z["land_use"],z["zoning"],z["tier"],z["prescore"]))
  c={k:sum(z["tier"]==k for z in self.rows) for k in ("HIGH","MEDIUM","UNKNOWN","LOW")};self.st.set(f'{len(self.rows)} candidates — HIGH {c["HIGH"]}, MEDIUM {c["MEDIUM"]}, UNKNOWN {c["UNKNOWN"]}, LOW {c["LOW"]}');self.b.config(state="normal")
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
