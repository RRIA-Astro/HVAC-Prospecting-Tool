import base64,json,threading,tkinter as tk
from tkinter import ttk,filedialog,messagebox
from pathlib import Path
from PIL import Image
from openai import OpenAI
MODEL="gpt-5.4-mini"
OBS={"type":"object","additionalProperties":False,"properties":{k:{"type":"object","additionalProperties":False,"properties":{"status":{"type":"string","enum":["strong","probable","possible","not_observed"]},"quantity":{"type":"string","enum":["none","one","few","several","many","unknown"]},"confidence":{"type":"integer"},"evidence":{"type":"string"}},"required":["status","quantity","confidence","evidence"]} for k in ["cooling_towers","air_cooled_chillers","large_packaged_hvac","small_packaged_hvac","condensers","piping","mechanical_yard"]},"required":["cooling_towers","air_cooled_chillers","large_packaged_hvac","small_packaged_hvac","condensers","piping","mechanical_yard"]}
FINAL={"type":"object","additionalProperties":False,"properties":{"class":{"type":"string","enum":["GOOD","MAYBE","POOR"]},"score":{"type":"integer"},"confidence":{"type":"integer"},"cooling_towers":{"type":"string"},"air_cooled_chillers":{"type":"string"},"large_packaged_hvac":{"type":"string"},"small_packaged_hvac":{"type":"string"},"piping":{"type":"string"},"central_system_evidence":{"type":"string"},"ambiguities":{"type":"array","items":{"type":"string"}},"summary":{"type":"string"}},"required":["class","score","confidence","cooling_towers","air_cooled_chillers","large_packaged_hvac","small_packaged_hvac","piping","central_system_evidence","ambiguities","summary"]}
IP="""BLIND HVAC aerial inspection. Systematically inspect ALL visible roof AND ground/perimeter areas in this view. Look for screened/partly enclosed cooling towers, air-cooled chillers, large packaged RTUs/AHUs, small RTUs, condensers, mechanical yards, and exposed hydronic/condenser-water piping. Trace piping toward equipment/penthouses. Do not infer building identity/type. Never call equipment absent because it is unseen in one crop: use not_observed. Use quantity bands, not exact counts. Be conservative in identification but do not ignore plausible large mechanical equipment."""
SP="""These are independent observations from overlapping views of ONE property. Deduplicate overlap. Favor recall for prospecting: plausible large chillers, towers, large packaged HVAC, or central-system piping should keep a property alive. Numerous small RTUs alone are weak. Not_observed is not proof of absence. Synthesize visible mechanical evidence only; do not infer identity/type."""
def url(p):
 m="image/png" if str(p).lower().endswith(".png") else "image/jpeg";return f"data:{m};base64,"+base64.b64encode(Path(p).read_bytes()).decode()
def ask(c,prompt,content,schema,name,tok=5000,effort="low"):
 last=None
 for attempt in range(2):
  budget=tok if attempt==0 else max(tok,8000)
  r=c.responses.create(model=MODEL,reasoning={"effort":effort},input=[{"role":"user","content":[{"type":"input_text","text":prompt}]+content}],text={"format":{"type":"json_schema","name":name,"strict":True,"schema":schema},"verbosity":"low"},max_output_tokens=budget)
  last=r
  if r.status=="completed" and (r.output_text or "").strip():
   return json.loads(r.output_text),r
  reason=getattr(getattr(r,"incomplete_details",None),"reason",None)
  if attempt==0 and reason=="max_output_tokens":
   continue
  raise RuntimeError(f"response {r.status}: {getattr(r,'incomplete_details',None)}")
 raise RuntimeError(f"No usable response: {getattr(last,'status',None)}")
def crops(path):
 im=Image.open(path).convert("RGB");w,h=im.size;d=Path(path).with_name(Path(path).stem+"_crops");d.mkdir(exist_ok=True);out=[("overview",path)]
 tw,th=int(w*.5),int(h*.5);n=0
 for cy in (.25,.5,.75):
  for cx in (.25,.5,.75):
   x=max(0,min(w-tw,int(w*cx-tw/2)));y=max(0,min(h-th,int(h*cy-th/2)));n+=1;p=d/f"crop_{n}.jpg";im.crop((x,y,x+tw,y+th)).save(p,quality=96);out.append((f"crop {n}",str(p)))
 return out
