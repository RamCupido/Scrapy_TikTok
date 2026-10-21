"""Funciones de normalización para transformar textos de métricas y corregir desbordamientos int32."""
import re
from typing import Optional, Union

MULTIPLIERS = {
    "K": 1_000,
    "M": 1_000_000,
    "B": 1_000_000_000,
}

UINT32_MODULO = 4_294_967_296  # 2^32

def fix_int32_overflow(value: Optional[Union[int, str]]) -> Optional[int]:
    """
    Corrige el bug de desbordamiento de entero de 32 bits (int32 overflow) de TikTok
    en cuentas que superan los 2,147,483,647 likes (ej. Khaby Lame).
    """
    if value is None:
        return None

    try:
        num = int(value)
    except (ValueError, TypeError):
        return parse_metric_string(str(value))

    # Si el número es negativo en un contador que jamás puede ser negativo,
    # aplicamos conversión de complemento a dos (unsigned 32-bit integer)
    if num < 0:
        return num + UINT32_MODULO
    return num

def parse_metric_string(raw_value: Optional[str]) -> Optional[int]:
    """
    Convierte una representación textual de métrica (ej. '1.5M', '12.3K', '845', '1,200')
    en un número entero. Si el dato no es numérico o no está disponible, retorna None.
    """
    if raw_value is None:
        return None

    text = str(raw_value).strip().upper()
    if not text or text in {"-", "N/A", "NULL"}:
        return None

    # Si es un entero negativo en texto proveniente de stats, corregir overflow
    if text.startswith("-") and text[1:].isdigit():
        return fix_int32_overflow(int(text))

    multiplier = 1
    for suffix, mult_val in MULTIPLIERS.items():
        if text.endswith(suffix):
            multiplier = mult_val
            text = text[:-1].strip()
            break

    if multiplier > 1:
        text = text.replace(",", ".")
    else:
        text = re.sub(r"[.,\s]", "", text)

    try:
        numeric_value = float(text)
        return int(numeric_value * multiplier)
    except ValueError:
        return None