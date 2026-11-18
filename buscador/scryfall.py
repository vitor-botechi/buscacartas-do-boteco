"""Caixa "Apenas nome exato": usa o Scryfall para descobrir os nomes da carta em inglês e português."""

import re
import threading
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


def english_for_portuguese(card, cards):
    """Nome em inglês da carta cujo nome em português é EXATAMENTE o digitado; None se nenhuma ou várias.

    A busca do Scryfall por "Thalia" em português traz todas as cartas que CONTÊM a palavra
    ("Thalia e O Monstro Gitrog", "Tenente de Thalia"...). Antes o programa ficava com a primeira da
    lista, uma escolha quase ao acaso; agora só aceita a carta se o nome em português bater por inteiro.
    """
    wanted = norm(card)
    found = set()
    for c in cards:
        printed = [c.get("printed_name")] + [f.get("printed_name") for f in c.get("card_faces", []) or []]
        if any(p and norm(p) == wanted for p in printed) and c.get("name"):
            found.add(c["name"])
    return found.pop() if len(found) == 1 else None


def resolve_names(card):
    """Devolve (conjunto de nomes aceitos, scryfall_respondeu). Sempre inclui o texto digitado."""
    names = set()
    add_names(names, card)
    try:
        english = None
        r = scry_get("/cards/named", {"fuzzy": card})
        if r.status_code == 200:
            english = r.json().get("name")
        else:  # nome ambíguo, com erro de digitação ou em português
            r2 = scry_get("/cards/search", {"q": f'"{card}" lang:pt', "include_multilingual": "true",
                                            "unique": "prints"})
            if r2.status_code == 200:
                english = english_for_portuguese(card, r2.json().get("data", []))
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


# ---- arte da carta (ao passar o mouse) ---------------------------------------------------------
# Para mostrar a arte da edição certa, a edição é procurada no Scryfall pelo nome ("Magic 2012"; com e
# sem o que vem entre parênteses) e pelo código do ícone da loja ("afc"; também sem números no fim:
# "sld107" -> "sld"). Algumas edições as lojas escrevem em português; aí vale o código. Se nada servir,
# fica a arte da carta numa edição qualquer. Cada carta/edição é consultada uma vez por execução (fica
# guardada aqui), e as consultas passam uma por vez (trava), no ritmo de scry_get.

_arte_trava = threading.Lock()
_artes = {}       # (nome, edição) normalizados -> endereço da imagem ("" = o Scryfall não tem)
_edicoes = None   # nome normalizado da edição -> código ("m12"), lido uma vez de /sets
_codigos = set()  # códigos de edição que o Scryfall conhece


def card_query_name(item_name):
    """Nome para o Scryfall a partir do nome na loja: 'Ilha / Island (#266)' -> 'Island'.

    " / " separa o nome em português do nome em inglês; "A // B" (carta de duas faces) fica inteiro.
    """
    base = strip_suffix(item_name)
    partes = [p.strip() for p in re.split(r"\s/\s", base) if p.strip()]
    return partes[-1] if partes else base


def card_image(card):
    """Endereço da imagem "normal" (488×680) da carta; nas de duas faces, a da frente. "" se não houver."""
    uris = card.get("image_uris") or ((card.get("card_faces") or [{}])[0] or {}).get("image_uris") or {}
    url = uris.get("normal") or ""
    return url if url.startswith("https://") else ""


def set_codes(edition, code=""):
    """Códigos do Scryfall que podem ser a edição (no máximo 2, do mais provável ao menos).
    Lê a lista de edições uma vez."""
    global _edicoes, _codigos
    if not edition and not code:
        return []
    if _edicoes is None:
        r = scry_get("/sets", {})
        if r.status_code != 200:
            return []  # tenta de novo na próxima vez
        dados = [s for s in r.json().get("data", []) if s.get("code")]
        _edicoes = {norm(s["name"]): s["code"] for s in dados if s.get("name")}
        _codigos = {s["code"] for s in dados}
    achados = [_edicoes.get(norm(edition or "")), _edicoes.get(norm(strip_suffix(edition or "")))]
    code = (code or "").lower()
    achados += [c for c in (code, re.sub(r"\d+$", "", code)) if c in _codigos]
    return list(dict.fromkeys(c for c in achados if c))[:2]


def _buscar_carta(nome, edicao, codigo=""):
    for code in set_codes(edicao, codigo):
        r = scry_get("/cards/named", {"exact": nome, "set": code})
        if r.status_code == 200:
            return r.json()
    r = scry_get("/cards/named", {"fuzzy": nome})
    if r.status_code == 200:
        return r.json()
    # nome só em português: descobre o nome em inglês e tenta de novo
    r = scry_get("/cards/search", {"q": f'"{nome}" lang:pt', "include_multilingual": "true", "unique": "prints"})
    english = english_for_portuguese(nome, r.json().get("data", [])) if r.status_code == 200 else None
    if english and norm(english) != norm(nome):
        return _buscar_carta(english, edicao, codigo)
    return None


def card_art(item_name, edition="", code=""):
    """Endereço da imagem da carta (da edição, se o Scryfall a conhecer). "" se não houver.

    Falha de rede não fica guardada: a pessoa pode passar o mouse de novo para tentar.
    """
    chave = (norm(item_name or ""), norm(edition or ""), (code or "").lower())
    if not chave[0] or requests is None:
        return ""
    with _arte_trava:
        if chave in _artes:
            return _artes[chave]
        try:
            carta = _buscar_carta(card_query_name(item_name), edition, code)
        except (requests.RequestException, ValueError):
            return ""
        _artes[chave] = card_image(carta) if carta else ""
        return _artes[chave]
