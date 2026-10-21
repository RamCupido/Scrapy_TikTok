"""Módulo de automatización web con soporte de estado de cookies e interceptación pasiva XHR."""
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from playwright.sync_api import (
    sync_playwright,
    Response,
    TimeoutError as PlaywrightTimeoutError,
    Error as PlaywrightError,
)
from src.config import DEFAULT_TIMEOUT_MS, RENDER_WAIT_MS, HEADLESS_MODE, DEFAULT_USER_AGENT, TIKTOK_BASE_URL
from src.models import TikTokProfile
from src.validators import validate_and_clean_username
from src.parser import TikTokHTMLParser
from src.exceptions import NetworkOrNavigationError, ProfileNotFoundError

logger = logging.getLogger(__name__)

class TikTokProfileScraper:
    """Gestiona la navegación, el estado de cookies de invitado y la captura de datos."""

    def __init__(
        self,
        headless: bool = HEADLESS_MODE,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
        cookies_path: Optional[str] = "session_state.json",
        scroll_steps: int = 2,
    ) -> None:
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.cookies_file = Path(cookies_path) if cookies_path else None
        self.scroll_steps = scroll_steps

    def fetch_profile(self, raw_username: str, save_cookies: bool = True) -> TikTokProfile:
        """
        Navega al perfil, reutiliza cookies si existen, intercepta las respuestas
        internas de videos y retorna el perfil con todas las métricas disponibles.
        """
        username = validate_and_clean_username(raw_username)
        target_url = f"{TIKTOK_BASE_URL}/@{username}"
        intercepted_video_payloads: List[Dict[str, Any]] = []

        def _handle_response(response: Response) -> None:
            """Captura pasivamente el JSON de publicaciones que carga el navegador."""
            if "/api/post/item_list/" in response.url and response.status == 200:
                try:
                    data = response.json()
                    if isinstance(data, dict) and "itemList" in data:
                        intercepted_video_payloads.append(data)
                except Exception:
                    pass

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)

                # Si ya existe un archivo de cookies de invitado, se carga en el contexto
                context_kwargs: Dict[str, Any] = {
                    "user_agent": DEFAULT_USER_AGENT,
                    "viewport": {"width": 1366, "height": 850},
                    "locale": "es-ES",
                }
                if self.cookies_file and self.cookies_file.exists():
                    logger.info("Cargando cookies previas desde: %s", self.cookies_file)
                    context_kwargs["storage_state"] = str(self.cookies_file)

                context = browser.new_context(**context_kwargs)
                page = context.new_page()

                # Suscribir el listener de red antes de navegar
                page.on("response", _handle_response)

                try:
                    response = page.goto(target_url, wait_until="domcontentloaded", timeout=self.timeout_ms)

                    if response and response.status == 404:
                        raise ProfileNotFoundError(f"El perfil '@{username}' devolvió HTTP 404.")

                    # Esperar hidratación inicial
                    page.wait_for_timeout(RENDER_WAIT_MS)

                    # Realizar scroll suave para disparar o completar la carga de la cuadrícula
                    for _ in range(self.scroll_steps):
                        page.mouse.wheel(0, 900)
                        page.wait_for_timeout(1800)

                    html_content = page.content()

                    # Guardar las cookies actualizadas (ttwid, s_v_web_id, msToken) para futuras consultas
                    if save_cookies and self.cookies_file:
                        context.storage_state(path=str(self.cookies_file))

                finally:
                    context.close()
                    browser.close()

        except PlaywrightTimeoutError as exc:
            raise NetworkOrNavigationError(
                f"Tiempo de espera agotado ({self.timeout_ms} ms) al cargar {target_url}."
            ) from exc
        except PlaywrightError as exc:
            raise NetworkOrNavigationError(f"Error en Playwright: {exc}") from exc

        parser = TikTokHTMLParser(
            html_content=html_content,
            requested_username=username,
            intercepted_video_Payloads=intercepted_video_payloads,
        )
        return parser.parse()