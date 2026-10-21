"""Módulo de análisis HTML y procesamiento de respuestas JSON de TikTok."""
import json
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup
from src.models import TikTokProfile, VideoMetrics
from src.normalizers import parse_metric_string, fix_int32_overflow
from src.exceptions import ProfileNotFoundError, AccessControlTriggeredError

class TikTokHTMLParser:
    """Analiza el HTML del perfil y combina los videos capturados en la red o en el DOM."""

    def __init__(
        self,
        html_content: str,
        requested_username: str,
        intercepted_video_payloads: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self.html = html_content
        self.requested_username = requested_username
        self.soup = BeautifulSoup(html_content, "html.parser")
        self.intercepted_payloads = intercepted_video_payloads or []

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
                "TikTok presentó un control CAPTCHA. Ejecuta el comando con '--headed' "
                "para validar la sesión de invitado en el navegador."
            )

    def parse(self) -> TikTokProfile:
        """Combina los datos del perfil con las métricas completas de los videos."""
        self.check_access_restrictions()

        profile = self._parse_from_rehydration_json() or self._parse_from_dom()
        if not profile:
            raise ProfileNotFoundError(
                f"No se encontró información pública para '@{self.requested_username}'."
            )

        # 1. Intentar con paquetes JSON interceptados de la red (/api/post/item_list/)
        xhr_videos = self._parse_intercepted_videos(profile.username)
        if xhr_videos:
            profile.recent_videos = xhr_videos
            profile.extraction_method += " + XHR_ITEM_LIST"
        elif not profile.recent_videos and not profile.is_private:
            # 2. Respaldo desde el DOM de la cuadrícula
            dom_videos = self._extract_videos_from_dom(profile.username)
            if dom_videos:
                profile.recent_videos = dom_videos
                profile.extraction_method += " + DOM_VIDEO_GRID"

        return profile

    def _parse_from_rehydration_json(self) -> Optional[TikTokProfile]:
        """Extrae datos exactos del perfil desde __UNIVERSAL_DATA_FOR_REHYDRATION__ corrigiendo int32 overflow."""
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
        # statsV2 almacena los enteros en 64 bits (como string) sin sufrir desbordamiento en cuentas gigantes
        stats_v2 = user_info.get("statsV2", {})

        is_private = bool(user_data.get("privateAccount", False))
        notes: List[str] = []
        if is_private:
            notes.append("Este perfil es privado; no es posible acceder a sus publicaciones.")

        raw_followers = stats_v2.get("followerCount") or stats_data.get("followerCount")
        raw_following = stats_v2.get("followingCount") or stats_data.get("followingCount")
        raw_likes = stats_v2.get("heartCount") or stats_v2.get("heart") or stats_data.get("heart") or stats_data.get("heartCount")
        raw_videos = stats_v2.get("videoCount") or stats_data.get("videoCount")

        return TikTokProfile(
            username=user_data.get("uniqueId", self.requested_username),
            display_name=user_data.get("nickname") or None,
            biography=user_data.get("signature") or None,
            followers_count=fix_int32_overflow(raw_followers),
            following_count=fix_int32_overflow(raw_following),
            total_likes_count=fix_int32_overflow(raw_likes),
            videos_count=fix_int32_overflow(raw_videos),
            is_verified=bool(user_data.get("verified", False)),
            is_private=is_private,
            extraction_method="SSR_JSON_REHYDRATION",
            recent_videos=[],
            notes=notes,
        )

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

                stats = item.get("statsV2") or item.get("stats", {})
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
                    views=fix_int32_overflow(stats.get("playCount")),
                    likes=fix_int32_overflow(stats.get("diggCount")),
                    comments=fix_int32_overflow(stats.get("commentCount")),
                    shares=fix_int32_overflow(stats.get("shareCount")),
                    saves=fix_int32_overflow(stats.get("collectCount")),
                )

        return list(videos_by_id.values())

    def _extract_videos_from_dom(self, username: str) -> List[VideoMetrics]:
        """Busca contenedores de video en el DOM por data-e2e o por patrón de enlaces /video/ID."""
        videos_by_id: Dict[str, VideoMetrics] = {}

        # Vía A: Por atributo data-e2e="user-post-item"
        for item in self.soup.find_all(attrs={"data-e2e": "user-post-item"}):
            link_tag = item.find("a", href=re.compile(r"/video/\d+"))
            if not link_tag:
                continue
            video_url = link_tag["href"]
            vid_id = video_url.split("/video/")[-1].split("?")[0]
            views_tag = item.find(attrs={"data-e2e": "video-views"})
            img_tag = item.find("img", alt=True)

            videos_by_id[vid_id] = VideoMetrics(
                video_id=vid_id,
                url=video_url if video_url.startswith("http") else f"https://www.tiktok.com{video_url}",
                description=img_tag["alt"].strip() if img_tag and img_tag.get("alt") else None,
                views=parse_metric_string(views_tag.get_text(strip=True)) if views_tag else None,
            )

        # Vía B: Si TikTok cambió data-e2e, buscar cualquier etiqueta <a> que apunte a un video del usuario
        if not videos_by_id:
            pattern = re.compile(rf"/@{re.escape(username)}/video/(\d+)", re.IGNORECASE)
            for a_tag in self.soup.find_all("a", href=pattern):
                match = pattern.search(a_tag["href"])
                if not match:
                    continue
                vid_id = match.group(1)
                if vid_id in videos_by_id:
                    continue
                views_tag = a_tag.find(attrs={"data-e2e": "video-views"}) or a_tag.find("strong")
                img_tag = a_tag.find("img", alt=True)
                videos_by_id[vid_id] = VideoMetrics(
                    video_id=vid_id,
                    url=f"https://www.tiktok.com/@{username}/video/{vid_id}",
                    description=img_tag["alt"].strip() if img_tag and img_tag.get("alt") else None,
                    views=parse_metric_string(views_tag.get_text(strip=True)) if views_tag else None,
                )

        return list(videos_by_id.values())

    @staticmethod
    def parse_single_video_html(html_content: str, fallback_video: VideoMetrics) -> VideoMetrics:
        """
        Extrae las métricas completas (likes, comentarios, guardados, compartidos, fecha y desc)
        desde el JSON de hidratación de la página individual de un video.
        """
        soup = BeautifulSoup(html_content, "html.parser")
        script_tag = soup.find("script", id="__UNIVERSAL_DATA_FOR_REHYDRATION__")
        if not script_tag or not script_tag.string:
            return fallback_video

        try:
            data = json.loads(script_tag.string)
            video_detail = data.get("__DEFAULT_SCOPE__", {}).get("webapp.video-detail", {})
            item_struct = video_detail.get("itemInfo", {}).get("itemStruct", {})
            if not item_struct:
                return fallback_video

            stats = item_struct.get("statsV2") or item_struct.get("stats", {})
            create_time = item_struct.get("createTime")
            created_iso = fallback_video.created_at
            if create_time and str(create_time).isdigit():
                created_iso = datetime.fromtimestamp(int(create_time), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

            return VideoMetrics(
                video_id=str(item_struct.get("id") or fallback_video.video_id),
                url=fallback_video.url,
                description=item_struct.get("desc") or fallback_video.description,
                created_at=created_iso,
                views=fix_int32_overflow(stats.get("playCount")) or fallback_video.views,
                likes=fix_int32_overflow(stats.get("diggCount")),
                comments=fix_int32_overflow(stats.get("commentCount")),
                shares=fix_int32_overflow(stats.get("shareCount")),
                saves=fix_int32_overflow(stats.get("collectCount")),
            )
        except Exception:
            return fallback_video

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