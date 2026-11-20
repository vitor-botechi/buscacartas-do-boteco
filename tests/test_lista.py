"""Busca de lista: leitura da lista colada e a busca carta por carta numa loja (sem requisições)."""

import threading

import pytest

from buscador import lista
from buscador.lista import Freio, Nomes, buscar_na_loja, ler_linha, ler_lista
from buscador.modelos import Item, Offer, StoreResult

LOJA = {"name": "Loja Teste", "url": "https://loja.example"}


@pytest.mark.parametrize("linha, esperado", [
    ("4 Lightning Bolt", (4, "Lightning Bolt")),
    ("4x Lightning Bolt", (4, "Lightning Bolt")),
    ("4 x Lightning Bolt", (4, "Lightning Bolt")),
    ("4X Counterspell", (4, "Counterspell")),
    ("1 Sol Ring (CMM) 410 *F*", (1, "Sol Ring")),
    ("1 Sol Ring (CMM) 410", (1, "Sol Ring")),
    ("1x Sol Ring (cmm) 410 [Ramp] ^Have,#37d67a^", (1, "Sol Ring")),
    ("1 Sol Ring [C21]", (1, "Sol Ring")),
    ("1 Lightning Bolt (PLST) M10-146", (1, "Lightning Bolt")),
    ("Counterspell", (1, "Counterspell")),
    ("Lightning Bolt x4", (4, "Lightning Bolt")),
    ("2 Anel Solar", (2, "Anel Solar")),
    ("1 Fire // Ice", (1, "Fire // Ice")),
    ("1 Xenagos, the Reveler", (1, "Xenagos, the Reveler")),
    ("SB: 2 Duress", (2, "Duress")),
    ("  3   Thalia,  Guardian of Thraben  ", (3, "Thalia, Guardian of Thraben")),
    ("1 Sol Ring - Foil", (1, "Sol Ring")),
])
def test_linhas_de_carta(linha, esperado):
    assert ler_linha(linha) == esperado


@pytest.mark.parametrize("linha", [
    "", "   ", "Deck", "Sideboard", "Sideboard:", "Commander", "Companion", "Maybeboard", "Creatures (20)",
    "// comentário", "# outro comentário", "12", "4x",
])
def test_linhas_que_nao_sao_carta(linha):
    assert ler_linha(linha) is None


def test_lista_soma_repetidas_e_marca_basicos():
    texto = """Deck
4 Lightning Bolt (M10) 146
4x Counterspell
1 Sol Ring [C21] *F*
20 Island
2 Ilha

Sideboard
2 Counterspell
???
"""
    lida = ler_lista(texto)
    assert [(c["qtd"], c["nome"], c["basico"]) for c in lida["cartas"]] == [
        (4, "Lightning Bolt", False), (6, "Counterspell", False), (1, "Sol Ring", False),
        (20, "Island", True), (2, "Ilha", True),
    ]
    assert lida["ignoradas"] == ["???"]


def test_repetida_com_maiusculas_e_acentos_diferentes():
    lida = ler_lista("1 Pântano\n2 pantano")
    assert lida["cartas"] == [{"qtd": 3, "nome": "Pântano", "basico": True}]


# ---- busca numa loja ----------------------------------------------------------------------------

def oferta(preco, estoque):
    return Offer("Edição", "Inglês", "NM", "", estoque, preco)


class LojaFalsa:
    """Simula safe_search e fetch_product. respostas: carta -> lista de status da busca, um por tentativa."""

    def __init__(self, monkeypatch, buscas=None, produtos=None):
        self.buscas = buscas or {}
        self.produtos = produtos or {}
        self.pedidos = []
        monkeypatch.setattr(lista, "safe_search", self.buscar)
        monkeypatch.setattr(lista, "fetch_product", self.produto)

    def buscar(self, loja, carta, paginas):
        assert paginas == 1
        self.pedidos.append(("busca", carta))
        fila = self.buscas.get(carta, ["none"])
        status = fila.pop(0) if len(fila) > 1 else fila[0]
        if status == "found":
            itens = [Item(carta, None, f"https://loja.example/{carta}"),
                     Item(carta + " (Art Card)", None, "https://loja.example/art"),
                     Item("Outra " + carta, None, "https://loja.example/outra")]
            return StoreResult(loja, "busca", "found", itens)
        return StoreResult(loja, "busca", status)

    def produto(self, loja, url):
        self.pedidos.append(("produto", url))
        fila = self.produtos.get(url, ["ok"])
        status = fila.pop(0) if len(fila) > 1 else fila[0]
        return {"status": status, "offers": [oferta(5.0, 2)] if status == "ok" else []}


def rodar(cartas, retomar=(60, 120)):
    """Uma loja, com relógio de mentira: dormir só avança o relógio."""
    parar = threading.Event()
    nomes = Nomes(cartas, lambda c: ({c.lower()}, True), parar)
    nomes.trabalhar()
    eventos, dormido, relogio = [], [], [0.0]

    def dormir(s):
        dormido.append(s)
        relogio[0] += s

    freio = Freio(retomar, agora=lambda: relogio[0])
    buscar_na_loja(LOJA, cartas, nomes, parar, lambda t, d: eventos.append((t, d)), dormir=dormir, freio=freio)
    return eventos, dormido


def test_busca_so_le_itens_de_nome_exato(monkeypatch):
    loja = LojaFalsa(monkeypatch, buscas={"Sol Ring": ["found"]})
    eventos, _ = rodar(["Sol Ring", "Ilha"])
    assert [t for t, _ in eventos] == ["lista", "lista", "listafim"]
    res = eventos[0][1]["res"]
    assert res.status == "found" and [i.name for i in res.items] == ["Sol Ring"]  # sem Art Card e sem "Outra"
    assert res.items[0].offers[0].price == 5.0
    assert eventos[1][1]["res"].status == "none"
    assert loja.pedidos == [("busca", "Sol Ring"), ("produto", "https://loja.example/Sol Ring"), ("busca", "Ilha")]


