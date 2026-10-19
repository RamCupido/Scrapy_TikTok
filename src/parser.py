"""Módulo de análisis HTML y extracción de datos estructurados de TikTok."""
import json
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup
from src.models import TikTokProfile, VideoMetrics
from src.normalizers import parse_metric_string
from src.exceptions import ProfileNotFoundError, AccessControlTriggeredError

class TikTokHTMLParser:
    """Analiza el documento HTML de un perfil de TikTok utilizando BeautifulSoup4."""

    def __init__(self, html_content: str, requested_username: str) -> None:
        self.html = html_content
        self.requested_username = requested_username
        self.soup = BeautifulSoup(html_content, "html.parser")

    def check_access_restrictions(self) -> None:
        """Verifica si la página devuelta corresponde a un bloqueo o CAPTCHA."""
        title = self.soup.title.string.lower() if self.soup.title and self.soup.title.string else ""
        
        if (
            self.soup.find(id="captcha-verify-image")
            or self.soup.find("div", class_=lambda c: c and "captcha" in c.lower())
            or "verify to continue" in title
            or "security check" in title
        ):
            raise AccessControlTriggeredError(
                "TikTok presentó un control de verificación (CAPTCHA). "
                "Respetando las restricciones del proyecto, la ejecución se detiene sin evadir el control."
            )

    def parse(self) -> TikTokProfile:
        """
        Ejecuta la estrategia de extracción de doble capa:
        1. JSON de rehidratación (__UNIVERSAL_DATA_FOR_REHYDRATION__).
        2. Respaldo mediante selectores DOM (data-e2e).
        """
        self.check_access_restrictions()

        profile = self._parse_from_rehydration_json()
        if profile:
            # Si el JSON no incluyó la lista de videos (habitual sin login),
            # intentamos complementar con las miniaturas visibles en el DOM.
            if not profile.recent_videos:
                dom_videos = self._extract_videos_from_dom()
                if dom_videos:
                    profile.recent_videos = dom_videos
                    profile.notes.append(
                        "Las métricas individuales de likes, comentarios y compartidos por video "
                        "no están expuestas en la cuadrícula pública sin sesión; se extrajeron las visualizaciones del DOM."
                    )
                elif not profile.is_private:
                    profile.notes.append(
                        "No fue posible cargar la cuadrícula de videos (TikTok requiere sesión activa o interacción en este entorno)."
                    )
            return profile

        # Si el JSON falló o cambió de formato, intentamos el respaldo por DOM
        dom_profile = self._parse_from_dom()
        if dom_profile:
            return dom_profile

        raise ProfileNotFoundError(
            f"No se encontró información pública para el perfil '@{self.requested_username}'. "
            "Verifique que el usuario exista o que TikTok no haya restringido temporalmente la vista."
        )

    def _parse_from_rehydration_json(self) -> Optional[TikTokProfile]:
        """Extrae datos exactos desde el bloque JSON de estado inyectado por el servidor."""
        script_tag = self.soup.find("script", id="__UNIVERSAL_DATA_FOR_REHYDRATION__")
        if not script_tag or not script_tag.string:
            return None

        try:
            raw_json = json.loads(script_tag.string)
        except json.JSONDecodeError:
            return None

        default_scope = raw_json.get("__DEFAULT_SCOPE__", {})
        user_detail = default_scope.get("webapp.user-detail", {})
        
        # Códigos de estado internos de TikTok para usuarios inexistentes (ej. 10202, 10221)
        status_code = user_detail.get("statusCode", 0)
        user_info = user_detail.get("userInfo", {})

        if status_code != 0 or not user_info or not user_info.get("user"):
            if status_code in (10202, 10221, 10222):
                raise ProfileNotFoundError(
                    f"El perfil '@{self.requested_username}' no existe en TikTok (Código interno: {status_code})."
                )
            return None

        user_data: Dict[str, Any] = user_info.get("user", {})
        stats_data: Dict[str, Any] = user_info.get("stats", {})

        is_private = bool(user_data.get("privateAccount", False))
        notes: List[str] = []
        if is_private:
            notes.append("Este perfil es privado. TikTok solo expone los contadores generales, no sus publicaciones.")

        # Intentar extraer publicaciones si el nodo ItemModule está presente en la hidratación
        item_module = default_scope.get("webapp.user-detail", {}).get("itemList", []) or raw_json.get("ItemModule", {})
        videos: List[VideoMetrics] = []
        if isinstance(item_module, dict):
            for vid_id, vid_data in item_module.items():
                if isinstance(vid_data, dict):
                    v_stats = vid_data.get("stats", {})
                    videos.append(
                        VideoMetrics(
                            video_id=str(vid_id),
                            url=f"https://www.tiktok.com/@{user_data.get('uniqueId', self.requested_username)}/video/{vid_id}",
                            description=vid_data.get("desc"),
                            views=v_stats.get("playCount"),
                            likes=v_stats.get("diggCount"),
                            comments=v_stats.get("commentCount"),
                            shares=v_stats.get("shareCount"),
                        )
                    )

        return TikTokProfile(
            username=user_data.get("uniqueId", self.requested_username),
            display_name=user_data.get("nickname") or None,
            biography=user_data.get("signature") or None,
            followers_count=stats_data.get("followerCount"),
            following_count=stats_data.get("followingCount"),
            total_likes_count=stats_data.get("heartCount") or stats_data.get("heart"),
            videos_count=stats_data.get("videoCount"),
            is_verified=bool(user_data.get("verified", False)),
            is_private=is_private,
            extraction_method="SSR_JSON_REHYDRATION",
            recent_videos=videos,
            notes=notes,
        )

    def _parse_from_dom(self) -> Optional[TikTokProfile]:
        """Extrae los datos leyendo directamente las etiquetas HTML con atributos data-e2e."""
        title_node = self.soup.find(attrs={"data-e2e": "user-title"})
        subtitle_node = self.soup.find(attrs={"data-e2e": "user-subtitle"})
        followers_node = self.soup.find(attrs={"data-e2e": "followers-count"})
        following_node = self.soup.find(attrs={"data-e2e": "following-count"})
        likes_node = self.soup.find(attrs={"data-e2e": "likes-count"})
        bio_node = self.soup.find(attrs={"data-e2e": "user-bio"})

        if not any([title_node, followers_node, following_node]):
            return None

        username_val = title_node.get_text(strip=True) if title_node else self.requested_username
        display_name_val = subtitle_node.get_text(strip=True) if subtitle_node else None
        bio_val = bio_node.get_text(strip=True) if bio_node else None

        # Detectar si hay mensaje de cuenta privada en el DOM
        page_text = self.soup.get_text(" ", strip=True).lower()
        is_private = "this account is private" in page_text or "esta cuenta es privada" in page_text

        videos = [] if is_private else self._extract_videos_from_dom()
        notes = [
            "Datos extraídos mediante selectores DOM (data-e2e). Los conteos numéricos son aproximaciones normalizadas de la interfaz."
        ]
        if is_private:
            notes.append("El perfil está configurado como cuenta privada.")

        return TikTokProfile(
            username=username_val,
            display_name=display_name_val,
            biography=bio_val,
            followers_count=parse_metric_string(followers_node.get_text(strip=True)) if followers_node else None,
            following_count=parse_metric_string(following_node.get_text(strip=True)) if following_node else None,
            total_likes_count=parse_metric_string(likes_node.get_text(strip=True)) if likes_node else None,
            videos_count=None,  # El conteo total de videos rara vez tiene un nodo data-e2e en texto plano
            is_verified=None,
            is_private=is_private,
            extraction_method="DOM_DATA_E2E_FALLBACK",
            recent_videos=videos,
            notes=notes,
        )

    def _extract_videos_from_dom(self) -> List[VideoMetrics]:
        """Busca los contenedores de publicaciones en la cuadrícula del perfil y extrae URL y vistas."""
        videos: List[VideoMetrics] = []
        item_containers = self.soup.find_all(attrs={"data-e2e": "user-post-item"})

        for item in item_containers:
            link_tag = item.find("a", href=True)
            views_tag = item.find(attrs={"data-e2e": "video-views"})
            img_tag = item.find("img", alt=True)

            video_url = link_tag["href"] if link_tag else None
            video_id = None
            if video_url and "/video/" in video_url:
                video_id = video_url.split("/video/")[-1].split("?")[0]

            views_count = parse_metric_string(views_tag.get_text(strip=True)) if views_tag else None
            desc = img_tag["alt"].strip() if img_tag and img_tag.get("alt") else None

            videos.append(
                VideoMetrics(
                    video_id=video_id,
                    url=video_url,
                    description=desc,
                    views=views_count,
                    likes=None,      # No disponible en la miniatura de la cuadrícula sin abrir el video
                    comments=None,   # No disponible en la miniatura de la cuadrícula
                    shares=None,     # No disponible en la miniatura de la cuadrícula
                )
            )

        return videos