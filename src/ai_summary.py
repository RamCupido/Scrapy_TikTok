import logging
import torch
from transformers import pipeline
from src.models import ProfileIntelligence

logger = logging.getLogger(__name__)

class AIIntelligenceAnalyst:

    def __init__(self, model_name: str = "Qwen/Qwen2.5-1.5B-Instruct"):
        self.device = 0 if torch.cuda.is_available() else -1
        logger.info("Cargando LLM '%s' para generación de texto...", model_name)
        
        self.generator = pipeline(
            "text-generation",
            model=model_name,
            device=self.device,
            torch_dtype=torch.float16 if self.device == 0 else torch.float32,
        )

    def _build_prompt(self, intel: ProfileIntelligence) -> str:
        viral_info = "Ninguna"
        if intel.viral_outliers:
            top_viral = intel.viral_outliers[0]
            viral_info = f"1 video con {top_viral.views:,} vistas (Z-Score: {top_viral.z_score})"

        hashtags_info = ", ".join([f"#{k}" for k in list(intel.hashtag_performance.keys())[:3]]) or "No disponibles"

        # Formato ChatML compatible con modelos Instruct
        return (
            "<|im_start|>system\n"
            "Eres un analista experto en algoritmos de TikTok e inteligencia de negocio. "
            "Tu objetivo es interpretar métricas y decir que significan cada una de estas para que sean interpretadas por usuarios no especializados.<|im_end|>\n"
            "<|im_start|>user\n"
            "Redacta un párrafo analizando estas métricas de un creador:\n"
            f"- Conversión Seguidores a Vistas: {intel.follower_to_view_ratio * 100:.2f}%\n"
            f"- Engagement Rate (ER): {intel.average_engagement_rate:.2f}%\n"
            f"- ER Ponderado (Guardados/Compartidos x2): {intel.weighted_engagement_rate:.2f}%\n"
            f"- Anomalía Viral: {viral_info}\n"
            f"- Top Hashtags: {hashtags_info}\n"
            "¿Qué significan estos datos y como deberian de ser interpretados?<|im_end|>\n"
            "<|im_start|>assistant\n"
        )

    def generate_summary(self, intel: ProfileIntelligence) -> str:
        prompt = self._build_prompt(intel)
        
        try:
            output = self.generator(
                prompt,
                max_new_tokens=500,
                temperature=0.7, # Creatividad balanceada
                do_sample=True,
                return_full_text=False
            )
            return output[0]["generated_text"].strip()
        except Exception as e:
            logger.error("Fallo en la generación de IA: %s", e)
            return "No se pudo generar el análisis automático debido a un error del modelo."