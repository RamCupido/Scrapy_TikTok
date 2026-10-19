"""Funciones de normalización para transformar textos de métricas en tipos numéricos."""
import re
from typing import Optional

MULTIPLIERS = {
    "K": 1_000,
    "M": 1_000_000,
    "B": 1_000_000_000,
}

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

    # Eliminar separadores de miles como comas si no hay sufijo multiplicador
    multiplier = 1
    for suffix, mult_val in MULTIPLIERS.items():
        if text.endswith(suffix):
            multiplier = mult_val
            text = text[:-1].strip()
            break

    # Si tiene sufijo, el punto o coma actúa como separador decimal (ej. 1.5M o 1,5M)
    if multiplier > 1:
        text = text.replace(",", ".")
    else:
        # Sin sufijo, eliminamos comas o puntos de miles
        text = re.sub(r"[.,\s]", "", text)

    try:
        numeric_value = float(text)
        return int(numeric_value * multiplier)
    except ValueError:
        return None