"""
Window Focus Helper
-------------------
- Systray: click derecho para abrir el selector o salir
- Selector: elegís una ventana activa → genera la URL lista para Companion
- HTTP server en localhost:PUERTO (configurable con --port o desde la app)
- Al iniciar registra automáticamente todas las ventanas visibles
  (las de Google Chrome como "Google Chrome")

Compilar:
    pip install pyinstaller pystray pillow
    pyinstaller --onefile --noconsole --hidden-import=pystray._win32 window_focus.py

Uso:
    window_focus.exe                  (puerto 3500)
    window_focus.exe --port=8000
    window_focus.exe -p 8000
"""

import sys
import os
import re
import argparse
import threading
import tempfile
import ctypes
import ctypes.wintypes
import tkinter as tk
from tkinter import font as tkfont, simpledialog
from http.server import HTTPServer, BaseHTTPRequestHandler

import pystray
from PIL import Image, ImageDraw

# ──────────────────────────────────────────────
# Configuración del puerto (por línea de comandos)
# ──────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--port", "-p", type=int, default=3500, help="Puerto del servidor HTTP")
args = parser.parse_args()
PORT = args.port

# ──────────────────────────────────────────────
# Variables globales para el servidor y el icono
# ──────────────────────────────────────────────
http_server = None
http_server_lock = threading.Lock()
tray_icon = None

# ──────────────────────────────────────────────
# Rutas registradas (slug → título parcial)
# ──────────────────────────────────────────────
ROUTES: dict = {}
ROUTES_LOCK = threading.Lock()

# ──────────────────────────────────────────────
# Win32 helpers
# ──────────────────────────────────────────────
WNDENUMPROC = ctypes.WINFUNCTYPE(
    ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM
)

def get_visible_windows():
    results = []
    def callback(hwnd, _):
        if not ctypes.windll.user32.IsWindowVisible(hwnd):
            return True
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value.strip()
            if title:
                results.append((hwnd, title))
        return True
    ctypes.windll.user32.EnumWindows(WNDENUMPROC(callback), 0)
    return results

def activate_hwnd(hwnd):
    """
    Activa la ventana y la trae al frente INCLUSO si el proceso Python
    no está en primer plano. Usa una simulación de tecla Alt para
    ganar el derecho de foco.
    """
    u32 = ctypes.windll.user32
    VK_MENU = 0x12   # Alt key

    # Simular Alt
    u32.keybd_event(VK_MENU, 0, 0, 0)   # down
    u32.keybd_event(VK_MENU, 0, 2, 0)   # up

    # Restaurar si está minimizada
    u32.ShowWindow(hwnd, 9)  # SW_RESTORE

    # Top-most temporal
    u32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0002 | 0x0001)   # HWND_TOPMOST
    u32.SetWindowPos(hwnd, -2, 0, 0, 0, 0, 0x0002 | 0x0001)   # HWND_NOTOPMOST

    # Traer al frente y dar foco
    u32.BringWindowToTop(hwnd)
    u32.SetForegroundWindow(hwnd)
    return True

def activate_by_partial(partial):
    for hwnd, title in get_visible_windows():
        if partial.lower() in title.lower():
            activate_hwnd(hwnd)
            return True
    return False

# ──────────────────────────────────────────────
# HTTP server
# ──────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        key = self.path.strip("/").lower()
        with ROUTES_LOCK:
            partial = ROUTES.get(key)
        if partial:
            ok = activate_by_partial(partial)
            self.send_response(200 if ok else 404)
        else:
            self.send_response(404)
        self.end_headers()

    def log_message(self, *args):
        pass

def run_server(port):
    """Ejecuta el servidor HTTP en el puerto dado (bloqueante)."""
    global http_server
    server = HTTPServer(("localhost", port), Handler)
    with http_server_lock:
        http_server = server
    try:
        server.serve_forever()
    finally:
        server.server_close()
        with http_server_lock:
            if http_server == server:
                http_server = None

def start_server(port):
    """Inicia el servidor en un hilo daemon y retorna el hilo."""
    t = threading.Thread(target=run_server, args=(port,), daemon=True)
    t.start()
    return t

def stop_server():
    """Detiene el servidor actual si está corriendo."""
    with http_server_lock:
        server = http_server
    if server:
        server.shutdown()

# ──────────────────────────────────────────────
# Helpers slug / título
# ──────────────────────────────────────────────
def extract_base_title(full_title):
    """Extrae la parte estable antes de ' - ', ' | ', etc."""
    segment = re.split(r"\s+[-|:]\s+", full_title)[0].strip()
    return segment

