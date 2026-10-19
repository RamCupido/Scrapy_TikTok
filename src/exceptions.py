"""Excepciones personalizadas para el flujo de extracción de TikTok."""

class TikTokScraperError(Exception):
    """Excepción base para todos los errores del extractor."""

class InvalidUsernameError(TikTokScraperError):
    """El formato del nombre de usuario ingresado no es válido según las reglas de TikTok."""

class ProfileNotFoundError(TikTokScraperError):
    """El perfil solicitado no existe o no está disponible públicamente."""

class AccessControlTriggeredError(TikTokScraperError):
    """TikTok activó un control de acceso (CAPTCHA, Login Wall o Rate Limit)."""

class NetworkOrNavigationError(TikTokScraperError):
    """Error de conexión, tiempo de espera agotado o fallo al cargar el navegador."""