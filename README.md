
# Window Focus

**Window Focus Helper** es una herramienta liviana que se ejecuta en la bandeja del sistema (systray) y permite **traer al frente cualquier ventana** de Windows mediante una simple URL HTTP.  
Está pensada especialmente para integrarse con **Companion** (Elgato Stream Deck, Bitfocus Companion, etc.), aunque puede usarse con cualquier software que pueda hacer peticiones HTTP GET.

---

## 🚀 Características

- 📋 **Generá URLs para Companion** con un solo clic.
- 🖥️ **Auto‑registro al iniciar**: detecta todas las ventanas abiertas y crea rutas automáticamente.
- 🧠 **Simplifica navegadores**: las ventanas de Google Chrome se agrupan bajo `google-chrome` (sin el título de la pestaña).
- ⚙️ **Puerto configurable** por línea de comandos o desde el menú del systray.
- 🔄 **Funciona siempre**: incluso si la app está en segundo plano, las ventanas saltan al frente correctamente (truco de foco).
- 🎨 Interfaz oscura moderna con búsqueda y selección de ventanas.
- 🧷 Mismo ícono para la ventana y la bandeja.
- 📦 Ejecutable único (compilado con PyInstaller).

---

## 📥 Uso del ejecutable

Si ya tenés el `.exe` compilado, simplemente ejecutalo.  
El programa se aloja en la bandeja del sistema (cerca del reloj).

### Abrir la interfaz
Hacé **clic derecho** en el icono de la bandeja y elegí **"Seleccionar ventana…"**.

### Cambiar el puerto
- **Desde línea de comandos:**  
  `WindowFocus.exe --port=8080` (por defecto es `3500`).
- **Desde la aplicación:**  
  Clic derecho en el icono > **"Cambiar puerto…"** → ingresá un puerto entre `1024` y `65535`.

---

## 🌐 Servidor HTTP

La aplicación inicia un pequeño servidor HTTP en `localhost:PUERTO`.  
**Cada URL corresponde a una ventana** y tiene el formato:

```

http://localhost:3500/nombre-de-la-ventana

```

Ejemplos:
- `http://localhost:3500/whatsapp` (trae al frente WhatsApp)
- `http://localhost:3500/google-chrome` (trae Chrome, sin importar la pestaña)
- `http://localhost:3500/resolume-arena` (trae Resolume Arena)

---

## 🔗 Integración con Companion (Stream Deck / Bitfocus Companion)

1. **Abrí la interfaz de Window Focus** y seleccioná la ventana que querés controlar.
2. **Ajustá el texto de búsqueda** si es necesario (p. ej., `Resolume Arena` en lugar del título completo).
3. **Copiá la URL** con el botón `📋 Copiar URL para Companion`.
4. En Companion, creá un **botón** (o usá un paso en una secuencia) y agregá una acción de tipo **HTTP Request** (`http: GET`).
5. Pegá la URL copiada en el campo **URI**.
6. Listo. Al presionar el botón, la ventana saltará al frente inmediatamente.

---

## 📋 Cómo generar URLs manualmente

La barra lateral derecha de la interfaz te muestra:
- El **título completo** de la ventana seleccionada.
- Un campo **"Buscar por"** editable, donde podés acortar el texto (ejemplo: `Resolume Arena` en vez de `Resolume Arena - Composition (1920x1080, 8bpc)`).
- La **URL generada** que se actualiza automáticamente.

Pegá esa URL en Companion o en cualquier herramienta que pueda hacer `GET`.

---

## 🧪 Solución de problemas

**"El HTTP server no responde"**  
Verificá que el puerto no esté bloqueado por otro programa. Probá cambiar el puerto.

**"La ventana no se trae al frente desde Companion"**  
La última versión ya incluye una técnica avanzada (simulación de tecla `Alt`) para eludir las restricciones de foco de Windows. Si aún así falla, asegurate de que la ventana **no esté minimizada en la barra de tareas con animación** (raro). Reiniciá el programa también puede ayudar.

**"El texto en la interfaz se ve extraño"**  
El ejecutable incluye fuentes Segoe UI y Consolas; si faltan, usa las fuentes por defecto del sistema y debería verse bien.

**"No se registran ventanas nuevas automáticamente"**  
El auto‑registro ocurre solo **al iniciar** la aplicación. Si abrís o cerrás ventanas después, tenés que abrir el selector y copiar la URL manualmente (o reiniciar el programa).

---

## 🛠️ Compilación desde el código fuente

Si querés generar el `.exe` por tu cuenta:

1. Instalá Python 3.9 o superior.
2. Instalá las dependencias:
   ```bash
   pip install pyinstaller pystray pillow

1. Ejecutá PyInstaller:
   ```bash
   pyinstaller --onefile --noconsole --hidden-import=pystray._win32 window_focus.py
   ```
2. El ejecutable aparecerá en la carpeta dist/.

---

Autor: Pedro Becerra - 2026
Proyecto creado para integración con Companion y automatización de escritorio.

```
