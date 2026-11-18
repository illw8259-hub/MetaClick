import ctypes
from ctypes import wintypes
import os, threading, time, tkinter as tk
from tkinter import ttk, messagebox

if os.name != "nt":
    raise SystemExit("Metaclick : Macro работает только в Windows.")
u = ctypes.windll.user32
WM_MOUSEMOVE, WM_LDOWN, WM_LUP = 0x0200, 0x0201, 0x0202
WM_RDOWN, WM_RUP, WM_MDOWN, WM_MUP = 0x0204, 0x0205, 0x0207, 0x0208
WM_KEYDOWN, WM_KEYUP = 0x0100, 0x0101
VK = {"space":0x20,"enter":0x0D,"tab":9,"esc":0x1B,"shift":0x10,"ctrl":0x11,"alt":0x12}
VK.update({chr(c):c for c in range(48,58)})
VK.update({chr(c):c-32 for c in range(97,123)})
VK.update({f"f{i}":0x6F+i for i in range(1,13)})

def windows():
    result=[]
    @ctypes.WINFUNCTYPE(ctypes.c_bool,wintypes.HWND,wintypes.LPARAM)
    def cb(hwnd,_):
        if u.IsWindowVisible(hwnd):
            n=u.GetWindowTextLengthW(hwnd)
            if n:
                b=ctypes.create_unicode_buffer(n+1); u.GetWindowTextW(hwnd,b,n+1)
                if b.value.strip(): result.append((b.value.strip(),int(hwnd)))
        return True
    u.EnumWindows(cb,0)
    return sorted(result)

class App:
    def __init__(self,root):
        self.root=root; root.title("Metaclick : Macro"); root.geometry("520x480"); root.resizable(False,False)
        self.items=[]; self.stop_event=threading.Event(); self.worker=None
        self.target=tk.StringVar(); self.interval=tk.StringVar(value="500"); self.x=tk.StringVar(value="100"); self.y=tk.StringVar(value="100")
        self.button=tk.StringVar(value="Левая"); self.count=tk.StringVar(value="0"); self.status=tk.StringVar(value="Остановлен")
        ttk.Label(root,text="Metaclick : Macro",font=("Segoe UI",19,"bold")).pack(pady=12)
        box=ttk.LabelFrame(root,text="Окно приложения"); box.pack(fill="x",padx=14,pady=6)
        row=ttk.Frame(box); row.pack(fill="x",padx=8,pady=8)
        self.combo=ttk.Combobox(row,textvariable=self.target,state="readonly"); self.combo.pack(side="left",fill="x",expand=True)
        ttk.Button(row,text="Обновить",command=self.refresh).pack(side="left",padx=6)
        box=ttk.LabelFrame(root,text="Настройки клика"); box.pack(fill="x",padx=14,pady=6)
        for label,var in [("Интервал (мс)",self.interval),("Координата X",self.x),("Координата Y",self.y),("Количество (0 = бесконечно)",self.count)]:
            r=ttk.Frame(box); r.pack(fill="x",padx=8,pady=4); ttk.Label(r,text=label,width=27).pack(side="left"); ttk.Entry(r,textvariable=var).pack(side="left",fill="x",expand=True)
        r=ttk.Frame(box); r.pack(fill="x",padx=8,pady=5); ttk.Label(r,text="Кнопка мыши",width=27).pack(side="left")
        ttk.Combobox(r,textvariable=self.button,values=["Левая","Правая","Средняя"],state="readonly").pack(side="left")
        ttk.Label(root,text="Старт: F6     Стоп: F7",font=("Segoe UI",10)).pack(pady=6)
        r=ttk.Frame(root); r.pack(fill="x",padx=14,pady=10)
        self.start_btn=ttk.Button(r,text="СТАРТ",command=self.start); self.start_btn.pack(side="left",fill="x",expand=True,padx=4,ipady=9)
        self.stop_btn=ttk.Button(r,text="СТОП",command=self.stop,state="disabled"); self.stop_btn.pack(side="left",fill="x",expand=True,padx=4,ipady=9)
        ttk.Label(root,textvariable=self.status).pack()
        ttk.Label(root,text="Фоновый ввод поддерживается не всеми играми и программами.",foreground="#777").pack(pady=8)
        self.refresh(); root.bind_all("<F6>",lambda e:self.start()); root.bind_all("<F7>",lambda e:self.stop()); root.protocol("WM_DELETE_WINDOW",self.close)
    def refresh(self):
        self.items=windows(); labels=[f"{t} [HWND {h}]" for t,h in self.items]; self.combo["values"]=labels
        if labels: self.combo.current(0)
        else: self.target.set("Окна не найдены")
    def start(self):
        if self.worker and self.worker.is_alive(): return
        try:
            idx=self.combo.current()
            if idx<0: raise ValueError("Сначала выбери окно.")
            hwnd=self.items[idx][1]; delay=max(10,int(self.interval.get()))/1000
            x,y=int(self.x.get()),int(self.y.get()); count=max(0,int(self.count.get()))
        except Exception as e: messagebox.showerror("Настройки",str(e)); return
        if not u.IsWindow(hwnd): messagebox.showerror("Окно","Окно больше не существует. Обнови список."); return
        self.stop_event.clear(); self.status.set("Работает"); self.start_btn.configure(state="disabled"); self.stop_btn.configure(state="normal")
        self.worker=threading.Thread(target=self.loop,args=(hwnd,x,y,delay,count),daemon=True); self.worker.start()
    def loop(self,hwnd,x,y,delay,count):
        down,up,flag={"Левая":(WM_LDOWN,WM_LUP,1),"Правая":(WM_RDOWN,WM_RUP,2),"Средняя":(WM_MDOWN,WM_MUP,16)}[self.button.get()]
        lp=((y&0xffff)<<16)|(x&0xffff); done=0
        while not self.stop_event.is_set() and (count==0 or done<count) and u.IsWindow(hwnd):
            u.PostMessageW(hwnd,WM_MOUSEMOVE,0,lp); u.PostMessageW(hwnd,down,flag,lp); time.sleep(.025); u.PostMessageW(hwnd,up,0,lp)
            done+=1; self.stop_event.wait(delay)
        self.root.after(0,self.stopped)
    def stopped(self):
        self.status.set("Остановлен"); self.start_btn.configure(state="normal"); self.stop_btn.configure(state="disabled")
    def stop(self):
        self.stop_event.set()
    def close(self):
        self.stop(); self.root.destroy()

if __name__=="__main__":
    root=tk.Tk(); App(root); root.mainloop()