def to_slug(text):
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", "-", text.strip())
    text = re.sub(r"-+", "-", text)
    return text

# ──────────────────────────────────────────────
# Registro automático inicial
# ──────────────────────────────────────────────
def auto_register_windows():
    """Registra automáticamente todas las ventanas visibles en las rutas."""
    windows = get_visible_windows()
    with ROUTES_LOCK:
        for hwnd, title in windows:
            # Si es Google Chrome (o navegador Chrome), usar solo "Google Chrome"
            if "google chrome" in title.lower():
                partial = "Google Chrome"
            else:
                partial = extract_base_title(title)

            slug = to_slug(partial)
            # Solo registrar si no existe ya (para no pisar edits manuales posteriores)
            if slug not in ROUTES:
                ROUTES[slug] = partial

# ──────────────────────────────────────────────
# Paleta
# ──────────────────────────────────────────────
C = {
    "bg":           "#0d0d15",
    "panel":        "#161622",
    "panel2":       "#1e1e30",
    "border":       "#252538",
    "accent":       "#7c6af7",
    "accent_dim":   "#4a3fa0",
    "accent_hover": "#9d8fff",
    "text":         "#e2e2f0",
    "muted":        "#5a5a7a",
    "success":      "#50fa7b",
    "warn":         "#f1c40f",
    "select_bg":    "#3a3060",
}

# ──────────────────────────────────────────────
# Icono común (ventana + systray)
# ──────────────────────────────────────────────
def create_app_icon():
    sz = 64
    img = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([0, 0, sz - 1, sz - 1], fill="#161622")
    m = 12
    d.rectangle([m, m + 6, sz - m, sz - m], outline="#7c6af7", width=3)
    d.rectangle([m, m + 6, sz - m, m + 16], fill="#7c6af7")
    d.ellipse([m + 3, m + 8, m + 9, m + 14], fill="#161622")
    d.ellipse([m + 13, m + 8, m + 19, m + 14], fill="#161622")
    ico_file = os.path.join(tempfile.gettempdir(), "window_focus_icon.ico")
    img.save(ico_file, format="ICO", sizes=[(64, 64)])
    return ico_file

