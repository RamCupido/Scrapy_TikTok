import json
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st


OUTPUT_FILE = Path(__file__).resolve().with_name("scraped_profiles.json")

PERSONALITY_TRAITS = {
    "openness": "Apertura",
    "conscientiousness": "Responsabilidad",
    "extraversion": "Extraversión",
    "agreeableness": "Amabilidad",
    "neuroticism": "Neuroticismo",
}


def load_profiles() -> list[dict[str, Any]]:
    if not OUTPUT_FILE.exists():
        return []

    with OUTPUT_FILE.open("r", encoding="utf-8") as file:
        profiles = json.load(file)

    if not isinstance(profiles, list):
        raise ValueError("El historial JSON debe contener una lista de perfiles.")
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
        ("Likes acumulados", profile.get("total_likes_count")),
        ("Publicaciones totales", profile.get("videos_count")),
    ]
    for column, (label, value) in zip(columns, metrics):
        column.metric(label, format_number(value))

    details = st.columns(3)
    details[0].write(f"**Nombre visible:** {profile.get('display_name') or 'No disponible'}")
    details[1].write(f"**Cuenta verificada:** {format_number(profile.get('is_verified'))}")
    details[2].write(f"**Cuenta privada:** {format_number(profile.get('is_private'))}")
    st.write(f"**Método de extracción:** {profile.get('extraction_method') or 'No disponible'}")


def render_videos(profile: dict[str, Any]) -> None:
    videos = profile.get("recent_videos") or []
    st.subheader(f"Publicaciones recopiladas ({len(videos)})")
    if not videos:
        st.info("No se recopilaron publicaciones en esta extracción.")
        return

    rows = []
    for index, video in enumerate(videos, start=1):
        rows.append(
            {
                "N.º": index,
                "ID": video.get("video_id"),
                "Fecha": video.get("created_at"),
                "Vistas": video.get("views"),
                "Likes": video.get("likes"),
                "Comentarios": video.get("comments"),
                "Compartidos": video.get("shares"),
                "Guardados": video.get("saves"),
                "Descripción": video.get("description"),
                "URL": video.get("url"),
            }
        )

    st.dataframe(rows, width="stretch", hide_index=True)

    view_rows = [
        (f"Video {index}", video.get("views"))
        for index, video in enumerate(videos, start=1)
        if numeric(video.get("views"))
    ]
    if view_rows:
        st.markdown("#### Visualizaciones por publicación")
        st.bar_chart(
            {
                "Publicación": [label for label, _ in view_rows],
                "Vistas": [value for _, value in view_rows],
            },
            x="Publicación",
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
                "Publicación": f"Video {index}",
                **{
                    interaction_names[key]: video.get(key)
                    for key in interaction_keys
                    if numeric(video.get(key))
                },
            }
            for index, video in enumerate(videos, start=1)
        ]
        st.markdown("#### Interacciones por publicación")
        st.bar_chart(interaction_rows, x="Publicación")


def render_personality(profile: dict[str, Any]) -> None:
    personality = profile.get("personality")
    st.subheader("Análisis de personalidad · Big Five")
    st.info(
        "Estimación automatizada basada únicamente en la biografía y las descripciones "
        "públicas recopiladas. Es orientativa: no es una evaluación psicológica ni un "
        "diagnóstico."
    )
    if not isinstance(personality, dict):
        st.warning(
            "Esta extracción no contiene un análisis de personalidad. "
            "Genera otra con la opción `--analyze-personality`."
        )
        return

    scores = [
        (label, personality.get(key))
        for key, label in PERSONALITY_TRAITS.items()
        if numeric(personality.get(key))
    ]
    if not scores:
        st.warning("No hay puntuaciones Big Five disponibles para esta extracción.")
        return

    st.bar_chart(
        {
            "Rasgo": [label for label, _ in scores],
            "Puntuación": [value for _, value in scores],
        },
        x="Rasgo",
        y="Puntuación",
    )
    for label, score in scores:
        st.progress(float(max(0, min(score, 1))), text=f"{label}: {score:.0%}")


