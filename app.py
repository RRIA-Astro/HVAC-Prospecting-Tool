import base64, json, re, threading, tkinter as tk
from tkinter import ttk, messagebox, filedialog
try:
    from openai import OpenAI
except Exception as e:
    raise SystemExit("OpenAI Python package could not load: " + str(e))

PROMPT = """Perform a BLIND commercial HVAC aerial-image inspection. Do not infer the address, occupant, company, or business type. Focus only on visible mechanical evidence. Target equipment includes cooling towers, air-cooled chillers, large AHUs, hydronic piping and central-plant evidence. Small packaged RTUs are weak targets. Refrigeration condenser arrays can resemble chillers, so flag ambiguity rather than guessing.

Return ONLY valid JSON with keys: cooling_towers, air_cooled_chillers, large_ahu_or_rtu, small_packaged_rtus, condenser_arrays, visible_hydronic_piping, mechanical_yard, central_plant_likelihood, equipment_complexity, equipment_score, visual_prospect_class, overall_confidence, ambiguities, summary.

For each equipment item include status, count when appropriate, confidence 0-100, and short evidence. condenser_arrays must include refrigeration_possibility. central_plant_likelihood and equipment_complexity use high/medium/low. equipment_score is 0-100. visual_prospect_class is GOOD, MAYBE, or POOR. Absence of visible equipment does not prove central HVAC is absent. Do not reward building size alone."""

def analyze(key, path):
    client = OpenAI(api_key=key, timeout=120)
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    ext = path.lower().rsplit(".",1)[-1]
    mime = "image/png" if ext == "png" else "image/jpeg"
    r = client.responses.create(
        model="gpt-5.4-mini",
        reasoning={"effort":"medium"},
        input=[{"role":"user","content":[
            {"type":"input_text","text":PROMPT},
            {"type":"input_image","image_url":f"data:{mime};base64,{b64}","detail":"high"}
        ]}],
        max_output_tokens=1800
    )
    s = r.output_text.strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s, flags=re.I|re.S)
    return json.loads(s), r.usage

class App:
    def __init__(self, root):
        self.root=root
        root.title("HVAC Deep Vision v0.6.1")
        root.geometry("900x780")
        top=ttk.Frame(root,padding=10); top.pack(fill="x")
        ttk.Label(top,text="OpenAI API key:").pack(side="left")
        self.key=tk.StringVar()
        ttk.Entry(top,textvariable=self.key,show="*",width=40).pack(side="left",padx=6)
        ttk.Button(top,text="Choose Aerial Image",command=self.choose).pack(side="left",padx=5)
        self.go=ttk.Button(top,text="Analyze HVAC",command=self.start,state="disabled")
        self.go.pack(side="left")
        self.path=tk.StringVar(value="No image selected")
        ttk.Label(root,textvariable=self.path,padding=(10,0)).pack(fill="x")
        self.status=tk.StringVar(value="Ready.")
        ttk.Label(root,textvariable=self.status,padding=10).pack(fill="x")
        self.out=tk.Text(root,wrap="word",font=("Segoe UI",10))
        self.out.pack(fill="both",expand=True,padx=10,pady=10)

    def choose(self):
        p=filedialog.askopenfilename(filetypes=[("Images","*.jpg *.jpeg *.png")])
        if p:
            self.path.set(p); self.go.config(state="normal")

    def start(self):
        if not self.key.get().strip():
            messagebox.showinfo("API key","Paste your API key into the masked field. It is not saved.")
            return
        self.go.config(state="disabled")
        self.status.set("GPT-5.4 mini is inspecting the aerial image...")
        threading.Thread(target=self.work,daemon=True).start()

    def work(self):
        try:
            x,u=analyze(self.key.get().strip(),self.path.get())
            self.root.after(0,lambda:self.show(x,u))
        except Exception as e:
            self.root.after(0,lambda e=e:messagebox.showerror("Analysis failed",repr(e)))
            self.root.after(0,lambda:self.status.set("Analysis failed. See error dialog."))
        finally:
            self.root.after(0,lambda:self.go.config(state="normal"))

    def show(self,x,u):
        self.out.delete("1.0","end")
        self.out.insert("end",f"VISUAL PROSPECT: {x.get('visual_prospect_class','?')}\n")
        self.out.insert("end",f"EQUIPMENT SCORE: {x.get('equipment_score','?')}/100\n")
        self.out.insert("end",f"CONFIDENCE: {x.get('overall_confidence','?')}%\n\n")
        for k,v in x.items():
            if isinstance(v,dict):
                self.out.insert("end",k.replace("_"," ").title()+"\n")
                for a,b in v.items(): self.out.insert("end",f"  {a}: {b}\n")
                self.out.insert("end","\n")
        self.out.insert("end","AMBIGUITIES\n")
        for a in x.get("ambiguities",[]): self.out.insert("end","• "+str(a)+"\n")
        self.out.insert("end","\nSUMMARY\n"+str(x.get("summary",""))+"\n")
        try:self.out.insert("end",f"\nTokens: {u.input_tokens:,} input / {u.output_tokens:,} output")
        except Exception:pass
        self.status.set("Blind HVAC analysis complete.")

root=tk.Tk()
App(root)
root.mainloop()
