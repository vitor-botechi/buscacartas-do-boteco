"""
Buscador de Cartas Magic: The Gathering
---------------------------------------
Digite o nome da carta, escolha as lojas e veja num só lugar quais têm a carta
e por quanto. Funciona com lojas no padrão LigaMagic.

Instalação (uma vez):
    pip install requests beautifulsoup4

Uso:
    python buscador_mtg.py
"""

import json
import os
import queue
import random
import re
import sys
import threading
import time
import unicodedata
import webbrowser
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from urllib.parse import quote_plus, urljoin, urlparse

import tkinter as tk
from tkinter import messagebox, ttk

try:
    import requests
    from bs4 import BeautifulSoup

    HAS_SCRAPING = True
except ImportError:  # o app ainda abre; só a busca interna fica desativada
    HAS_SCRAPING = False

# --------------------------------------------------------------------------
# Configuração
# --------------------------------------------------------------------------

# Lojas que já vêm no programa. Para incluir mais por padrão, basta adicionar aqui.
DEFAULT_STORES = [
    {"name": "Overrun", "url": "https://www.overrun.com.br"},
    {"name": "Jackpot Jogos", "url": "https://www.jackpotjogos.com.br"},
    {"name": "Legacy TCG", "url": "https://www.legacytcg.com.br"},
    {"name": "Deckmaster Games", "url": "https://www.deckmastergames.com.br"},
]

# Padrão de busca das lojas LigaMagic: só itens COM ESTOQUE, do menor para o maior
# preço, 120 por página. Se alguma loja usar outro formato, mude este modelo.
SEARCH_PATH = "/?view=ecom/itens&busca={query}&txt_estoque=1&txt_order=3&txt_limit=120&page={page}"
PAGE_SIZE = 120
MAX_PAGES = 3

# Detalhes automáticos (edições e preços sem precisar clicar). Valores conservadores de propósito:
DEFAULT_AUTO_LIMIT = 5      # só detalha sozinho quando a loja tem até N itens
MAX_AUTO_LIMIT = 10         # teto do controle na tela
AUTO_TOTAL_CAP = 24         # no máximo N páginas de produto por busca, somando todas as lojas
AUTO_DELAY = 0.8            # segundos entre páginas da MESMA loja (mais um pouco de aleatoriedade)
CACHE_TTL = 300             # segundos que uma página de produto lida fica guardada
HISTORY_MAX = 10            # quantas buscas o Voltar/Avançar lembram
STALE_AFTER = 30 * 60       # resultados guardados mais velhos que isto (30 min) são refeitos ao voltar/avançar
DETAIL_W = 560              # largura do painel de edições e preços (a janela cresce isso ao abri-lo)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}
TIMEOUT = 15
MAX_ITEMS_PER_STORE = 8


def app_dir():
    if getattr(sys, "frozen", False):  # quando virar .exe com PyInstaller
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


CONFIG_FILE = os.path.join(app_dir(), "lojas.json")
SETTINGS_FILE = os.path.join(app_dir(), "config.json")


def load_settings():
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(data):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


# --------------------------------------------------------------------------
# Lojas (carregar / salvar / normalizar)
# --------------------------------------------------------------------------

def normalize_base(url):
    url = url.strip()
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    p = urlparse(url)
    if not p.netloc or "." not in p.netloc:
        raise ValueError("Link inválido")
    return f"{p.scheme}://{p.netloc}"


def host_key(url):
    return urlparse(url).netloc.lower().replace("www.", "")


def default_name(url):
    return host_key(url).split(".")[0].capitalize()


def build_search_url(base, card, page=1):
    return base.rstrip("/") + SEARCH_PATH.format(query=quote_plus(card), page=page)


def load_stores():
    stores = [dict(s, builtin=True, enabled=True) for s in DEFAULT_STORES]
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            saved = json.load(f).get("stores", [])
    except (OSError, ValueError):
        return stores

    by_host = {host_key(s["url"]): s for s in stores}
    for s in saved:
        try:
            key = host_key(s["url"])
        except (KeyError, TypeError):
            continue
        if key in by_host:  # loja padrão: só lembra se estava marcada
            by_host[key]["enabled"] = bool(s.get("enabled", True))
        else:  # loja adicionada pelo usuário
            stores.append(
                {
                    "name": s.get("name") or default_name(s["url"]),
                    "url": s["url"],
                    "builtin": False,
                    "enabled": bool(s.get("enabled", True)),
                }
            )
    return stores


def save_stores(stores):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"stores": stores}, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


# --------------------------------------------------------------------------
# Busca e leitura da página
# --------------------------------------------------------------------------

PRICE_RE = re.compile(r"R\$\s*([\d.]+,\d{2})")
NONE_PHRASES = (
    "nenhum produto", "nenhum resultado", "nenhum item", "nao encontramos",
    "nao foram encontrad", "sem resultados", "0 resultado", "nada encontrado",
)
BLOCK_MARKERS = (
    "just a moment", "cf-browser-verification", "captcha", "access denied",
    "attention required", "verificando se voce", "checking your browser",
)
SOLDOUT_MARKERS = ("indisponivel", "esgotado", "sem estoque")


@dataclass
class Item:
    name: str
    price: float | None
    url: str
    available: bool = True
    offers: list | None = None  # preenchido quando a busca já devolveu a página do produto


@dataclass
class StoreResult:
    store: dict
    search_url: str
    status: str  # found | soldout | none | blocked | unknown | error
    items: list = field(default_factory=list)
    msg: str = ""


def norm(s):
    for ch in "’‘´`":
        s = s.replace(ch, "'")
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()


INVISIBLE_CHARS = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff"))  # zero-width, comuns ao copiar de sites


def clean_card_name(text):
    """Tira espaços nas pontas, junta espaços repetidos e remove espaços 'invisíveis' de textos copiados."""
    return " ".join(text.translate(INVISIBLE_CHARS).split())


