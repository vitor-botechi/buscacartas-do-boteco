"""Arte da carta ao passar o mouse: nome usado no Scryfall, edição certa e cache (sem requisições)."""

import pytest

from buscador import scryfall


class Resposta:
    def __init__(self, status, dados=None):
        self.status_code = status
        self._dados = dados or {}

    def json(self):
        return self._dados


def carta(url):
    return {"image_uris": {"normal": url}}


@pytest.fixture
def scry(monkeypatch):
    """Scryfall simulado: guarda os pedidos e responde pelo dicionário `respostas`."""
    monkeypatch.setattr(scryfall, "_artes", {})
    monkeypatch.setattr(scryfall, "_edicoes", None)
    monkeypatch.setattr(scryfall, "_codigos", set())
    pedidos, respostas = [], {}

    def falso(caminho, params):
        pedidos.append((caminho, params))
        chave = (caminho, tuple(sorted(params.items())))
        return respostas.get(chave, respostas.get(caminho, Resposta(404)))

    monkeypatch.setattr(scryfall, "scry_get", falso)
    respostas["/sets"] = Resposta(200, {"data": [
        {"name": "Magic 2012", "code": "m12"}, {"name": "The Brothers' War Commander", "code": "brc"},
        {"name": "Commander Masters", "code": "cmm"}, {"name": "Secret Lair Drop", "code": "sld"}]})
    return pedidos, respostas


@pytest.mark.parametrize("nome, esperado", [
    ("Ilha / Island (#266)", "Island"),
    ("Sol Ring (Human)", "Sol Ring"),
    ("Fable of the Mirror-Breaker // Reflection of Kiki-Jiki", "Fable of the Mirror-Breaker // Reflection of Kiki-Jiki"),
    ("Elfos de Llanowar / Llanowar Elves", "Llanowar Elves"),
])
def test_nome_para_o_scryfall(nome, esperado):
    assert scryfall.card_query_name(nome) == esperado


def test_imagem_da_carta():
    assert scryfall.card_image(carta("https://cards.scryfall.io/a.jpg")) == "https://cards.scryfall.io/a.jpg"
    duas_faces = {"card_faces": [{"image_uris": {"normal": "https://cards.scryfall.io/frente.jpg"}}, {}]}
    assert scryfall.card_image(duas_faces) == "https://cards.scryfall.io/frente.jpg"
    assert scryfall.card_image({"image_uris": {"normal": "http://inseguro/a.jpg"}}) == ""
    assert scryfall.card_image({}) == ""


def test_arte_da_edicao_certa_e_guardada(scry):
    pedidos, respostas = scry
    respostas[("/cards/named", (("exact", "Llanowar Elves"), ("set", "m12")))] = Resposta(200, carta("https://cards.scryfall.io/m12.jpg"))
    assert scryfall.card_art("Elfos de Llanowar / Llanowar Elves", "Magic 2012") == "https://cards.scryfall.io/m12.jpg"
    feitos = len(pedidos)
    assert scryfall.card_art("Elfos de Llanowar / Llanowar Elves", "Magic 2012") == "https://cards.scryfall.io/m12.jpg"
    assert len(pedidos) == feitos  # segunda vez: sem consulta


def test_edicao_desconhecida_usa_a_carta(scry):
    pedidos, respostas = scry
    respostas[("/cards/named", (("fuzzy", "Sol Ring"),))] = Resposta(200, carta("https://cards.scryfall.io/sol.jpg"))
    assert scryfall.card_art("Sol Ring", "Edição que não existe") == "https://cards.scryfall.io/sol.jpg"


def test_nome_so_em_portugues(scry):
    pedidos, respostas = scry
    respostas[("/cards/search", (("include_multilingual", "true"), ("q", '"Elfos de Llanowar" lang:pt'), ("unique", "prints")))] = \
        Resposta(200, {"data": [{"name": "Llanowar Elves", "printed_name": "Elfos de Llanowar"}]})
    respostas[("/cards/named", (("fuzzy", "Llanowar Elves"),))] = Resposta(200, carta("https://cards.scryfall.io/elfos.jpg"))
    assert scryfall.card_art("Elfos de Llanowar", "") == "https://cards.scryfall.io/elfos.jpg"


def test_sem_arte_fica_guardado_mas_falha_de_rede_nao(scry, monkeypatch):
    pedidos, _ = scry
    assert scryfall.card_art("Booster de Coleção", "") == ""
    feitos = len(pedidos)
    assert scryfall.card_art("Booster de Coleção", "") == ""
    assert len(pedidos) == feitos

    def cai(caminho, params):
        raise scryfall.requests.ConnectionError("sem internet")

    monkeypatch.setattr(scryfall, "scry_get", cai)
    assert scryfall.card_art("Sol Ring", "") == ""
    assert ("sol ring", "", "") not in scryfall._artes  # tenta de novo na próxima vez


def test_edicoes_possiveis(scry):
    assert scryfall.set_codes("Magic 2012") == ["m12"]
    assert scryfall.set_codes("Commander Masters (Borderless Frame Break)", "bfcmm") == ["cmm"]
    assert scryfall.set_codes("A Guerra dos Irmãos Commander", "brc") == ["brc"]  # nome em português: vale o código
    assert scryfall.set_codes("Secret Lair Drop Series: Goblin Storm", "sld373") == ["sld"]
    assert scryfall.set_codes("Edição desconhecida", "xyz") == []
    assert scryfall.set_codes("", "") == []


def test_edicao_em_portugues_pelo_codigo_do_icone(scry):
    pedidos, respostas = scry
    respostas[("/cards/named", (("exact", "Sol Ring"), ("set", "brc")))] = Resposta(200, carta("https://cards.scryfall.io/brc.jpg"))
    assert scryfall.card_art("Anel Solar / Sol Ring", "A Guerra dos Irmãos Commander", "brc") == "https://cards.scryfall.io/brc.jpg"


def test_imagem_da_edicao_e_fotos_da_loja_na_pagina_do_produto():
    from buscador.lojas.ligamagic import parse_product_page
    html = open("tests/fixtures/produto_fotos_da_loja.html", encoding="utf-8").read()
    ofertas, status = parse_product_page(html)
    assert status == "ok" and len(ofertas) == 1
    o = ofertas[0]
    assert o.edition == "Contos da Terra Média Commander" and o.edition_code == "ltc"
    # a carta naquela edição (a imagem que o site mostra ao passar o mouse na linha)
    assert o.image.startswith("https://repositorio.sbrauble.com/arquivos/in/magic/480238/")
    # duas fotos do próprio item, sem repetir
    assert len(o.photos) == 2 and all(f.startswith("https://repositorio.sbrauble.com/arquivos/up/ecom/tcg/fotos/") for f in o.photos)


def test_pagina_sem_imagens():
    from buscador.lojas.ligamagic import parse_product_page
    ofertas, _ = parse_product_page(open("tests/fixtures/produto_promocao.html", encoding="utf-8").read())
    assert all(o.image == "" and o.photos == [] for o in ofertas)


def test_tela_recebe_so_quantas_fotos_a_loja_tem():
    from buscador.lojas.ligamagic import parse_product_page
    from buscador.web import serializar
    ofertas, _ = parse_product_page(open("tests/fixtures/produto_fotos_da_loja.html", encoding="utf-8").read())
    o = serializar.oferta(ofertas[0])
    assert o["fotos"] == 2 and o["imagem"].startswith("https://")
