"""Funções de texto: normalização de nomes, formatação de dinheiro e de tempo."""

import re
import unicodedata


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


def preorder_text(date):
    """'pré-venda, envio 13/11/2026' (ou só 'pré-venda' quando a loja não deu a data)."""
    return f"pré-venda, envio {date}" if date else "pré-venda"


def offer_desc(o):
    """Resumo de uma oferta: 'Português · NM · 2 un. · Foil · -10% · pré-venda, envio 13/11/2026'."""
    parts = [o.language or "—", o.quality or "—", f"{o.stock} un."]
    if o.extras:
        parts.append(o.extras)
    if o.original_price and o.price:
        parts.append(f"-{round((1 - o.price / o.original_price) * 100)}%")
    if o.preorder:
        parts.append(preorder_text(o.preorder_date))
    if o.note:
        parts.append("contém observação")
    return "    ·    ".join(parts)


def strip_suffix(name):
    """'Sol Ring (Human)' -> 'Sol Ring'; 'Ilha (#266)' -> 'Ilha'."""
    prev = None
    while prev != name:
        prev = name
        name = re.sub(r"\s*\([^)]*\)\s*$", "", name)
    return name.strip()
