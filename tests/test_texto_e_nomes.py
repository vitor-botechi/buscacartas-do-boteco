"""Funções de texto, comparação de nome exato e normalização do link das lojas (sem rede)."""

import json

import pytest

from buscador import armazenamento
from buscador.scryfall import add_names, matches_exact
from buscador.texto import clean_card_name, norm, strip_suffix


def test_clean_card_name_tira_espacos_e_caracteres_invisiveis():
    assert clean_card_name("  Jace,​   o  Escultor ") == "Jace, o Escultor"


def test_norm_tira_acentos_e_padroniza_apostrofos():
    assert norm("Árbitro Leonino") == "arbitro leonino"
    assert norm("God-Pharaoh’s Gift") == "god-pharaoh's gift"


@pytest.mark.parametrize("nome, base", [("Sol Ring (Human)", "Sol Ring"), ("Ilha (#266) (Foil)", "Ilha"),
                                        ("Island", "Island")])
def test_strip_suffix(nome, base):
    assert strip_suffix(nome) == base


# ---- nome exato ----

def nomes(*textos):
    conjunto = set()
    for t in textos:
        add_names(conjunto, t)
    return conjunto


def test_nome_exato_aceita_portugues_ou_ingles():
    aceitos = nomes("Unholy Grotto", "Gruta Profana")
    assert matches_exact("Gruta Profana / Unholy Grotto", aceitos)
    assert matches_exact("Gruta Profana (Foil)", aceitos)


def test_nome_exato_recusa_carta_parecida():
    assert not matches_exact("Thalia, the Survivor", nomes("Thalia, Guardian of Thraben"))


def test_nome_exato_aceita_cada_face_de_carta_dupla():
    aceitos = nomes("Never // Return")
    assert "never" in aceitos and "return" in aceitos
    assert matches_exact("Jamais // Retornar / Never // Return", aceitos)


# ---- lojas ----

@pytest.mark.parametrize("digitado, base", [
    ("overrun.com.br", "https://overrun.com.br"),
    ("https://www.overrun.com.br/?view=ecom/itens&busca=x", "https://www.overrun.com.br"),
])
def test_normalize_base(digitado, base):
    assert armazenamento.normalize_base(digitado) == base


def test_normalize_base_recusa_link_invalido():
    with pytest.raises(ValueError):
        armazenamento.normalize_base("loja")


def test_nome_padrao_da_loja():
    assert armazenamento.default_name("https://www.jackpotjogos.com.br") == "Jackpotjogos"


def test_lojas_salvas_mantem_as_padrao_e_acrescentam_as_novas(monkeypatch, tmp_path):
    arquivo = tmp_path / "lojas.json"
    arquivo.write_text(json.dumps({"stores": [
        {"name": "Overrun", "url": "https://www.overrun.com.br", "enabled": False},
        {"name": "Nova", "url": "https://www.novaloja.com.br", "enabled": True},
    ]}), encoding="utf-8")
    monkeypatch.setattr(armazenamento, "CONFIG_FILE", str(arquivo))
    lojas = {s["name"]: s for s in armazenamento.load_stores()}
    assert not lojas["Overrun"]["enabled"]
    assert lojas["Nova"]["builtin"] is False
    assert len(lojas) == len(armazenamento.DEFAULT_STORES) + 1


def test_sem_arquivo_de_lojas_usa_as_padrao(monkeypatch, tmp_path):
    monkeypatch.setattr(armazenamento, "CONFIG_FILE", str(tmp_path / "nao_existe.json"))
    lojas = armazenamento.load_stores()
    assert [s["name"] for s in lojas] == [s["name"] for s in armazenamento.DEFAULT_STORES]
    assert all(s["enabled"] for s in lojas)




def test_reconhece_art_card():
    from buscador.texto import is_art_card
    assert is_art_card("Thalia, Guardiã de Thraben (Art Card)")
    assert is_art_card("Sol Ring - Art Series")
    assert not is_art_card("Thalia, Guardiã de Thraben")
    assert not is_art_card("Heart Card")  # só a expressão inteira
