"""Converte os resultados da busca em dicionários simples (JSON) para a página."""

from buscador.lojas.ligamagic import liga_card_url
from buscador.scryfall import matches_exact


def oferta(o):
    promo = 0
    if o.original_price and o.price:
        promo = round((1 - o.price / o.original_price) * 100)
    return {
        "edicao": o.edition, "idioma": o.language, "qualidade": o.quality, "extras": o.extras,
        "estoque": o.stock, "preco": o.price, "preco_original": o.original_price, "promo": promo,
        "pre": o.preorder, "pre_data": o.preorder_date, "obs": o.note, "bandeira": o.language_flag,
        "edicao_cod": o.edition_code, "imagem": o.image,
        "fotos": len(o.photos),  # só quantas: a tela avisa que há fotos, sem mostrá-las
    }


def ofertas(lista):
    return None if lista is None else [oferta(o) for o in lista]


def item(it, nomes=None):
    """nomes: nomes aceitos pelo "Apenas nome exato" (None = ainda não se sabe)."""
    return {
        "nome": it.name, "url": it.url, "liga": liga_card_url(it.name),
        "ofertas": ofertas(it.offers),
        "exato": None if nomes is None else matches_exact(it.name, nomes),
    }


def resultado(res, nomes=None):
    return {
        "loja": {**aparencia(res.store), "nome": res.store["name"], "url": res.store["url"]},
        "url_busca": res.search_url, "status": res.status, "msg": res.msg,
        "itens": [item(i, nomes) for i in res.items],
    }


def aparencia(s):
    """Cores e logo da loja, para o cartão de resultados."""
    return {"cor": s.get("color") or "", "cor2": s.get("color2") or "", "logo": s.get("logo") or "",
            "padrao": bool(s.get("builtin"))}


def loja(s):
    return {"nome": s["name"], "url": s["url"], "padrao": s["builtin"], "marcada": s["enabled"], **aparencia(s)}
