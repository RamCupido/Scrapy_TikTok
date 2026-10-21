"""Excepciones específicas de la extracción de perfiles de TikTok."""


class TikTokScraperError(Exception):
    """Clase base para errores controlados durante la extracción."""


class ProfileNotFoundError(TikTokScraperError):
    """El perfil solicitado no existe o no contiene datos públicos."""


class AccessControlTriggeredError(TikTokScraperError):
    """TikTok ha solicitado una verificación o ha bloqueado el acceso."""


class NetworkOrNavigationError(TikTokScraperError):
    """Se produjo un error de red o navegación al cargar el perfil."""
