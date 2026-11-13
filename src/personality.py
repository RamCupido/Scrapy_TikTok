import json
import logging
import os
import re
from typing import List, Optional
import requests
from dotenv import load_dotenv
from src.config import ENV_PATH, GEMINI_MODEL
from src.exceptions import TikTokScraperError
from src.models import BigFiveScores, VideoMetrics

logger = logging.getLogger(__name__)

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class MissingGeminiKeyError(TikTokScraperError):
    """Falta configurar la clave GEMINI_API_KEY para el análisis con Gemini."""


class BigFiveAnalyzer:
    """Analizador psicométrico Big Five (OCEAN) impulsado por Google Gemini API."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        load_dotenv(dotenv_path=ENV_PATH, override=True)
        self.api_key = (
            api_key
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
            or ""
        ).strip()
        self.model_name = (model_name or os.getenv("GEMINI_MODEL") or GEMINI_MODEL).strip()

        if not self.api_key or self.api_key.startswith("Tu_clave"):
            raise MissingGeminiKeyError(
                "No se encontró una GEMINI_API_KEY válida. Configúrala en el archivo .env "
                "(GEMINI_API_KEY=\"tu_api_key\") o ingrésala en la barra lateral del dashboard."
            )

    @staticmethod
    def clean_tiktok_text(text: Optional[str]) -> str:
        if not text:
            return ""

        # Eliminar URLs
        cleaned = re.sub(r"https?://\S+|www\.\S+", "", text)
        # Eliminar menciones de usuarios (@usuario)
        cleaned = re.sub(r"@\w+", "", cleaned)
        # Eliminar hashtags virales genéricos sin carga semántica profunda
        cleaned = re.sub(
            r"#(?:fyp|foryou|parati|viral|trend|foryoupage|tiktok|xyzbca)\b",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        # Convertir hashtags temáticos (#python -> python)
        cleaned = re.sub(r"#(\w+)", r"\1", cleaned)
        # Normalizar espacios en blanco repetidos
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _call_gemini_big_five(self, corpus_prompt: str) -> Optional[BigFiveScores]:
        models_to_try = [self.model_name]
        if "gemini-2.0-flash" not in models_to_try:
            models_to_try.append("gemini-2.0-flash")

        payload = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            "Eres un psicometrista computacional experto en el modelo de personalidad "
                            "Big Five (OCEAN):\n"
                            "- openness (Apertura a la experiencia: creatividad, curiosidad, arte, ideas originales)\n"
                            "- conscientiousness (Responsabilidad: disciplina, organización, constancia, metas)\n"
                            "- extraversion (Extraversión: sociabilidad, entusiasmo, energía, expresividad)\n"
                            "- agreeableness (Amabilidad: empatía, calidez, cooperación, afecto)\n"
                            "- neuroticism (Neuroticismo: reactividad emocional, preocupación, vulnerabilidad)\n\n"
                            "Evalúa el corpus textual del perfil de TikTok y devuelve un objeto JSON con "
                            "las 5 puntuaciones numéricas (entre 0.01 y 1.0) que reflejen el peso relativo "
                            "de cada dimensión en la personalidad expresada."
                        )
                    }
                ]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": corpus_prompt}],
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "OBJECT",
                    "properties": {
                        "openness": {"type": "NUMBER"},
                        "conscientiousness": {"type": "NUMBER"},
                        "extraversion": {"type": "NUMBER"},
                        "agreeableness": {"type": "NUMBER"},
                        "neuroticism": {"type": "NUMBER"},
                    },
                    "required": [
                        "openness",
                        "conscientiousness",
                        "extraversion",
                        "agreeableness",
                        "neuroticism",
                    ],
                },
            },
        }

        last_error: Optional[str] = None
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
                if response.status_code != 200:
                    last_error = f"HTTP {response.status_code}: {response.text[:300]}"
                    logger.error("Error de Gemini API (%s): %s", model, last_error)
                    break

                data = response.json()
                candidates = data.get("candidates") or []
                if not candidates:
                    return None
                parts = candidates[0].get("content", {}).get("parts") or []
                if not parts or "text" not in parts[0]:
                    return None

                raw_scores = json.loads(parts[0]["text"])
                return BigFiveScores(
                    openness=max(float(raw_scores.get("openness", 0.2)), 0.001),
                    conscientiousness=max(float(raw_scores.get("conscientiousness", 0.2)), 0.001),
                    extraversion=max(float(raw_scores.get("extraversion", 0.2)), 0.001),
                    agreeableness=max(float(raw_scores.get("agreeableness", 0.2)), 0.001),
                    neuroticism=max(float(raw_scores.get("neuroticism", 0.2)), 0.001),
                )
            except Exception as exc:
                last_error = str(exc)
                logger.error("Excepción al invocar Gemini (%s): %s", model, exc)

        if last_error:
            raise TikTokScraperError(f"Error al analizar personalidad con Gemini: {last_error}")
        return None

    def analyze_text(self, text: str) -> Optional[BigFiveScores]:
        cleaned = self.clean_tiktok_text(text)
        if len(cleaned.split()) < 2:
            return None

        prompt = f"Analiza el siguiente texto de TikTok y estima sus puntuaciones Big Five (OCEAN):\n\n{cleaned}"
        return self._call_gemini_big_five(prompt)

    def analyze_profile_corpus(
        self,
        biography: Optional[str],
        videos: List[VideoMetrics],
    ) -> Optional[BigFiveScores]:
        clean_bio = self.clean_tiktok_text(biography)
        video_lines: List[str] = []

        for idx, vid in enumerate(videos[:15], start=1):
            clean_desc = self.clean_tiktok_text(vid.description)
            if clean_desc:
                video_lines.append(f"{idx}. {clean_desc}")

        total_words = len(clean_bio.split()) + sum(len(line.split()) - 1 for line in video_lines)
        if total_words < 2:
            return None

        sections = []
        if clean_bio:
            sections.append(f"BIOGRAFÍA DEL PERFIL (peso principal):\n{clean_bio}")
        if video_lines:
            sections.append("DESCRIPCIONES DE PUBLICACIONES RECIENTES:\n" + "\n".join(video_lines))

        corpus_prompt = (
            "Analiza el siguiente corpus extraído de un perfil público de TikTok y determina "
            "su perfil de personalidad Big Five (OCEAN):\n\n" + "\n\n".join(sections)
        )
        return self._call_gemini_big_five(corpus_prompt)
