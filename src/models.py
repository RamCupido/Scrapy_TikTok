"""Modelos de datos para representar perfiles y métricas de publicaciones."""
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

@dataclass
class VideoMetrics:
    """Métricas públicas asociadas a una publicación individual."""
    video_id: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    views: Optional[int] = None
    likes: Optional[int] = None
    comments: Optional[int] = None
    shares: Optional[int] = None

@dataclass
class TikTokProfile:
    """Representación estructurada de un perfil público de TikTok."""
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

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el modelo completo a un diccionario serializable."""
        return asdict(self)