def run(key,path,progress):
 c=OpenAI(api_key=key,timeout=180);views=crops(path);allobs=[];use=[0,0]
 for i,(label,p) in enumerate(views):
  progress(f"Inspecting {label}: {i+1}/10");x,r=ask(c,IP,[{"type":"input_image","image_url":url(p),"detail":"high"}],OBS,"crop_inspection");allobs.append({"view":label,"observations":x})
  try:use[0]+=r.usage.input_tokens;use[1]+=r.usage.output_tokens
  except:pass
 progress("Synthesizing all views...");x,r=ask(c,SP,[{"type":"input_text","text":json.dumps(allobs,separators=(",",":"))}],FINAL,"property_synthesis",6000,"medium")
 try:use[0]+=r.usage.input_tokens;use[1]+=r.usage.output_tokens
 except:pass
 return x,allobs,use
class A:
 def __init__(self,r):
  self.r=r;r.title("HVAC Deep Vision v0.6.4 — Multi-Crop");r.geometry("980x840");f=ttk.Frame(r,padding=10);f.pack(fill="x");ttk.Label(f,text="API key:").pack(side="left");self.k=tk.StringVar();ttk.Entry(f,textvariable=self.k,show="*",width=38).pack(side="left",padx=5);ttk.Button(f,text="Choose Image",command=self.choose).pack(side="left");self.b=ttk.Button(f,text="Run 10-View Inspection",command=self.start,state="disabled");self.b.pack(side="left",padx=5);self.p=tk.StringVar(value="No image selected");ttk.Label(r,textvariable=self.p).pack(fill="x",padx=10);self.s=tk.StringVar(value="Ready");ttk.Label(r,textvariable=self.s).pack(fill="x",padx=10,pady=8);self.o=tk.Text(r,wrap="word");self.o.pack(fill="both",expand=True,padx=10,pady=10)
 def choose(self):
  p=filedialog.askopenfilename(filetypes=[("Images","*.jpg *.jpeg *.png")])
  if p:self.p.set(p);self.b.config(state="normal")
 def prog(self,x):self.r.after(0,lambda:self.s.set(x))
 def start(self):
  if not self.k.get().strip():messagebox.showinfo("API key","Enter your API key.");return
  self.b.config(state="disabled");threading.Thread(target=self.work,daemon=True).start()
 def work(self):
  try:x,o,u=run(self.k.get().strip(),self.p.get(),self.prog);self.r.after(0,lambda:self.show(x,o,u))
  except Exception as e:self.r.after(0,lambda e=e:self.fail(e))
  finally:self.r.after(0,lambda:self.b.config(state="normal"))
 def fail(self,e):self.o.delete("1.0","end");self.o.insert("end",repr(e));self.s.set("Failed")
 def show(self,x,o,u):
  self.o.delete("1.0","end");self.o.insert("end",f"VISUAL PROSPECT: {x['class']}\nSCORE: {x['score']}/100\nCONFIDENCE: {x['confidence']}%\n\n")
  for k in ["cooling_towers","air_cooled_chillers","large_packaged_hvac","small_packaged_hvac","piping","central_system_evidence"]:self.o.insert("end",k.replace("_"," ").upper()+"\n"+x[k]+"\n\n")
  self.o.insert("end","AMBIGUITIES\n"+"".join("• "+a+"\n" for a in x["ambiguities"])+"\nSUMMARY\n"+x["summary"]+f"\n\nTOKENS ACROSS 11 CALLS: {sum(u):,} ({u[0]:,} in / {u[1]:,} out)\n\nPER-VIEW POSITIVE DETECTIONS\n")
  for z in o:
   hits=[f"{k}={v['status']} {v['confidence']}%" for k,v in z["observations"].items() if v["status"]!="not_observed"]
   self.o.insert("end",z["view"]+": "+("; ".join(hits) if hits else "none")+"\n")
  self.s.set("10-view inspection complete (v0.6.4)")
r=tk.Tk();A(r);r.mainloop()
