import base64,json,threading,tkinter as tk
from tkinter import ttk,filedialog,messagebox
from pathlib import Path
from PIL import Image
from openai import OpenAI
MODEL="gpt-5.4-mini"
OBS={"type":"object","additionalProperties":False,"properties":{k:{"type":"object","additionalProperties":False,"properties":{"status":{"type":"string","enum":["strong","probable","possible","not_observed"]},"quantity":{"type":"string","enum":["none","one","few","several","many","unknown"]},"confidence":{"type":"integer"},"evidence":{"type":"string"}},"required":["status","quantity","confidence","evidence"]} for k in ["cooling_towers","air_cooled_chillers","large_packaged_hvac","small_packaged_hvac","condensers","piping","mechanical_yard"]},"required":["cooling_towers","air_cooled_chillers","large_packaged_hvac","small_packaged_hvac","condensers","piping","mechanical_yard"]}
FINAL={"type":"object","additionalProperties":False,"properties":{"class":{"type":"string","enum":["GOOD","MAYBE","POOR"]},"score":{"type":"integer"},"confidence":{"type":"integer"},"cooling_towers":{"type":"string"},"air_cooled_chillers":{"type":"string"},"large_packaged_hvac":{"type":"string"},"small_packaged_hvac":{"type":"string"},"piping":{"type":"string"},"central_system_evidence":{"type":"string"},"ambiguities":{"type":"array","items":{"type":"string"}},"summary":{"type":"string"}},"required":["class","score","confidence","cooling_towers","air_cooled_chillers","large_packaged_hvac","small_packaged_hvac","piping","central_system_evidence","ambiguities","summary"]}
IP="""BLIND COMMERCIAL HVAC FORENSIC AERIAL INSPECTION. Inspect ALL visible roof AND ground/perimeter areas.

Identify candidate equipment AND trace visible piping to discriminate equipment types.

HYDRONIC / PROCESS-WATER PIPING uses WEIGHTED evidence. Valves/flanges are NOT required. Strong clues include:
- substantial diameter relative to condensate/drain piping;
- paired supply/return-style runs;
- multiple 90-degree turns or complex purposeful routing;
- elevation changes/supports;
- direct equipment-to-building or equipment-to-penthouse termination;
- insulation;
- valves, flanges, headers, strainers, gauges, pumps and fittings WHEN visible.
White pipe is not automatically PVC. Large insulated white piping can be hydronic/process-water piping.

CONDENSATE / DX:
- A small PVC condensate drain is POSITIVE evidence for direct-expansion packaged HVAC and AGAINST interpreting that unit as an air-cooled water chiller.
- Condensate drainage is generally small and comparatively simple/gravity-routed.
- Do not confuse a drain with a substantial paired circuit having multiple turns and purposeful routing.

CONNECTION TRACING:
- Whenever credible substantial or complex piping is visible, trace it in BOTH directions as far as the view permits.
- Determine whether it appears equipment-to-building, equipment-to-penthouse, equipment-to-equipment, or unresolved.
- If piping reaches an ambiguous fan-topped object, RECONSIDER that object's identity using the connection.
- Strong equipment-to-building paired water piping can support a chiller/process-cooling interpretation even when valves/flanges are indoors or obscured.

AIR-COOLED / PROCESS CHILLERS:
- Morphology alone is insufficient.
- Large multi-fan equipment connected to a substantial paired/routed water circuit can be a chiller even without externally visible specialties.
- Process chillers may look different from typical comfort-cooling chillers; connection evidence may be more diagnostic than cabinet shape.

PACKAGED RTU / AHU:
- Favor packaged DX when cabinet/curb/duct morphology is present, especially with a small condensate drain and no substantial water circuit.
- Do not classify prominent exhaust, make-up-air, kitchen-hood, or ventilation equipment as a large RTU solely because it is physically large.

COOLING TOWERS / HEAT REJECTION:
- Search for conventional towers AND screened, partly enclosed, low-profile, closed-circuit, evaporative, induced-draft, and process heat-rejection equipment.
- Do not require a visible plume.
- Atypical fan-array/tower morphology PLUS substantial condenser/process-water piping is meaningful combined evidence.
- If credible large water piping terminates at a tower-like/fan-array object, raise heat-rejection probability even if the form factor is unfamiliar.

CENTRAL SYSTEM CAUTION:
- Mechanical complexity alone does NOT establish a central plant.
- Generic conduit, roof drains, seams, rails, shadows, gas piping, or isolated lines do NOT establish hydronic piping.
- Conversely, do not reject a central system merely because valves/flanges are not visible when pipe size, pairing, routing geometry, and termination strongly support a pumped water circuit.

Do not infer address, occupant, company, or building type. Use not_observed rather than claiming absence from one crop. Use quantity bands, not exact counts. Preserve plausible high-value equipment for synthesis."""
SP="""Synthesize the independent overlapping observations from ONE property and deduplicate them. Use HVAC forensic CONNECTION EVIDENCE.

WEIGHTED PIPING RULE:
Do NOT require visible valves/flanges for hydronic/process-water piping. Strong evidence can arise from substantial diameter + paired runs + multiple 90-degree turns/complex routing + direct equipment-to-building/penthouse termination. Insulation, valves, flanges, headers, pumps and fittings strengthen the conclusion but are not mandatory. White pipe is not automatically PVC.

DX RULE:
Small simple PVC condensate drainage is positive DX evidence and MUST NOT create central-plant evidence. Large paired complex routed piping is fundamentally different.

TRACE BEFORE CLASSIFYING:
- If any crop reports credible substantial or complex piping, use the reported endpoints and geometry to reconsider connected equipment.
- Large fan-topped equipment connected by a substantial paired routed circuit to a building/penthouse may be an air-cooled or process chiller despite atypical morphology.
- Tower-like/fan-array equipment connected to substantial condenser/process-water piping may be cooling-tower/heat-rejection equipment even if screened, low-profile, enclosed, or nonstandard.
- If strong piping evidence exists but equipment identity remains uncertain, preserve the property as a high-value prospect rather than automatically collapsing it to packaged DX.

PACKAGED DX CHECK:
Favor packaged RTU/AHU when cabinet/curb/duct evidence exists AND no substantial water circuit connects to the unit. A small condensate drain supports DX. Mechanical complexity alone does NOT establish a central plant.

SCORING:
- Confirmed/probable chiller, cooling tower, or strong traceable pumped central/process-water circuit should materially raise prospect score.
- A credible unresolved large chiller/tower candidate with strong connection evidence should generally keep the property GOOD or upper-MAYBE for human review.
- Genuinely large packaged RTUs can be worthwhile.
- Numerous small packaged units alone are weak.
- Not_observed is not proof of absence.

In central_system_evidence and summary, explicitly explain the evidence chain, for example: substantial paired piping + multiple routed turns + equipment-to-building termination -> probable pumped hydronic/process-water circuit. Do not infer property identity or building type."""
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
  self.r=r;r.title("HVAC Deep Vision v0.6.6 — Connection Tracing");r.geometry("980x840");f=ttk.Frame(r,padding=10);f.pack(fill="x");ttk.Label(f,text="API key:").pack(side="left");self.k=tk.StringVar();ttk.Entry(f,textvariable=self.k,show="*",width=38).pack(side="left",padx=5);ttk.Button(f,text="Choose Image",command=self.choose).pack(side="left");self.b=ttk.Button(f,text="Run 10-View Inspection",command=self.start,state="disabled");self.b.pack(side="left",padx=5);self.p=tk.StringVar(value="No image selected");ttk.Label(r,textvariable=self.p).pack(fill="x",padx=10);self.s=tk.StringVar(value="Ready");ttk.Label(r,textvariable=self.s).pack(fill="x",padx=10,pady=8);self.o=tk.Text(r,wrap="word");self.o.pack(fill="both",expand=True,padx=10,pady=10)
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
  self.s.set("10-view connection-tracing inspection complete (v0.6.6)")
r=tk.Tk();A(r);r.mainloop()
