"""Módulo de automatización web con soporte de estado de cookies, anti-webdriver y enriquecimiento de videos."""
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from playwright.sync_api import (
    sync_playwright,
    Response,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    Error as PlaywrightError,
)
from src.config import DEFAULT_TIMEOUT_MS, RENDER_WAIT_MS, HEADLESS_MODE, DEFAULT_USER_AGENT, TIKTOK_BASE_URL
from src.models import TikTokProfile, VideoMetrics
from src.validators import validate_and_clean_username
from src.parser import TikTokHTMLParser
from src.exceptions import NetworkOrNavigationError, ProfileNotFoundError

logger = logging.getLogger(__name__)

class TikTokProfileScraper:
    """Gestiona la navegación, el estado de cookies de invitado y la captura profunda de videos."""

    def __init__(
        self,
        headless: bool = HEADLESS_MODE,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
        cookies_path: Optional[str] = "session_state.json",
        scroll_steps: int = 3,
        max_deep_videos: int = 5,
    ) -> None:
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.cookies_file = Path(cookies_path) if cookies_path else None
        self.scroll_steps = scroll_steps
        self.max_deep_videos = max_deep_videos

    def _dismiss_login_modals(self, page: Page) -> None:
        """Intenta cerrar modales emergentes de inicio de sesión o modo invitado que frenan la carga."""
        selectors = [
            '[data-e2e="modal-close-inner-button"]',
            'div[role="dialog"] button[aria-label="Close"]',
            'text="Continuar como invitado"',
            'text="Continue as guest"',
        ]
        for sel in selectors:
            try:
                locator = page.locator(sel).first
                if locator.is_visible(timeout=500):
                    locator.click(timeout=1000)
            except Exception:
                pass

    def fetch_profile(self, raw_username: str, save_cookies: bool = True) -> TikTokProfile:
        """
        Navega al perfil, intercepta respuestas de videos y, si es necesario,
        enriquece las métricas visitando los primeros videos detectados.
        """
        username = validate_and_clean_username(raw_username)
        target_url = f"{TIKTOK_BASE_URL}/@{username}"
        intercepted_video_payloads: List[Dict[str, Any]] = []

        def _handle_response(response: Response) -> None:
            """Captura cualquier paquete JSON de lista de publicaciones de TikTok."""
            if ("item_list" in response.url or "/api/post/" in response.url) and response.status == 200:
                try:
                    text_body = response.text()
                    if text_body and "itemList" in text_body:
                        import json
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
                        page.wait_for_selector('[data-e2e="user-post-item"]', timeout=6000)
                    except PlaywrightTimeoutError:
                        page.wait_for_timeout(RENDER_WAIT_MS)

                    self._dismiss_login_modals(page)

                    # Scroll progresivo para activar el IntersectionObserver de la cuadrícula de videos
                    for _ in range(self.scroll_steps):
                        page.mouse.wheel(0, 800)
                        page.wait_for_timeout(1500)
                        self._dismiss_login_modals(page)

                    html_content = page.content()

                    # Parsear el perfil y los videos obtenidos hasta el momento
                    parser = TikTokHTMLParser(
                        html_content=html_content,
                        requested_username=username,
                        intercepted_video_payloads=intercepted_video_payloads,
                    )
                    profile = parser.parse()

                    # Si tenemos videos del DOM pero nos faltan likes/comentarios/guardados (porque XHR fue bloqueado),
                    # visitamos los primeros N videos para extraer sus métricas completas desde su propio SSR JSON
                    if profile.recent_videos and profile.recent_videos[0].likes is None:
                        enriched_videos: List[VideoMetrics] = []
                        for vid in profile.recent_videos[: self.max_deep_videos]:
                            if not vid.url:
                                enriched_videos.append(vid)
                                continue
                            try:
                                page.goto(vid.url, wait_until="domcontentloaded", timeout=15000)
                                page.wait_for_timeout(1200)
                                vid_html = page.content()
                                enriched_videos.append(
                                    TikTokHTMLParser.parse_single_video_html(vid_html, vid)
                                )
                            except Exception:
                                enriched_videos.append(vid)

                        # Conservar el resto de videos detectados en la cuadrícula
                        profile.recent_videos = enriched_videos + profile.recent_videos[self.max_deep_videos :]
                        profile.extraction_method += " + DEEP_VIDEO_SSR"

                    if save_cookies and self.cookies_file:
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