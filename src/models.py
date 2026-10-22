from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

@dataclass
class VideoMetrics:
    video_id: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    created_at: Optional[str] = None
    views: Optional[int] = None
    likes: Optional[int] = None
    comments: Optional[int] = None
    shares: Optional[int] = None
    saves: Optional[int] = None

@dataclass
class BigFiveScores:
    """Puntuaciones normalizadas (0.0 a 1.0) para las 5 dimensiones OCEAN."""
    openness: float = 0.5
    conscientiousness: float = 0.5
    extraversion: float = 0.5
    agreeableness: float = 0.5
    neuroticism: float = 0.5

    def to_dict(self) -> Dict[str, float]:
        return {
            "openness": round(self.openness, 3),
            "conscientiousness": round(self.conscientiousness, 3),
            "extraversion": round(self.extraversion, 3),
            "agreeableness": round(self.agreeableness, 3),
            "neuroticism": round(self.neuroticism, 3),
        }

@dataclass
class TikTokProfile:
    username: str
    display_name: Optional[str] = None
    biography: Optional[str] = None
    followers_count: Optional[int] = None
    following_count: Optional[int] = None
    total_likes_count: Optional[int] = None
    videos_count: Optional[int] = None
    is_verified: Optional[bool] = None
    is_private: Optional[bool] = None
    extraction_method: str = "unknown"
    recent_videos: List[VideoMetrics] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    extracted_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    personality: Optional[BigFiveScores] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)