# ──────────────────────────────────────────────
# UI
# ──────────────────────────────────────────────
def show_selector():
    all_windows = get_visible_windows()
    shown = list(all_windows)

    root = tk.Tk()
    root.title("Window Focus")
    root.geometry("700x500")
    root.minsize(580, 380)
    root.configure(bg=C["bg"])
    root.attributes("-topmost", True)

    ico = create_app_icon()
    root.iconbitmap(default=ico)

    root.update_idletasks()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"700x500+{(sw-700)//2}+{(sh-500)//2}")

    # Fuentes seguras (dentro de show_selector)
    def safe_font(family, size, weight="normal"):
        try:
            return tkfont.Font(family=family, size=size, weight=weight)
        except Exception:
            fallback = tkfont.nametofont("TkDefaultFont").copy()
            fallback.configure(size=size, weight=weight)
            return fallback

    f_title = safe_font("Segoe UI", 13, "bold")
    f_body  = safe_font("Segoe UI", 10)
    f_mono  = safe_font("Consolas", 10)
    f_small = safe_font("Segoe UI", 9)
    f_btn   = safe_font("Segoe UI", 10, "bold")
    f_lbl   = safe_font("Segoe UI", 8)

    # ── Header ──
    hdr = tk.Frame(root, bg=C["panel"], pady=12)
    hdr.pack(fill="x")
    tk.Label(hdr, text="⬡  WINDOW FOCUS", bg=C["panel"],
             fg=C["accent"], font=f_title, padx=18).pack(side="left")
    count_var = tk.StringVar(value=f"{len(shown)} ventanas")
    tk.Label(hdr, textvariable=count_var, bg=C["panel"],
             fg=C["muted"], font=f_small, padx=18).pack(side="right")
    tk.Frame(root, bg=C["border"], height=1).pack(fill="x")

    # ── Columnas ──
    main = tk.Frame(root, bg=C["bg"])
    main.pack(fill="both", expand=True)

    # Izquierda: lista
    left = tk.Frame(main, bg=C["bg"], width=320)
    left.pack(side="left", fill="both", expand=True)
    left.pack_propagate(False)

    sf = tk.Frame(left, bg=C["bg"], padx=12, pady=8)
    sf.pack(fill="x")
    tk.Label(sf, text="🔍", bg=C["bg"], fg=C["muted"]).pack(side="left")
    search_var = tk.StringVar()
    tk.Entry(sf, textvariable=search_var, bg=C["panel2"], fg=C["text"],
             insertbackground=C["accent"], relief="flat", font=f_mono, bd=0
             ).pack(side="left", fill="x", expand=True, padx=6, ipady=5)
    tk.Frame(left, bg=C["border"], height=1).pack(fill="x", padx=12)

    lf = tk.Frame(left, bg=C["bg"], padx=12, pady=6)
    lf.pack(fill="both", expand=True)
    sb = tk.Scrollbar(lf, bg=C["panel"], troughcolor=C["bg"],
                      relief="flat", bd=0, width=6)
    sb.pack(side="right", fill="y")
    lb = tk.Listbox(lf, yscrollcommand=sb.set, bg=C["panel2"], fg=C["text"],
                    selectbackground=C["select_bg"], selectforeground=C["text"],
                    activestyle="none", relief="flat", bd=0, font=f_mono,
                    highlightthickness=1, highlightcolor=C["accent"],
                    highlightbackground=C["border"], cursor="hand2")
    lb.pack(side="left", fill="both", expand=True)
    sb.config(command=lb.yview)

    # Separador
    tk.Frame(main, bg=C["border"], width=1).pack(side="left", fill="y")

    # Derecha: detalle
    right = tk.Frame(main, bg=C["panel"], width=340, padx=20, pady=18)
    right.pack(side="left", fill="both")
    right.pack_propagate(False)

    def section_label(parent, text):
        tk.Label(parent, text=text, bg=C["panel"],
                 fg=C["muted"], font=f_lbl).pack(anchor="w", pady=(10, 2))

    section_label(right, "VENTANA SELECCIONADA")
    sel_var = tk.StringVar(value="Seleccioná una ventana")
    tk.Label(right, textvariable=sel_var, bg=C["panel"], fg=C["text"],
             font=f_body, wraplength=290, justify="left", anchor="w"
             ).pack(anchor="w")

    section_label(right, "BUSCAR POR (editable)")
    search_by_var = tk.StringVar()
    sb_entry = tk.Entry(right, textvariable=search_by_var,
                        bg=C["panel2"], fg=C["text"],
                        insertbackground=C["accent"], relief="flat",
                        font=f_mono, bd=0, state="disabled",
                        disabledbackground=C["panel2"],
                        disabledforeground=C["muted"])
    sb_entry.pack(fill="x", ipady=7, pady=(0, 4))
    tk.Label(right, text="Podés acortarlo para que funcione aunque el título cambie",
             bg=C["panel"], fg=C["muted"], font=f_lbl, wraplength=290,
             justify="left").pack(anchor="w")

    section_label(right, "URL PARA COMPANION")
    url_frame = tk.Frame(right, bg=C["panel2"], padx=8, pady=1)
    url_frame.pack(fill="x", pady=(0, 4))
    url_var = tk.StringVar(value="—")
    tk.Label(url_frame, textvariable=url_var, bg=C["panel2"], fg=C["accent"],
             font=f_mono, anchor="w", wraplength=270, justify="left",
             pady=6).pack(side="left", fill="x", expand=True)

    feedback_var = tk.StringVar(value="")
    tk.Label(right, textvariable=feedback_var, bg=C["panel"],
             fg=C["success"], font=f_small).pack(anchor="w")

    reg_var = tk.StringVar(value="")
    tk.Label(right, textvariable=reg_var, bg=C["panel"],
             fg=C["warn"], font=f_small).pack(anchor="w")

    current_hwnd = [None]
    current_slug = [None]

    def update_url(*_):
        txt = search_by_var.get().strip()
        if not txt:
            url_var.set("—")
            current_slug[0] = None
            return
        slug = to_slug(txt)
        current_slug[0] = slug
        url_var.set(f"http://localhost:{PORT}/{slug}")
        with ROUTES_LOCK:
            existing = ROUTES.get(slug)
        if existing and existing != txt:
            reg_var.set(f"⚠ Slug ya usado → '{existing}'")
        else:
            reg_var.set("")
        feedback_var.set("")

    search_by_var.trace_add("write", update_url)

    def on_select(event=None):
        sel = lb.curselection()
        if not sel:
            return
        hwnd, title = shown[sel[0]]
        current_hwnd[0] = hwnd
        sel_var.set(title)
        sb_entry.config(state="normal")
        # Usamos extract_base_title para el campo, pero el usuario puede editarlo
        search_by_var.set(extract_base_title(title))
        feedback_var.set("")

    lb.bind("<<ListboxSelect>>", on_select)
    lb.bind("<Double-Button-1>", lambda e: do_activate())

    def do_copy():
        url = url_var.get()
        if url == "—" or not current_slug[0]:
            return
        with ROUTES_LOCK:
            ROUTES[current_slug[0]] = search_by_var.get().strip()
        root.clipboard_clear()
        root.clipboard_append(url)
        root.update()
        feedback_var.set("✓ URL copiada al portapapeles")
        reg_var.set(f"✓ Ruta activa → '{search_by_var.get().strip()}'")

    def do_activate():
        if current_hwnd[0]:
            activate_hwnd(current_hwnd[0])

    # Botones
    btn_frame = tk.Frame(right, bg=C["panel"])
    btn_frame.pack(fill="x", side="bottom", pady=(16, 0))

    tk.Button(btn_frame, text="📋  Copiar URL para Companion",
              bg=C["accent"], fg="#fff",
              activebackground=C["accent_hover"], activeforeground="#fff",
              relief="flat", bd=0, padx=12, pady=8,
              font=f_btn, cursor="hand2",
              command=do_copy).pack(fill="x", pady=(0, 6))

    tk.Button(btn_frame, text="↗  Traer al frente ahora",
              bg=C["panel2"], fg=C["text"],
              activebackground=C["border"], activeforeground=C["text"],
              relief="flat", bd=0, padx=12, pady=7,
              font=f_btn, cursor="hand2",
              command=do_activate).pack(fill="x")

    # Poblar lista
    def populate(filter_text=""):
        nonlocal shown
        lb.delete(0, tk.END)
        shown = [(h, t) for h, t in all_windows
                 if filter_text.lower() in t.lower()]
        for _, title in shown:
            lb.insert(tk.END, f"  {title}")
        count_var.set(f"{len(shown)} ventanas")

    search_var.trace_add("write", lambda *_: populate(search_var.get()))
    populate()
    root.bind("<Escape>", lambda e: root.destroy())
    root.mainloop()

