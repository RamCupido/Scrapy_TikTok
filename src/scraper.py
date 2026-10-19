"""Módulo de automatización web con Playwright para obtener el contenido del perfil."""
import logging
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError
from src.config import DEFAULT_TIMEOUT_MS, RENDER_WAIT_MS, HEADLESS_MODE, DEFAULT_USER_AGENT, TIKTOK_BASE_URL
from src.models import TikTokProfile
from src.validators import validate_and_clean_username
from src.parser import TikTokHTMLParser
from src.exceptions import NetworkOrNavigationError, ProfileNotFoundError

logger = logging.getLogger(__name__)

class TikTokProfileScraper:
    """Gestiona la navegación hacia TikTok y coordina la extracción de datos."""

    def __init__(self, headless: bool = HEADLESS_MODE, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> None:
        self.headless = headless
        self.timeout_ms = timeout_ms

    def fetch_profile(self, raw_username: str) -> TikTokProfile:
        """
        Valida el username, navega al perfil público usando Chromium y retorna
        un objeto TikTokProfile con las métricas disponibles.
        """
        username = validate_and_clean_username(raw_username)
        target_url = f"{TIKTOK_BASE_URL}/@{username}"
        logger.info("Iniciando extracción para el perfil: @%s (%s)", username, target_url)

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)
                context = browser.new_context(
                    user_agent=DEFAULT_USER_AGENT,
                    viewport={"width": 1366, "height": 768},
                    locale="es-ES",
                )
                page = context.new_page()

                try:
                    response = page.goto(target_url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                    
                    if response and response.status == 404:
                        raise ProfileNotFoundError(f"El servidor devolvió HTTP 404 para el usuario '@{username}'.")

                    # Espera controlada para permitir que React hidrate la cuadrícula de videos
                    page.wait_for_timeout(RENDER_WAIT_MS)
                    html_content = page.content()
                finally:
                    context.close()
                    browser.close()

        except PlaywrightTimeoutError as exc:
            raise NetworkOrNavigationError(
                f"Se agotó el tiempo de espera ({self.timeout_ms} ms) al intentar cargar {target_url}."
            ) from exc
        except PlaywrightError as exc:
            raise NetworkOrNavigationError(f"Error en el motor del navegador Playwright: {exc}") from exc

        parser = TikTokHTMLParser(html_content=html_content, requested_username=username)
        return parser.parse()