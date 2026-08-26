import base64,json,threading,tkinter as tk
from tkinter import ttk,messagebox,filedialog
from openai import OpenAI
SCHEMA={"type":"object","additionalProperties":False,"properties":{
"cooling_towers":{"$ref":"#/$defs/equipment"},"air_cooled_chillers":{"$ref":"#/$defs/equipment"},
"large_ahu_or_rtu":{"$ref":"#/$defs/equipment"},"small_packaged_rtus":{"$ref":"#/$defs/equipment"},
"condenser_arrays":{"type":"object","additionalProperties":False,"properties":{"status":{"type":"string"},"count":{"type":"integer"},"refrigeration_possibility":{"type":"string"},"confidence":{"type":"integer"},"evidence":{"type":"string"}},"required":["status","count","refrigeration_possibility","confidence","evidence"]},
"visible_hydronic_piping":{"$ref":"#/$defs/simple"},"mechanical_yard":{"$ref":"#/$defs/simple"},
"central_plant_likelihood":{"$ref":"#/$defs/level"},"equipment_complexity":{"$ref":"#/$defs/level"},
"equipment_score":{"type":"integer"},"visual_prospect_class":{"type":"string","enum":["GOOD","MAYBE","POOR"]},
"overall_confidence":{"type":"integer"},"ambiguities":{"type":"array","items":{"type":"string"}},"summary":{"type":"string"}},
"required":["cooling_towers","air_cooled_chillers","large_ahu_or_rtu","small_packaged_rtus","condenser_arrays","visible_hydronic_piping","mechanical_yard","central_plant_likelihood","equipment_complexity","equipment_score","visual_prospect_class","overall_confidence","ambiguities","summary"],
"$defs":{"equipment":{"type":"object","additionalProperties":False,"properties":{"status":{"type":"string"},"count":{"type":"integer"},"confidence":{"type":"integer"},"evidence":{"type":"string"}},"required":["status","count","confidence","evidence"]},
"simple":{"type":"object","additionalProperties":False,"properties":{"status":{"type":"string"},"confidence":{"type":"integer"},"evidence":{"type":"string"}},"required":["status","confidence","evidence"]},
"level":{"type":"object","additionalProperties":False,"properties":{"level":{"type":"string","enum":["high","medium","low"]},"confidence":{"type":"integer"},"evidence":{"type":"string"}},"required":["level","confidence","evidence"]}}}
PROMPT="""Perform a BLIND commercial HVAC aerial-image inspection. Do not infer address, occupant, company, or business type. Judge visible mechanical evidence only. Favor central plants, cooling towers, air-cooled chillers, hydronic systems, large AHUs and mechanical complexity. Small packaged RTU sites are weak. Refrigeration condenser arrays can resemble chillers: flag ambiguity rather than guessing. GOOD requires strong visible evidence; MAYBE means meaningful but ambiguous/incomplete evidence; POOR means predominantly small/sparse/unattractive equipment. Absence of visible equipment does not prove central HVAC is absent. Do not reward building size alone. Keep evidence concise."""
def analyze(key,path):
 c=OpenAI(api_key=key,timeout=150)
 with open(path,"rb") as f:data=base64.b64encode(f.read()).decode()
 mime="image/png" if path.lower().endswith(".png") else "image/jpeg"
 last=None
 for attempt in range(2):
  r=c.responses.create(model="gpt-5.4-mini",reasoning={"effort":"medium"},
   input=[{"role":"user","content":[{"type":"input_text","text":PROMPT},{"type":"input_image","image_url":f"data:{mime};base64,{data}","detail":"high"}]}],
   text={"format":{"type":"json_schema","name":"hvac_assessment","strict":True,"schema":SCHEMA},"verbosity":"low"},max_output_tokens=4000)
  last=r; raw=(r.output_text or "").strip()
  if r.status=="completed" and raw:
   try:return json.loads(raw),r,None
   except Exception as e:
    if attempt==0:continue
    return None,r,f"Parse error: {e}\n\nRAW RESPONSE:\n{raw}"
  if attempt==0 and r.status in ("incomplete","failed"):continue
  reason=getattr(getattr(r,"incomplete_details",None),"reason",None)
  return None,r,f"Response status: {r.status}\nReason: {reason}\nError: {r.error}\n\nRAW RESPONSE:\n{raw or '[empty]'}"
 return None,last,"No usable response."
class App:
 def __init__(self,r):
  self.r=r;r.title("HVAC Deep Vision v0.6.2");r.geometry("940x820")
  f=ttk.Frame(r,padding=10);f.pack(fill="x");ttk.Label(f,text="OpenAI API key:").pack(side="left")
  self.k=tk.StringVar();ttk.Entry(f,textvariable=self.k,show="*",width=40).pack(side="left",padx=6)
  ttk.Button(f,text="Choose Aerial Image",command=self.choose).pack(side="left",padx=5);self.b=ttk.Button(f,text="Analyze HVAC",command=self.start,state="disabled");self.b.pack(side="left")
  self.p=tk.StringVar(value="No image selected");ttk.Label(r,textvariable=self.p,padding=(10,0)).pack(fill="x")
  self.s=tk.StringVar(value="Ready.");ttk.Label(r,textvariable=self.s,padding=10).pack(fill="x");self.o=tk.Text(r,wrap="word");self.o.pack(fill="both",expand=True,padx=10,pady=10)
 def choose(self):
  p=filedialog.askopenfilename(filetypes=[("Images","*.jpg *.jpeg *.png")])
  if p:self.p.set(p);self.b.config(state="normal")
 def start(self):
  if not self.k.get().strip():messagebox.showinfo("API key","Paste your API key. It is not saved.");return
  self.b.config(state="disabled");self.s.set("GPT-5.4 mini inspecting HVAC...");threading.Thread(target=self.work,daemon=True).start()
 def work(self):
  try:x,r,e=analyze(self.k.get().strip(),self.p.get());self.r.after(0,lambda:self.show(x,r,e))
  except Exception as e:self.r.after(0,lambda e=e:self.show(None,None,repr(e)))
  finally:self.r.after(0,lambda:self.b.config(state="normal"))
 def show(self,x,r,e):
  self.o.delete("1.0","end")
  if e:self.o.insert("end","DIAGNOSTIC ERROR\n\n"+e);self.s.set("Analysis failed — details shown.");return
  self.o.insert("end",f"VISUAL PROSPECT: {x['visual_prospect_class']}\nEQUIPMENT SCORE: {x['equipment_score']}/100\nCONFIDENCE: {x['overall_confidence']}%\n\n")
  for k,v in x.items():
   if isinstance(v,dict):
    self.o.insert("end",k.replace("_"," ").title()+"\n")
    for a,b in v.items():self.o.insert("end",f"  {a}: {b}\n")
    self.o.insert("end","\n")
  self.o.insert("end","AMBIGUITIES\n"+"".join("• "+a+"\n" for a in x["ambiguities"])+"\nSUMMARY\n"+x["summary"])
  try:self.o.insert("end",f"\n\nAPI USAGE\nInput: {r.usage.input_tokens:,}\nOutput: {r.usage.output_tokens:,}\nTotal: {r.usage.total_tokens:,}")
  except:pass
  self.s.set("Blind HVAC analysis complete.")
r=tk.Tk();App(r);r.mainloop()
