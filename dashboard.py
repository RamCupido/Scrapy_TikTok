import json
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from src.exceptions import (
    AccessControlTriggeredError,
    NetworkOrNavigationError,
    ProfileNotFoundError,
    TikTokScraperError,
)
from src.scraper import TikTokProfileScraper
from src.validators import InvalidUsernameError


OUTPUT_FILE = Path(__file__).resolve().with_name("scraped_profiles.json")

PERSONALITY_TRAITS = {
    "openness": "Apertura (Creatividad y curiosidad)",
    "conscientiousness": "Responsabilidad (Orden y constancia)",
    "extraversion": "Extraversión (Sociabilidad y energía)",
    "agreeableness": "Amabilidad (Empatía y cercanía)",
    "neuroticism": "Sensibilidad emocional (Reactividad)",
}


def load_profiles() -> list[dict[str, Any]]:
    if not OUTPUT_FILE.exists():
        return []

    with OUTPUT_FILE.open("r", encoding="utf-8") as file:
        profiles = json.load(file)

    if not isinstance(profiles, list):
        raise ValueError("El historial debe contener una lista de perfiles.")
    if not all(isinstance(profile, dict) for profile in profiles):
        raise ValueError("El historial contiene registros que no son perfiles válidos.")

    return profiles


def format_number(value: Any) -> str:
    if value is None:
        return "No disponible"
    if isinstance(value, bool):
        return "Sí" if value else "No"
    if isinstance(value, (int, float)):
        return f"{value:,.0f}".replace(",", ".")
    return str(value)


def format_date(value: Any) -> str:
    if not isinstance(value, str) or not value:
        return "No disponible"
    try:
        parsed_date = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed_date.astimezone().strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return value


def numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def profile_label(index: int, profiles: list[dict[str, Any]]) -> str:
    profile = profiles[index]
    username = profile.get("username") or "usuario desconocido"
    extracted_at = format_date(profile.get("extracted_at"))
    return f"@{username} · {extracted_at}"


def render_profile_overview(profile: dict[str, Any]) -> None:
    st.subheader("Resumen del perfil")
    st.caption(profile.get("biography") or "Este perfil no tiene una biografía disponible.")

    columns = st.columns(4)
    metrics = [
        ("Seguidores", profile.get("followers_count")),
        ("Seguidos", profile.get("following_count")),
        ("Likes totales", profile.get("total_likes_count")),
        ("Videos publicados", profile.get("videos_count")),
    ]
    for column, (label, value) in zip(columns, metrics):
        column.metric(label, format_number(value))

    details = st.columns(3)
    details[0].write(f"**Nombre visible:** {profile.get('display_name') or 'No disponible'}")
    details[1].write(f"**Cuenta verificada:** {format_number(profile.get('is_verified'))}")
    details[2].write(f"**Cuenta privada:** {format_number(profile.get('is_private'))}")

    intelligence = profile.get("intelligence")
    if isinstance(intelligence, dict):
        ai_summary = intelligence.get("ai_summary")
        if isinstance(ai_summary, str) and ai_summary.strip():
            st.markdown("#### Evaluación general con IA")
            st.info(ai_summary)


def render_videos(profile: dict[str, Any]) -> None:
    videos = profile.get("recent_videos") or []
    st.subheader(f"Videos recientes analizados ({len(videos)})")
    if not videos:
        st.info("No se encontraron videos públicos en esta extracción.")
        return

    rows = []
    for index, video in enumerate(videos, start=1):
        rows.append(
            {
                "N.º": index,
                "Descripción": video.get("description") or "Sin descripción",
                "Fecha": video.get("created_at") or "No disponible",
                "Vistas": video.get("views"),
                "Likes": video.get("likes"),
                "Comentarios": video.get("comments"),
                "Compartidos": video.get("shares"),
                "Guardados": video.get("saves"),
                "Enlace": video.get("url"),
            }
        )

    st.dataframe(rows, width="stretch", hide_index=True)

    view_rows = [
        (f"Video {index}", video.get("views"))
        for index, video in enumerate(videos, start=1)
        if numeric(video.get("views"))
    ]
    if view_rows:
        st.markdown("#### Vistas por video")
        st.bar_chart(
            {
                "Video": [label for label, _ in view_rows],
                "Vistas": [value for _, value in view_rows],
            },
            x="Video",
            y="Vistas",
        )

    interaction_keys = ("likes", "comments", "shares", "saves")
    interaction_names = {
        "likes": "Likes",
        "comments": "Comentarios",
        "shares": "Compartidos",
        "saves": "Guardados",
    }
    if any(numeric(video.get(key)) for video in videos for key in interaction_keys):
        interaction_rows = [
            {
                "Video": f"Video {index}",
                **{
                    interaction_names[key]: video.get(key)
                    for key in interaction_keys
                    if numeric(video.get(key))
                },
            }
            for index, video in enumerate(videos, start=1)
        ]
        st.markdown("#### Interacciones por video")
        st.bar_chart(interaction_rows, x="Video")


