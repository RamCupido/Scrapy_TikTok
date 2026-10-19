# TikTok Public Profile Scraper

Herramienta de línea de comandos desarrollada en Python para la extracción de métricas públicas de perfiles de TikTok mediante automatización de navegador (`Playwright`) y análisis del DOM/SSR (`BeautifulSoup4`), sin usar APIs oficiales ni servicios de terceros.

## 1. Funcionalidades

**Funcionalidades principales:**
- Validación sintáctica previa del `username` según las reglas de TikTok.
- Extracción de **Doble Capa**:
  1. **Capa Primaria (SSR JSON Rehydration):** Lectura del árbol de estado `__UNIVERSAL_DATA_FOR_REHYDRATION__` para obtener cifras exactas sin redondeos.
  2. **Capa Secundaria (DOM Fallback):** Lectura de selectores de prueba `data-e2e` y normalización matemática de abreviaciones (`K`, `M`, `B`).
- Obtención de: `username`, `nombre visible`, `biografía`, `seguidores`, `seguidos`, `likes totales acumulados`, `total de publicaciones` y `visualizaciones` de los videos cargados en la vista inicial.
- Detección respetuosa de perfiles privados, perfiles inexistentes y controles de acceso (CAPTCHAs).
- Exportación opcional de los resultados a formatos **JSON** y **CSV**.

## 2. Tecnologías Utilizadas
- **Python 3.10+**
- **Playwright:** Automatización del motor Chromium para permitir el renderizado inicial e hidratación del cliente.
- **BeautifulSoup4:** Análisis estático del árbol HTML capturado.
- Librería estándar de Python (`dataclasses`, `argparse`, `json`, `csv`, `re`).

## 3. Requisitos Previos
- Python 3.10 o superior instalado.
- Conexión a internet para descargar los binarios del navegador Chromium de Playwright y consultar los perfiles públicos.

## 4. Instalación Paso a Paso

1. **Clonar el repositorio:**
   ```bash
   git clone [https://github.com/tu-usuario/tiktok-profile-scraper.git](https://github.com/tu-usuario/tiktok-profile-scraper.git)
   cd tiktok-profile-scraper
   ```

2. **Crear y activar un entorno virtual:**
   - En Windows:
     ```bash
     python -m venv .venv
     .venv\Scripts\activate
     ```
   - En Linux / macOS:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

3. **Instalar las dependencias de Python:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Instalar el navegador Chromium para Playwright:**
   ```bash
   playwright install chromium
   ```

## 5. Ejemplos de Uso

### A. Ejecutar la Prueba de Concepto (Fase de viabilidad)
Para verificar que el entorno puede leer tanto el JSON de rehidratación como los nodos `data-e2e`:
```bash
python poc_viability.py
```

### B. Ejecución interactiva por consola
```bash
python main.py
```
El programa solicitará que ingreses el nombre de usuario manualmente.

### C. Ejecución por parámetros CLI y exportación a JSON/CSV
```bash
python main.py -u @tiktok --json output/tiktok_profile.json --csv output/tiktok_summary.csv
```

### D. Ejecución con navegador visible (modo depuración académica)
```bash
python main.py -u @khaby.lame --headed
```

## 6. Ejemplo de Salida en Consola

```text
=================================================================
 REPORTE DE PERFIL PÚBLICO DE TIKTOK: @tiktok
=================================================================
  Nombre visible      : TikTok
  Cuenta verificada   : Sí
  Cuenta privada      : No
  Biografía           : One TikTok can make a big impact
-----------------------------------------------------------------
 MÉTRICAS E INTERACCIONES GENERALES DEL PERFIL:
  Seguidores          : 82,400,000
  Seguidos            : 5
  Likes acumulados    : 365,100,000
  Publicaciones (tot) : 1,120
-----------------------------------------------------------------
 PUBLICACIONES RECIENTES DETECTADAS EN VISTA INICIAL (6):
  01. ID: 7419001234567890123 | Vistas: 2,400,000 | Likes: No disponible | Comentarios: No disponible | Compartidos: No disponible
  02. ID: 7418559876543210987 | Vistas: 1,100,000 | Likes: No disponible | Comentarios: No disponible | Compartidos: No disponible
-----------------------------------------------------------------
 NOTAS TÉCNICAS DE LA EXTRACCIÓN:
  * Las métricas individuales de likes, comentarios y compartidos por video no están expuestas en la cuadrícula pública sin sesión; se extrajeron las visualizaciones del DOM.
-----------------------------------------------------------------
  Método utilizado    : SSR_JSON_REHYDRATION
  Fecha UTC           : 2026-10-19T01:42:00+00:00
=================================================================
```

## 7. Limitaciones Conocidas
1. **Métricas granulares por video sin sesión:** En la página pública de un perfil (`/@username`), TikTok solo renderiza el conteo de **visualizaciones** sobre las miniaturas de los videos. Los conteos de *likes*, *comentarios* y *compartidos* de cada publicación individual solo se obtienen si TikTok incluye el diccionario `ItemModule` en la hidratación inicial; cuando la plataforma lo omite para usuarios no autenticados, el programa los reporta limpiamente como `No disponible`.
2. **Paginación (Scroll infinito):** Sin una sesión autenticada, el desplazamiento hacia abajo para cargar cientos de videos adicionales es bloqueado por un muro de inicio de sesión (*Login Wall*). El programa se limita a la carga inicial pública.
3. **Controles de acceso (CAPTCHA):** Si se realizan múltiples consultas en un corto periodo desde la misma dirección IP, TikTok puede desplegar un reto CAPTCHA.

## 8. Consideraciones de Seguridad y Uso Responsable
- **Sin evasión de protecciones:** Este software **no** implementa ni promueve técnicas para vulnerar CAPTCHAs, falsificar firmas criptográficas (`X-Bogus` / `_signature`) ni eludir muros de autenticación. Si la plataforma solicita verificación, la aplicación detiene su ejecución de forma controlada.
- **Privacidad y credenciales:** El proyecto opera exclusivamente sobre datos públicos sin utilizar cuentas, cookies de sesión ni tokens privados.
- **Propósito educativo:** Desarrollado con fines de investigación académica sobre arquitecturas web modernas, renderizado híbrido y calidad de software en Python.