def render_intelligence(profile: dict[str, Any]) -> None:
    intelligence = profile.get("intelligence")
    st.subheader("Análisis de métricas")
    if not isinstance(intelligence, dict):
        st.warning(
            "Esta extracción no contiene un análisis de métricas. "
            "Genera otra con la opción `--analytics`."
        )
        return

    follower_ratio = intelligence.get("follower_to_view_ratio")
    columns = st.columns(3)
    columns[0].metric(
        "Conversión seguidores → vistas",
        f"{follower_ratio * 100:.2f}%" if numeric(follower_ratio) else "No disponible",
    )
    for column, key, label in (
        (columns[1], "average_engagement_rate", "Engagement promedio"),
        (columns[2], "weighted_engagement_rate", "Engagement ponderado"),
    ):
        value = intelligence.get(key)
        column.metric(label, f"{value:.2f}%" if numeric(value) else "No disponible")

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
            st.markdown("#### Hashtags con más vistas promedio")
            st.bar_chart(
                {
                    "Hashtag": [f"#{tag}" for tag, _ in hashtag_rows],
                    "Vistas promedio": [value for _, value in hashtag_rows],
                },
                x="Hashtag",
                y="Vistas promedio",
            )

    outliers = intelligence.get("viral_outliers") or []
    st.markdown("#### Publicaciones virales atípicas")
    if outliers:
        st.dataframe(
            [
                {
                    "ID del video": item.get("video_id"),
                    "Vistas": item.get("views"),
                    "Z-Score": item.get("z_score"),
                }
                for item in outliers
                if isinstance(item, dict)
            ],
            width="stretch",
            hide_index=True,
        )
    else:
        st.caption("No se detectaron anomalías virales en la muestra.")

    summary = intelligence.get("ai_summary")
    st.markdown("#### Interpretación estratégica")
    if summary:
        st.write(summary)
    else:
        st.caption("Esta extracción no contiene una síntesis generada por IA.")


def main() -> None:
    st.set_page_config(page_title="TikTok Profile Insights", page_icon="📊", layout="wide")
    st.title("TikTok Profile Insights")
    st.caption("Panel local de perfiles públicos, publicaciones y análisis recopilados.")

    try:
        profiles = load_profiles()
    except (OSError, json.JSONDecodeError, ValueError) as error:
        st.error(f"No se pudo leer el historial `{OUTPUT_FILE.name}`: {error}")
        st.stop()
        return

    if not profiles:
        st.info(
            "Todavía no hay perfiles en el historial. Ejecuta primero el scraper desde "
            "la carpeta del proyecto y vuelve a cargar este panel."
        )
        st.code("python main.py --username USUARIO --analyze-personality --analytics")
        st.stop()
        return

    st.sidebar.header("Historial")
    st.sidebar.caption(f"{len(profiles)} extracciones guardadas")
    if st.sidebar.button("Actualizar historial"):
        st.rerun()

    profile_indices = list(reversed(range(len(profiles))))
    selected_index = st.sidebar.selectbox(
        "Selecciona una extracción",
        profile_indices,
        format_func=lambda index: profile_label(index, profiles),
    )
    profile = profiles[selected_index]
    username = profile.get("username") or "usuario desconocido"
    st.header(f"@{username}")
    if profile.get("display_name"):
        st.caption(profile["display_name"])
    st.caption(f"Extracción: {format_date(profile.get('extracted_at'))}")

    overview_tab, videos_tab, personality_tab, intelligence_tab, raw_tab = st.tabs(
        ["Resumen", "Publicaciones", "Personalidad", "Métricas", "Datos completos"]
    )
    with overview_tab:
        render_profile_overview(profile)
        if profile.get("notes"):
            with st.expander("Notas de extracción"):
                for note in profile["notes"]:
                    st.write(f"- {note}")

    with videos_tab:
        render_videos(profile)

    with personality_tab:
        render_personality(profile)

    with intelligence_tab:
        render_intelligence(profile)

    with raw_tab:
        st.json(profile)
        st.download_button(
            "Descargar esta extracción como JSON",
            data=json.dumps(profile, ensure_ascii=False, indent=2),
            file_name=f"{username}_profile.json",
            mime="application/json",
        )


if __name__ == "__main__":
    main()
