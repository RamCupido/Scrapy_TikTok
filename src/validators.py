"""Validación y sanitización de nombres de usuario de TikTok."""
import re

class InvalidUsernameError(ValueError):
    """El formato del nombre de usuario ingresado no es válido según las reglas de TikTok."""

# Reglas de TikTok: letras, números, guiones bajos y puntos.
# Longitud entre 2 y 24 caracteres. No puede terminar en punto.
USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9_.]{2,24}$")

def validate_and_clean_username(raw_username: str) -> str:
    """
    Limpia el símbolo '@' inicial, recorta espacios y valida el formato del username.
    Lanza InvalidUsernameError si no cumple las reglas de la plataforma.
    """
    if not raw_username or not isinstance(raw_username, str):
        raise InvalidUsernameError("El nombre de usuario no puede estar vacío.")

    cleaned = raw_username.strip().lstrip("@").strip()

    if not cleaned:
        raise InvalidUsernameError("El nombre de usuario ingresado solo contenía espacios o '@'.")

    if cleaned.endswith("."):
        raise InvalidUsernameError("Un nombre de usuario de TikTok no puede finalizar con un punto.")

    if not USERNAME_REGEX.match(cleaned):
        raise InvalidUsernameError(
            f"El username '{cleaned}' es inválido. Debe tener entre 2 y 24 caracteres "
            "y contener únicamente letras, números, puntos o guiones bajos."
        )

    return cleaned