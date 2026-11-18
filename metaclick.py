import ctypes
from ctypes import wintypes
import json, os, threading, time, tkinter as tk
from tkinter import ttk, messagebox, filedialog

if os.name != "nt":
    raise SystemExit("Metaclick : Macro работает только в Windows.")

u = ctypes.windll.user32
# Correct Win32 prototypes: HWND must remain pointer-sized on 64-bit Windows.
u.IsWindow.argtypes = [wintypes.HWND]
u.IsWindow.restype = wintypes.BOOL
u.GetWindowTextLengthW.argtypes = [wintypes.HWND]
u.GetWindowTextLengthW.restype = ctypes.c_int
u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
u.GetWindowTextW.restype = ctypes.c_int
u.IsWindowVisible.argtypes = [wintypes.HWND]
u.IsWindowVisible.restype = wintypes.BOOL
u.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
u.GetClientRect.restype = wintypes.BOOL
u.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
u.PostMessageW.restype = wintypes.BOOL
u.GetAsyncKeyState.argtypes = [ctypes.c_int]
u.GetAsyncKeyState.restype = ctypes.c_short
u.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
u.MapVirtualKeyW.restype = wintypes.UINT

WM_MOUSEMOVE = 0x0200
MOUSE = {
    "Левая": (0x0201, 0x0202, 1),
    "Правая": (0x0204, 0x0205, 2),
    "Средняя": (0x0207, 0x0208, 16),
}
WM_KEYDOWN, WM_KEYUP = 0x0100, 0x0101
VK = {"SPACE": 0x20, "ENTER": 0x0D, "TAB": 0x09, "ESC": 0x1B,
      "SHIFT": 0x10, "CTRL": 0x11, "ALT": 0x12, "BACKSPACE": 0x08,
      "DELETE": 0x2E, "UP": 0x26, "DOWN": 0x28, "LEFT": 0x25, "RIGHT": 0x27}
VK.update({str(i): ord(str(i)) for i in range(10)})
VK.update({chr(i): i for i in range(65, 91)})
VK.update({f"F{i}": 0x6F + i for i in range(1, 13)})


def list_windows():
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _):
        if u.IsWindowVisible(hwnd):
            length = u.GetWindowTextLengthW(hwnd)
            if length:
                buf = ctypes.create_unicode_buffer(length + 1)
                u.GetWindowTextW(hwnd, buf, length + 1)
                if buf.value.strip():
                    found.append((buf.value.strip(), int(hwnd)))
        return True

    u.EnumWindows(callback, 0)
    return found