def render_personality(profile: dict[str, Any]) -> None:
    personality = profile.get("personality")
    st.subheader("Estilo de comunicación y personalidad")
    st.info(
        "Análisis generado con Inteligencia Artificial a partir de la biografía y las "
        "descripciones de los videos del creador. Muestra qué rasgos destacan más en su contenido."
    )
    if not isinstance(personality, dict):
        st.warning(
            "Este perfil no incluye análisis de personalidad. "
            "Marca la casilla «Incluir análisis de personalidad» en la barra lateral y vuelve a analizarlo."
        )
        return

    short_labels = {
        "openness": "Apertura",
        "conscientiousness": "Responsabilidad",
        "extraversion": "Extraversión",
        "agreeableness": "Amabilidad",
        "neuroticism": "Sensibilidad emocional",
    }

    scores = [
        (short_labels[key], PERSONALITY_TRAITS[key], personality.get(key))
        for key in PERSONALITY_TRAITS
        if numeric(personality.get(key))
    ]
    if not scores:
        st.warning("No hay puntuaciones de personalidad disponibles para este perfil.")
        return

    st.bar_chart(
        {
            "Rasgo": [short_label for short_label, _, _ in scores],
            "Proporción": [value for _, _, value in scores],
        },
        x="Rasgo",
        y="Proporción",
    )
    for _, full_label, score in scores:
        st.progress(float(max(0, min(score, 1))), text=f"{full_label}: {score:.0%}")


def render_intelligence(profile: dict[str, Any]) -> None:
    intelligence = profile.get("intelligence")
    st.subheader("Rendimiento del contenido y conclusión IA")
    if not isinstance(intelligence, dict):
        st.warning(
            "Este perfil no contiene un análisis de rendimiento. "
            "Marca la casilla «Incluir análisis de métricas e IA» en la barra lateral y vuelve a analizarlo."
        )
        return

    ai_summary = intelligence.get("ai_summary")
    st.markdown("#### Conclusión del análisis con IA")
    if isinstance(ai_summary, str) and ai_summary.strip():
        st.info(ai_summary)
    else:
        st.caption("No hay conclusión de IA registrada para este perfil.")

    follower_ratio = intelligence.get("follower_to_view_ratio")
    avg_er = intelligence.get("average_engagement_rate")
    weighted_er = intelligence.get("weighted_engagement_rate")

    columns = st.columns(3)
    columns[0].metric(
        "Alcance frente a seguidores",
        f"{follower_ratio * 100:.1f}%" if numeric(follower_ratio) else "No disponible",
        help="Compara el promedio de vistas por video con el total de seguidores de la cuenta.",
    )
    columns[1].metric(
        "Interacción promedio",
        f"{avg_er:.2f}%" if numeric(avg_er) else "No disponible",
        help="Porcentaje de personas que dan like, comentan, guardan o comparten tras ver un video.",
    )
    columns[2].metric(
        "Interacción de alto impacto",
        f"{weighted_er:.2f}%" if numeric(weighted_er) else "No disponible",
        help="Mide la interacción dándole el doble de valor a los videos guardados y compartidos.",
    )

    hashtags = intelligence.get("hashtag_performance")
    if isinstance(hashtags, dict) and hashtags:
        hashtag_rows = sorted(
            (
                (str(tag), value)
                for tag, value in hashtags.items()
                if numeric(value)
            ),
            key=lambda row: row[1],
            reverse=True,
        )
        if hashtag_rows:
            st.markdown("#### Hashtags que generan más vistas")
            st.bar_chart(
                {
                    "Hashtag": [f"#{tag}" for tag, _ in hashtag_rows],
                    "Vistas promedio": [value for _, value in hashtag_rows],
                },
                x="Hashtag",
                y="Vistas promedio",
            )

    outliers = intelligence.get("viral_outliers") or []
    st.markdown("#### Videos que superaron por mucho el promedio del perfil")
    if outliers:
        st.dataframe(
            [
                {
                    "Vistas alcanzadas": format_number(item.get("views")),
                    "Nivel de viralidad": f"{item.get('z_score')}x sobre lo habitual",
                }
                for item in outliers
                if isinstance(item, dict)
            ],
            width="stretch",
            hide_index=True,
        )
    else:
        st.caption("Todos los videos recientes mantienen un nivel de vistas similar (sin picos atípicos).")