# ──────────────────────────────────────────────
# Systray con el mismo icono de la app
# ──────────────────────────────────────────────
def make_systray_image():
    sz = 64
    img = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([0, 0, sz - 1, sz - 1], fill="#161622")
    m = 12
    d.rectangle([m, m + 6, sz - m, sz - m], outline="#7c6af7", width=3)
    d.rectangle([m, m + 6, sz - m, m + 16], fill="#7c6af7")
    d.ellipse([m + 3, m + 8, m + 9, m + 14], fill="#161622")
    d.ellipse([m + 13, m + 8, m + 19, m + 14], fill="#161622")
    return img

def open_selector_thread(icon=None, item=None):
    threading.Thread(target=show_selector, daemon=True).start()

def change_port_dialog(icon, item):
    """Abre un diálogo para cambiar el puerto y aplica el cambio."""
    global PORT, tray_icon
    # Usamos un diálogo simple de Tkinter (fuera del bucle principal)
    root = tk.Tk()
    root.withdraw()  # ocultar ventana principal
    new_port = simpledialog.askinteger(
        "Cambiar puerto",
        f"Puerto actual: {PORT}\nIngresá el nuevo puerto (1024-65535):",
        minvalue=1024, maxvalue=65535,
        parent=root
    )
    root.destroy()
    if new_port and new_port != PORT:
        apply_new_port(new_port)

def apply_new_port(new_port):
    """Detiene el servidor viejo, actualiza PORT y lanza uno nuevo."""
    global PORT, tray_icon
    stop_server()
    PORT = new_port
    start_server(PORT)
    # Actualizar el título del systray y el menú
    if tray_icon:
        tray_icon.title = f"Window Focus  |  :{PORT}"
        # Reconstruir el menú con el nuevo puerto
        menu = pystray.Menu(
            pystray.MenuItem("Seleccionar ventana…", open_selector_thread, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Cambiar puerto…", change_port_dialog),
            pystray.MenuItem(f"HTTP activo en :{PORT}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Salir", on_quit),
        )
        tray_icon.menu = menu
        tray_icon.update_menu()

def on_quit(icon, item):
    icon.stop()
    sys.exit(0)

def main():
    global tray_icon

    # Iniciar servidor HTTP en el puerto configurado inicialmente
    start_server(PORT)

    # Auto-registrar las ventanas que ya están abiertas
    auto_register_windows()

    # Menú del systray
    menu = pystray.Menu(
        pystray.MenuItem("Seleccionar ventana…", open_selector_thread, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Cambiar puerto…", change_port_dialog),
        pystray.MenuItem(f"HTTP activo en :{PORT}", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Salir", on_quit),
    )

    tray_icon = pystray.Icon(
        name="WindowFocus",
        icon=make_systray_image(),
        title=f"Window Focus  |  :{PORT}",
        menu=menu,
    )
    tray_icon.run()

if __name__ == "__main__":
    main()
