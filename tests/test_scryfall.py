"""Descoberta dos nomes aceitos em "Apenas nome exato", com as respostas do Scryfall simuladas."""

import pytest

from buscador import scryfall


class RespostaFalsa:
    def __init__(self, status_code, dados):
        self.status_code, self._dados = status_code, dados

    def json(self):
        return self._dados


AMBIGUO = RespostaFalsa(404, {"code": "not_found", "details": "Too many cards match ambiguous name"})


def carta(nome_en, nome_pt):
    return {"name": nome_en, "printed_name": nome_pt}


# o que a busca de "Thalia" em português devolve: todas as cartas que CONTÊM a palavra
THALIAS_PT = [
    carta("Thalia and The Gitrog Monster", "Thalia e O Monstro Gitrog"),
    carta("Thalia's Lieutenant", "Tenente de Thalia"),
    carta("Thalia, Guardian of Thraben", "Thalia, Guardiã de Thraben"),
]


@pytest.fixture
def scryfall_falso(monkeypatch):
    """Responde às chamadas do programa conforme o dicionário: (caminho, q ou fuzzy) -> resposta."""
    respostas = {}

    def get_falso(path, params):
        chave = (path, params.get("fuzzy") or params.get("q"))
        return respostas.get(chave, RespostaFalsa(404, {}))

    monkeypatch.setattr(scryfall, "scry_get", get_falso)
    return respostas


def test_nome_ambiguo_nao_escolhe_uma_carta_ao_acaso(scryfall_falso):
    scryfall_falso[("/cards/named", "Thalia")] = AMBIGUO
    scryfall_falso[("/cards/search", '"Thalia" lang:pt')] = RespostaFalsa(200, {"data": THALIAS_PT})
    nomes, respondeu = scryfall.resolve_names("Thalia")
    assert respondeu
    assert nomes == {"thalia"}  # só o que foi digitado
    assert not scryfall.matches_exact("Thalia e O Monstro Gitrog", nomes)
    assert not scryfall.matches_exact("Tenente de Thalia", nomes)


def test_nome_completo_em_portugues_encontra_o_ingles(scryfall_falso):
    scryfall_falso[("/cards/search", '"Tenente de Thalia" lang:pt')] = RespostaFalsa(200, {"data": THALIAS_PT})
    scryfall_falso[("/cards/search", '!"Thalia\'s Lieutenant" lang:pt')] = RespostaFalsa(
        200, {"data": [carta("Thalia's Lieutenant", "Tenente de Thalia")]})
    nomes, _ = scryfall.resolve_names("Tenente de Thalia")
    assert nomes == {"tenente de thalia", "thalia's lieutenant"}
    assert scryfall.matches_exact("Tenente de Thalia / Thalia's Lieutenant", nomes)
    assert not scryfall.matches_exact("Thalia e O Monstro Gitrog", nomes)


def test_nome_em_ingles_usa_a_busca_aproximada(scryfall_falso):
    scryfall_falso[("/cards/named", "unholy groto")] = RespostaFalsa(200, {"name": "Unholy Grotto"})
    scryfall_falso[("/cards/search", '!"Unholy Grotto" lang:pt')] = RespostaFalsa(
        200, {"data": [carta("Unholy Grotto", "Gruta Profana")]})
    nomes, _ = scryfall.resolve_names("unholy groto")
    assert {"unholy grotto", "gruta profana"} <= nomes


def test_face_de_carta_dupla_em_portugues():
    cartas = [{"name": "Never // Return", "card_faces": [{"printed_name": "Jamais"}, {"printed_name": "Retornar"}]}]
    assert scryfall.english_for_portuguese("Jamais", cartas) == "Never // Return"


def test_mesmo_nome_em_portugues_para_cartas_diferentes_nao_escolhe():
    cartas = [carta("Card A", "Nome Igual"), carta("Card B", "Nome Igual")]
    assert scryfall.english_for_portuguese("Nome Igual", cartas) is None


def test_varias_impressoes_da_mesma_carta_contam_como_uma():
    cartas = [carta("Unholy Grotto", "Gruta Profana"), carta("Unholy Grotto", "Gruta Profana")]
    assert scryfall.english_for_portuguese("gruta profana", cartas) == "Unholy Grotto"


def test_sem_resposta_do_scryfall_usa_so_o_digitado(monkeypatch):
    def sem_conexao(*_a, **_k):
        raise scryfall.requests.ConnectionError("sem internet")

    monkeypatch.setattr(scryfall, "scry_get", sem_conexao)
    assert scryfall.resolve_names("Thalia") == ({"thalia"}, False)
