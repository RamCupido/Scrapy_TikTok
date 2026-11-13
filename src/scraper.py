import json
import logging
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from playwright.sync_api import (
    sync_playwright,
    Response,
    Page,
    BrowserContext,
    TimeoutError as PlaywrightTimeoutError,
    Error as PlaywrightError,
)
from src.config import DEFAULT_TIMEOUT_MS, RENDER_WAIT_MS, HEADLESS_MODE, DEFAULT_USER_AGENT, TIKTOK_BASE_URL
from src.models import TikTokProfile, VideoMetrics
from src.validators import validateAndCleanUsername
from src.parser import TikTokHTMLParser
from src.exceptions import NetworkOrNavigationError, ProfileNotFoundError

logger = logging.getLogger(__name__)

# Cookies que TikTok establece únicamente cuando un usuario ha iniciado sesión real
AUTH_COOKIE_NAMES = {"sessionid", "sessionid_ss", "sid_tt", "uid_tt", "uid_tt_ss"}


class TikTokProfileScraper:
    def __init__(
        self,
        headless: bool = HEADLESS_MODE,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
        cookies_path: Optional[str] = "session_state.json",
        scroll_steps: int = 4,
        max_deep_videos: int = 15,
    ) -> None:
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.cookies_file = Path(cookies_path) if cookies_path else None
        self.scroll_steps = scroll_steps
        self.max_deep_videos = max_deep_videos

    @staticmethod
    def getSessionStatus(cookies_path: Optional[str | Path] = "session_state.json") -> Dict[str, Any]:
        """Inspecciona el archivo de estado de sesión y verifica si contiene cookies de cuenta autenticada."""
        if not cookies_path:
            return {"file_exists": False, "authenticated": False, "auth_cookies": [], "total_cookies": 0}

        path = Path(cookies_path)
        if not path.exists():
            return {"file_exists": False, "authenticated": False, "auth_cookies": [], "total_cookies": 0}

        try:
            with path.open("r", encoding="utf-8") as file:
                state = json.load(file)
            cookies = state.get("cookies", []) if isinstance(state, dict) else []
            now = time.time()
            found_auth: List[str] = []

            for cookie in cookies:
                if not isinstance(cookie, dict):
                    continue
                name = cookie.get("name", "")
                value = str(cookie.get("value", "")).strip()
                expires = cookie.get("expires", -1)
                if name in AUTH_COOKIE_NAMES and value:
                    if expires is None or expires == -1 or float(expires) > now:
                        found_auth.append(name)

            return {
                "file_exists": True,
                "authenticated": len(found_auth) > 0,
                "auth_cookies": sorted(set(found_auth)),
                "total_cookies": len(cookies),
            }
        except Exception as exc:
            logger.warning("No se pudo leer el estado de sesión '%s': %s", path, exc)
            return {"file_exists": True, "authenticated": False, "auth_cookies": [], "total_cookies": 0}

    def isSessionAuthenticated(self) -> bool:
        return bool(self.getSessionStatus(self.cookies_file).get("authenticated"))

    @staticmethod
    def _context_has_auth_cookies(context: BrowserContext) -> bool:
        try:
            now = time.time()
            for cookie in context.cookies():
                name = cookie.get("name", "")
                value = str(cookie.get("value", "")).strip()
                expires = cookie.get("expires", -1)
                if name in AUTH_COOKIE_NAMES and value:
                    if expires is None or expires == -1 or float(expires) > now:
                        return True
        except Exception:
            pass
        return False

    def loginInteractive(
        self,
        login_timeout_ms: int = 300_000,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """
        Abre una ventana visible de Chromium en la página de login de TikTok para que el usuario
        inicie sesión manualmente y guarda las cookies autenticadas en session_state.json.
        """
        def report(msg: str) -> None:
            if progress_callback:
                progress_callback(msg)

        if not self.cookies_file:
            raise ValueError("No se configuró una ruta de archivo para guardar las cookies (cookies_path).")

        login_url = f"{TIKTOK_BASE_URL}/login"
        report("Abriendo navegador en TikTok Login. Por favor inicia sesión en la ventana emergente...")

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=False,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                    ],
                )
                context_kwargs: Dict[str, Any] = {
                    "user_agent": DEFAULT_USER_AGENT,
                    "viewport": {"width": 1366, "height": 850},
                    "locale": "es-ES",
                }
                # Solo cargar estado previo si ya tenía sesión autenticada
                if self.cookies_file.exists() and self.isSessionAuthenticated():
                    context_kwargs["storage_state"] = str(self.cookies_file)

                context = browser.new_context(**context_kwargs)
                context.add_init_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
                )

                page = context.new_page()
                try:
                    page.goto(login_url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                    report(
                        "Esperando a que completes el inicio de sesión en TikTok "
                        "(QR, usuario/contraseña o red social)..."
                    )

                    elapsed_ms = 0
                    poll_interval_ms = 1000
                    while elapsed_ms < login_timeout_ms:
                        if page.is_closed():
                            if self._context_has_auth_cookies(context):
                                context.storage_state(path=str(self.cookies_file))
                                report("Sesión autenticada guardada correctamente.")
                                return True
                            report("La ventana del navegador se cerró antes de completar el inicio de sesión.")
                            return False

                        if self._context_has_auth_cookies(context):
                            report("¡Inicio de sesión detectado! Sincronizando cookies de sesión...")
                            try:
                                page.wait_for_timeout(3000)
                            except Exception:
                                pass
                            context.storage_state(path=str(self.cookies_file))
                            report(f"Cookies de sesión autenticada guardadas en '{self.cookies_file.name}'.")
                            return True

                        page.wait_for_timeout(poll_interval_ms)
                        elapsed_ms += poll_interval_ms

                    report("Tiempo de espera agotado para iniciar sesión.")
                    return False
                finally:
                    try:
                        context.close()
                    except Exception:
                        pass
                    try:
                        browser.close()
                    except Exception:
                        pass
        except PlaywrightError as exc:
            raise NetworkOrNavigationError(f"Error en Playwright durante el inicio de sesión: {exc}") from exc

    def dismissLoginModals(self, page: Page, is_authenticated: bool = False) -> None:
        selectors = [
            '[data-e2e="modal-close-inner-button"]',
            'div[role="dialog"] button[aria-label="Close"]',
        ]
        # Solo pulsar "Continuar como invitado" si NO tenemos sesión autenticada
        if not is_authenticated:
            selectors.extend([
                'text="Continuar como invitado"',
                'text="Continue as guest"',
            ])
        for sel in selectors:
            try:
                locator = page.locator(sel).first
                if locator.is_visible(timeout=500):
                    locator.click(timeout=1000)
            except Exception:
                pass

    def fetchProfile(self, raw_username: str, save_cookies: bool = True) -> TikTokProfile:
        username = validateAndCleanUsername(raw_username)
        target_url = f"{TIKTOK_BASE_URL}/@{username}"
        intercepted_video_payloads: List[Dict[str, Any]] = []
        had_auth_session = self.isSessionAuthenticated()

        def _handle_response(response: Response) -> None:
            """Captura únicamente paquetes JSON de publicaciones del perfil (/api/post/item_list)."""
            if "/api/post/item_list" in response.url and response.status == 200:
                try:
                    text_body = response.text()
                    if text_body and "itemList" in text_body:
                        data = json.loads(text_body)
                        if isinstance(data, dict) and data.get("itemList"):
                            intercepted_video_payloads.append(data)
                except Exception:
                    pass

        try:
            with sync_playwright() as p:
                # Desactivar AutomationControlled evita que el frontend de TikTok aborte la carga de videos
                browser = p.chromium.launch(
                    headless=self.headless,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                    ],
                )

                context_kwargs: Dict[str, Any] = {
                    "user_agent": DEFAULT_USER_AGENT,
                    "viewport": {"width": 1366, "height": 850},
                    "locale": "es-ES",
                }
                if self.cookies_file and self.cookies_file.exists():
                    context_kwargs["storage_state"] = str(self.cookies_file)

                context = browser.new_context(**context_kwargs)
                # Evitar que navigator.webdriver sea true al evaluar los scripts de hidratación
                context.add_init_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
                )

                page = context.new_page()
                page.on("response", _handle_response)

                try:
                    response = page.goto(target_url, wait_until="domcontentloaded", timeout=self.timeout_ms)

                    if response and response.status == 404:
                        raise ProfileNotFoundError(f"El perfil '@{username}' devolvió HTTP 404.")

                    # Esperar a que se hidrate la cuadrícula o transcurra el tiempo base
                    try:
                        page.wait_for_selector('[data-e2e="user-post-item"]', timeout=8000)
                    except PlaywrightTimeoutError:
                        page.wait_for_timeout(RENDER_WAIT_MS)

                    is_currently_auth = self._context_has_auth_cookies(context)
                    self.dismissLoginModals(page, is_authenticated=is_currently_auth)

                    # Scroll progresivo para activar el IntersectionObserver de la cuadrícula de videos
                    for _ in range(self.scroll_steps):
                        page.mouse.wheel(0, 900)
                        page.wait_for_timeout(1500)
                        self.dismissLoginModals(page, is_authenticated=is_currently_auth)

                    html_content = page.content()

                    # Parsear el perfil y los videos obtenidos hasta el momento
                    parser = TikTokHTMLParser(
                        html_content=html_content,
                        requested_username=username,
                        intercepted_video_payloads=intercepted_video_payloads,
                    )
                    profile = parser.parse()

                    # Si alguno de los primeros N videos no tiene métricas detalladas (likes/comentarios/guardados),
                    # visitamos individualmente esos videos para enriquecerlos desde su propio SSR JSON o DOM.
                    target_slice = profile.recent_videos[: self.max_deep_videos]
                    if target_slice and any(v.likes is None for v in target_slice):
                        enriched_videos: List[VideoMetrics] = []
                        for vid in target_slice:
                            if vid.likes is not None or not vid.url:
                                enriched_videos.append(vid)
                                continue
                            try:
                                page.goto(vid.url, wait_until="domcontentloaded", timeout=15000)
                                page.wait_for_timeout(1200)
                                vid_html = page.content()
                                enriched_videos.append(
                                    TikTokHTMLParser.parseSingleVideoHtml(vid_html, vid)
                                )
                            except Exception:
                                enriched_videos.append(vid)

                        profile.recent_videos = enriched_videos + profile.recent_videos[self.max_deep_videos :]
                        if "DEEP_VIDEO_SSR" not in profile.extraction_method:
                            profile.extraction_method += " + DEEP_VIDEO_SSR"

                    if is_currently_auth:
                        profile.notes.append("Extracción realizada con sesión autenticada de TikTok.")
                    else:
                        profile.notes.append(
                            "Extracción realizada en modo invitado. Inicia sesión (--login) para mayor estabilidad."
                        )

                    if save_cookies and self.cookies_file:
                        # Evitar sobrescribir una sesión autenticada previa si por algún motivo se perdió en el contexto
                        if not had_auth_session or self._context_has_auth_cookies(context):
                            context.storage_state(path=str(self.cookies_file))

                    return profile

                finally:
                    context.close()
                    browser.close()

        except PlaywrightTimeoutError as exc:
            raise NetworkOrNavigationError(
                f"Tiempo de espera agotado ({self.timeout_ms} ms) al cargar {target_url}."
            ) from exc
        except PlaywrightError as exc:
            raise NetworkOrNavigationError(f"Error en Playwright: {exc}") from exc