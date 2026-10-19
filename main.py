"""
Punto de entrada principal de la aplicación CLI para extraer datos públicos de TikTok.
"""
import argparse
import sys
from typing import Any
from src.scraper import TikTokProfileScraper
from src.exporter import export_to_json, export_to_csv
from src.models import TikTokProfile
from src.exceptions import TikTokScraperError

def format_value(value: Any) -> str:
    """Formatea valores opcionales para mostrarlos claramente en consola."""
    if value is None:
        return "No disponible"
    if isinstance(value, bool):
        return "Sí" if value else "No"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)

def print_profile_report(profile: TikTokProfile) -> None:
    """Imprime en consola un reporte estructurado y legible de los datos obtenidos."""
    separator = "=" * 65
    print(f"\n{separator}")
    print(f" REPORTE DE PERFIL PÚBLICO DE TIKTOK: @{profile.username}")
    print(separator)
    print(f"  Nombre visible      : {format_value(profile.display_name)}")
    print(f"  Cuenta verificada   : {format_value(profile.is_verified)}")
    print(f"  Cuenta privada      : {format_value(profile.is_private)}")
    print(f"  Biografía           : {format_value(profile.biography)}")
    print("-" * 65)
    print(" MÉTRICAS E INTERACCIONES GENERALES DEL PERFIL:")
    print(f"  Seguidores          : {format_value(profile.followers_count)}")
    print(f"  Seguidos            : {format_value(profile.following_count)}")
    print(f"  Likes acumulados    : {format_value(profile.total_likes_count)}")
    print(f"  Publicaciones (tot) : {format_value(profile.videos_count)}")
    print("-" * 65)
    print(f" PUBLICACIONES RECIENTES DETECTADAS EN VISTA INICIAL ({len(profile.recent_videos)}):")
    
    if not profile.recent_videos:
        print("  [!] No se obtuvieron métricas de publicaciones individuales en esta sesión.")
    else:
        for idx, vid in enumerate(profile.recent_videos[:10], start=1):
            print(
                f"  {idx:02d}. ID: {vid.video_id or 'N/A'} | "
                f"Vistas: {format_value(vid.views)} | "
                f"Likes: {format_value(vid.likes)} | "
                f"Comentarios: {format_value(vid.comments)} | "
                f"Compartidos: {format_value(vid.shares)}"
            )

    if profile.notes:
        print("-" * 65)
        print(" NOTAS TÉCNICAS DE LA EXTRACCIÓN:")
        for note in profile.notes:
            print(f"  * {note}")

    print("-" * 65)
    print(f"  Método utilizado    : {profile.extraction_method}")
    print(f"  Fecha UTC           : {profile.extracted_at}")
    print(f"{separator}\n")

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extractor ético de información pública de perfiles de TikTok (Sin APIs)."
    )
    parser.add_argument(
        "-u", "--username",
        type=str,
        help="Nombre de usuario de TikTok (ej. tiktok o @tiktok). Si se omite, se solicitará por consola.",
    )
    parser.add_argument(
        "--json",
        type=str,
        metavar="RUTA_ARCHIVO",
        help="Ruta opcional para exportar el resultado en formato JSON (ej. salida/perfil.json).",
    )
    parser.add_argument(
        "--csv",
        type=str,
        metavar="RUTA_ARCHIVO",
        help="Ruta opcional para exportar el resumen en formato CSV (ej. salida/perfil.csv).",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Ejecuta el navegador con ventana visible en lugar de modo headless.",
    )
    return parser

def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    raw_username = args.username
    if not raw_username:
        try:
            raw_username = input("Introduce el username del perfil de TikTok (ej. @tiktok): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nOperación cancelada por el usuario.")
            return 1

    scraper = TikTokProfileScraper(headless=not args.headed)

    try:
        profile = scraper.fetch_profile(raw_username)
        print_profile_report(profile)

        if args.json:
            json_path = export_to_json(profile, args.json)
            print(f"[+] Datos exportados correctamente a JSON: {json_path}")

        if args.csv:
            csv_path = export_to_csv(profile, args.csv)
            print(f"[+] Resumen exportado correctamente a CSV: {csv_path}")

        return 0

    except TikTokScraperError as err:
        print(f"\n[ERROR CONTROLADO] {err}", file=sys.stderr)
        return 2
    except Exception as unexpected_err:
        print(f"\n[ERROR INESPERADO] Ocurrió un fallo no previsto: {unexpected_err}", file=sys.stderr)
        return 3

if __name__ == "__main__":
    sys.exit(main())