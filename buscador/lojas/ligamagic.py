"""Leitura das páginas das lojas no padrão LigaMagic (só HTML, sem fazer requisições)."""

import colorsys
import re
from urllib.parse import quote, quote_plus, urljoin

try:
    from bs4 import BeautifulSoup
except ImportError:  # sem a biblioteca a busca interna fica desligada (ver rede.HAS_SCRAPING)
    BeautifulSoup = None

from buscador.config import SEARCH_PATH
from buscador.modelos import Item, Offer
from buscador.texto import is_art_card, norm, strip_suffix


def build_search_url(base, card, page=1):
    return base.rstrip("/") + SEARCH_PATH.format(query=quote_plus(card), page=page)


LIGA_CARD_URL = "https://www.ligamagic.com.br/?view=cards/card&card={}"


def liga_card_url(item_name):
    """Página da carta no site da LigaMagic, para comparar preços no navegador da pessoa (botão "LigaMagic ↗").

    O programa nunca lê essa página: ela tem verificação contra robôs (ver docs/ROTEIRO.md).
    'Anel Solar / Sol Ring' usa o nome em inglês; 'Ilha (#266)' vira 'Ilha'. Art Card fica sem link.
    """
    if not item_name or is_art_card(item_name):
        return ""
    nome = strip_suffix(item_name.split(" / ")[-1])
    return LIGA_CARD_URL.format(quote(nome)) if nome else ""


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


DATE_RE = re.compile(r"\d{1,2}/\d{1,2}/\d{2,4}")


def preorder_info(box):
    """Procura o "P" verde de pré-venda dentro de box. Devolve (é_pré_venda, data_prevista).
    A loja põe a data no title do "P" ou da célula em volta:
    "Data de previsão de envio do item: 13/11/2026"."""
    icon = box.select_one(".icone-pre-order") if box is not None else None
    if icon is None:
        return False, ""
    for tag in (icon, icon.parent):
        m = DATE_RE.search((tag.get("title") or "") if tag is not None else "")
        if m:
            return True, m.group(0)
    return True, ""


def is_product_href(href):
    return "view=ecom/item" in href and "ecom/itens" not in href


def parse_results(html, base_url):
    """Lê a página de busca e devolve (itens, texto_normalizado_da_página)."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    # O resumo do carrinho aparece em toda página e diz "Nenhum item em seu carrinho". Se ficasse,
    # "nenhum item" (NONE_PHRASES) seria achado em qualquer página, e uma página que não conseguimos
    # ler passaria por "não encontrada". A frase real de busca vazia ("Nenhum item encontrado com os
    # filtros utilizados") fica fora do carrinho e continua valendo.
    for tag in soup.select(".carrinho"):
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

        entry = products.setdefault(href, {"name": "", "prices": [], "sold": False, "pre": (False, "")})
        if len(name) > len(entry["name"]):
            entry["name"] = name
        if not entry["prices"]:
            entry["prices"] = [float(p.replace(".", "").replace(",", ".")) for p in PRICE_RE.findall(box_text)]
        if any(m in norm(box_text) for m in SOLDOUT_MARKERS):
            entry["sold"] = True
        if not entry["pre"][0]:
            entry["pre"] = preorder_info(a.find_parent(class_="card-item") or box)

    items = [
        Item(
            name=e["name"] or "Produto",
            price=min(e["prices"]) if e["prices"] else None,
            url=urljoin(base_url.rstrip("/") + "/", href),
            available=not e["sold"],
            preorder=e["pre"][0],
            preorder_date=e["pre"][1],
        )
        for href, e in products.items()
    ]
    # a loja já manda do mais barato para o mais caro; os Art Cards vão para o fim, sem mudar o resto
    items.sort(key=lambda i: is_art_card(i.name))
    return items, page_text


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


COLOR_RE = re.compile(r"--color-primary\s*:\s*(#[0-9a-fA-F]{6})\b")


LOGO_RE = re.compile(r"""src=["']((?:https?:)?//[^"']+/ecom/logo/[^"']+\.(?:jpe?g|png|gif|webp|svg))["']""", re.I)


def web_image(src):
    """Endereço completo (https) de uma imagem da loja, ou "" se não for uma imagem da web."""
    src = (src or "").strip()
    if src.startswith("//"):
        src = "https:" + src
    return src if re.match(r"https://[^\s\"'<>]+$", src) else ""


def theme_logo(html):
    """Logo da loja na página inicial (padrão LigaMagic: imagem em .../ecom/logo/...)."""
    m = LOGO_RE.search(html or "")
    return web_image(m.group(1)) if m else ""


