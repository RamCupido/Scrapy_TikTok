"""
Módulo de generación de análisis narrativo con IA (Hugging Face Text Generation).
"""
import logging
import torch
from transformers import pipeline
from typing import Any
from src.models import ProfileIntelligence, TikTokProfile # Importar TikTokProfile para acceder a personality

logger = logging.getLogger(__name__)

class AIIntelligenceAnalyst:
    """Genera resúmenes de riesgo crediticio alternativo usando un LLM local."""

    def __init__(self, model_name: str = "Qwen/Qwen2.5-1.5B-Instruct"):
        self.device = 0 if torch.cuda.is_available() else -1
        logger.info("Cargando LLM '%s' para generación de texto...", model_name)
        
        self.generator = pipeline(
            "text-generation",
            model=model_name,
            device=self.device,
            torch_dtype=torch.float16 if self.device == 0 else torch.float32,
        )

    def _build_fintech_prompt(self, profile: TikTokProfile) -> str:
        """Construye el prompt estructurado para evaluación de riesgo crediticio."""
        
        intel = profile.intelligence
        pers = profile.personality

        # Validaciones de seguridad en caso de que falten datos
        if not intel or not pers:
            return ""

        viral_info = "Ninguna anomalía detectada (tráfico estable)."
        if intel.viral_outliers:
            top_viral = intel.viral_outliers[0]
            viral_info = f"Pico viral de {top_viral.views:,} vistas (Z-Score: {top_viral.z_score})"

        # Formato ChatML para instruir al modelo
        return (
            "<|im_start|>system\n"
            "Eres el Arquitecto de Riesgos de una FinTech. Tu tarea es evaluar la viabilidad de otorgar "
            "un microcrédito a un creador de contenido basándote en su huella digital. Analizas dos pilares: "
            "1) Estabilidad de ingresos (métricas de tráfico) y 2) Voluntad de pago (psicometría Big Five). "
            "Sé técnico, objetivo, directo y concluye con el Nivel de Riesgo (Bajo, Medio o Alto).<|im_end|>\n"
            "<|im_start|>user\n"
            "Emite un dictamen de riesgo crediticio en un solo párrafo basado en los siguientes datos del solicitante:\n\n"
            "AUDITORÍA DE TRÁFICO (Ingresos):\n"
            f"- Engagement Rate Ponderado: {intel.weighted_engagement_rate:.2f}%\n"
            f"- Conversión Seguidores a Vistas: {intel.follower_to_view_ratio * 100:.2f}%\n"
            f"- Volatilidad: {viral_info}\n\n"
            "AUDITORÍA PSICOMÉTRICA (Voluntad de Pago):\n"
            f"- Responsabilidad (Conscientiousness): {pers.conscientiousness * 100:.1f}%\n"
            f"- Neuroticismo (Inestabilidad): {pers.neuroticism * 100:.1f}%\n"
            f"- Apertura y Extraversión combinada: {(pers.openness + pers.extraversion) * 50:.1f}%\n\n"
            "Redacta el dictamen justificando la decisión.<|im_end|>\n"
            "<|im_start|>assistant\n"
        )

    def generate_summary(self, profile: TikTokProfile) -> str:
        """Ejecuta la inferencia y devuelve el dictamen de crédito."""
        prompt = self._build_fintech_prompt(profile)
        if not prompt:
            return "Datos insuficientes (faltan métricas o análisis psicométrico) para generar el dictamen de riesgo."
        
        try:
            output = self.generator(
                prompt,
                max_new_tokens=250,
                temperature=0.4, # Temperatura baja (0.4) para respuestas más analíticas y menos creativas
                do_sample=True,
                return_full_text=False 
            )
            return output[0]["generated_text"].strip()
        except Exception as e:
            logger.error("Fallo en la generación de IA: %s", e)
            return "Error al generar el dictamen crediticio."