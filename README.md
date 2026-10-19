# TikTok Public Profile Scraper

Herramienta de línea de comandos desarrollada en Python para la extracción de métricas públicas de perfiles de TikTok mediante automatización de navegador (`Playwright`) y análisis del DOM/SSR (`BeautifulSoup4`), sin usar APIs oficiales ni servicios de terceros.

## 1. Funcionalidades

**Funcionalidades principales:**
- Validación sintáctica previa del `username` según las reglas de TikTok.
- Extracción de **Doble Capa**:
  1. **Capa Primaria (SSR JSON Rehydration):** Lectura del árbol de estado `__UNIVERSAL_DATA_FOR_REHYDRATION__` para obtener cifras exactas sin redondeos.
  2. **Capa Secundaria (DOM Fallback):** Lectura de selectores de prueba `data-e2e` y normalización matemática de abreviaciones (`K`, `M`, `B`).
- Obtención de: `username`, `nombre visible`, `biografía`, `seguidores`, `seguidos`, `likes totales acumulados`, `total de publicaciones` y `visualizaciones` de los videos cargados en la vista inicial.
- Detección de perfiles privados, perfiles inexistentes y controles de acceso (CAPTCHAs).
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
   git clone [https://github.com/RamCupido/Scrapy_TikTok.git]
   cd Scrapy_TikTok
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
