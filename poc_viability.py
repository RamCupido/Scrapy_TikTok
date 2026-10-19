"""
Fase 4: Prueba de Concepto (PoC) para validar la viabilidad técnica.
Comprueba la presencia del árbol JSON de rehidratación y los selectores data-e2e.
"""
import json
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

def verify_tiktok_access(username: str) -> None:
    clean_user = username.lstrip("@").strip()
    url = f"https://www.tiktok.com/@{clean_user}"
    print(f"[*] Iniciando prueba de viabilidad para: {url}")

    with sync_playwright() as p:
        # Se lanza Chromium. Si en las pruebas iniciales TikTok detecta headless,
        # se puede cambiar headless=False para observar el comportamiento.
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/128.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="es-ES",
        )
        page = context.new_page()

        try:
            response = page.goto(url, wait_until="domcontentloaded", timeout=20000)
            # Breve espera pasiva para permitir la hidratación de la cuadrícula de videos
            page.wait_for_timeout(3000)
            
            status = response.status if response else "Desconocido"
            print(f"[*] Código de estado HTTP: {status}")

            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            # 1. Comprobar bloqueo o CAPTCHA
            if soup.find(id="captcha-verify-image") or "verify" in page.title().lower():
                print("[!] ADVERTENCIA: TikTok ha presentado un control CAPTCHA. Abortando.")
                return

            # 2. Comprobar Vía 1: Script de rehidratación SSR
            script_tag = soup.find("script", id="__UNIVERSAL_DATA_FOR_REHYDRATION__")
            if script_tag and script_tag.string:
                data = json.loads(script_tag.string)
                user_detail = data.get("__DEFAULT_SCOPE__", {}).get("webapp.user-detail", {})
                user_info = user_detail.get("userInfo", {})
                if user_info:
                    print("[+] ÉXITO Vía 1 (JSON SSR): Datos exactos del perfil localizados.")
                    print(f"    - Usuario: {user_info.get('user', {}).get('uniqueId')}")
                    print(f"    - Seguidores: {user_info.get('stats', {}).get('followerCount')}")
                else:
                    print("[-] El script SSR existe pero no contiene 'userInfo' (posible perfil inexistente).")
            else:
                print("[-] Vía 1 (JSON SSR) no encontrada en el HTML.")

            # 3. Comprobar Vía 2: Selectores DOM data-e2e
            followers_dom = soup.find(attrs={"data-e2e": "followers-count"})
            video_views_dom = soup.find_all(attrs={"data-e2e": "video-views"})
            print(f"[+] ÉXITO Vía 2 (DOM data-e2e):")
            print(f"    - Nodo seguidores en DOM: {followers_dom.text if followers_dom else 'No disponible'}")
            print(f"    - Miniaturas de videos detectadas en el DOM inicial: {len(video_views_dom)}")

        except Exception as e:
            print(f"[!] Error durante la prueba de concepto: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    verify_tiktok_access("tiktok")