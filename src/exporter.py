"""Módulo de exportación de resultados a archivos JSON y CSV."""
import csv
import json
from pathlib import Path
from src.models import TikTokProfile

def export_to_json(profile: TikTokProfile, filepath: str) -> Path:
    """Exporta todos los datos del perfil (incluyendo lista de videos) a un archivo JSON."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(profile.to_dict(), f, ensure_ascii=False, indent=4)
    return path

def export_to_csv(profile: TikTokProfile, filepath: str) -> Path:
    """Exporta el resumen de métricas del perfil a un archivo CSV."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    headers = [
        "username",
        "display_name",
        "followers_count",
        "following_count",
        "total_likes_count",
        "videos_count",
        "is_verified",
        "is_private",
        "recent_videos_captured",
        "biography",
        "extraction_method",
        "extracted_at",
    ]
    
    row = {
        "username": profile.username,
        "display_name": profile.display_name if profile.display_name is not None else "No disponible",
        "followers_count": profile.followers_count if profile.followers_count is not None else "No disponible",
        "following_count": profile.following_count if profile.following_count is not None else "No disponible",
        "total_likes_count": profile.total_likes_count if profile.total_likes_count is not None else "No disponible",
        "videos_count": profile.videos_count if profile.videos_count is not None else "No disponible",
        "is_verified": profile.is_verified if profile.is_verified is not None else "No disponible",
        "is_private": profile.is_private if profile.is_private is not None else "No disponible",
        "recent_videos_captured": len(profile.recent_videos),
        "biography": (profile.biography or "").replace("\n", " "),
        "extraction_method": profile.extraction_method,
        "extracted_at": profile.extracted_at,
    }

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerow(row)
        
    return path