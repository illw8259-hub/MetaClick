import ctypes
from ctypes import wintypes
import json, os, threading, time, tkinter as tk
from tkinter import ttk, messagebox

if os.name != "nt":
    raise SystemExit("Metaclick : Macro работает только в Windows.")
u=ctypes.windll.user32
WM_MOUSEMOVE=0x0200
MOUSE={"Левая":(0x0201,0x0202,1),"Правая":(0x0204,0x0205,2),"Средняя":(0x0207,0x0208,16)}
WM_KEYDOWN,WM_KEYUP=0x0100,0x0101
VK={"SPACE":0x20,"ENTER":0x0D,"TAB":0x09,"ESC":0x1B,"SHIFT":0x10,"CTRL":0x11,"ALT":0x12,"BACKSPACE":0x08,"DELETE":0x2E}
VK.update({str(i):ord(str(i)) for i in range(10)})
VK.update({chr(i):i for i in range(65,91)})
VK.update({f"F{i}":0x6F+i for i in range(1,13)})

def list_windows():
    found=[]
    @ctypes.WINFUNCTYPE(ctypes.c_bool,wintypes.HWND,wintypes.LPARAM)
    def cb(hwnd,_):
        if u.IsWindowVisible(hwnd):
            n=u.GetWindowTextLengthW(hwnd)
            if n:
                b=ctypes.create_unicode_buffer(n+1); u.GetWindowTextW(hwnd,b,n+1)
                if b.value.strip(): found.append((b.value.strip(),int(hwnd)))
        return True
    u.EnumWindows(cb,0)
    return found

