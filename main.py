import argparse
import json
import sys
from pathlib import Path
from typing import Any
from src.scraper import TikTokProfileScraper
from src.exceptions import (
    AccessControlTriggeredError,
    NetworkOrNavigationError,
    ProfileNotFoundError,
)
from src.validators import InvalidUsernameError
from src.models import TikTokProfile

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

    print("-" * 65)
    print(f"{separator}\n")

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

    scraper = TikTokProfileScraper(headless=not args.headed)

    try:
        profile = scraper.fetchProfile(raw_username)
        printProfileReport(profile)
        json_path = appendProfileToJson(profile)
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