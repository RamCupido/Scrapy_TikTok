"""
Punto de entrada principal de la aplicación CLI para extraer datos públicos de TikTok.
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Any
from src.scraper import TikTokProfileScraper, NetworkOrNavigationError
from src.parser import ProfileNotFoundError, AccessControlTriggeredError
from src.validators import InvalidUsernameError
from src.models import TikTokProfile

OUTPUT_FILE = Path(__file__).resolve().with_name("scraped_profiles.json")

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

    if profile.notes:
        print("-" * 65)
        print(" NOTAS TÉCNICAS DE LA EXTRACCIÓN:")
        for note in profile.notes:
            print(f"  * {note}")

    print("-" * 65)
    print(f"{separator}\n")

def append_profile_to_json(profile: TikTokProfile, filepath: Path = OUTPUT_FILE) -> Path:
    """Agrega el perfil extraído al historial JSON sin reemplazar registros anteriores."""
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
        json_path = append_profile_to_json(profile)
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