import re
import logging
from typing import List, Dict, Optional, Tuple
import torch
from transformers import pipeline
from src.models import BigFiveScores, VideoMetrics

logger = logging.getLogger(__name__)

TRAIT_HYPOTHESES = {
    "openness": {
        "positive": "Este texto demuestra una mente abierta, curiosidad, arte, creatividad o ideas originales.",
        "negative": "Este texto es convencional, rutinario, conservador y predecible.",
    },
    "conscientiousness": {
        "positive": "Este texto refleja disciplina, organización, esfuerzo, enfoque en el trabajo o metas claras.",
        "negative": "Este texto es espontáneo, desordenado, impulsivo o despreocupado.",
    },
    "extraversion": {
        "positive": "Este texto es entusiasta, sociable, energético, extrovertido y busca conectar con la gente.",
        "negative": "Este texto es reservado, introvertido, callado, sobrio y reflexivo.",
    },
    "agreeableness": {
        "positive": "Este texto expresa empatía, amabilidad, calidez, agradecimiento y cooperación.",
        "negative": "Este texto es competitivo, escéptico, crítico, sarcástico o desafiante.",
    },
    "neuroticism": {
        "positive": "Este texto expresa preocupación, queja, ansiedad, vulnerabilidad emocional o estrés.",
        "negative": "Este texto transmite calma, seguridad en sí mismo, estabilidad y control emocional.",
    },
}

class BigFiveAnalyzer:

    def __init__( self, model_name: str = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli", device: Optional[str] = None,) -> None:
        if device is None:
            self.device = 0 if torch.cuda.is_available() else -1
        else:
            self.device = 0 if device == "cuda" else -1

        logger.info("Cargando modelo de Hugging Face '%s' en device=%s...", model_name, self.device)
        self.classifier = pipeline(
            "zero-shot-classification",
            model=model_name,
            device=self.device,
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

    def predict_trait_score(self, text: str, trait: str) -> float:
        hypotheses = [
            TRAIT_HYPOTHESES[trait]["positive"],
            TRAIT_HYPOTHESES[trait]["negative"],
        ]
        
        result = self.classifier(
            text,
            candidate_labels=hypotheses,
            hypothesis_template="{}",
            multi_label=False,
        )

        # La probabilidad asociada a la hipótesis positiva determina el score (0 a 1)
        labels = result["labels"]
        scores = result["scores"]

        pos_idx = labels.index(TRAIT_HYPOTHESES[trait]["positive"])
        return float(scores[pos_idx])

    def analyze_text(self, text: str) -> Optional[BigFiveScores]:
        cleaned = self.clean_tiktok_text(text)
        # Si el texto limpio tiene menos de 2 palabras reales, el análisis no es estadísticamente viable
        if len(cleaned.split()) < 2:
            return None

        scores = {}
        for trait in ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]:
            scores[trait] = self.predict_trait_score(cleaned, trait)

        return BigFiveScores(
            openness=scores["openness"],
            conscientiousness=scores["conscientiousness"],
            extraversion=scores["extraversion"],
            agreeableness=scores["agreeableness"],
            neuroticism=scores["neuroticism"],
        )

    def analyze_profile_corpus(self, biography: Optional[str], videos: List[VideoMetrics],) -> Optional[BigFiveScores]:
        valid_samples: List[Tuple[str, float]] = []

        clean_bio = self.clean_tiktok_text(biography)
        if len(clean_bio.split()) >= 2:
            # La biografía recibe un peso relativo mayor (peso = 2.0)
            valid_samples.append((clean_bio, 2.0))

        for v in videos:
            clean_desc = self.clean_tiktok_text(v.description)
            if len(clean_desc.split()) >= 3:
                valid_samples.append((clean_desc, 1.0))

        if not valid_samples:
            return None

        # Acumular sumas ponderadas
        accumulators = {
            "openness": 0.0,
            "conscientiousness": 0.0,
            "extraversion": 0.0,
            "agreeableness": 0.0,
            "neuroticism": 0.0,
        }
        total_weight = 0.0

        for text_sample, weight in valid_samples:
            sample_scores = self.analyze_text(text_sample)
            if sample_scores:
                accumulators["openness"] += sample_scores.openness * weight
                accumulators["conscientiousness"] += sample_scores.conscientiousness * weight
                accumulators["extraversion"] += sample_scores.extraversion * weight
                accumulators["agreeableness"] += sample_scores.agreeableness * weight
                accumulators["neuroticism"] += sample_scores.neuroticism * weight
                total_weight += weight

        if total_weight == 0.0:
            return None

        return BigFiveScores(
            openness=accumulators["openness"] / total_weight,
            conscientiousness=accumulators["conscientiousness"] / total_weight,
            extraversion=accumulators["extraversion"] / total_weight,
            agreeableness=accumulators["agreeableness"] / total_weight,
            neuroticism=accumulators["neuroticism"] / total_weight,
        )