class App:
    def __init__(self,root):
        self.root=root
        root.title("Metaclick : Macro"); root.geometry("440x410"); root.resizable(False,False)
        self.folder=os.path.join(os.environ.get("APPDATA",os.path.expanduser("~")),"MetaclickMacro")
        os.makedirs(self.folder,exist_ok=True); self.path=os.path.join(self.folder,"settings.json")
        self.items=[]; self.stop_event=threading.Event(); self.worker=None; self.saved_target=""
        self.target=tk.StringVar(); self.interval=tk.StringVar(value="500"); self.count=tk.StringVar(value="0")
        self.mouse_on=tk.BooleanVar(value=True); self.key_on=tk.BooleanVar(value=False)
        self.mouse_button=tk.StringVar(value="Левая"); self.key=tk.StringVar(value="SPACE")
        self.status=tk.StringVar(value="Готово")
        self.load()
        for v in (self.interval,self.count,self.mouse_on,self.key_on,self.mouse_button,self.key):
            v.trace_add("write",lambda *_:self.save())

        top=ttk.Frame(root); top.pack(fill="x",padx=12,pady=12)
        ttk.Label(top,text="Metaclick : Macro",font=("Segoe UI",17,"bold")).pack(side="left")
        self.start_btn=ttk.Button(top,text="▶ Старт",command=self.start); self.start_btn.pack(side="right",padx=3)
        self.stop_btn=ttk.Button(top,text="■ Стоп",command=self.stop,state="disabled"); self.stop_btn.pack(side="right")

        win=ttk.LabelFrame(root,text="Окно"); win.pack(fill="x",padx=12,pady=5)
        row=ttk.Frame(win); row.pack(fill="x",padx=8,pady=8)
        self.combo=ttk.Combobox(row,textvariable=self.target,state="readonly")
        self.combo.pack(side="left",fill="x",expand=True)
        ttk.Button(row,text="⟳",width=3,command=self.refresh).pack(side="left",padx=5)

        box=ttk.LabelFrame(root,text="Что выполнять"); box.pack(fill="x",padx=12,pady=5)
        ttk.Checkbutton(box,text="Автоклик мышью",variable=self.mouse_on,command=self.save).pack(anchor="w",padx=8,pady=(6,2))
        row=ttk.Frame(box); row.pack(fill="x",padx=8,pady=3)
        ttk.Label(row,text="Кнопка мыши",width=15).pack(side="left")
        ttk.Combobox(row,textvariable=self.mouse_button,values=["Левая","Правая","Средняя"],state="readonly",width=12).pack(side="left")
        ttk.Checkbutton(box,text="Нажимать клавишу одновременно",variable=self.key_on,command=self.toggle_key).pack(anchor="w",padx=8,pady=(6,2))
        self.key_row=ttk.Frame(box); self.key_row.pack(fill="x",padx=8,pady=4)
        ttk.Label(self.key_row,text="Клавиша",width=15).pack(side="left")
        ttk.Entry(self.key_row,textvariable=self.key,width=14).pack(side="left")
        ttk.Label(self.key_row,text="A, SPACE, ENTER, F1",foreground="#777").pack(side="left",padx=6)

        timing=ttk.LabelFrame(root,text="Повторение"); timing.pack(fill="x",padx=12,pady=5)
        for label,var in [("Интервал (мс)",self.interval),("Количество (0 = бесконечно)",self.count)]:
            row=ttk.Frame(timing); row.pack(fill="x",padx=8,pady=5)
            ttk.Label(row,text=label,width=27).pack(side="left")
            ttk.Entry(row,textvariable=var,width=12).pack(side="left")
        ttk.Label(root,text="F6 — старт     F7 — стоп").pack(pady=(7,2))
        ttk.Label(root,textvariable=self.status).pack()
        ttk.Label(root,text="Настройки сохраняются автоматически.",foreground="#777").pack(pady=4)
        ttk.Label(root,text="Фоновый ввод работает не во всех играх.",foreground="#777").pack()
        self.refresh(); self.toggle_key()
        root.bind_all("<F6>",lambda e:self.start()); root.bind_all("<F7>",lambda e:self.stop())
        root.protocol("WM_DELETE_WINDOW",self.close)

    def load(self):
        try:
            with open(self.path,encoding="utf-8") as f: d=json.load(f)
            self.interval.set(str(d.get("interval","500"))); self.count.set(str(d.get("count","0")))
            self.mouse_on.set(d.get("mouse_on",True)); self.key_on.set(d.get("key_on",False))
            self.mouse_button.set(d.get("mouse_button","Левая")); self.key.set(d.get("key","SPACE"))
            self.saved_target=d.get("target","")
        except (OSError,ValueError): pass

    def save(self):
        d={"interval":self.interval.get(),"count":self.count.get(),"mouse_on":self.mouse_on.get(),
           "key_on":self.key_on.get(),"mouse_button":self.mouse_button.get(),"key":self.key.get(),
           "target":self.items[self.combo.current()][0] if self.combo.current()>=0 and self.items else self.saved_target}
        try:
            with open(self.path,"w",encoding="utf-8") as f: json.dump(d,f,ensure_ascii=False,indent=2)
        except (OSError,AttributeError): pass

    def toggle_key(self):
        if self.key_on.get(): self.key_row.pack(fill="x",padx=8,pady=4)
        else: self.key_row.pack_forget()
        self.save()

    def refresh(self):
        self.items=list_windows(); labels=[f"{t}  (#{h})" for t,h in self.items]
        self.combo["values"]=labels
        if labels:
            i=next((i for i,x in enumerate(self.items) if x[0]==self.saved_target),0)
            self.combo.current(i)
        else: self.target.set("Окна не найдены")

    def start(self):
        if self.worker and self.worker.is_alive(): return
        try:
            i=self.combo.current()
            if i<0: raise ValueError("Сначала выбери окно.")
            hwnd=self.items[i][1]; delay=max(10,int(self.interval.get()))/1000; count=max(0,int(self.count.get()))
            mouse_on=self.mouse_on.get(); key_on=self.key_on.get(); vk=VK.get(self.key.get().strip().upper())
            if not mouse_on and not key_on: raise ValueError("Включи мышь, клавиатуру или оба действия.")
            if key_on and vk is None: raise ValueError("Неизвестная клавиша. Примеры: A, SPACE, ENTER, F1.")
            button=self.mouse_button.get()
            if mouse_on and button not in MOUSE: raise ValueError("Выбери кнопку мыши.")
        except Exception as e:
            messagebox.showerror("Настройки",str(e)); return
        if not u.IsWindow(hwnd): messagebox.showerror("Окно","Окно закрыто. Обнови список."); return
        self.saved_target=self.items[i][0]; self.save(); self.stop_event.clear()
        self.status.set("Работает"); self.start_btn.configure(state="disabled"); self.stop_btn.configure(state="normal")
        self.worker=threading.Thread(target=self.run,args=(hwnd,delay,count,mouse_on,key_on,button,vk),daemon=True)
        self.worker.start()

    def run(self,hwnd,delay,count,mouse_on,key_on,button,vk):
        done=0; down,up,flag=MOUSE.get(button,(0,0,0))
        while not self.stop_event.is_set() and (count==0 or done<count) and u.IsWindow(hwnd):
            if mouse_on:
                rect=(ctypes.c_long*4)(); u.GetClientRect(hwnd,ctypes.byref(rect))
                x=max(1,(rect[2]-rect[0])//2); y=max(1,(rect[3]-rect[1])//2); lp=((y&0xffff)<<16)|(x&0xffff)
                u.PostMessageW(hwnd,WM_MOUSEMOVE,0,lp); u.PostMessageW(hwnd,down,flag,lp)
            if key_on: u.PostMessageW(hwnd,WM_KEYDOWN,vk,0)
            time.sleep(0.03)
            if mouse_on: u.PostMessageW(hwnd,up,0,lp)
            if key_on: u.PostMessageW(hwnd,WM_KEYUP,vk,0)
            done+=1; self.stop_event.wait(delay)
        self.root.after(0,self.stopped)

    def stopped(self):
        self.status.set("Готово"); self.start_btn.configure(state="normal"); self.stop_btn.configure(state="disabled")
    def stop(self): self.stop_event.set()
    def close(self): self.save(); self.stop(); self.root.destroy()

if __name__=="__main__":
    root=tk.Tk(); App(root); root.mainloop()
