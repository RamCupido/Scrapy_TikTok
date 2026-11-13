"""
Módulo de generación de análisis narrativo con IA (Google Gemini API).
"""
import logging
import os
from typing import Optional
import requests
from dotenv import load_dotenv
from src.config import ENV_PATH, GEMINI_MODEL
from src.models import TikTokProfile

logger = logging.getLogger(__name__)

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class AIIntelligenceAnalyst:
    """Genera resúmenes de riesgo crediticio alternativo usando Google Gemini."""

    def __init__(self, model_name: Optional[str] = None, api_key: Optional[str] = None) -> None:
        load_dotenv(dotenv_path=ENV_PATH, override=True)
        self.api_key = (
            api_key
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
            or ""
        ).strip()
        self.model_name = (model_name or os.getenv("GEMINI_MODEL") or GEMINI_MODEL).strip()

    def _build_fintech_prompt(self, profile: TikTokProfile) -> str:
        """Construye el prompt estructurado para evaluación de riesgo crediticio."""
        intel = profile.intelligence
        pers = profile.personality

        if not intel or not pers:
            return ""

        viral_info = "Ninguna anomalía detectada (tráfico estable)."
        if intel.viral_outliers:
            top_viral = intel.viral_outliers[0]
            viral_info = f"Pico viral de {top_viral.views:,} vistas (Z-Score: {top_viral.z_score})"

        return (
            "Emite un dictamen de riesgo crediticio en un solo párrafo basado en los siguientes "
            "datos del creador de contenido solicitante:\n\n"
            "AUDITORÍA DE TRÁFICO (Ingresos):\n"
            f"- Engagement Rate Ponderado: {intel.weighted_engagement_rate:.2f}%\n"
            f"- Conversión Seguidores a Vistas: {intel.follower_to_view_ratio * 100:.2f}%\n"
            f"- Volatilidad: {viral_info}\n\n"
            "AUDITORÍA PSICOMÉTRICA BIG FIVE (Voluntad de Pago):\n"
            f"- Responsabilidad (Conscientiousness): {pers.conscientiousness * 100:.1f}%\n"
            f"- Neuroticismo (Inestabilidad): {pers.neuroticism * 100:.1f}%\n"
            f"- Apertura y Extraversión combinada: {(pers.openness + pers.extraversion) * 50:.1f}%\n\n"
            "Redacta el dictamen en español, de forma técnica, objetiva y directa, y concluye "
            "indicando el Nivel de Riesgo (Bajo, Medio o Alto)."
        )

    def generate_summary(self, profile: TikTokProfile) -> str:
        """Ejecuta la inferencia con Gemini y devuelve el dictamen de crédito."""
        prompt = self._build_fintech_prompt(profile)
        if not prompt:
            return "Datos insuficientes (faltan métricas o análisis psicométrico) para generar el dictamen de riesgo."

        if not self.api_key or self.api_key.startswith("Tu_clave"):
            return "Configura GEMINI_API_KEY en el archivo .env para generar el dictamen con IA."

        models_to_try = [self.model_name]
        if "gemini-2.0-flash" not in models_to_try:
            models_to_try.append("gemini-2.0-flash")

        payload = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            "Eres el Arquitecto de Riesgos de una FinTech. Tu tarea es evaluar la viabilidad "
                            "de otorgar un microcrédito a un creador de contenido basándote en su huella digital. "
                            "Analizas dos pilares: 1) Estabilidad de ingresos (métricas de tráfico) y "
                            "2) Voluntad de pago (psicometría Big Five)."
                        )
                    }
                ]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "temperature": 0.4,
                "maxOutputTokens": 350,
            },
        }

        for model in models_to_try:
            url = f"{GEMINI_API_BASE}/{model}:generateContent"
            try:
                response = requests.post(
                    url,
                    headers={
                        "Content-Type": "application/json",
                        "x-goog-api-key": self.api_key,
                    },
                    json=payload,
                    timeout=30,
                )
                if response.status_code == 404 and model != models_to_try[-1]:
                    continue
                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates") or []
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts") or []
                        if parts and "text" in parts[0]:
                            return str(parts[0]["text"]).strip()
            except Exception as exc:
                logger.error("Fallo en la generación de resumen con Gemini (%s): %s", model, exc)

        return "Error al generar el dictamen crediticio con Gemini."
