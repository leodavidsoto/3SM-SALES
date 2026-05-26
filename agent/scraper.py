"""
Extractor de leads desde Google Maps (via Places API) y búsqueda web orgánica.

Uso básico:
    from scraper import buscar_leads
    leads = buscar_leads("casino", "Santiago", max_results=20)

Para Google Maps Places API se requiere GOOGLE_MAPS_API_KEY en .env.
Si no hay clave, el scraper cae al modo de búsqueda web orgánica (más lento).
"""

import os
import re
import time
import json
from pathlib import Path
from typing import Optional
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

GOOGLE_MAPS_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")

TIPO_A_QUERY = {
    "casino":      ["casino", "restaurante bar", "pub live music", "restobar", "discoteca"],
    "empresa":     ["empresa grande", "corporación", "holding", "recursos humanos eventos"],
    "boda":        ["wedding planner", "organizador de bodas", "eventos sociales", "salón de eventos"],
    "productora":  ["productora de eventos", "productora audiovisual", "agencia de eventos"],
    "hotel":       ["hotel 4 estrellas", "hotel 5 estrellas", "apart hotel eventos", "hotel boutique"],
    "municipal":   ["municipalidad", "municipio", "departamento de cultura", "centro cultural"],
    "educacion":   ["universidad", "instituto profesional", "colegio particular", "bienestar estudiantil"],
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def _places_search(query: str, ciudad: str, max_results: int) -> list[dict]:
    """Busca lugares usando Google Maps Places API (Text Search)."""
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    results = []
    next_page = None

    while len(results) < max_results:
        params = {
            "query": f"{query} en {ciudad}",
            "key": GOOGLE_MAPS_KEY,
            "language": "es",
        }
        if next_page:
            params = {"pagetoken": next_page, "key": GOOGLE_MAPS_KEY}
            time.sleep(2)

        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        for place in data.get("results", []):
            if len(results) >= max_results:
                break
            results.append({
                "nombre": place.get("name", ""),
                "ciudad": ciudad,
                "direccion": place.get("formatted_address", ""),
                "telefono": "",
                "email": "",
                "contacto": "",
                "cargo": "",
                "fuente": "google_maps",
            })
            place_id = place.get("place_id")
            if place_id:
                phone = _get_place_phone(place_id)
                if phone:
                    results[-1]["telefono"] = phone

        next_page = data.get("next_page_token")
        if not next_page:
            break

    return results


def _get_place_phone(place_id: str) -> str:
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": "formatted_phone_number",
        "key": GOOGLE_MAPS_KEY,
    }
    try:
        resp = requests.get(url, params=params, timeout=8)
        data = resp.json()
        return data.get("result", {}).get("formatted_phone_number", "")
    except Exception:
        return ""


def _web_search_leads(query: str, ciudad: str, max_results: int) -> list[dict]:
    """Extrae leads desde resultados de búsqueda web (DuckDuckGo HTML)."""
    search_url = "https://html.duckduckgo.com/html/"
    params = {"q": f"{query} {ciudad} contacto email", "kl": "es-cl"}
    results = []

    try:
        resp = requests.post(search_url, data=params, headers=HEADERS, timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        for result in soup.select(".result")[:max_results]:
            title_el = result.select_one(".result__title a")
            snippet_el = result.select_one(".result__snippet")
            url_el = result.select_one(".result__url")

            name = title_el.get_text(strip=True) if title_el else ""
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            site_url = url_el.get_text(strip=True) if url_el else ""

            email = _extract_email(snippet) or _extract_email(name)

            if name:
                results.append({
                    "nombre": name,
                    "ciudad": ciudad,
                    "direccion": "",
                    "telefono": _extract_phone(snippet),
                    "email": email,
                    "contacto": "",
                    "cargo": "",
                    "fuente": f"web:{site_url}",
                })
    except Exception as e:
        print(f"[scraper] Error en búsqueda web: {e}")

    return results


def _extract_email(text: str) -> str:
    match = re.search(r"[\w.\-+]+@[\w.\-]+\.[a-z]{2,}", text, re.IGNORECASE)
    return match.group(0).lower() if match else ""


def _extract_phone(text: str) -> str:
    match = re.search(r"(\+?56\s?)?(\(?\d{1,4}\)?[\s.\-]?)?\d{3,4}[\s.\-]?\d{4}", text)
    return match.group(0).strip() if match else ""


def buscar_leads(tipo: str, ciudad: str, max_results: int = 20) -> list[dict]:
    """
    Busca prospectos para el tipo de negocio y ciudad dados.
    Usa Google Maps Places API si GOOGLE_MAPS_API_KEY está configurada,
    de lo contrario usa búsqueda web orgánica.

    tipo: 'casino' | 'empresa' | 'boda' | 'productora' | 'hotel' | 'municipal' | 'educacion'
    """
    queries = TIPO_A_QUERY.get(tipo, [tipo])
    all_leads: list[dict] = []

    for q in queries:
        per_query = max(5, max_results // len(queries))
        remaining = max_results - len(all_leads)
        if remaining <= 0:
            break

        if GOOGLE_MAPS_KEY:
            leads = _places_search(q, ciudad, min(per_query, remaining))
        else:
            leads = _web_search_leads(q, ciudad, min(per_query, remaining))

        all_leads.extend(leads)
        time.sleep(1)

    seen = set()
    unique = []
    for lead in all_leads:
        key = lead["nombre"].lower().strip()
        if key and key not in seen:
            seen.add(key)
            lead["tipo"] = tipo
            unique.append(lead)

    return unique[:max_results]
