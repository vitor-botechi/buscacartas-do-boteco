"""Caixa "Apenas nome exato": usa o Scryfall para descobrir os nomes da carta em inglês e português."""

import re
import time

try:
    import requests
except ImportError:  # sem a biblioteca a busca interna fica desligada (ver rede.HAS_SCRAPING)
    requests = None

from buscador.texto import norm, strip_suffix


SCRY_HEADERS = {"User-Agent": "BuscadorMTG/1.0", "Accept": "application/json;q=0.9,*/*;q=0.8"}
SCRY_API = "https://api.scryfall.com"


def scry_get(path, params):
    r = requests.get(SCRY_API + path, params=params, headers=SCRY_HEADERS, timeout=10)
    time.sleep(0.12)  # cortesia: o Scryfall pede no máximo ~10 requisições por segundo
    return r


def add_names(names, text):
    n = norm(text or "")
    if not n:
        return
    names.add(n)
    for part in n.split("//"):  # cartas de duas faces: aceita cada face
        if part.strip():
            names.add(part.strip())


def matches_exact(item_name, names):
    base = norm(strip_suffix(item_name))
    parts = [p.strip() for p in re.split(r"/+", base) if p.strip()]  # "Nome PT / Nome EN" ou "A // B"
    return base in names or any(p in names for p in parts)


def resolve_names(card):
    """Devolve (conjunto de nomes aceitos, scryfall_respondeu). Sempre inclui o texto digitado."""
    names = set()
    add_names(names, card)
    try:
        english = None
        r = scry_get("/cards/named", {"fuzzy": card})
        if r.status_code == 200:
            english = r.json().get("name")
        else:  # talvez a pessoa tenha digitado em português
            r2 = scry_get("/cards/search", {"q": f'"{card}" lang:pt', "include_multilingual": "true",
                                            "unique": "prints"})
            if r2.status_code == 200 and r2.json().get("data"):
                english = r2.json()["data"][0].get("name")
        if english:
            add_names(names, english)
            r3 = scry_get("/cards/search", {"q": f'!"{english}" lang:pt', "include_multilingual": "true",
                                            "unique": "prints"})
            if r3.status_code == 200:
                for c in r3.json().get("data", []):
                    add_names(names, c.get("printed_name"))
                    for face in c.get("card_faces", []) or []:
                        add_names(names, face.get("printed_name"))
        return names, True
    except (requests.RequestException, ValueError):
        return names, False
