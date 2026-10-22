# TikTok Public Profile Scraper

Aplicación de línea de comandos escrita en Python para recopilar información visible de perfiles públicos de TikTok. Usa Playwright para abrir la página y Beautiful Soup para analizar el HTML y los datos de hidratación que TikTok incluye en la página.

La herramienta no necesita credenciales de TikTok. La cantidad de datos disponible depende de lo que TikTok muestre sin iniciar sesión y puede cambiar si la plataforma modifica su sitio o limita el acceso.

## Información que puede recopilar

Del perfil:

- Nombre de usuario y nombre visible.
- Biografía.
- Indicadores de cuenta verificada y privada, cuando estén disponibles.
- Seguidores, seguidos, likes acumulados y cantidad de publicaciones, cuando estén disponibles.

De las publicaciones que se carguen en la página:

- ID, URL, descripción y fecha.
- Visualizaciones, likes, comentarios, compartidos y guardados, según los datos que TikTok permita obtener.

El programa intenta extraer los datos desde el JSON de la página y usa el DOM como alternativa. Si no consigue las métricas completas de las publicaciones, puede visitar algunas publicaciones para intentar completar los datos. Por eso, los campos individuales pueden aparecer vacíos y los resultados no necesariamente incluirán todas las publicaciones del perfil.

## Requisitos

- Python 3.10 o superior.
- Conexión a Internet.
- Chromium, instalado mediante Playwright.

## Instalación

1. Clona el repositorio y entra en la carpeta:

   ```bash
   git clone https://github.com/RamCupido/Scrapy_TikTok.git
   cd Scrapy_TikTok
   ```

2. Crea y activa un entorno virtual.

   **Windows (PowerShell):**

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   **Windows (Símbolo del sistema):**

   ```bat
   python -m venv .venv
   .venv\Scripts\activate.bat
   ```

   **Linux o macOS:**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Instala las dependencias y el navegador Chromium:

   ```bash
   python -m pip install -r requirements.txt
   python -m playwright install chromium
   ```

   ## Panel visual

   El panel muestra el historial guardado en `scraped_profiles.json`, incluidas las
   métricas de perfil y publicaciones, los análisis que existan y una vista de los
   datos completos. Para iniciarlo desde la carpeta del proyecto:

   ```bash
   streamlit run dashboard.py
   ```

   Se abrirá en el navegador. Si quieres que una nueva extracción incluya los
   análisis de personalidad y métricas, ejecútala con ambas opciones:

   ```bash
   python main.py --username USUARIO --analyze-personality --analytics
   ```

   El panel indica cuando un análisis no está disponible en una extracción antigua
   o cuando la recolección no obtuvo determinados datos.

   ## Uso

   Desde la carpeta del proyecto, ejecuta el comando principal:

```bash
python main.py -u khaby.lame --headed
```

`-u` (o `--username`) indica el usuario de TikTok. `--headed` abre Chromium en una ventana visible. También puedes escribir el nombre con `@`:

```bash
python main.py --username @khaby.lame --headed
```

Si omites el usuario, el programa lo solicitará en la consola:

```bash
python main.py
```

Sin `--headed`, Playwright intenta usar el navegador en modo oculto (headless):

```bash
python main.py -u khaby.lame
```

Para ver las opciones de línea de comandos:

```bash
python main.py --help
```

## Archivos generados

- **`scraped_profiles.json`**: el programa agrega cada extracción exitosa a una lista JSON, sin reemplazar los registros anteriores. Incluye los datos del perfil, las publicaciones obtenidas, el método de extracción, notas y la fecha de extracción. Si el archivo existente no contiene una lista JSON válida, la escritura mostrará un error.
- **`session_state.json`**: Playwright carga el estado de navegación guardado si el archivo existe y lo actualiza después de la extracción. No es necesario crearlo manualmente.

Ambos archivos son datos locales generados durante el uso; no se incluyen en el repositorio.

## Configuración opcional

`src/config.py` permite ajustar estos valores mediante variables de entorno:

| Variable | Valor predeterminado | Descripción |
| --- | --- | --- |
| `SCRAPER_HEADLESS` | `true` | Modo headless predeterminado. El argumento `--headed` lo desactiva para esa ejecución. |
| `SCRAPER_TIMEOUT_MS` | `25000` | Tiempo máximo de navegación, en milisegundos. |
| `SCRAPER_RENDER_WAIT_MS` | `3500` | Espera adicional para que cargue la página cuando no aparece la cuadrícula de publicaciones. |
| `SCRAPER_USER_AGENT` | Agente de usuario definido en `src/config.py` | Agente de usuario enviado por el navegador. |

El archivo `.env.example` muestra los valores de referencia, pero la aplicación no carga archivos `.env` automáticamente; configura las variables en el entorno antes de ejecutar el programa.

## Errores y limitaciones

- El nombre de usuario se valida antes de navegar: debe tener entre 2 y 24 caracteres y contener solo letras, números, puntos o guiones bajos; no puede terminar en punto. Se acepta un `@` inicial.
- Los perfiles privados no exponen sus publicaciones. Un perfil inexistente, una respuesta de red/navigation fallida o un CAPTCHA puede impedir la extracción.
- Si TikTok presenta un control de acceso, prueba el comando con `--headed` para poder ver el navegador. Esto no garantiza que el acceso sea permitido.
- TikTok puede cambiar la estructura de sus páginas, bloquear solicitudes o limitar los datos disponibles; por ello, la extracción puede ser parcial o dejar campos como “No disponible”.
- Usa la herramienta respetando los términos de TikTok y las leyes aplicables. Está destinada a información visible públicamente y no elude controles de acceso.
