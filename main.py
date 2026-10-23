import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable
from src.ai_summary import AIIntelligenceAnalyst
from src.scraper import TikTokProfileScraper
from src.exceptions import (
    AccessControlTriggeredError,
    NetworkOrNavigationError,
    ProfileNotFoundError,
)
from src.validators import InvalidUsernameError
from src.models import BigFiveScores, TikTokProfile
from src.personality import BigFiveAnalyzer
from src.analytics import DataIntelligenceAnalyzer

OUTPUT_FILE = Path(__file__).resolve().with_name("scraped_profiles.json")

def formatValue(value: Any) -> str:
    if value is None:
        return "No disponible"
    if isinstance(value, bool):
        return "Sí" if value else "No"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)

def printProfileReport(profile: TikTokProfile) -> None:
    separator = "=" * 65
    print(f"\n{separator}")
    print(f" REPORTE DE PERFIL PÚBLICO DE TIKTOK: @{profile.username}")
    print(separator)
    print(f"  Nombre visible      : {formatValue(profile.display_name)}")
    print(f"  Cuenta verificada   : {formatValue(profile.is_verified)}")
    print(f"  Cuenta privada      : {formatValue(profile.is_private)}")
    print(f"  Biografía           : {formatValue(profile.biography)}")
    print("-" * 65)
    print(" MÉTRICAS E INTERACCIONES GENERALES DEL PERFIL:")
    print(f"  Seguidores          : {formatValue(profile.followers_count)}")
    print(f"  Seguidos            : {formatValue(profile.following_count)}")
    print(f"  Likes acumulados    : {formatValue(profile.total_likes_count)}")
    print(f"  Publicaciones (tot) : {formatValue(profile.videos_count)}")

    if not profile.recent_videos:
        print("  [!] No se obtuvieron métricas de publicaciones individuales en esta sesión.")
    else:
        for idx, vid in enumerate(profile.recent_videos[:15], start=1):
            short_desc = (vid.description or "Sin descripción").replace("\n", " ")
            if len(short_desc) > 55:
                short_desc = short_desc[:52] + "..."
            print(
                f"  {idx:02d}. ID: {vid.video_id or 'N/A'} | Fecha: {vid.created_at or 'N/A'}\n"
                f"      Vistas: {formatValue(vid.views)} | Likes: {formatValue(vid.likes)} | "
                f"Comentarios: {formatValue(vid.comments)} | Guardados: {formatValue(vid.saves)} | "
                f"Compartidos: {formatValue(vid.shares)}\n"
                f"      Desc: {short_desc}"
            )

    if profile.notes:
        print("-" * 65)
        print(" NOTAS TÉCNICAS DE LA EXTRACCIÓN:")
        for note in profile.notes:
            print(f"  * {note}")

def render_score_bar(score: float, width: int = 20) -> str:
    """Genera una barra ASCII visual para representar la escala de 0.0 a 1.0."""
    filled = int(round(score * width))
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {score * 100:5.1f}%"

def print_personality_report(scores: BigFiveScores) -> None:
    print("-" * 65)
    print(" ANÁLISIS DE PERSONALIDAD BIG FIVE (OCEAN - HUGGING FACE):")
    print("-" * 65)
    print(f"  [O] Apertura (Openness)            : {render_score_bar(scores.openness)}")
    print(f"  [C] Responsabilidad (Conscient.)   : {render_score_bar(scores.conscientiousness)}")
    print(f"  [E] Extraversión (Extraversion)    : {render_score_bar(scores.extraversion)}")
    print(f"  [A] Amabilidad (Agreeableness)     : {render_score_bar(scores.agreeableness)}")
    print(f"  [N] Neuroticismo (Neuroticism)     : {render_score_bar(scores.neuroticism)}")
    print("-" * 65)

def print_intelligence_report(intel: Any) -> None:
    print("-" * 65)
    print(" INTELIGENCIA DE NEGOCIO Y AUDITORÍA DE DATOS:")
    print("-" * 65)
    
    print(f"  [1] Conversión Seguidores -> Vistas : {intel.follower_to_view_ratio * 100:.2f}%")
    print(f"  [2] Engagement Rate (ER) Promedio   : {intel.average_engagement_rate:.2f}%")
    print(f"  [2] ER Ponderado (Saves/Shares x2)  : {intel.weighted_engagement_rate:.2f}%")
    
    print(f"\n  [1] Anomalías Virales Detectadas (Z-Score > 2.0):")
    if intel.viral_outliers:
        for out in intel.viral_outliers:
            print(f"      * Video ID: {out.video_id} | Vistas: {out.views:,} | Z-Score: {out.z_score}")
    else:
        print("      Ninguna anomalía estadística en la muestra reciente.")

    print(f"\n  [3] Top Hashtags por Impacto Promedio (Vistas):")
    if intel.hashtag_performance:
        for idx, (tag, avg_v) in enumerate(intel.hashtag_performance.items(), 1):
            print(f"      {idx}. #{tag.ljust(15)} : {avg_v:,} vistas prom.")
    else:
        print("      No se detectaron hashtags suficientes en la muestra.")
        
    print("-" * 65)