def test_nada_com_nome_exato_vira_nao_tem(monkeypatch):
    LojaFalsa(monkeypatch, buscas={"Sol Ring": ["found"]})
    parar = threading.Event()
    nomes = Nomes(["Sol Ring"], lambda c: ({"anel solar"}, True), parar)
    nomes.trabalhar()
    eventos = []
    buscar_na_loja(LOJA, ["Sol Ring"], nomes, parar, lambda t, d: eventos.append((t, d)), dormir=lambda s: None)
    assert eventos[0][1]["res"].status == "none"


def test_bloqueio_espera_e_retoma_sozinha(monkeypatch):
    loja = LojaFalsa(monkeypatch, buscas={"Sol Ring": ["blocked", "found"]})
    eventos, dormido = rodar(["Sol Ring"])
    assert [t for t, _ in eventos] == ["listapausa", "listaretoma", "lista", "listafim"]
    assert eventos[0][1] == {"segundos": 60, "tentativa": 1}
    assert sum(dormido) >= 60
    assert [p for p in loja.pedidos if p[0] == "busca"] == [("busca", "Sol Ring")] * 2  # tentou a mesma carta


def test_bloqueio_na_pagina_do_produto_tambem_pausa(monkeypatch):
    LojaFalsa(monkeypatch, buscas={"Sol Ring": ["found"]},
              produtos={"https://loja.example/Sol Ring": ["blocked", "ok"]})
    eventos, _ = rodar(["Sol Ring"])
    assert [t for t, _ in eventos] == ["listapausa", "listaretoma", "lista", "listafim"]


def test_desiste_depois_das_esperas(monkeypatch):
    LojaFalsa(monkeypatch, buscas={"A": ["found"], "B": ["blocked"]})
    eventos, _ = rodar(["A", "B", "C"], retomar=(60, 120))
    assert [t for t, _ in eventos] == ["lista", "listapausa", "listaretoma", "listapausa", "listaretoma", "listadesiste"]
    assert eventos[-1][1] == {"de": 1}


def test_cancelar_para_no_meio_da_espera(monkeypatch):
    LojaFalsa(monkeypatch, buscas={"A": ["blocked"]})
    parar = threading.Event()
    nomes = Nomes(["A"], lambda c: ({"a"}, True), parar)
    nomes.trabalhar()
    eventos = []

    def dormir(_s):
        parar.set()  # a pessoa clicou em Cancelar durante a espera

    buscar_na_loja(LOJA, ["A"], nomes, parar, lambda t, d: eventos.append(t), dormir=dormir)
    assert eventos == ["listapausa"]


def test_pausa_entre_requisicoes_da_mesma_loja(monkeypatch):
    LojaFalsa(monkeypatch, buscas={"A": ["found"]})
    _, dormido = rodar(["A", "B"])
    # 3 requisições (busca A, produto A, busca B): a 1ª sai na hora, as outras depois de >= LISTA_PAUSA
    assert sum(dormido) >= 2 * lista.LISTA_PAUSA


def test_scryfall_fora_do_ar_usa_o_nome_digitado():
    parar = threading.Event()

    def falha(_c):
        raise OSError("sem internet")

    nomes = Nomes(["Sol Ring"], falha, parar)
    nomes.trabalhar()
    assert nomes.de(0) == {"sol ring"}


def test_loja_barrada_pausa_todas(monkeypatch):
    """Duas lojas ao mesmo tempo: a A é barrada uma vez; a B também pausa e as duas terminam."""
    monkeypatch.setattr(lista, "LISTA_PAUSA", 0.05)
    barrou = []

    def busca(loja, carta, paginas):
        if loja["name"] == "A" and carta == "C2" and not barrou:
            barrou.append(1)
            return StoreResult(loja, "b", "blocked")
        return StoreResult(loja, "b", "none")

    monkeypatch.setattr(lista, "safe_search", busca)
    cartas = [f"C{i}" for i in range(8)]
    parar = threading.Event()
    nomes = Nomes(cartas, lambda c: ({c.lower()}, True), parar)
    nomes.trabalhar()
    freio = Freio((0.4,))
    eventos = {"A": [], "B": []}
    lojas = [threading.Thread(target=buscar_na_loja, args=(
        {"name": n, "url": n}, cartas, nomes, parar, lambda t, d, n=n: eventos[n].append(t)), kwargs={"freio": freio})
        for n in eventos]
    for t in lojas:
        t.start()
    for t in lojas:
        t.join(timeout=10)
    for n in eventos:
        assert "listapausa" in eventos[n] and "listaretoma" in eventos[n], (n, eventos[n])
        assert eventos[n][-1] == "listafim" and eventos[n].count("lista") == 8


def test_freio_desiste_depois_das_esperas():
    relogio = [0.0]
    freio = Freio((10, 20), agora=lambda: relogio[0])
    freio.bloqueou()
    assert freio.falta() == 10
    freio.bloqueou()  # outra loja barrada durante a pausa: não conta de novo
    assert freio.tentativa == 1
    relogio[0] = 11
    freio.bloqueou()
    assert freio.falta() == 20
    relogio[0] = 40
    freio.bloqueou()
    assert freio.desistiu


def test_freio_zera_depois_de_dar_certo():
    relogio = [0.0]
    freio = Freio((10, 20), agora=lambda: relogio[0])
    freio.bloqueou()
    relogio[0] = 11
    freio.deu_certo()
    freio.bloqueou()
    assert freio.falta() == 10  # voltou para a primeira espera
