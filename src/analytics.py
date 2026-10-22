import math
import re
from collections import defaultdict
from typing import List, Dict
from src.models import TikTokProfile, ProfileIntelligence, VideoOutlier

class DataIntelligenceAnalyzer:

    def __init__(self, profile: TikTokProfile):
        self.profile = profile
        # Filtrar solo los videos que tienen al menos la métrica de vistas
        self.valid_videos = [v for v in profile.recent_videos if v.views is not None]

    def _calculate_follower_to_view_ratio(self, avg_views: float) -> float:
        """Punto 1: Tasa de conversión de seguidores a visualizaciones reales"""
        followers = self.profile.followers_count
        if not followers or followers <= 0:
            return 0.0
        return avg_views / followers

    def _detect_outliers(self, mean_views: float) -> List[VideoOutlier]:
        """Punto 1: Detección de videos virales anómalos usando Z-Score"""
        n = len(self.valid_videos)
        if n < 2:
            return []

        # Calcular la varianza y la desviación estándar
        variance = sum((v.views - mean_views) ** 2 for v in self.valid_videos) / (n - 1)
        std_dev = math.sqrt(variance)

        if std_dev == 0:
            return []

        outliers = []
        for video in self.valid_videos:
            # Z-Score: a cuántas desviaciones estándar está este video de la media
            z_score = (video.views - mean_views) / std_dev
            # Consideramos anomalía (viral) si supera 2 desviaciones estándar (~95% de confianza)
            if z_score >= 2.0:
                outliers.append(VideoOutlier(video_id=video.video_id, views=video.views, z_score=round(z_score, 2)))
        
        # Ordenar de mayor a menor anomalía
        return sorted(outliers, key=lambda x: x.z_score, reverse=True)

    def _calculate_engagement_rates(self) -> tuple[float, float]:
        total_views = 0
        total_standard_interactions = 0
        total_weighted_interactions = 0

        for v in self.valid_videos:
            views = v.views or 0
            if views == 0:
                continue

            likes = v.likes or 0
            comments = v.comments or 0
            shares = v.shares or 0
            saves = v.saves or 0

            total_views += views
            total_standard_interactions += (likes + comments + shares + saves)
            # Ponderación algorítmica: Guardados y Compartidos valen el doble
            total_weighted_interactions += (likes + comments + (shares * 2) + (saves * 2))

        if total_views == 0:
            return 0.0, 0.0

        avg_er = (total_standard_interactions / total_views) * 100
        weighted_er = (total_weighted_interactions / total_views) * 100
        return avg_er, weighted_er

    def _analyze_hashtags(self) -> Dict[str, int]:
        hashtag_views = defaultdict(list)

        for v in self.valid_videos:
            if not v.description or v.views is None:
                continue
            
            # Extraer hashtags ignorando mayúsculas/minúsculas
            tags = re.findall(r"#(\w+)", v.description.lower())
            for tag in set(tags):  # set para evitar contar dos veces el mismo tag en un video
                hashtag_views[tag].append(v.views)

        # Calcular el promedio de vistas por hashtag y filtrar aquellos usados al menos 1 vez
        hashtag_performance = {}
        for tag, views_list in hashtag_views.items():
            avg_tag_views = int(sum(views_list) / len(views_list))
            hashtag_performance[tag] = avg_tag_views

        # Ordenar el diccionario por promedio de vistas descendente
        return dict(sorted(hashtag_performance.items(), key=lambda item: item[1], reverse=True)[:10])

    def generate_intelligence(self) -> ProfileIntelligence:
        if not self.valid_videos:
            return ProfileIntelligence()

        avg_views = sum(v.views for v in self.valid_videos) / len(self.valid_videos)
        
        ftv_ratio = self._calculate_follower_to_view_ratio(avg_views)
        outliers = self._detect_outliers(avg_views)
        standard_er, weighted_er = self._calculate_engagement_rates()
        hashtags = self._analyze_hashtags()

        return ProfileIntelligence(
            follower_to_view_ratio=ftv_ratio,
            average_engagement_rate=standard_er,
            weighted_engagement_rate=weighted_er,
            viral_outliers=outliers,
            hashtag_performance=hashtags
        )