def theme_color(html):
    """Cor principal do site da loja (variável --color-primary do padrão LigaMagic).

    Devolve None se não houver ou se for cinza, quase branca ou quase preta (não serve de destaque).
    """
    m = COLOR_RE.search(html or "")
    if not m:
        return None
    cor = m.group(1).lower()
    r, g, b = (int(cor[i:i + 2], 16) / 255 for i in (1, 3, 5))
    _, luz, sat = colorsys.rgb_to_hls(r, g, b)
    if sat < 0.25 or luz > 0.85 or luz < 0.08:
        return None
    return cor


# ícone da edição: ".../arquivos/up/ed_mtg/AFC_U.gif" (código da edição e raridade)
EDITION_CODE_RE = re.compile(r"/ed_mtg/([A-Za-z0-9]+)_[A-Za-z]+\.\w+")


# cada linha de oferta chama itemMouseOver(N) ao passar o mouse, e o site mostra a imagem de #stickyN
# (a carta naquela edição) e, se a loja colocou fotos do próprio item, as de #stickyN_2, #stickyN_3...
ITEM_MOUSE_RE = re.compile(r"itemMouseOver\((\d+)\)")


def offer_images(soup, row):
    """(imagem da edição, [fotos da loja]) de uma linha de oferta; ("", []) se a página não tiver."""
    m = ITEM_MOUSE_RE.search(row.get("onmouseover") or "")
    if not m:
        return "", []
    n = m.group(1)
    img = soup.find(id=f"sticky{n}")
    image = web_image(img.img.get("src")) if img and img.img else ""
    photos = []
    for div in soup.find_all(id=re.compile(rf"^sticky{n}_\d+$")):
        foto = web_image(div.img.get("src")) if div.img else ""
        if foto and foto not in photos:
            photos.append(foto)
    return image, photos


def offer_note(icon):
    """Texto da observação que a loja colocou numa oferta (atributo observacao do ícone)."""
    texto = (icon.get("observacao") or "").replace("{{br}}", "\n")
    linhas = [" ".join(linha.split()) for linha in texto.splitlines()]
    return "\n".join(linha for linha in linhas if linha)


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
        image, photos = offer_images(soup, row)
        cells = row.find_all("div", class_="table-cards-body-cell", recursive=False)
        price_cell = row.select_one(".card-preco")
        if len(cells) < 4 or price_cell is None:
            continue
        idx = cells.index(price_cell)
        stock_cell = cells[idx - 1]

        # o ícone da edição (antes dele pode vir uma foto do item que a loja colocou)
        img = cells[0].select_one("img.icon-edicao") or cells[0].select_one("img")
        edition = (img.get("title") or img.get("alt") or "") if img else ""
        m_cod = EDITION_CODE_RE.search((img.get("src") or "") if img else "")
        edition_code = m_cod.group(1).lower() if m_cod else ""
        tip = cells[0].select_one(".tooltip")
        if tip and tip.get_text(strip=True):
            edition = tip.get_text(strip=True)
        lang_img = cells[1].select_one("img")
        language = (lang_img.get("title") or lang_img.get("alt") or "") if lang_img else ""
        flag = web_image(lang_img.get("src")) if lang_img else ""

        q_cell = row.select_one(".quality")
        quality = ""
        if q_cell:
            for t in q_cell.select(".tooltip"):
                t.decompose()
            quality = q_cell.get_text(" ", strip=True)
        e_cell = row.select_one(".card-extras")
        note = ""
        if e_cell:
            # a observação da loja vem num ícone, com o texto "Visualizar observação" escondido ao lado
            for icon in e_cell.select(".icon-observacao"):
                note = note or offer_note(icon) or "A loja colocou uma observação nesta oferta."
                icon.decompose()
            for t in e_cell.select(".tooltip"):
                t.decompose()
        extras = e_cell.get_text(" ", strip=True) if e_cell else ""
        extras = "" if extras in ("-", "–") else extras

        preorder, preorder_date = preorder_info(stock_cell)
        m = re.search(r"(\d+)\s*unid", stock_cell.get_text(" ", strip=True))
        stock = int(m.group(1)) if m else None
        prices = [float(x.replace(".", "").replace(",", "."))
                  for x in PRICE_RE.findall(price_cell.get_text(" ", strip=True))]
        # em promoção a loja mostra o preço riscado e, depois, o preço novo
        price = prices[-1] if prices else None
        original = prices[0] if len(prices) >= 2 and prices[0] > prices[-1] else None

        offers.append(Offer(edition, language, quality, extras, stock, price, preorder, original, preorder_date, note, flag,
                            edition_code, image, photos))

    if not offers or all(o.stock is None and o.price is None for o in offers):
        return [], "unreadable"  # existem linhas, mas os números não vieram como texto
    offers = [o for o in offers if o.stock]  # a página também lista edições sem estoque
    if not offers:
        return [], "empty"
    offers.sort(key=lambda o: (o.price is None, o.price if o.price is not None else 0))
    return offers, "ok"
