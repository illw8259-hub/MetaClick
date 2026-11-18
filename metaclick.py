import ctypes
from ctypes import wintypes
import json, os, threading, time, tkinter as tk
from tkinter import ttk, messagebox

if os.name != "nt":
    raise SystemExit("Metaclick : Macro работает только в Windows.")
user32 = ctypes.windll.user32
WM_MOUSEMOVE, WM_LDOWN, WM_LUP = 0x0200, 0x0201, 0x0202
WM_KEYDOWN, WM_KEYUP = 0x0100, 0x0101
VK = {"space":0x20,"enter":0x0D,"tab":0x09,"esc":0x1B,"shift":0x10,
      "ctrl":0x11,"alt":0x12,"backspace":0x08,"delete":0x2E}
VK.update({str(i):ord(str(i)) for i in range(10)})
VK.update({chr(i):i for i in range(65,91)})
VK.update({f"f{i}":0x70+i-1 for i in range(1,13)})

def list_windows():
    found=[]
    @ctypes.WINFUNCTYPE(ctypes.c_bool,wintypes.HWND,wintypes.LPARAM)
    def callback(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            length=user32.GetWindowTextLengthW(hwnd)
            if length:
                title=ctypes.create_unicode_buffer(length+1)
                user32.GetWindowTextW(hwnd,title,length+1)
                if title.value.strip(): found.append((title.value.strip(),int(hwnd)))
        return True
    user32.EnumWindows(callback,0)
    return found

class App:
    def __init__(self, root):
        self.root=root
        root.title("Metaclick : Macro")
        root.geometry("430x390")
        root.resizable(False,False)
        self.config_dir=os.path.join(os.environ.get("APPDATA",os.path.expanduser("~")),"MetaclickMacro")
        os.makedirs(self.config_dir,exist_ok=True)
        self.config_path=os.path.join(self.config_dir,"settings.json")
        self.items=[]
        self.stop_event=threading.Event()
        self.worker=None
        self.target=tk.StringVar()
        self.interval=tk.StringVar(value="500")
        self.count=tk.StringVar(value="0")
        self.action=tk.StringVar(value="Клик мышью")
        self.key=tk.StringVar(value="SPACE")
        self.status=tk.StringVar(value="Готово")
        self.saved_target=""
        self.load_settings()
        for variable in (self.interval,self.count,self.action,self.key):
            variable.trace_add("write",lambda *_: self.save_settings())

        top=ttk.Frame(root)
        top.pack(fill="x",padx=12,pady=(12,6))
        ttk.Label(top,text="Metaclick : Macro",font=("Segoe UI",17,"bold")).pack(side="left")
        self.start_btn=ttk.Button(top,text="▶ Старт",command=self.start)
        self.start_btn.pack(side="right",padx=(5,0))
        self.stop_btn=ttk.Button(top,text="■ Стоп",command=self.stop,state="disabled")
        self.stop_btn.pack(side="right")

        win=ttk.LabelFrame(root,text="Целевое окно")
        win.pack(fill="x",padx=12,pady=6)
        row=ttk.Frame(win); row.pack(fill="x",padx=8,pady=8)
        self.combo=ttk.Combobox(row,textvariable=self.target,state="readonly")
        self.combo.pack(side="left",fill="x",expand=True)
        ttk.Button(row,text="⟳",width=3,command=self.refresh).pack(side="left",padx=(5,0))

        settings=ttk.LabelFrame(root,text="Действие")
        settings.pack(fill="x",padx=12,pady=6)
        row=ttk.Frame(settings); row.pack(fill="x",padx=8,pady=6)
        ttk.Label(row,text="Что повторять",width=15).pack(side="left")
        action_box=ttk.Combobox(row,textvariable=self.action,values=["Клик мышью","Нажатие клавиши"],state="readonly")
        action_box.pack(side="left",fill="x",expand=True)
        action_box.bind("<<ComboboxSelected>>",lambda e:self.toggle_key())
        self.key_row=ttk.Frame(settings)
        self.key_row.pack(fill="x",padx=8,pady=5)
        ttk.Label(self.key_row,text="Клавиша",width=15).pack(side="left")
        ttk.Entry(self.key_row,textvariable=self.key).pack(side="left",fill="x",expand=True)
        ttk.Label(self.key_row,text="Напр. A, SPACE, F6",foreground="#777").pack(side="left",padx=6)

        timing=ttk.LabelFrame(root,text="Повторение")
        timing.pack(fill="x",padx=12,pady=6)
        for label,var in [("Интервал (мс)",self.interval),("Количество (0 = бесконечно)",self.count)]:
            row=ttk.Frame(timing); row.pack(fill="x",padx=8,pady=5)
            ttk.Label(row,text=label,width=25).pack(side="left")
            ttk.Entry(row,textvariable=var,width=12).pack(side="left")

        ttk.Label(root,text="F6 — старт     F7 — стоп",font=("Segoe UI",10)).pack(pady=(6,2))
        ttk.Label(root,textvariable=self.status).pack()
        ttk.Label(root,text="Настройки сохраняются автоматически.",foreground="#777").pack(pady=5)
        ttk.Label(root,text="Фоновый ввод поддерживается не всеми играми.",foreground="#777").pack()

        self.refresh()
        self.toggle_key()
        root.bind_all("<F6>",lambda e:self.start())
        root.bind_all("<F7>",lambda e:self.stop())
        root.protocol("WM_DELETE_WINDOW",self.close)

    def load_settings(self):
        try:
            with open(self.config_path,"r",encoding="utf-8") as f: data=json.load(f)
            self.interval.set(str(data.get("interval","500")))
            self.count.set(str(data.get("count","0")))
            self.action.set(data.get("action","Клик мышью"))
            self.key.set(data.get("key","SPACE"))
            self.saved_target=data.get("target","")
        except (OSError,ValueError): pass

    def save_settings(self):
        data={"interval":self.interval.get(),"count":self.count.get(),
              "action":self.action.get(),"key":self.key.get(),
              "target":self.items[self.combo.current()][0] if self.combo.current()>=0 and self.items else self.saved_target}
        try:
            with open(self.config_path,"w",encoding="utf-8") as f:
                json.dump(data,f,ensure_ascii=False,indent=2)
        except OSError: pass

    def toggle_key(self):
        if self.action.get()=="Нажатие клавиши": self.key_row.pack(fill="x",padx=8,pady=5)
        else: self.key_row.pack_forget()
        self.save_settings()

    def refresh(self):
        self.items=list_windows()
        labels=[f"{title}  (#{hwnd})" for title,hwnd in self.items]
        self.combo["values"]=labels
        if labels:
            wanted=next((i for i,item in enumerate(self.items) if item[0]==self.saved_target),0)
            self.combo.current(wanted)
        else:
            self.target.set("Окна не найдены")

    def start(self):
        if self.worker and self.worker.is_alive(): return
        try:
            idx=self.combo.current()
            if idx<0: raise ValueError("Сначала выбери окно.")
            hwnd=self.items[idx][1]
            delay=max(10,int(self.interval.get()))/1000
            count=max(0,int(self.count.get()))
            key_name=self.key.get().strip().lower()
            vk=VK.get(key_name)
            if self.action.get()=="Нажатие клавиши" and vk is None:
                raise ValueError("Неизвестная клавиша. Примеры: A, SPACE, ENTER, F6.")
        except Exception as e:
            messagebox.showerror("Проверь настройки",str(e)); return
        if not user32.IsWindow(hwnd):
            messagebox.showerror("Окно","Окно закрыто. Обнови список."); return
        self.saved_target=self.items[idx][0]
        self.save_settings()
        self.stop_event.clear()
        self.status.set("Работает")
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.worker=threading.Thread(target=self.run,args=(hwnd,delay,count,vk),daemon=True)
        self.worker.start()

    def run(self,hwnd,delay,count,vk):
        done=0
        while not self.stop_event.is_set() and (count==0 or done<count) and user32.IsWindow(hwnd):
            if self.action.get()=="Клик мышью":
                rect=(ctypes.c_long*4)()
                user32.GetClientRect(hwnd,ctypes.byref(rect))
                x=max(1,(rect[2]-rect[0])//2); y=max(1,(rect[3]-rect[1])//2)
                lp=((y&0xffff)<<16)|(x&0xffff)
                user32.PostMessageW(hwnd,WM_MOUSEMOVE,0,lp)
                user32.PostMessageW(hwnd,WM_LDOWN,1,lp)
                time.sleep(0.03)
                user32.PostMessageW(hwnd,WM_LUP,0,lp)
            else:
                user32.PostMessageW(hwnd,WM_KEYDOWN,vk,0)
                time.sleep(0.03)
                user32.PostMessageW(hwnd,WM_KEYUP,vk,0)
            done+=1
            self.stop_event.wait(delay)
        self.root.after(0,self.stopped)

    def stopped(self):
        self.status.set("Готово")
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

    def stop(self):
        self.stop_event.set()

    def close(self):
        self.save_settings()
        self.stop()
        self.root.destroy()

if __name__=="__main__":
    root=tk.Tk()
    App(root)
    root.mainloop()
