"""Funções de texto: normalização e limpeza de nomes de cartas."""

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


def strip_suffix(name):
    """'Sol Ring (Human)' -> 'Sol Ring'; 'Ilha (#266)' -> 'Ilha'."""
    prev = None
    while prev != name:
        prev = name
        name = re.sub(r"\s*\([^)]*\)\s*$", "", name)
    return name.strip()