def main() -> None:
    st.set_page_config(page_title="TikTok Profile Insights", page_icon="📊", layout="wide")
    st.title("Análisis de Perfiles de TikTok")
    st.caption("Consulta de forma sencilla las estadísticas, el impacto de los videos y el perfil de comunicación de cualquier cuenta pública.")

    st.sidebar.header("Cuenta de TikTok")
    session_status = TikTokProfileScraper.getSessionStatus()
    if session_status["authenticated"]:
        st.sidebar.success("Cuenta de TikTok conectada")
    elif session_status["file_exists"]:
        st.sidebar.warning("Modo invitado (sin cuenta conectada)")
    else:
        st.sidebar.info("Sin sesión iniciada")

    if st.sidebar.button("Conectar / Cambiar cuenta de TikTok", width="stretch"):
        with st.status("Abriendo ventana de TikTok...", expanded=True) as login_status:
            try:
                scraper = TikTokProfileScraper(headless=False)
                logged_in = scraper.loginInteractive(
                    progress_callback=lambda msg: login_status.update(
                        label=msg, state="running", expanded=True
                    )
                )
                if logged_in:
                    login_status.update(
                        label="Cuenta conectada correctamente",
                        state="complete",
                    )
                    st.rerun()
                else:
                    login_status.update(
                        label="No se completó el inicio de sesión",
                        state="error",
                    )
            except Exception as error:
                login_status.update(label="Error al iniciar sesión", state="error")
                st.error(str(error))

    st.sidebar.header("Analizar un perfil")
    with st.sidebar.form("profile_analysis_form"):
        raw_username = st.text_input("Usuario de TikTok", placeholder="@usuario")
        analyze_personality = st.checkbox("Incluir análisis de personalidad", value=True)
        analyze_metrics = st.checkbox("Incluir análisis de métricas e IA", value=True)
        headed = st.checkbox("Mostrar navegador durante la búsqueda", value=False)
        submitted = st.form_submit_button("Analizar perfil", type="primary")

    if submitted:
        if not raw_username.strip():
            st.sidebar.error("Escribe un nombre de usuario para comenzar.")
        else:
            succeeded = False
            with st.status("Iniciando análisis...", expanded=True) as status:
                try:
                    from main import runProfileAnalysis

                    profile, _ = runProfileAnalysis(
                        raw_username,
                        headed=headed,
                        analyze_personality=analyze_personality,
                        analytics=analyze_metrics,
                        progress_callback=lambda message: status.update(
                            label=message,
                            state="running",
                            expanded=True,
                        ),
                    )
                    status.update(label="Análisis completado", state="complete")
                    succeeded = True
                except (
                    InvalidUsernameError,
                    ProfileNotFoundError,
                    AccessControlTriggeredError,
                    NetworkOrNavigationError,
                    TikTokScraperError,
                ) as error:
                    status.update(label="No se pudo completar el análisis", state="error")
                    st.error(str(error))
                except Exception as error:
                    status.update(label="Ocurrió un error inesperado", state="error")
                    st.exception(error)

            if succeeded:
                st.success(f"Perfil @{profile.username} analizado correctamente.")
                st.rerun()

    try:
        profiles = load_profiles()
    except (OSError, json.JSONDecodeError, ValueError) as error:
        st.error(f"No se pudo leer el historial de perfiles: {error}")
        st.stop()
        return

    if not profiles:
        st.info(
            "Todavía no hay perfiles analizados. Escribe un usuario en la barra lateral "
            "para realizar tu primera consulta."
        )
        return

    st.sidebar.header("Perfiles consultados")
    st.sidebar.caption(f"{len(profiles)} análisis guardados")
    if st.sidebar.button("Actualizar lista"):
        st.rerun()

    profile_indices = list(reversed(range(len(profiles))))
    selected_index = st.sidebar.selectbox(
        "Selecciona un perfil",
        profile_indices,
        format_func=lambda index: profile_label(index, profiles),
    )
    profile = profiles[selected_index]
    username = profile.get("username") or "usuario desconocido"
    st.header(f"@{username}")
    if profile.get("display_name"):
        st.caption(profile["display_name"])
    st.caption(f"Fecha de consulta: {format_date(profile.get('extracted_at'))}")

    overview_tab, videos_tab, personality_tab, intelligence_tab = st.tabs(
        ["Resumen", "Videos", "Personalidad", "Rendimiento e IA"]
    )
    with overview_tab:
        render_profile_overview(profile)

    with videos_tab:
        render_videos(profile)

    with personality_tab:
        render_personality(profile)

    with intelligence_tab:
        render_intelligence(profile)


if __name__ == "__main__":
    main()