def age_text(seconds):
    m = int(seconds // 60)
    if m < 60:
        return f"há {m} min"
    h, m = divmod(m, 60)
    return f"há {h} h" + (f" {m} min" if m else "")


def money(v):
    if v is None:
        return ""
    s = f"{v:,.2f}"
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def is_product_href(href):
    return "view=ecom/item" in href and "ecom/itens" not in href


def parse_results(html, base_url):
    """Lê a página de busca e devolve (itens, texto_normalizado_da_página)."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    page_text = norm(soup.get_text(" ", strip=True))

    products = {}
    scope = soup.select(".cards:not(.cards-hint) .card-item")
    anchors = ([a for c in scope for a in c.find_all("a", href=True)] if scope
               else soup.find_all("a", href=True))
    for a in anchors:
        href = a["href"]
        if not is_product_href(href):
            continue

        # sobe na árvore até achar o "cartão" do produto (que tenha preço)
        box = a
        for _ in range(5):
            parent = box.parent
            if parent is None or parent.name in ("body", "html"):
                break
            others = {
                x["href"] for x in parent.find_all("a", href=True)
                if is_product_href(x["href"])
            } - {href}
            if others:  # o pai já engloba outros produtos
                break
            box = parent
            if PRICE_RE.search(box.get_text(" ", strip=True)):
                break
        box_text = box.get_text(" ", strip=True)

        img = a.find("img")
        name = a.get("title") or a.get_text(" ", strip=True) or (img.get("alt") if img else "") or ""
        name = PRICE_RE.sub("", str(name)).strip(" -|")[:90]

        entry = products.setdefault(href, {"name": "", "prices": [], "sold": False})
        if len(name) > len(entry["name"]):
            entry["name"] = name
        if not entry["prices"]:
            entry["prices"] = [float(p.replace(".", "").replace(",", ".")) for p in PRICE_RE.findall(box_text)]
        if any(m in norm(box_text) for m in SOLDOUT_MARKERS):
            entry["sold"] = True

    items = [
        Item(
            name=e["name"] or "Produto",
            price=min(e["prices"]) if e["prices"] else None,
            url=urljoin(base_url.rstrip("/") + "/", href),
            available=not e["sold"],
        )
        for href, e in products.items()
    ]
    return items, page_text


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


def safe_search(store, card):
    """Qualquer erro inesperado vira um resultado 'error' em vez de travar a busca."""
    try:
        return search_store(store, card)
    except Exception as e:  # noqa: BLE001
        url = build_search_url(store["url"], card)
        return StoreResult(store, url, "error", msg=f"{type(e).__name__}: {e}"[:120])


def product_from_page(html, page_url):
    """Se a busca devolveu direto a página de UM produto (acontece quando há um único resultado),
    devolve (nome, url, ofertas, status); senão, None."""
    soup = BeautifulSoup(html, "html.parser")
    if not soup.select_one("#product--list"):
        return None
    pt, en = soup.select_one(".nome_pt_cards"), soup.select_one(".nome_en_cards")
    names = [x.get_text(" ", strip=True) for x in (pt, en) if x and x.get_text(strip=True)]
    name = " / ".join(dict.fromkeys(names)) or "Produto"
    og = soup.select_one('meta[property="og:url"]')
    url = og.get("content") if og and og.get("content") else page_url
    offers, status = parse_product_page(html)
    return name, url, offers, status


def offer_desc(o):
    """Resumo de uma oferta: 'Português · NM · 2 un. · Foil · -10%'."""
    parts = [o.language or "—", o.quality or "—", f"{o.stock} un."]
    if o.extras:
        parts.append(o.extras)
    if o.original_price and o.price:
        parts.append(f"-{round((1 - o.price / o.original_price) * 100)}%")
    return "    ·    ".join(parts)


def fetch_page(store, card, page):
    url = build_search_url(store["url"], card, page)
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    return url, r


def search_store(store, card):
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
    pages = min(MAX_PAGES, -(-total // PAGE_SIZE))
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


# --------------------------------------------------------------------------
# Página do produto: edições, idioma, qualidade, estoque e preço (sob demanda)
# --------------------------------------------------------------------------

@dataclass
class Offer:
    edition: str
    language: str
    quality: str
    extras: str
    stock: int | None
    price: float | None
    preorder: bool = False
    original_price: float | None = None  # preço riscado, quando a oferta está em promoção


def parse_product_page(html):
    """Devolve (ofertas, status). status: ok | empty | unreadable."""
    soup = BeautifulSoup(html, "html.parser")
    for t in soup.select(".title-mobile"):
        t.decompose()
    rows = soup.select("div.table-cards-row")
    if not rows:
        return [], "empty"

    offers = []
    for row in rows:
        cells = row.find_all("div", class_="table-cards-body-cell", recursive=False)
        price_cell = row.select_one(".card-preco")
        if len(cells) < 4 or price_cell is None:
            continue
        idx = cells.index(price_cell)
        stock_cell = cells[idx - 1]

        img = cells[0].select_one("img.icon-edicao, img")
        edition = (img.get("title") or img.get("alt") or "") if img else ""
        tip = cells[0].select_one(".tooltip")
        if tip and tip.get_text(strip=True):
            edition = tip.get_text(strip=True)
        lang_img = cells[1].select_one("img")
        language = (lang_img.get("title") or lang_img.get("alt") or "") if lang_img else ""

        q_cell = row.select_one(".quality")
        quality = ""
        if q_cell:
            for t in q_cell.select(".tooltip"):
                t.decompose()
            quality = q_cell.get_text(" ", strip=True)
        e_cell = row.select_one(".card-extras")
        extras = e_cell.get_text(" ", strip=True) if e_cell else ""
        extras = "" if extras in ("-", "–") else extras

        preorder = stock_cell.select_one(".icone-pre-order") is not None
        m = re.search(r"(\d+)\s*unid", stock_cell.get_text(" ", strip=True))
        stock = int(m.group(1)) if m else None
        prices = [float(x.replace(".", "").replace(",", "."))
                  for x in PRICE_RE.findall(price_cell.get_text(" ", strip=True))]
        # em promoção a loja mostra o preço riscado e, depois, o preço novo
        price = prices[-1] if prices else None
        original = prices[0] if len(prices) >= 2 and prices[0] > prices[-1] else None

        offers.append(Offer(edition, language, quality, extras, stock, price, preorder, original))

    if not offers or all(o.stock is None and o.price is None for o in offers):
        return [], "unreadable"  # existem linhas, mas os números não vieram como texto
    offers = [o for o in offers if o.stock]  # a página também lista edições sem estoque
    if not offers:
        return [], "empty"
    offers.sort(key=lambda o: (o.price is None, o.price if o.price is not None else 0))
    return offers, "ok"


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


# --------------------------------------------------------------------------
# Detalhes automáticos (com freios para não sobrecarregar nem ser bloqueado)
# --------------------------------------------------------------------------

class AutoCtl:
    """Orçamento total de requisições da busca + freio de emergência compartilhado entre as lojas."""

    def __init__(self, cap):
        self.cap = cap
        self.lock = threading.Lock()
        self.stop = threading.Event()

    def take(self):
        with self.lock:
            if self.cap <= 0:
                return False
            self.cap -= 1
            return True


def auto_details(res, limit, ctl, exact, names_box, names_ready, post):
    """Lê, uma por vez e devagar, as páginas dos itens de UMA loja (se forem poucos)."""
    items = res.items
    if exact:
        names_ready.wait(timeout=10)
        names = names_box.get("names")
        if names:
            items = [i for i in items if matches_exact(i.name, names)]
    todo = [i for i in items if i.offers is None]
    if not todo or len(items) > limit:
        return
    store_url = res.store["url"]
    post("autostart", (store_url, [i.url for i in todo]))
    done = 0
    try:
        for n, it in enumerate(todo):
            if ctl.stop.is_set() or not ctl.take():
                return
            time.sleep(0.3 if n == 0 else random.uniform(AUTO_DELAY, AUTO_DELAY * 1.5))
            data = fetch_product(res.store, it.url)
            done += 1
            status = data["status"]
            if status == "ok":
                post("offers", (store_url, it.url, data["offers"]))
            post("autostep", (store_url, it.url))
            if status in ("blocked", "error"):
                ctl.stop.set()  # qualquer sinal de bloqueio: todas as lojas param
                post("autostop", res.store["name"])
                return
            if status == "unreadable":
                return  # esta loja não entrega os números como texto: não adianta insistir
    finally:
        post("autoend", (store_url, [i.url for i in todo[done:]]))


# --------------------------------------------------------------------------
# "Só nome exato" (usa o Scryfall para descobrir os nomes da carta em inglês e português)
# --------------------------------------------------------------------------

SCRY_HEADERS = {"User-Agent": "BuscadorMTG/1.0", "Accept": "application/json;q=0.9,*/*;q=0.8"}
SCRY_API = "https://api.scryfall.com"


def scry_get(path, params):
    r = requests.get(SCRY_API + path, params=params, headers=SCRY_HEADERS, timeout=10)
    time.sleep(0.12)  # cortesia: o Scryfall pede no máximo ~10 requisições por segundo
    return r


def strip_suffix(name):
    """'Sol Ring (Human)' -> 'Sol Ring'; 'Ilha (#266)' -> 'Ilha'."""
    prev = None
    while prev != name:
        prev = name
        name = re.sub(r"\s*\([^)]*\)\s*$", "", name)
    return name.strip()


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


# --------------------------------------------------------------------------
# Interface
# --------------------------------------------------------------------------

STATUS_TEXT = {
    "found": "✅ Encontrada",
    "soldout": "🟡 Cadastrada, mas indisponível",
    "none": "❌ Não encontrada",
    "blocked": "⚠ Site bloqueou a leitura — dê duplo clique para abrir",
    "unknown": "⚠ Não consegui ler — dê duplo clique para abrir",
    "error": "⚠ Falha de conexão — dê duplo clique para abrir",
}


class Tooltip:
    """Dica que aparece ao passar o mouse sobre um widget."""

    def __init__(self, widget, text):
        self.widget, self.text, self.tip = widget, text, None
        widget.bind("<Enter>", self.show, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")

    def show(self, _event=None):
        if self.tip:
            return
        x = self.widget.winfo_rootx()
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, background="#ffffe0", relief="solid", borderwidth=1,
                 padx=6, pady=3).pack()

    def hide(self, _event=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


def enable_word_editing(entry):
    """Ctrl+Backspace e Ctrl+Delete apagam uma palavra; Ctrl+A seleciona tudo (o Tk não faz isso sozinho)."""

    def back(event):
        w = event.widget
        if w.selection_present():
            w.delete("sel.first", "sel.last")
            return "break"
        pos, text = w.index("insert"), w.get()
        i = pos
        while i > 0 and text[i - 1].isspace():
            i -= 1
        while i > 0 and not text[i - 1].isspace():
            i -= 1
        w.delete(i, pos)
        return "break"

    def forward(event):
        w = event.widget
        if w.selection_present():
            w.delete("sel.first", "sel.last")
            return "break"
        pos, text = w.index("insert"), w.get()
        i, n = pos, len(text)
        while i < n and not text[i].isspace():
            i += 1
        while i < n and text[i].isspace():
            i += 1
        w.delete(pos, i)
        return "break"

    def select_all(event):
        event.widget.selection_range(0, "end")
        event.widget.icursor("end")
        return "break"

    entry.bind("<Control-BackSpace>", back)
    entry.bind("<Control-Delete>", forward)
    entry.bind("<Control-a>", select_all)
    entry.bind("<Control-A>", select_all)


class App:
    def __init__(self, root):
        self.root = root
        root.title("Buscador de Cartas MTG")
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        w = min(1200, sw - 60)
        h = min(720, sh - 120)
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2 - 20)  # um pouco acima do centro, por causa da barra de tarefas
        root.geometry(f"{w}x{h}+{x}+{y}")
        root.minsize(min(980, w), min(520, h))

        self.stores = load_stores()
        self.vars = {}
        self.results = {}
        self.url_by_iid = {}
        self.queue = queue.Queue()
        self.search_id = 0
        self.pending = 0
        self.current_card = ""
        self.expanded = set()
        self.exact_names = None
        self.exact_ok = True
        self.names_requested = 0
        self.item_by_iid = {}
        self.auto_note = ""
        self.auto_active = 0
        self.auto_total = 0
        self.auto_done = 0
        self.auto_loading = set()
        self.stores_total = 0
        self.stores_done = 0
        self.open_state = {}
        self.all_collapsed = False
        self._last_toggle = 0.0
        self.detail_seq = 0
        self.history = []
        self.forward = []
        self.search_time = time.time()
        self.ctl = None
        self.detail_open = False
        self.detail_token = 0
        self.detail_url = ""
        self.grown_by = 0

        self.build_ui()
        self.refresh_store_list()
        self.root.after(100, self.poll)
        self.paste_btn.focus_set()  # Enter/Espaço cola o nome copiado; digitar leva o texto ao campo

        if not HAS_SCRAPING:
            self.status_var.set(
                "Para ver os resultados aqui dentro, instale: pip install requests beautifulsoup4 "
                "(enquanto isso, o botão 'Abrir lojas no navegador' funciona normalmente)."
            )

    # ---- construção da tela -------------------------------------------------
    def build_ui(self):
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill="both", expand=True)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        # coluna das lojas
        left = ttk.LabelFrame(main, text=" Lojas ", padding=8)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        self.store_frame = ttk.Frame(left)
        self.store_frame.pack(fill="x")
        row = ttk.Frame(left)
        row.pack(fill="x", pady=(8, 0))
        ttk.Button(row, text="Todas", width=8, command=lambda: self.set_all(True)).pack(side="left")
        ttk.Button(row, text="Nenhuma", width=8, command=lambda: self.set_all(False)).pack(side="left", padx=4)
        ttk.Button(left, text="＋ Adicionar loja", command=self.add_store_dialog).pack(fill="x", pady=(8, 0))

        # coluna da busca + resultados
        right = ttk.Frame(main)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(2, weight=1)

        ttk.Label(right, text="Nome da carta:", font=("", 10, "bold")).grid(row=0, column=0, sticky="w")
        bar = ttk.Frame(right)
        bar.grid(row=1, column=0, sticky="ew", pady=(2, 8))
        bar.columnconfigure(0, weight=1)
        self.card_var = tk.StringVar()
        self.entry = ttk.Entry(bar, textvariable=self.card_var, font=("", 12))
        self.entry.grid(row=0, column=0, sticky="ew", ipady=3)
        self.entry.bind("<Return>", lambda e: self.start_search())
        enable_word_editing(self.entry)
        paste_btn = self.paste_btn = ttk.Button(bar, text="📋 Colar nome", command=self.paste_from_clipboard)
        paste_btn.grid(row=0, column=1, padx=(6, 0), sticky="ew")
        Tooltip(paste_btn, "Limpa o campo e cola o nome da carta que você copiou")
        for seq in ("<Return>", "<KP_Enter>"):  # o botão do ttk só responde ao Espaço; aqui também ao Enter
            paste_btn.bind(seq, lambda e: (self.paste_from_clipboard(), "break")[1])
        paste_btn.bind("<Key>", self.on_paste_btn_key)
        self.root.bind("<FocusIn>", self.on_window_focus)
        ttk.Button(bar, text="🔍 Buscar", command=self.start_search).grid(row=0, column=2, padx=(6, 0))
        ttk.Button(bar, text="🌐 Abrir lojas no navegador", command=self.open_selected_tabs).grid(
            row=0, column=3, padx=(6, 0))
        self.exact_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Apenas nome exato", variable=self.exact_var,
                        command=self.on_exact_toggle).grid(row=1, column=0, sticky="w", pady=(4, 0))
        nav = ttk.Frame(bar)
        nav.grid(row=1, column=1, sticky="e", pady=(4, 0), padx=(6, 0))
        self.back_btn = ttk.Button(nav, text="◀ Voltar", command=self.go_back, state="disabled")
        self.back_btn.pack(side="left")
        self.fwd_btn = ttk.Button(nav, text="Avançar ▶", command=self.go_forward, state="disabled")
        self.fwd_btn.pack(side="left", padx=(4, 0))
        self.back_tip = Tooltip(self.back_btn, "Não há busca anterior")
        self.fwd_tip = Tooltip(self.fwd_btn, "Não há busca para avançar")
        self.root.bind("<Alt-Left>", lambda e: self.go_back())
        self.root.bind("<Alt-Right>", lambda e: self.go_forward())
        self.details_btn = ttk.Button(bar, text="🔎 Ver edições e preços", command=self.show_details,
                                      state="disabled")
        self.details_btn.grid(row=1, column=2, sticky="e", pady=(4, 0), padx=(6, 0))
        self.collapse_btn = ttk.Button(bar, text="▲ Recolher listas", command=self.toggle_all)
        self.collapse_btn.grid(row=1, column=3, sticky="e", pady=(4, 0), padx=(6, 0))

        auto_row = ttk.Frame(bar)
        auto_row.grid(row=2, column=0, columnspan=4, sticky="w", pady=(4, 0))
        self.auto_var = tk.IntVar(value=self.initial_auto_limit())
        ttk.Label(auto_row, text="Mostrar edições e preços automaticamente quando a loja tiver até").pack(side="left")
        ttk.Spinbox(auto_row, from_=0, to=MAX_AUTO_LIMIT, width=3, textvariable=self.auto_var,
                    command=self.save_auto_limit).pack(side="left", padx=4)
        ttk.Label(auto_row, text="itens  (0 = desligado)").pack(side="left")
        self.auto_var.trace_add("write", lambda *_: self.save_auto_limit())

        cols = ("status", "price")
        self.tree = ttk.Treeview(right, columns=cols, show="tree headings", selectmode="browse")
        self.tree.heading("#0", text="Loja / Produto")
        self.tree.heading("status", text="Situação")
        self.tree.heading("price", text="Preço", anchor="w")
        self.tree.column("#0", width=380, minwidth=200)
        self.tree.column("status", width=400, minwidth=240)
        self.tree.column("price", width=160, minwidth=110, anchor="w")
        self.tree.grid(row=2, column=0, sticky="nsew")
        sb = ttk.Scrollbar(right, orient="vertical", command=self.tree.yview)
        sb.grid(row=2, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<<TreeviewOpen>>", self.mark_toggle, add="+")
        self.tree.bind("<<TreeviewClose>>", self.mark_toggle, add="+")
        self.tree.bind("<Return>", lambda e: self.show_details())
        self.tree.bind("<Button-3>", self.on_right_click)
        self.tree.bind("<Button-2>", self.on_right_click)
        self.tree.tag_configure("found", foreground="#0a7d2c")
        self.tree.tag_configure("soldout", foreground="#a06a00")
        self.tree.tag_configure("none", foreground="#888888")
        self.tree.tag_configure("more", foreground="#1d4ed8")
        self.tree.tag_configure("hint", foreground="#8a8f98")
        self.tree.tag_configure("alt", background="#f4f5f7")  # listra suave para guiar o olho entre linhas
        for t in ("blocked", "unknown", "error"):
            self.tree.tag_configure(t, foreground="#b45309")

        foot = ttk.Frame(right)
        foot.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        foot.columnconfigure(0, weight=1)
        self.status_var = tk.StringVar(value="Selecione uma linha e clique em “Ver edições e preços”, ou dê duplo clique para abrir a página na loja.")
        ttk.Label(foot, textvariable=self.status_var, wraplength=560, justify="left").grid(row=0, column=0, sticky="w")
        self.open_found_btn = ttk.Button(foot, text="Abrir só as lojas com a carta",
                                         command=self.open_found_tabs, state="disabled")
        self.open_found_btn.grid(row=0, column=1, padx=(8, 0))
        self.progress = ttk.Progressbar(right, mode="determinate")
        self.progress.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.build_detail_panel(main)

    def build_detail_panel(self, main):
        """Painel lateral 'Edições e preços': fica escondido até a pessoa pedir; a janela cresce ao abri-lo."""
        self.detail_frame = ttk.LabelFrame(main, text=" Edições e preços ", padding=8)
        f = self.detail_frame
        f.columnconfigure(0, weight=1)
        f.rowconfigure(2, weight=1)
        head = ttk.Frame(f)
        head.grid(row=0, column=0, columnspan=2, sticky="ew")
        head.columnconfigure(0, weight=1)
        self.detail_title = ttk.Label(head, text="", font=("", 10, "bold"), wraplength=DETAIL_W - 90, justify="left")
        self.detail_title.grid(row=0, column=0, sticky="w")
        ttk.Button(head, text="▶ Ocultar painel", command=self.close_details).grid(row=0, column=1, sticky="e")
        self.detail_info = ttk.Label(f, text="", wraplength=DETAIL_W - 40, justify="left")
        self.detail_info.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 6))

        tv = ttk.Treeview(f, columns=("lang", "stock", "price", "extra"), show="tree headings")
        for col, title, width, minw, anchor in (("#0", "Edição", 190, 120, "w"), ("lang", "Idioma · Qualid.", 110, 90, "w"),
                                                ("stock", "Estoque", 60, 50, "center"), ("price", "Preço", 75, 60, "w"),
                                                ("extra", "Extras / promoção", 150, 100, "w")):
            tv.heading(col, text=title, anchor="w" if anchor != "center" else "center")
            tv.column(col, width=width, minwidth=minw, anchor=anchor)
        tv.tag_configure("alt", background="#f4f5f7")
        tv.grid(row=2, column=0, sticky="nsew")
        sb = ttk.Scrollbar(f, orient="vertical", command=tv.yview)
        sb.grid(row=2, column=1, sticky="ns")
        tv.configure(yscrollcommand=sb.set)
        tv.bind("<Double-1>", self.on_detail_double_click)
        self.detail_tree = tv
        ttk.Button(f, text="🌐 Abrir página na loja",
                   command=lambda: self.detail_url and webbrowser.open_new_tab(self.detail_url)).grid(
            row=3, column=0, columnspan=2, sticky="e", pady=(8, 0))

    def on_detail_double_click(self, event):
        if self.detail_tree.identify_row(event.y) and self.detail_url:  # só em linha, não no cabeçalho
            webbrowser.open_new_tab(self.detail_url)
        return "break"

    def resize_for_panel(self, opening):
        """Aumenta a largura da janela ao abrir o painel (se couber na tela) e devolve ao fechar."""
        root = self.root
        if root.state() == "zoomed":
            return  # maximizada: o Tk redistribui o espaço sozinho
        root.update_idletasks()
        w, h = root.winfo_width(), root.winfo_height()
        x, y = root.winfo_x(), root.winfo_y()
        screen_w = root.winfo_screenwidth()
        if opening:
            new_w = min(w + DETAIL_W + 10, screen_w - 20)
            self.grown_by = max(0, new_w - w)
            if x + new_w > screen_w - 10:
                x = max(0, screen_w - new_w - 10)  # empurra a janela para a esquerda para caber
        else:
            new_w = max(600, w - self.grown_by)
            self.grown_by = 0
        root.geometry(f"{new_w}x{h}+{x}+{y}")

    def open_detail_panel(self):
        if self.detail_open:
            return
        self.detail_frame.grid(row=0, column=2, sticky="nsew", padx=(10, 0))
        self.detail_open = True
        self.resize_for_panel(True)

    def close_details(self):
        if not self.detail_open:
            return
        self.detail_token += 1  # descarta respostas que ainda estejam a caminho
        self.detail_frame.grid_remove()
        self.detail_open = False
        self.resize_for_panel(False)

    def on_window_focus(self, event):
        """Ao voltar para o app (Alt+Tab), o foco vai para 'Colar nome': Enter cola, Enter de novo busca."""
        if event.widget is not self.root or self.root.grab_current() is not None:
            return
        self.root.after(30, self.focus_paste_btn)

    def focus_paste_btn(self):
        if self.root.grab_current() is None:
            self.paste_btn.focus_set()

    def on_paste_btn_key(self, event):
        """Com o foco no botão: Ctrl+V cola; digitar uma letra leva o texto para o campo (substituindo o antigo)."""
        alt = 0x20000 if sys.platform == "win32" else 0x8
        if event.state & 0x4 and event.keysym.lower() == "v":
            self.paste_from_clipboard()
            return "break"
        if event.state & (0x4 | alt):
            return None
        ch = event.char
        if ch and ch.isprintable() and ch != " ":
            self.card_var.set(ch)
            self.entry.focus_set()
            self.entry.icursor("end")
            return "break"
        return None

    def paste_from_clipboard(self):
        """Limpa o campo e cola o nome copiado (primeira linha, sem espaços sobrando)."""
        try:
            raw = self.root.clipboard_get()
        except tk.TclError:
            raw = ""
        name = clean_card_name(next((ln for ln in raw.splitlines() if ln.strip()), ""))
        self.entry.focus_set()
        if not name:
            self.status_var.set("Não há texto copiado. Copie o nome da carta e clique em “📋 Colar nome”.")
            return
        self.card_var.set(name)
        self.entry.icursor("end")
        self.status_var.set(f"Colado: “{name}”. Aperte Enter ou clique em Buscar.")

    # ---- limite dos detalhes automáticos ------------------------------------------
    @staticmethod
    def initial_auto_limit():
        try:
            v = int(load_settings().get("auto_limit", DEFAULT_AUTO_LIMIT))
        except (TypeError, ValueError):
            v = DEFAULT_AUTO_LIMIT
        return max(0, min(MAX_AUTO_LIMIT, v))

    def auto_limit(self):
        try:
            return max(0, min(MAX_AUTO_LIMIT, int(self.auto_var.get())))
        except (tk.TclError, ValueError):
            return DEFAULT_AUTO_LIMIT

    def save_auto_limit(self):
        data = load_settings()
        data["auto_limit"] = self.auto_limit()
        save_settings(data)

    # ---- lojas ----------------------------------------------------------------
    def refresh_store_list(self):
        for w in self.store_frame.winfo_children():
            w.destroy()
        for s in self.stores:
            var = self.vars.get(s["url"]) or tk.BooleanVar(value=s["enabled"])
            self.vars[s["url"]] = var
            row = ttk.Frame(self.store_frame)
            row.pack(fill="x", pady=1)
            ttk.Checkbutton(row, text=s["name"], variable=var, command=self.persist).pack(side="left")
            if not s["builtin"]:
                ttk.Button(row, text="✕", width=2, command=lambda st=s: self.remove_store(st)).pack(side="right")

    def persist(self):
        for s in self.stores:
            s["enabled"] = self.vars[s["url"]].get()
        save_stores(self.stores)

    def set_all(self, value):
        for v in self.vars.values():
            v.set(value)
        self.persist()

    def selected_stores(self):
        return [s for s in self.stores if self.vars[s["url"]].get()]

    def add_store_dialog(self):
        win = tk.Toplevel(self.root)
        win.title("Adicionar loja")
        win.transient(self.root)
        win.resizable(False, False)
        win.grab_set()
        frm = ttk.Frame(win, padding=12)
        frm.pack()
        ttk.Label(frm, text="Link da loja (ex.: www.minhaloja.com.br):").grid(row=0, column=0, sticky="w")
        url_var = tk.StringVar()
        e1 = ttk.Entry(frm, textvariable=url_var, width=42)
        e1.grid(row=1, column=0, pady=(0, 8))
        ttk.Label(frm, text="Nome (opcional):").grid(row=2, column=0, sticky="w")
        name_var = tk.StringVar()
        e2 = ttk.Entry(frm, textvariable=name_var, width=42)
        e2.grid(row=3, column=0, pady=(0, 10))
        enable_word_editing(e1)
        enable_word_editing(e2)

        def ok(_=None):
            try:
                base = normalize_base(url_var.get())
            except ValueError:
                messagebox.showwarning("Link inválido", "Confira o link da loja.", parent=win)
                return
            if any(host_key(s["url"]) == host_key(base) for s in self.stores):
                messagebox.showinfo("Já existe", "Essa loja já está na lista.", parent=win)
                return
            self.stores.append({"name": name_var.get().strip() or default_name(base),
                                "url": base, "builtin": False, "enabled": True})
            self.refresh_store_list()
            self.persist()
            win.destroy()

        ttk.Button(frm, text="Adicionar", command=ok).grid(row=4, column=0, sticky="e")
        win.bind("<Return>", ok)
        e1.focus_set()

    def remove_store(self, store):
        if messagebox.askyesno("Remover", f"Remover a loja “{store['name']}”?"):
            self.stores.remove(store)
            self.vars.pop(store["url"], None)
            self.refresh_store_list()
            self.persist()

    # ---- abrir no navegador ---------------------------------------------------
    @staticmethod
    def open_urls(urls):
        for u in urls:
            webbrowser.open_new_tab(u)

    def open_selected_tabs(self):
        card = clean_card_name(self.card_var.get())
        stores = self.selected_stores()
        if not card:
            messagebox.showinfo("Falta o nome", "Digite o nome da carta.")
            return
        if not stores:
            messagebox.showinfo("Nenhuma loja", "Marque ao menos uma loja.")
            return
        self.open_urls([build_search_url(s["url"], card) for s in stores])

    def mark_toggle(self, _event=None):
        """O Tk avisa (só em ação da pessoa) quando uma linha é aberta/fechada pelo +/−."""
        self._last_toggle = time.monotonic()

    def on_double_click(self, event):
        # Se um +/− acabou de ser acionado, este duplo clique é do botãozinho: não abre a loja.
        if time.monotonic() - self._last_toggle < 0.6:
            return "break"
        iid = self.tree.identify_row(event.y)
        if iid.endswith("|more"):
            self.render_store(iid.rsplit("|", 1)[0], expanded=True)
        elif iid.endswith(("|less_top", "|less_end")):
            store_iid = iid.rsplit("|", 1)[0]
            self.render_store(store_iid, expanded=False)
            self.tree.see(store_iid)  # volta para o nome da loja
        elif iid in self.url_by_iid:
            webbrowser.open_new_tab(self.url_by_iid[iid])
        return "break"  # impede que o duplo clique também expanda/recolha a linha

    def toggle_all(self):
        """Recolher: fecha as ofertas abertas e volta as listas longas às primeiras linhas.
        Expandir: reabre as ofertas de todos os itens."""
        collapse = not self.all_collapsed
        self.all_collapsed = collapse
        if collapse:
            self.expanded.clear()
        for iid, res in list(self.results.items()):
            for n, it in enumerate(self.visible_items(res)):
                if it.offers:
                    child = f"{iid}|{n}"
                    self.open_state[child] = not collapse
                    if self.tree.exists(child):
                        self.tree.item(child, open=not collapse)
            self.render_store(iid)
        self.collapse_btn.config(text="▼ Expandir listas" if collapse else "▲ Recolher listas")

    # ---- detalhes de um produto (sob demanda) -----------------------------------
    def product_iid_selected(self):
        sel = self.tree.selection()
        return sel[0] if sel and sel[0] in self.item_by_iid else None

    def on_select(self, _event=None):
        iid = self.product_iid_selected()
        self.details_btn.config(state="normal" if iid else "disabled")
        if iid and self.detail_open and self.item_by_iid[iid].url != self.detail_url:
            if self.item_by_iid[iid].offers:  # já lido: aparece na hora
                self.show_details()
            else:  # pequena espera, para não pedir páginas ao passar rápido pelas linhas com as setas
                self.root.after(350, lambda: self.load_selected_detail(iid))

    def load_selected_detail(self, iid):
        it = self.item_by_iid.get(iid)
        if (self.detail_open and it is not None and self.product_iid_selected() == iid
                and it.url != self.detail_url):
            self.show_details()

    def on_right_click(self, event):
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        self.tree.selection_set(iid)
        menu = tk.Menu(self.root, tearoff=0)
        if iid in self.item_by_iid:
            menu.add_command(label="🔎 Ver edições e preços", command=self.show_details)
        if iid in self.url_by_iid:
            menu.add_command(label="🌐 Abrir no navegador",
                             command=lambda: webbrowser.open_new_tab(self.url_by_iid[iid]))
        if menu.index("end") is None:
            return
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def show_details(self):
        iid = self.product_iid_selected()
        if not iid:
            return
        it = self.item_by_iid[iid]
        store = self.results[iid.rsplit("|", 1)[0]].store
        self.detail_seq += 1
        token = self.detail_token = self.detail_seq
        self.detail_url = it.url
        self.open_detail_panel()
        self.detail_title.config(text=f"{it.name}\n{store['name']}")
        self.detail_tree.delete(*self.detail_tree.get_children())
        self.detail_info.config(text="⏳ Carregando edições, estoque e preço…")
        if it.offers:  # já lido (busca de resultado único ou detalhes automáticos): sem nova requisição
            self.fill_details(token, {"status": "ok", "offers": it.offers})
            return

        def worker():
            self.queue.put(("details", token, fetch_product(store, it.url)))

        threading.Thread(target=worker, daemon=True).start()

    def fill_details(self, token, data):
        if token != self.detail_token:
            return  # a pessoa já pediu outro item ou fechou o painel
        tv, info = self.detail_tree, self.detail_info
        tv.delete(*tv.get_children())
        status = data["status"]
        if status == "ok":
            offers = data["offers"]
            units = sum(o.stock or 0 for o in offers)
            info.config(text=f"{len(offers)} oferta(s) em estoque, {units} unidade(s) no total. "
                             f"Do menor para o maior preço. Duplo clique em uma linha abre a página na loja.")
            for idx, o in enumerate(offers):
                promo = ""
                if o.original_price and o.price:
                    promo = f"-{round((1 - o.price / o.original_price) * 100)}% (de {money(o.original_price)})"
                extra = "   ·   ".join(x for x in (o.extras, promo) if x)
                name = o.edition + ("  (pré-venda)" if o.preorder else "")
                tv.insert("", "end", text=name, tags=(("alt",) if idx % 2 else ()),
                          values=(f"{o.language or '—'} · {o.quality or '—'}", f"{o.stock} un.", money(o.price), extra))
        elif status == "empty":
            info.config(text="Esta página não tem ofertas em estoque no momento.")
        elif status == "unreadable":
            info.config(text="⚠ A loja não entregou estoque e preço como texto ao programa nesta página. "
                             "Use “Abrir página na loja”.")
        elif status == "blocked":
            info.config(text="⚠ A loja bloqueou a leitura. Use “Abrir página na loja”.")
        else:
            info.config(text=f"⚠ Falha de conexão: {data.get('msg', '')}")

    # ---- histórico (Voltar / Avançar) --------------------------------------------------
    def snapshot(self):
        return {
            "card": self.current_card, "exact": self.exact_var.get(), "names": self.exact_names,
            "ok": self.exact_ok, "results": dict(self.results), "order": list(self.tree.get_children("")),
            "open_state": dict(self.open_state), "expanded": set(self.expanded),
            "all_collapsed": self.all_collapsed, "note": self.auto_note, "time": self.search_time,
        }

    def screen_is_complete(self):
        return bool(self.current_card and self.results and self.pending == 0)

    def push_history(self, new_card):
        """Guarda a busca atual (só se terminou e se a nova é de outra carta); a nova busca zera o Avançar."""
        if not self.screen_is_complete() or norm(new_card) == norm(self.current_card):
            return  # repetir a mesma busca só atualiza; não cria outra entrada
        self.history.append(self.snapshot())
        del self.history[:-HISTORY_MAX]
        self.forward.clear()
        self.update_nav_buttons()

    def update_nav_buttons(self):
        for stack, btn, tip, empty, label, key in (
                (self.history, self.back_btn, self.back_tip, "Não há busca anterior",
                 "Voltar para a busca anterior", "Alt+←"),
                (self.forward, self.fwd_btn, self.fwd_tip, "Não há busca para avançar",
                 "Avançar para a próxima busca", "Alt+→")):
            if stack:
                snap = stack[-1]
                text = f"{label}: “{snap['card']}”  ({key})"
                if time.time() - snap["time"] > STALE_AFTER:
                    text += f"\nResultados {age_text(time.time() - snap['time'])}: a busca será refeita"
                btn.config(state="normal")
                tip.text = text
            else:
                btn.config(state="disabled")
                tip.text = empty

    def cancel_running(self):
        """Interrompe o que estiver em andamento; respostas atrasadas passam a ser ignoradas."""
        self.search_id += 1
        if self.ctl:
            self.ctl.stop.set()
        self.pending = self.auto_active = 0
        self.auto_total = self.auto_done = self.stores_total = self.stores_done = 0
        self.auto_loading = set()
        self.close_details()

    def go_back(self):
        self.navigate(self.history, self.forward)

    def go_forward(self):
        self.navigate(self.forward, self.history)

    def navigate(self, source, target):
        """Vai para a busca no topo de 'source' e guarda a tela atual em 'target' (Voltar <-> Avançar)."""
        if not source:
            return
        snap = source.pop()
        if self.screen_is_complete():
            target.append(self.snapshot())
            del target[:-HISTORY_MAX]
        self.cancel_running()
        if time.time() - snap["time"] > STALE_AFTER:
            # resultados antigos (preço e estoque podem ter mudado): refaz a busca em vez de mostrá-los
            self.card_var.set(snap["card"])
            self.exact_var.set(snap["exact"])
            self.update_nav_buttons()
            self.start_search(skip_history=True)
            return
        self.restore_snapshot(snap)
        self.update_nav_buttons()

    def restore_snapshot(self, snap):
        self.tree.delete(*self.tree.get_children())
        self.url_by_iid.clear()
        self.item_by_iid.clear()
        self.results.clear()
        self.results.update(snap["results"])
        self.current_card = snap["card"]
        self.search_time = snap["time"]
        self.card_var.set(snap["card"])
        self.exact_var.set(snap["exact"])
        self.exact_names, self.exact_ok = snap["names"], snap["ok"]
        self.open_state = dict(snap["open_state"])
        self.expanded = set(snap["expanded"])
        self.all_collapsed = snap["all_collapsed"]
        self.auto_note = snap["note"]
        self.collapse_btn.config(text="▼ Expandir listas" if self.all_collapsed else "▲ Recolher listas")
        for iid in snap["order"]:
            res = self.results.get(iid)
            self.tree.insert("", "end", iid=iid, text=res.store["name"] if res else iid, values=("", ""), open=True)
            if res:
                self.render_store(iid)
        self.progress.grid_remove()
        self.update_summary()
        self.on_select()
        self.entry.focus_set()

    # ---- busca ----------------------------------------------------------------
    def start_search(self, skip_history=False):
        card = clean_card_name(self.card_var.get())
        stores = self.selected_stores()
        if not card:
            messagebox.showinfo("Falta o nome", "Digite o nome da carta.")
            return
        if not stores:
            messagebox.showinfo("Nenhuma loja", "Marque ao menos uma loja.")
            return
        if not HAS_SCRAPING:
            if messagebox.askyesno(
                "Bibliotecas ausentes",
                "Para ler os resultados é preciso instalar:\n\n  pip install requests beautifulsoup4\n\n"
                "Quer abrir as abas no navegador por enquanto?",
            ):
                self.open_selected_tabs()
            return

        if not skip_history:
            self.push_history(card)  # guarda a busca que está na tela, para o Voltar
        if self.ctl:
            self.ctl.stop.set()  # a busca anterior não precisa mais carregar detalhes
        self.search_id += 1
        sid = self.search_id
        self.current_card = card
        self.search_time = time.time()
        self.results.clear()
        self.url_by_iid.clear()
        self.item_by_iid.clear()
        self.expanded.clear()
        self.exact_names = None
        self.exact_ok = True
        self.auto_note = ""
        self.auto_active = 0
        self.auto_total = self.auto_done = 0
        self.auto_loading = set()
        self.open_state = {}
        self.all_collapsed = False
        self.collapse_btn.config(text="▲ Recolher listas")
        self.stores_total = len(stores)
        self.stores_done = 0
        self.progress.grid()  # volta a mostrar a barra
        self.close_details()
        self.tree.delete(*self.tree.get_children())
        self.on_select()  # a seleção foi apagada junto com a lista
        self.open_found_btn.config(state="disabled")

        for s in stores:
            self.tree.insert("", "end", iid=s["url"], text=s["name"], values=("⏳ buscando...", ""), open=True)
            self.url_by_iid[s["url"]] = build_search_url(s["url"], card)

        self.pending = len(stores)
        self.progress.config(maximum=len(stores), value=0)
        self.status_var.set(f"Buscando “{card}” em {len(stores)} loja(s)...")

        limit = self.auto_limit()
        exact = self.exact_var.get()
        self.ctl = ctl = AutoCtl(AUTO_TOTAL_CAP)
        names_box = {"names": None}
        names_ready = threading.Event()

        def post(kind, payload):
            self.queue.put((kind, sid, payload))

        def names_job():
            names, ok = resolve_names(card)
            names_box["names"] = names
            post("names", (names, ok))
            names_ready.set()

        def store_job(store):
            res = safe_search(store, card)
            post("result", res)
            if limit > 0 and res.status == "found":
                try:
                    auto_details(res, limit, ctl, exact, names_box, names_ready, post)
                except Exception:  # noqa: BLE001 - detalhes são um extra; nunca derrubam a busca
                    pass

        def worker():
            with ThreadPoolExecutor(max_workers=max(6, len(stores))) as ex:
                for s in stores:
                    ex.submit(store_job, s)

        if exact:
            self.names_requested = sid
            threading.Thread(target=names_job, daemon=True).start()
        else:
            names_ready.set()
        threading.Thread(target=worker, daemon=True).start()

    def fetch_names(self, card, sid):
        if self.names_requested == sid:
            return
        self.names_requested = sid

        def w():
            names, ok = resolve_names(card)
            self.queue.put(("names", sid, (names, ok)))

        threading.Thread(target=w, daemon=True).start()

    def poll(self):
        try:
            while True:
                kind, sid, payload = self.queue.get_nowait()
                if kind == "details":
                    self.fill_details(sid, payload)
                    continue
                if sid != self.search_id:
                    continue
                if kind == "names":
                    self.exact_names, self.exact_ok = payload
                    self.refresh_all()
                    continue
                if kind == "offers":
                    self.apply_offers(*payload)
                    continue
                if kind in ("autostart", "autostep", "autoend", "autostop"):
                    self.on_auto_event(kind, payload)
                    continue
                self.show_result(payload)
                self.pending -= 1
                self.stores_done += 1
                self.refresh_progress()
                if self.pending == 0:
                    self.finish_search()
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def on_exact_toggle(self):
        if self.exact_var.get() and self.exact_names is None and self.current_card and self.results:
            self.fetch_names(self.current_card, self.search_id)
        self.refresh_all()

    def refresh_all(self):
        for iid in list(self.results):
            self.render_store(iid)
        if self.pending == 0 and self.results:
            self.update_summary()

    def visible_items(self, res):
        if self.exact_var.get() and self.exact_names:
            return [i for i in res.items if matches_exact(i.name, self.exact_names)]
        return res.items

    def show_result(self, res):
        self.results[res.store["url"]] = res
        self.render_store(res.store["url"])

    def _is_open(self, iid):
        try:
            return str(self.tree.item(iid, "open")).lower() in ("1", "true", "yes")
        except tk.TclError:
            return True

    def render_store(self, iid, expanded=None):
        res = self.results.get(iid)
        if not res:
            return
        if expanded is not None:
            (self.expanded.add if expanded else self.expanded.discard)(iid)
        expanded = iid in self.expanded

        selected = self.tree.selection()
        for child in self.tree.get_children(iid):
            self.open_state[child] = self._is_open(child)  # lembra o que a pessoa abriu/fechou
            for grand in self.tree.get_children(child):
                self.url_by_iid.pop(grand, None)
                self.item_by_iid.pop(grand, None)
            self.url_by_iid.pop(child, None)
            self.item_by_iid.pop(child, None)
            self.tree.delete(child)

        items = self.visible_items(res)
        status = res.status
        text = STATUS_TEXT[status]
        if status == "found":
            if items:
                text += f" ({len(items)} resultado{'s' if len(items) != 1 else ''})"
            else:
                status = "none"
                text = f"❌ Nenhum com o nome exato ({len(res.items)} parecidos escondidos)"
        elif status == "error" and res.msg:
            text += f" [{res.msg[:70]}]"
        self.tree.item(iid, values=(text, ""), tags=(status,))
        self.url_by_iid[iid] = res.search_url

        zebra = [0]

        def tags(*extra):
            zebra[0] += 1
            return tuple(extra) + (("alt",) if zebra[0] % 2 == 0 else ())

        # aviso único por loja: itens sem detalhes não são um erro, são "sob demanda"
        if any(it.offers is None and it.url not in self.auto_loading for it in items):
            self.tree.insert(iid, "end", iid=f"{iid}|hint", text="    ℹ Selecione e clique em 🔎 para ver edições e preços",
                             values=("", ""), tags=("hint",))

        big = len(items) > MAX_ITEMS_PER_STORE
        show_all = expanded and big
        limit = len(items) if (show_all or not big) else MAX_ITEMS_PER_STORE
        if show_all:
            self.tree.insert(iid, "end", iid=f"{iid}|less_top", text="    ▲ mostrar menos (recolher esta lista)",
                             values=("", ""), tags=("more",))
        for n, it in enumerate(items[:limit]):
            child = f"{iid}|{n}"
            if it.offers:
                best = min((o.price for o in it.offers if o.price is not None), default=None)
                self.tree.insert(iid, "end", iid=child, text="    " + it.name, open=self.open_state.get(child, not self.all_collapsed),
                                 values=(f"{len(it.offers)} oferta{'s' if len(it.offers) != 1 else ''} em estoque",
                                         ("a partir de " + money(best)) if best is not None else ""),
                                 tags=tags())
                for k, o in enumerate(it.offers):
                    oid = f"{child}#{k}"
                    self.tree.insert(child, "end", iid=oid,
                                     text="        " + o.edition + ("  (pré-venda)" if o.preorder else ""),
                                     values=(offer_desc(o), money(o.price)), tags=tags())
                    self.url_by_iid[oid] = it.url
                    self.item_by_iid[oid] = it
            else:
                label = "⏳ carregando edições e preços…" if it.url in self.auto_loading else "em estoque    ·    detalhes sob demanda 🔎"
                self.tree.insert(iid, "end", iid=child, text="    " + it.name, values=(label, "—"),
                                 tags=tags())
            self.url_by_iid[child] = it.url
            self.item_by_iid[child] = it
        if big and not show_all:
            self.tree.insert(iid, "end", iid=f"{iid}|more",
                             text=f"    ▼ mostrar mais {len(items) - MAX_ITEMS_PER_STORE} (duplo clique aqui)",
                             values=("", ""), tags=("more",))
        if show_all:
            self.tree.insert(iid, "end", iid=f"{iid}|less_end", text="    ▲ mostrar menos (recolher esta lista)",
                             values=("", ""), tags=("more",))

        for old in selected:  # mantém a seleção se a linha ainda existe
            if self.tree.exists(old):
                self.tree.selection_set(old)
                break
        self.on_select()  # a linha selecionada pode ter sido recriada ou removida

    def item_for(self, store_url, url):
        res = self.results.get(store_url)
        return next((i for i in res.items if i.url == url), None) if res else None

    def on_auto_event(self, kind, payload):
        if kind == "autostart":
            store_url, urls = payload
            self.auto_active += 1
            self.auto_total += len(urls)
            self.auto_loading.update(urls)
            self.render_store(store_url)
        elif kind == "autostep":
            store_url, url = payload
            self.auto_done += 1
            self.auto_loading.discard(url)
            it = self.item_for(store_url, url)
            if it is not None and it.offers is None:  # não conseguiu: volta ao aviso "sob demanda"
                self.render_store(store_url)
        elif kind == "autoend":
            store_url, rest = payload
            self.auto_active = max(0, self.auto_active - 1)
            self.auto_done += len(rest)
            self.auto_loading.difference_update(rest)
            if rest:
                self.render_store(store_url)
        else:  # autostop
            self.auto_note = (f"⚠ Detalhes automáticos pausados ({payload} limitou as requisições): "
                              "use “🔎 Ver edições e preços” nos itens.")
        self.refresh_progress()
        if self.pending == 0 and self.results:
            self.update_summary()

    def refresh_progress(self):
        """Barra = lojas consultadas + páginas de detalhes (estas entram na conta quando são planejadas)."""
        total = max(1, self.stores_total + self.auto_total)
        done = self.stores_done + self.auto_done
        self.progress.config(maximum=total, value=min(done, total))
        if self.pending == 0 and self.auto_active == 0:
            self.root.after(700, self.hide_progress_if_idle)  # some quando tudo terminou
        else:
            self.progress.grid()  # ainda há trabalho: garante que a barra está visível

    def hide_progress_if_idle(self):
        if self.pending == 0 and self.auto_active == 0:
            self.progress.grid_remove()

    def apply_offers(self, store_url, item_url, offers):
        res = self.results.get(store_url)
        if not res:
            return
        for it in res.items:
            if it.url == item_url:
                it.offers = offers
        self.render_store(store_url)

    def has_card(self, res):
        return res.status == "found" and bool(self.visible_items(res))

    def open_found_tabs(self):
        urls = [r.search_url for r in self.results.values()
                if self.has_card(r) or r.status in ("blocked", "unknown", "error")]
        if urls:
            self.open_urls(urls)

    def update_summary(self):
        total = len(self.results)
        ok = sum(1 for r in self.results.values() if self.has_card(r))
        check = sum(1 for r in self.results.values() if r.status in ("blocked", "unknown", "error"))
        msg = f"“{self.current_card}”: encontrada em {ok} de {total} loja(s)"
        msg += " (nome exato)." if self.exact_var.get() and self.exact_names else "."
        if self.auto_active > 0:
            msg += f" ⏳ Carregando edições e preços ({self.auto_done}/{self.auto_total})…"
        elif any(it.offers is None for r in self.results.values() if self.has_card(r)
                 for it in self.visible_items(r)):
            msg += " ℹ Onde há muitos resultados, edições e preços não carregam sozinhos: selecione um item e clique em “🔎 Ver edições e preços” (ou Enter)."
        if self.auto_note:
            msg += " " + self.auto_note
        if self.exact_var.get() and not self.exact_ok:
            msg += " Scryfall indisponível: filtrando só pelo texto digitado."
        if check:
            msg += f" {check} loja(s) não puderam ser lidas — confira no navegador (duplo clique)."
        age = time.time() - self.search_time
        if age >= 120:
            msg += f" 🕒 Resultados {age_text(age)}."
        if ok:
            msg += " Duplo clique abre a página na loja. Lista do menor para o maior preço."
        self.status_var.set(msg)
        self.open_found_btn.config(state="normal" if (ok or check) else "disabled")

    def finish_search(self):
        self.update_summary()
        self.refresh_progress()


def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista" if sys.platform == "win32" else "clam")
    except tk.TclError:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
