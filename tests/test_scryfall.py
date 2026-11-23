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


@pytest.fixture(autouse=True)
def sem_memoria(monkeypatch):
    """Cada teste começa sem nomes guardados e sem pausa do Scryfall."""
    monkeypatch.setattr(scryfall, "_nomes", {})
    monkeypatch.setattr(scryfall, "RITMO", scryfall._Ritmo())


@pytest.fixture
def scryfall_falso(monkeypatch):
    """Responde às chamadas do programa conforme o dicionário: (caminho, q ou fuzzy) -> resposta."""
    respostas = {}

    def get_falso(path, params, urgente=True):
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


def test_nomes_ficam_guardados(scryfall_falso):
    scryfall_falso[("/cards/named", "Sol Ring")] = RespostaFalsa(200, {"name": "Sol Ring"})
    chamadas = []
    original = scryfall.scry_get
    scryfall.scry_get = lambda *a, **k: chamadas.append(a) or original(*a, **k)
    try:
        primeira = scryfall.resolve_names("Sol Ring")
        n = len(chamadas)
        assert scryfall.resolve_names("sol ring") == primeira and len(chamadas) == n  # sem nova consulta
    finally:
        scryfall.scry_get = original


class RequestsFalso:
    """Conta as requisições de verdade ao Scryfall (sem rede)."""

    def __init__(self, status=200):
        self.status, self.feitas = status, []

    def get(self, url, **_k):
        self.feitas.append(url)
        return RespostaFalsa(self.status, {})


def test_ritmo_de_duas_consultas_por_segundo(monkeypatch):
    falso = RequestsFalso()
    monkeypatch.setattr(scryfall.requests, "get", falso.get)
    monkeypatch.setattr(scryfall, "SCRY_INTERVALO_CARTAS", 0.2)
    inicio = scryfall.time.monotonic()
    for _ in range(3):
        scryfall.scry_get("/cards/named", {"fuzzy": "x"})
    assert scryfall.time.monotonic() - inicio >= 0.4  # 3 consultas: 2 intervalos


def test_depois_de_um_429_nao_consulta_mais(monkeypatch):
    falso = RequestsFalso(429)
    monkeypatch.setattr(scryfall.requests, "get", falso.get)
    assert scryfall.scry_get("/cards/named", {"fuzzy": "x"}).status_code == 429
    with pytest.raises(scryfall.ScryfallEmPausa):
        scryfall.scry_get("/cards/named", {"fuzzy": "y"})
    assert len(falso.feitas) == 1  # a segunda nem saiu
    assert scryfall.resolve_names("Sol Ring") == ({"sol ring"}, False)  # tratado como sem resposta
    assert scryfall.card_art("Sol Ring") == ""


# ---- memória em disco (scryfall.json) ----

class Relogio:
    def __init__(self):
        self.t = 1_000_000.0

    def __call__(self):
        return self.t


def test_memoria_guarda_le_e_vence(tmp_path):
    relogio = Relogio()
    caminho = str(tmp_path / "s.json")
    m = scryfall.MemoriaEmDisco(caminho, agora=relogio)
    m.guardar("nomes", "sol ring", ["anel solar", "sol ring"], 30)
    m.gravar()
    outra = scryfall.MemoriaEmDisco(caminho, agora=relogio)  # como se o programa abrisse de novo
    assert outra.pegar("nomes", "sol ring") == ["anel solar", "sol ring"]
    relogio.t += 31 * 86400
    assert outra.pegar("nomes", "sol ring") is None


def test_memoria_com_arquivo_estragado_comeca_do_zero(tmp_path):
    caminho = tmp_path / "s.json"
    caminho.write_text("{ isto não é json", encoding="utf-8")
    m = scryfall.MemoriaEmDisco(str(caminho))
    assert m.pegar("nomes", "x") is None
    m.guardar("nomes", "x", ["x"], 1)
    m.gravar()
    assert scryfall.MemoriaEmDisco(str(caminho)).pegar("nomes", "x") == ["x"]


def test_memoria_tem_limite(tmp_path, monkeypatch):
    monkeypatch.setattr(scryfall, "SCRY_MAX_GUARDADOS", 3)
    relogio = Relogio()
    m = scryfall.MemoriaEmDisco(str(tmp_path / "s.json"), agora=relogio)
    for i in range(5):
        relogio.t += 1
        m.guardar("artes", f"c{i}", "u", 30)
    assert [m.pegar("artes", f"c{i}") for i in range(5)] == [None, None, "u", "u", "u"]  # saem as mais velhas


def test_nomes_vem_do_disco_depois_de_reabrir(scryfall_falso, scryfall_em_disco_de_teste, monkeypatch):
    scryfall_falso[("/cards/named", "Sol Ring")] = RespostaFalsa(200, {"name": "Sol Ring"})
    scryfall_falso[("/cards/search", '!"Sol Ring" lang:pt')] = RespostaFalsa(200, {"data": [carta("Sol Ring", "Anel Solar")]})
    nomes, _ = scryfall.resolve_names("Sol Ring")
    scryfall_em_disco_de_teste.gravar()
    # programa fechado e aberto de novo: memória vazia, Scryfall fora do ar
    monkeypatch.setattr(scryfall, "_nomes", {})
    monkeypatch.setattr(scryfall, "DISCO", scryfall.MemoriaEmDisco(scryfall_em_disco_de_teste.caminho()))

    def sem_conexao(*_a, **_k):
        raise AssertionError("não devia consultar o Scryfall")

    monkeypatch.setattr(scryfall, "scry_get", sem_conexao)
    assert scryfall.resolve_names("sol ring") == (nomes, True)


def test_carta_nao_reconhecida_fica_guardada_so_um_dia(scryfall_falso, scryfall_em_disco_de_teste):
    scryfall_falso[("/cards/named", "Sol Ring")] = RespostaFalsa(200, {"name": "Sol Ring"})
    scryfall.resolve_names("Sol Ring")
    scryfall.resolve_names("Carta Nova Que Ninguém Conhece")
    grupo = scryfall_em_disco_de_teste._dados["nomes"]
    dias = {k: round((v[0] - scryfall.time.time()) / 86400) for k, v in grupo.items()}
    assert dias == {"sol ring": scryfall.SCRY_DIAS, "carta nova que ninguem conhece": scryfall.SCRY_DIAS_SEM_RESPOSTA}


def test_falha_de_rede_nao_vai_para_o_disco(monkeypatch, scryfall_em_disco_de_teste):
    def sem_conexao(*_a, **_k):
        raise scryfall.requests.ConnectionError("sem internet")

    monkeypatch.setattr(scryfall, "scry_get", sem_conexao)
    scryfall.resolve_names("Thalia")
    assert scryfall_em_disco_de_teste.pegar("nomes", "thalia") is None