def appendProfileToJson(profile: TikTokProfile, filepath: Path = OUTPUT_FILE) -> Path:
    profiles = []
    if filepath.exists():
        with filepath.open("r", encoding="utf-8") as file:
            profiles = json.load(file)
        if not isinstance(profiles, list):
            raise ValueError(f"El archivo JSON existente no contiene una lista: {filepath}")

    profiles.append(profile.to_dict())
    with filepath.open("w", encoding="utf-8") as file:
        json.dump(profiles, file, ensure_ascii=False, indent=4)
        file.write("\n")

    return filepath

def runProfileAnalysis(
    raw_username: str,
    headed: bool = False,
    analyze_personality: bool = False,
    analytics: bool = False,
    progress_callback: Callable[[str], None] | None = None,
) -> tuple[TikTokProfile, Path]:
    def report_progress(message: str) -> None:
        if progress_callback:
            progress_callback(message)

    report_progress("Extrayendo datos públicos del perfil...")
    scraper = TikTokProfileScraper(headless=not headed)
    profile = scraper.fetchProfile(raw_username)

    if analyze_personality:
        report_progress("Analizando personalidad con Big Five...")
        analyzer = BigFiveAnalyzer()
        profile.personality = analyzer.analyze_profile_corpus(
            biography=profile.biography,
            videos=profile.recent_videos,
        )

    if analytics:
        report_progress("Calculando métricas de engagement y rendimiento...")
        analyzer = DataIntelligenceAnalyzer(profile)
        profile.intelligence = analyzer.generate_intelligence()

    report_progress("Guardando resultados en el historial...")
    json_path = appendProfileToJson(profile)
    return profile, json_path

def buildArgParser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extractor ético de información pública de perfiles de TikTok (Sin APIs)."
    )
    parser.add_argument(
        "-u", "--username",
        type=str,
        help="Nombre de usuario de TikTok (ej. tiktok o @tiktok). Si se omite, se solicitará por consola.",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Ejecuta el navegador con ventana visible en lugar de modo headless.",
    )
    parser.add_argument(
        "--analyze-personality",
        action="store_true",
        help="Ejecuta inferencia NLP con Hugging Face sobre la bio y descripciones de videos.",
    )
    parser.add_argument(
        "--analytics",
        action="store_true",
        help="Ejecuta el análisis estadístico, engagement y rendimiento de hashtags.",
    )
    return parser

def main() -> int:
    parser = buildArgParser()
    args = parser.parse_args()

    raw_username = args.username
    if not raw_username:
        try:
            raw_username = input("Introduce el username del perfil de TikTok (ej. @tiktok): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nOperación cancelada por el usuario.")
            return 1

    try:
        def print_progress(message: str) -> None:
            print(f"[*] {message}")

        profile, json_path = runProfileAnalysis(
            raw_username,
            headed=args.headed,
            analyze_personality=args.analyze_personality,
            analytics=args.analytics,
            progress_callback=print_progress,
        )
        printProfileReport(profile)
        if args.analyze_personality:
            if profile.personality:
                print_personality_report(profile.personality)
            else:
                print("[!] Texto insuficiente en bio y videos para inferir rasgos de personalidad.")
        if args.analytics:
            print("[*] Procesando auditoría estadística e inteligencia de datos...")
            analyzer = DataIntelligenceAnalyzer(profile)
            profile.intelligence = analyzer.generate_intelligence()
        
            if profile.personality:
                print("[*] Generando dictamen crediticio FinTech con LLM local...")
                ai_analyst = AIIntelligenceAnalyst()
                # Pasamos el profile completo para que el LLM lea inteligencia y personalidad
                profile.intelligence.ai_summary = ai_analyst.generate_summary(profile)
            else:
                profile.intelligence.ai_summary = "Requiere ejecutar el flag --analyze-personality previamente."
            
        print_intelligence_report(profile.intelligence)
        print(f"[+] Datos añadidos al historial JSON: {json_path}")

        return 0

    except (
        InvalidUsernameError,
        ProfileNotFoundError,
        AccessControlTriggeredError,
        NetworkOrNavigationError,
    ) as err:
        print(f"\n[ERROR CONTROLADO] {err}", file=sys.stderr)
        return 2
    except Exception as unexpected_err:
        print(f"\n[ERROR INESPERADO] Ocurrió un fallo no previsto: {unexpected_err}", file=sys.stderr)
        return 3

if __name__ == "__main__":
    sys.exit(main())