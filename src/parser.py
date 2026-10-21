"""Módulo de análisis HTML y procesamiento de respuestas JSON de TikTok."""
import json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup
from src.models import TikTokProfile, VideoMetrics
from src.normalizers import parse_metric_string
from src.exceptions import ProfileNotFoundError, AccessControlTriggeredError

class TikTokHTMLParser:
    """Analiza el HTML del perfil y combina los videos capturados en la red."""

    def __init__(
        self,
        html_content: str,
        requested_username: str,
        intercepted_video_Payloads: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self.html = html_content
        self.requested_username = requested_username
        self.soup = BeautifulSoup(html_content, "html.parser")
        self.intercepted_payloads = intercepted_video_Payloads or []

    def check_access_restrictions(self) -> None:
        """Verifica si la página devuelta corresponde a un bloqueo o CAPTCHA activo."""
        title = self.soup.title.string.lower() if self.soup.title and self.soup.title.string else ""

        if (
            self.soup.find(id="captcha-verify-image")
            or self.soup.find("div", class_=lambda c: c and "captcha-verify-container" in c.lower())
            or "verify to continue" in title
            or "security check" in title
        ):
            raise AccessControlTriggeredError(
                "TikTok presentó un control CAPTCHA. Ejecuta el comando con '--headed --save-cookies' "
                "una vez para generar y guardar las cookies de estado del navegador."
            )

    def parse(self) -> TikTokProfile:
        """Combina los datos del perfil con las métricas completas de los videos."""
        self.check_access_restrictions()

        profile = self._parse_from_rehydration_json() or self._parse_from_dom()
        if not profile:
            raise ProfileNotFoundError(
                f"No se encontró información pública para '@{self.requested_username}'."
            )

        # 1. Priorizar videos capturados desde la respuesta XHR interna (trae todas las métricas)
        xhr_videos = self._parse_intercepted_videos(profile.username)
        if xhr_videos:
            profile.recent_videos = xhr_videos
            profile.extraction_method += " + XHR_ITEM_LIST"
        elif not profile.recent_videos and not profile.is_private:
            # 2. Si no hubo paquete XHR, usar el respaldo visual del DOM
            dom_videos = self._extract_videos_from_dom()
            if dom_videos:
                profile.recent_videos = dom_videos
                profile.notes.append(
                    "Videos obtenidos del DOM visual (solo vistas disponibles). "
                    "Usa cookies de sesión de invitado para capturar likes, comentarios y guardados vía XHR."
                )
            else:
                profile.notes.append(
                    "TikTok no cargó la lista de videos en esta sesión anónima."
                )

        return profile

    def _parse_intercepted_videos(self, username: str) -> List[VideoMetrics]:
        """Extrae likes, comentarios, compartidos, guardados y descripción de los paquetes XHR."""
        videos_by_id: Dict[str, VideoMetrics] = {}

        for payload in self.intercepted_payloads:
            item_list = payload.get("itemList", [])
            if not isinstance(item_list, list):
                continue

            for item in item_list:
                if not isinstance(item, dict):
                    continue
                vid_id = str(item.get("id", ""))
                if not vid_id or vid_id in videos_by_id:
                    continue

                stats = item.get("stats", {})
                create_time = item.get("createTime")
                created_iso = None
                if create_time and str(create_time).isdigit():
                    created_iso = datetime.fromtimestamp(
                        int(create_time), tz=timezone.utc
                    ).strftime("%Y-%m-%d %H:%M:%S")

                videos_by_id[vid_id] = VideoMetrics(
                    video_id=vid_id,
                    url=f"https://www.tiktok.com/@{username}/video/{vid_id}",
                    description=item.get("desc") or None,
                    created_at=created_iso,
                    views=stats.get("playCount"),
                    likes=stats.get("diggCount"),
                    comments=stats.get("commentCount"),
                    shares=stats.get("shareCount"),
                    saves=stats.get("collectCount"),
                )

        return list(videos_by_id.values())

    def _parse_from_rehydration_json(self) -> Optional[TikTokProfile]:
        """Extrae datos exactos del perfil desde __UNIVERSAL_DATA_FOR_REHYDRATION__."""
        script_tag = self.soup.find("script", id="__UNIVERSAL_DATA_FOR_REHYDRATION__")
        if not script_tag or not script_tag.string:
            return None

        try:
            raw_json = json.loads(script_tag.string)
        except json.JSONDecodeError:
            return None

        user_detail = raw_json.get("__DEFAULT_SCOPE__", {}).get("webapp.user-detail", {})
        status_code = user_detail.get("statusCode", 0)
        user_info = user_detail.get("userInfo", {})

        if status_code != 0 or not user_info or not user_info.get("user"):
            if status_code in (10202, 10221, 10222):
                raise ProfileNotFoundError(
                    f"El perfil '@{self.requested_username}' no existe (Código: {status_code})."
                )
            return None

        user_data = user_info.get("user", {})
        stats_data = user_info.get("stats", {})
        is_private = bool(user_data.get("privateAccount", False))

        notes: List[str] = []
        if is_private:
            notes.append("Este perfil es privado; no es posible acceder a sus publicaciones.")

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
            recent_videos=[],
            notes=notes,
        )

    def _parse_from_dom(self) -> Optional[TikTokProfile]:
        """Respaldo mediante selectores data-e2e del DOM."""
        title_node = self.soup.find(attrs={"data-e2e": "user-title"})
        subtitle_node = self.soup.find(attrs={"data-e2e": "user-subtitle"})
        followers_node = self.soup.find(attrs={"data-e2e": "followers-count"})
        following_node = self.soup.find(attrs={"data-e2e": "following-count"})
        likes_node = self.soup.find(attrs={"data-e2e": "likes-count"})
        bio_node = self.soup.find(attrs={"data-e2e": "user-bio"})

        if not any([title_node, followers_node, following_node]):
            return None

        page_text = self.soup.get_text(" ", strip=True).lower()
        is_private = "this account is private" in page_text or "esta cuenta es privada" in page_text

        return TikTokProfile(
            username=title_node.get_text(strip=True) if title_node else self.requested_username,
            display_name=subtitle_node.get_text(strip=True) if subtitle_node else None,
            biography=bio_node.get_text(strip=True) if bio_node else None,
            followers_count=parse_metric_string(followers_node.get_text(strip=True)) if followers_node else None,
            following_count=parse_metric_string(following_node.get_text(strip=True)) if following_node else None,
            total_likes_count=parse_metric_string(likes_node.get_text(strip=True)) if likes_node else None,
            videos_count=None,
            is_verified=None,
            is_private=is_private,
            extraction_method="DOM_DATA_E2E_FALLBACK",
            recent_videos=[],
            notes=["Datos de cabecera extraídos del DOM visual."],
        )

    def _extract_videos_from_dom(self) -> List[VideoMetrics]:
        """Extrae vistas y descripción desde las miniaturas HTML si no hubo respuesta XHR."""
        videos: List[VideoMetrics] = []
        for item in self.soup.find_all(attrs={"data-e2e": "user-post-item"}):
            link_tag = item.find("a", href=True)
            views_tag = item.find(attrs={"data-e2e": "video-views"})
            img_tag = item.find("img", alt=True)

            video_url = link_tag["href"] if link_tag else None
            video_id = video_url.split("/video/")[-1].split("?")[0] if video_url and "/video/" in video_url else None

            videos.append(
                VideoMetrics(
                    video_id=video_id,
                    url=video_url,
                    description=img_tag["alt"].strip() if img_tag and img_tag.get("alt") else None,
                    views=parse_metric_string(views_tag.get_text(strip=True)) if views_tag else None,
                )
            )
        return videos