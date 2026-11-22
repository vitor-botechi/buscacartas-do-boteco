"""Requisições às lojas: busca, páginas seguintes, página do produto com cache curto e gravação em debug/."""

import os
import re
import time

try:
    import requests
except ImportError:  # sem a biblioteca a busca interna fica desligada (ver HAS_SCRAPING abaixo)
    requests = None

from buscador.armazenamento import host_key
from buscador.config import CACHE_TTL, HEADERS, MAX_PAGES, PAGE_SIZE, TIMEOUT, app_dir
from buscador.lojas.ligamagic import (
    BLOCK_MARKERS,
    BeautifulSoup,
    NONE_PHRASES,
    build_search_url,
    parse_product_page,
    parse_results,
    product_from_page,
    theme_color,
    svg_colors,
    theme_logo,
)
from buscador.modelos import Item, StoreResult


# o app abre mesmo sem as bibliotecas; só a busca interna fica desativada
HAS_SCRAPING = requests is not None and BeautifulSoup is not None


def fetch_store_look(base):
    """Abre a página inicial de uma loja nova (uma requisição só, ao adicionar).

    Devolve (o site respondeu?, cor ou None, segunda cor ou None, endereço da logo ou ""). Sem as
    bibliotecas, não confere. Se a logo for SVG, as cores vêm dela (mais uma requisição, à imagem),
    como nas lojas padrão; senão, a cor do site.
    """
    if not HAS_SCRAPING:
        return True, None, None, ""
    try:
        r = requests.get(base + "/", headers=HEADERS, timeout=TIMEOUT)
    except requests.RequestException:
        return False, None, None, ""
    if r.status_code in (403, 429, 503):  # o site existe, mas barrou a leitura
        return True, None, None, ""
    if r.status_code != 200:
        return False, None, None, ""
    cor, logo = theme_color(r.text), theme_logo(r.text)
    cores = logo_colors(logo) if logo.lower().endswith(".svg") else []
    if cores:
        return True, cores[0], (cores[1] if len(cores) > 1 else None), logo
    return True, cor, None, logo


def logo_colors(url):
    """Cores de uma logo em SVG (texto); qualquer erro, nenhuma."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        return svg_colors(r.text[:200_000]) if r.status_code == 200 else []
    except requests.RequestException:
        return []


def save_debug(store, url, r):
    """Grava o HTML recebido em debug/ e imprime um resumo no console (para diagnóstico)."""
    try:
        folder = os.path.join(app_dir(), "debug")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"debug_{host_key(store['url'])}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"<!-- {url} | HTTP {r.status_code} -->\n{r.text}")
        print(f"[{store['name']}] HTTP {r.status_code} | {len(r.text)} bytes | "
              f"links de produto: {r.text.count('view=ecom/item&')} | com refid: {r.text.count('refid=')}")
    except OSError:
        pass


def safe_search(store, card, max_pages=MAX_PAGES):
    """Qualquer erro inesperado vira um resultado 'error' em vez de travar a busca."""
    try:
        return search_store(store, card, max_pages)
    except Exception as e:  # noqa: BLE001
        url = build_search_url(store["url"], card)
        return StoreResult(store, url, "error", msg=f"{type(e).__name__}: {e}"[:120])


def fetch_page(store, card, page):
    url = build_search_url(store["url"], card, page)
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    return url, r


def search_store(store, card, max_pages=MAX_PAGES):
    url = build_search_url(store["url"], card)
    if not HAS_SCRAPING:
        return StoreResult(store, url, "error", msg="Bibliotecas ausentes")
    try:
        _, r = fetch_page(store, card, 1)
    except requests.RequestException as e:
        return StoreResult(store, url, "error", msg=str(e)[:120])

    save_debug(store, url, r)
    prod = product_from_page(r.text, r.url)
    if prod:
        name, purl, offers, pstatus = prod
        if offers:
            return StoreResult(store, url, "found", [Item(name, offers[0].price, purl, True, offers)])
        return StoreResult(store, url, "none" if pstatus == "empty" else "unknown")

    items, text = parse_results(r.text, store["url"])

    if not items:
        if r.status_code in (403, 429, 503) or any(m in text for m in BLOCK_MARKERS):
            return StoreResult(store, url, "blocked")
        # página de busca válida (tem o filtro de estoque) e sem produtos = não tem a carta
        if "txt_estoque" in r.text or any(p in text for p in NONE_PHRASES):
            return StoreResult(store, url, "none")
        return StoreResult(store, url, "unknown")

    # páginas seguintes (se houver mais resultados que cabem numa página)
    m = re.search(r"\d+-\d+ de (\d+)", text)
    total = int(m.group(1)) if m else len(items)
    pages = min(max_pages, -(-total // PAGE_SIZE))
    seen = {i.url for i in items}
    for page in range(2, pages + 1):
        try:
            _, rp = fetch_page(store, card, page)
        except requests.RequestException:
            break
        more, _ = parse_results(rp.text, store["url"])
        items += [i for i in more if i.url not in seen]
        seen.update(i.url for i in more)

    # a loja já devolve só itens com estoque, do menor para o maior preço
    return StoreResult(store, url, "found", items)


PRODUCT_CACHE = {}


def fetch_product(store, url):
    """Abre UMA página de produto e lê as ofertas (com cache curto para não repetir requisições)."""
    hit = PRODUCT_CACHE.get(url)
    if hit and time.time() - hit[0] < CACHE_TTL:
        return hit[1]
    data = _fetch_product(store, url)
    if data["status"] in ("ok", "empty"):
        PRODUCT_CACHE[url] = (time.time(), data)
    return data


def _fetch_product(store, url):
    if not HAS_SCRAPING:
        return {"status": "error", "msg": "Bibliotecas ausentes", "offers": []}
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    except requests.RequestException as e:
        return {"status": "error", "msg": str(e)[:120], "offers": []}
    try:
        folder = os.path.join(app_dir(), "debug")
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, f"debug_produto_{host_key(store['url'])}.html"), "w",
                  encoding="utf-8") as f:
            f.write(f"<!-- {url} | HTTP {r.status_code} -->\n{r.text}")
    except OSError:
        pass
    if r.status_code in (403, 429, 503):
        return {"status": "blocked", "offers": []}
    offers, status = parse_product_page(r.text)
    return {"status": status, "offers": offers}