class App:
    def __init__(self, root):
        self.root = root
        root.title("Metaclick : Macro")
        root.geometry("470x455")
        root.resizable(False, False)

        folder = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "MetaclickMacro")
        os.makedirs(folder, exist_ok=True)
        self.settings_path = os.path.join(folder, "settings.json")

        self.items = []
        self.stop_event = threading.Event()
        self.worker = None
        self.saved_target = ""
        self.hotkeys_running = True

        self.target = tk.StringVar()
        self.interval = tk.StringVar(value="500")
        self.count = tk.StringVar(value="0")
        self.mouse_on = tk.BooleanVar(value=True)
        self.key_on = tk.BooleanVar(value=False)
        self.mouse_button = tk.StringVar(value="Левая")
        self.key = tk.StringVar(value="SPACE")
        self.status = tk.StringVar(value="Готово")

        self.load_settings()
        for variable in (self.interval, self.count, self.mouse_on, self.key_on,
                         self.mouse_button, self.key):
            variable.trace_add("write", lambda *_: self.save_settings())

        top = ttk.Frame(root)
        top.pack(fill="x", padx=12, pady=10)
        ttk.Label(top, text="Metaclick : Macro", font=("Segoe UI", 17, "bold")).pack(side="left")
        self.start_btn = ttk.Button(top, text="▶ Старт", command=self.start)
        self.start_btn.pack(side="right", padx=3)
        self.stop_btn = ttk.Button(top, text="■ Стоп", command=self.stop, state="disabled")
        self.stop_btn.pack(side="right")

        win = ttk.LabelFrame(root, text="Приложение, в котором работает макрос")
        win.pack(fill="x", padx=12, pady=5)
        row = ttk.Frame(win)
        row.pack(fill="x", padx=8, pady=8)
        self.combo = ttk.Combobox(row, textvariable=self.target, state="readonly")
        self.combo.pack(side="left", fill="x", expand=True)
        self.combo.bind("<<ComboboxSelected>>", lambda _e: self.save_settings())
        ttk.Button(row, text="⟳", width=3, command=self.refresh).pack(side="left", padx=5)

        box = ttk.LabelFrame(root, text="Действия макроса")
        box.pack(fill="x", padx=12, pady=5)
        ttk.Checkbutton(box, text="Автоклик мышью", variable=self.mouse_on).pack(anchor="w", padx=8, pady=(6, 2))
        row = ttk.Frame(box)
        row.pack(fill="x", padx=8, pady=3)
        ttk.Label(row, text="Кнопка мыши", width=15).pack(side="left")
        ttk.Combobox(row, textvariable=self.mouse_button,
                     values=["Левая", "Правая", "Средняя"], state="readonly", width=12).pack(side="left")
        ttk.Checkbutton(box, text="Нажимать клавишу одновременно",
                        variable=self.key_on, command=self.toggle_key).pack(anchor="w", padx=8, pady=(6, 2))
        self.key_row = ttk.Frame(box)
        self.key_row.pack(fill="x", padx=8, pady=4)
        ttk.Label(self.key_row, text="Клавиша", width=15).pack(side="left")
        ttk.Entry(self.key_row, textvariable=self.key, width=14).pack(side="left")
        ttk.Label(self.key_row, text="A, SPACE, ENTER, F1", foreground="#777").pack(side="left", padx=6)

        timing = ttk.LabelFrame(root, text="Повторение")
        timing.pack(fill="x", padx=12, pady=5)
        for label, variable in [("Интервал (мс)", self.interval),
                                ("Количество (0 = бесконечно)", self.count)]:
            row = ttk.Frame(timing)
            row.pack(fill="x", padx=8, pady=5)
            ttk.Label(row, text=label, width=27).pack(side="left")
            ttk.Entry(row, textvariable=variable, width=12).pack(side="left")

        save_row = ttk.Frame(root)
        save_row.pack(fill="x", padx=12, pady=(8, 2))
        ttk.Button(save_row, text="Сохранить макрос…", command=self.save_macro).pack(side="left", expand=True, fill="x", padx=(0, 4))
        ttk.Button(save_row, text="Загрузить макрос…", command=self.load_macro).pack(side="left", expand=True, fill="x", padx=(4, 0))

        ttk.Label(root, text="F6 — старт     F7 — стоп").pack(pady=(7, 2))
        ttk.Label(root, textvariable=self.status).pack()
        ttk.Label(root, text="Настройки автоматически сохраняются отдельно.", foreground="#777").pack(pady=3)
        ttk.Label(root, text="Свернуть программу можно. Игра должна принимать фоновый ввод.",
                  foreground="#777", wraplength=440).pack()

        self.refresh()
        self.toggle_key()
        # Global hotkeys: work even while another application is focused.
        self.hotkey_thread = threading.Thread(target=self.poll_hotkeys, daemon=True)
        self.hotkey_thread.start()
        root.protocol("WM_DELETE_WINDOW", self.close)

    def poll_hotkeys(self):
        was_f6 = False
        was_f7 = False
        while self.hotkeys_running:
            f6 = bool(u.GetAsyncKeyState(0x75) & 0x8000)
            f7 = bool(u.GetAsyncKeyState(0x76) & 0x8000)
            if f6 and not was_f6:
                try:
                    self.root.after(0, self.start)
                except tk.TclError:
                    break
            if f7 and not was_f7:
                try:
                    self.root.after(0, self.stop)
                except tk.TclError:
                    break
            was_f6, was_f7 = f6, f7
            time.sleep(0.025)

    def current_target_title(self):
        index = self.combo.current()
        if 0 <= index < len(self.items):
            return self.items[index][0]
        return self.saved_target

    def macro_data(self):
        return {
            "format": "MetaclickMacro",
            "version": 1,
            "target": self.current_target_title(),
            "interval_ms": self.interval.get(),
            "repeat_count": self.count.get(),
            "mouse_enabled": self.mouse_on.get(),
            "mouse_button": self.mouse_button.get(),
            "key_enabled": self.key_on.get(),
            "key": self.key.get().strip().upper(),
            "start_hotkey": "F6",
            "stop_hotkey": "F7",
        }

    def apply_macro_data(self, data):
        if data.get("format") not in (None, "MetaclickMacro"):
            raise ValueError("Это не файл макроса Metaclick.")
        self.interval.set(str(data.get("interval_ms", data.get("interval", "500"))))
        self.count.set(str(data.get("repeat_count", data.get("count", "0"))))
        self.mouse_on.set(bool(data.get("mouse_enabled", data.get("mouse_on", True))))
        self.mouse_button.set(data.get("mouse_button", "Левая"))
        self.key_on.set(bool(data.get("key_enabled", data.get("key_on", False))))
        self.key.set(str(data.get("key", "SPACE")))
        self.saved_target = str(data.get("target", ""))
        self.refresh()
        self.toggle_key()
        self.save_settings()

    def save_macro(self):
        path = filedialog.asksaveasfilename(
            title="Сохранить макрос",
            defaultextension=".mcmacro",
            filetypes=[("Макрос Metaclick", "*.mcmacro"), ("JSON", "*.json")],
            initialfile="Мой макрос.mcmacro")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as file:
                json.dump(self.macro_data(), file, ensure_ascii=False, indent=2)
            self.status.set("Макрос сохранён")
        except OSError as error:
            messagebox.showerror("Сохранение", str(error))

    def load_macro(self):
        path = filedialog.askopenfilename(
            title="Загрузить макрос",
            filetypes=[("Макрос Metaclick", "*.mcmacro"), ("JSON", "*.json"), ("Все файлы", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as file:
                data = json.load(file)
            self.apply_macro_data(data)
            self.status.set("Макрос загружен")
        except (OSError, ValueError, TypeError) as error:
            messagebox.showerror("Загрузка макроса", str(error))

    def load_settings(self):
        try:
            with open(self.settings_path, encoding="utf-8") as file:
                data = json.load(file)
            self.interval.set(str(data.get("interval", "500")))
            self.count.set(str(data.get("count", "0")))
            self.mouse_on.set(data.get("mouse_on", True))
            self.key_on.set(data.get("key_on", False))
            self.mouse_button.set(data.get("mouse_button", "Левая"))
            self.key.set(data.get("key", "SPACE"))
            self.saved_target = data.get("target", "")
        except (OSError, ValueError):
            pass

    def save_settings(self):
        data = {
            "interval": self.interval.get(), "count": self.count.get(),
            "mouse_on": self.mouse_on.get(), "key_on": self.key_on.get(),
            "mouse_button": self.mouse_button.get(), "key": self.key.get(),
            "target": self.current_target_title() if hasattr(self, "combo") else self.saved_target,
        }
        try:
            with open(self.settings_path, "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)
        except (OSError, AttributeError):
            pass

    def toggle_key(self):
        if self.key_on.get():
            self.key_row.pack(fill="x", padx=8, pady=4)
        else:
            self.key_row.pack_forget()
        self.save_settings()

    def refresh(self):
        previous = self.current_target_title() if hasattr(self, "combo") else self.saved_target
        self.items = list_windows()
        labels = [f"{title}  (#{hwnd})" for title, hwnd in self.items]
        self.combo["values"] = labels
        if labels:
            index = next((i for i, item in enumerate(self.items) if item[0] == previous), 0)
            self.combo.current(index)
            self.saved_target = self.items[index][0]
        else:
            self.target.set("Окна не найдены")
        self.save_settings()

    def start(self):
        if self.worker and self.worker.is_alive():
            return
        try:
            index = self.combo.current()
            if index < 0:
                raise ValueError("Сначала выбери приложение.")
            hwnd = self.items[index][1]
            delay = max(10, int(self.interval.get())) / 1000
            count = max(0, int(self.count.get()))
            mouse_enabled = self.mouse_on.get()
            key_enabled = self.key_on.get()
            vk = VK.get(self.key.get().strip().upper())
            if not mouse_enabled and not key_enabled:
                raise ValueError("Включи мышь, клавиатуру или оба действия.")
            if key_enabled and vk is None:
                raise ValueError("Неизвестная клавиша. Примеры: A, SPACE, ENTER, F1.")
            button = self.mouse_button.get()
            if mouse_enabled and button not in MOUSE:
                raise ValueError("Выбери кнопку мыши.")
        except Exception as error:
            messagebox.showerror("Настройки", str(error))
            return
        if not u.IsWindow(hwnd):
            messagebox.showerror("Окно", "Окно закрыто. Обнови список.")
            return

        self.saved_target = self.items[index][0]
        self.save_settings()
        self.stop_event.clear()
        self.status.set("Работает в выбранном приложении")
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.worker = threading.Thread(
            target=self.run,
            args=(hwnd, delay, count, mouse_enabled, key_enabled, button, vk),
            daemon=True)
        self.worker.start()

    def run(self, hwnd, delay, count, mouse_enabled, key_enabled, button, vk):
        completed = 0
        down, up, flag = MOUSE.get(button, (0, 0, 0))
        while (not self.stop_event.is_set() and (count == 0 or completed < count)
               and u.IsWindow(hwnd)):
            if mouse_enabled:
                rect = wintypes.RECT()
                if not u.GetClientRect(hwnd, ctypes.byref(rect)):
                    break
                x = max(1, (rect.right - rect.left) // 2)
                y = max(1, (rect.bottom - rect.top) // 2)
                lparam = ((y & 0xffff) << 16) | (x & 0xffff)
                u.PostMessageW(hwnd, WM_MOUSEMOVE, 0, lparam)
                u.PostMessageW(hwnd, down, flag, lparam)
            if key_enabled:
                scan = u.MapVirtualKeyW(vk, 0)
                key_down_lparam = 1 | (scan << 16)
                key_up_lparam = key_down_lparam | (1 << 30) | (1 << 31)
                u.PostMessageW(hwnd, WM_KEYDOWN, vk, key_down_lparam)
            time.sleep(0.05)
            if mouse_enabled:
                u.PostMessageW(hwnd, up, 0, lparam)
            if key_enabled:
                u.PostMessageW(hwnd, WM_KEYUP, vk, key_up_lparam)
            completed += 1
            self.stop_event.wait(delay)
        try:
            self.root.after(0, self.stopped)
        except tk.TclError:
            pass

    def stopped(self):
        self.status.set("Готово")
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

    def stop(self):
        self.stop_event.set()

    def close(self):
        self.save_settings()
        self.hotkeys_running = False
        self.stop()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
