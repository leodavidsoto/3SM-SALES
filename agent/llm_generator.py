import os
import re
from pathlib import Path
from dotenv import load_dotenv
import anthropic

load_dotenv(Path(__file__).parent / ".env")

PROMPTS_DIR = Path(__file__).parent / "prompts"
TIPOS_VALIDOS = ("casino", "empresa", "boda", "productora")

_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY no está configurada en .env")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def _load_prompt(tipo: str) -> str:
    path = PROMPTS_DIR / f"{tipo}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt para tipo '{tipo}' no encontrado en {path}")
    return path.read_text(encoding="utf-8")


def _build_system(tipo: str, prospecto: dict) -> str:
    template = _load_prompt(tipo)
    banda_nombre = os.environ.get("BANDA_NOMBRE", "3 son Multitud")
    banda_contacto = os.environ.get("BANDA_CONTACTO", "")
    banda_email = os.environ.get("BANDA_EMAIL", "")
    banda_epk = os.environ.get("BANDA_EPK_URL", "")

    filled = template.format(
        nombre_local=prospecto.get("nombre", ""),
        ciudad=prospecto.get("ciudad", ""),
        nombre_contacto=prospecto.get("contacto", ""),
        cargo=prospecto.get("cargo", ""),
    )

    firma = (
        f"\n\nDATOS PARA LA FIRMA:\n"
        f"- Banda: {banda_nombre}\n"
        f"- Contacto: {banda_contacto}\n"
        f"- Email: {banda_email}\n"
        f"- EPK / Demo: {banda_epk}\n"
    )
    return filled + firma


def generar_correo(prospecto: dict) -> dict:
    """
    Genera un correo personalizado para un prospecto.
    Retorna dict con 'asunto' y 'cuerpo'.
    """
    tipo = prospecto.get("tipo", "").lower()
    if tipo not in TIPOS_VALIDOS:
        raise ValueError(f"tipo debe ser uno de {TIPOS_VALIDOS}, recibido: '{tipo}'")

    system_prompt = _build_system(tipo, prospecto)

    client = _get_client()
    message = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=800,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": "Genera el correo ahora.",
            }
        ],
    )

    raw = message.content[0].text.strip()
    return _parse_email(raw)


def _parse_email(raw: str) -> dict:
    """Separa asunto y cuerpo del texto generado."""
    lines = raw.splitlines()
    asunto = ""
    cuerpo_lines = []
    in_body = False

    for line in lines:
        if not in_body and re.match(r"^(Asunto|Subject)\s*:", line, re.IGNORECASE):
            asunto = re.sub(r"^(Asunto|Subject)\s*:\s*", "", line, flags=re.IGNORECASE).strip()
            in_body = True
            continue
        if in_body:
            cuerpo_lines.append(line)

    if not asunto:
        for i, line in enumerate(lines):
            if line.strip():
                asunto = line.strip()
                cuerpo_lines = lines[i + 1:]
                break

    cuerpo = "\n".join(cuerpo_lines).strip()
    return {"asunto": asunto, "cuerpo": cuerpo}


def generar_lote(prospectos: list) -> list:
    """Genera correos para una lista de prospectos. Retorna lista de dicts con resultado."""
    results = []
    for p in prospectos:
        try:
            correo = generar_correo(p)
            results.append({"prospecto_id": p["id"], "ok": True, **correo})
        except Exception as e:
            results.append({"prospecto_id": p["id"], "ok": False, "error": str(e)})
    return results
