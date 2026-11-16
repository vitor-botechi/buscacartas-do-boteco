"""Lado Python da interface HTML (buscador/web/ponte.py), sem janela e sem requisições."""

import json
import re
import threading
import time

import pytest

from buscador import armazenamento, automatico
from buscador.lojas.ligamagic import parse_results, product_from_page
from buscador.modelos import StoreResult
from buscador.web import ponte as ponte_mod
from buscador.web.ponte import Ponte, primeira_linha_limpa


class JanelaFalsa:
    """Guarda os acontecimentos que a Ponte manda para a página (app.evento(tipo, sid, dados))."""

    def __init__(self):
        self.eventos = []
        self.lock = threading.Lock()

    def evaluate_js(self, js):
        m = re.match(r'window\.app && app\.evento\("(\w+)", (-?\d+), (.*)\)$', js, re.S)
        assert m, js
        with self.lock:
            self.eventos.append((m.group(1), int(m.group(2)), json.loads(m.group(3))))

    def tipos(self):
        with self.lock:
            return [e[0] for e in self.eventos]

    def espera(self, condicao, tempo=5):
        fim = time.time() + tempo
        while time.time() < fim:
            with self.lock:
                if condicao(list(self.eventos)):
                    return
            time.sleep(0.02)
        raise AssertionError(f"não aconteceu; eventos: {self.tipos()}")


@pytest.fixture
def ponte(monkeypatch, tmp_path):
    monkeypatch.setattr(armazenamento, "CONFIG_FILE", str(tmp_path / "lojas.json"))
    monkeypatch.setattr(armazenamento, "SETTINGS_FILE", str(tmp_path / "config.json"))
    monkeypatch.setattr(automatico, "AUTO_DELAY", 0)
    monkeypatch.setattr(ponte_mod, "HAS_SCRAPING", True)
    monkeypatch.setattr(ponte_mod, "fetch_store_color", lambda base: "#123456")  # sem requisição
    p = Ponte(JanelaFalsa())
    # só a Overrun marcada, para os testes ficarem simples
    p.marcar_lojas({s["url"]: s["name"] == "Overrun" for s in p._lojas})
    return p


@pytest.fixture
def lojas_falsas(monkeypatch, pagina):
    """Busca: lista da Overrun com 2 itens (Anel Solar em pré-venda e Sol Ring (Human)).
    Página de produto: as ofertas do Anel Solar."""
    lista = pagina("busca_lista_pre_venda")
    produto = pagina("produto_pre_venda")
    pedidos = []

    def safe_search(store, card):
        itens, _ = parse_results(lista, store["url"])
        return StoreResult(store, "https://busca/" + card, "found", itens)

    def fetch_product(store, url):
        pedidos.append(url)
        _, _, ofertas, _ = product_from_page(produto, url)
        return {"status": "ok", "offers": ofertas}

    monkeypatch.setattr(ponte_mod, "safe_search", safe_search)
    monkeypatch.setattr(ponte_mod, "fetch_product", fetch_product)
    monkeypatch.setattr(automatico, "fetch_product", fetch_product)
    return pedidos


def test_iniciar_traz_lojas_e_preferencias(ponte):
    cfg = ponte.iniciar()
    assert [l["nome"] for l in cfg["lojas"]][:4] == ["Deckmaster Games", "Overrun", "Jackpot Jogos", "Legacy TCG"]
    assert all(l["cor"].startswith("#") for l in cfg["lojas"][:4])  # cada loja padrão tem a sua cor
    assert cfg["auto_limite"] == 5 and cfg["auto_max"] == 10
    assert cfg["tem_bibliotecas"] is True
    assert "_janela" not in dir(type(ponte))  # estado interno não vira função da página


def test_adicionar_e_remover_loja(ponte):
    assert ponte.adicionar_loja("nada") == {"erro": "Confira o link da loja."}
    assert ponte.adicionar_loja("overrun.com.br") == {"erro": "Essa loja já está na lista."}
    lojas = ponte.adicionar_loja("www.minhaloja.com.br", "")["lojas"]
    nova = lojas[-1]
    assert (nova["nome"], nova["url"], nova["padrao"]) == ("Minhaloja", "https://www.minhaloja.com.br", False)
    assert nova["cor"] == "#123456"  # cor lida do site da loja
    salva = Ponte().iniciar()["lojas"][-1]
    assert (salva["url"], salva["cor"]) == (nova["url"], "#123456")  # ficou salva, com a cor
    lojas = ponte.remover_loja(nova["url"])
    assert all(l["url"] != nova["url"] for l in lojas)
    assert len(ponte.remover_loja("https://www.overrun.com.br")) == len(lojas)  # loja padrão não sai


def test_auto_limite_fica_entre_0_e_10(ponte):
    assert ponte.salvar_auto_limite("99") == 10
    assert ponte.salvar_auto_limite("x") == 5
    assert ponte.salvar_auto_limite(0) == 0
    assert Ponte().iniciar()["auto_limite"] == 0


def test_buscar_sem_nome_ou_sem_loja(ponte):
    assert ponte.buscar("   ", False, 5) == {"erro": "Digite o nome da carta."}
    ponte.marcar_lojas({s["url"]: False for s in ponte._lojas})
    assert ponte.buscar("Sol Ring", False, 5) == {"erro": "Marque ao menos uma loja."}


def test_buscar_manda_o_resultado_e_os_detalhes_automaticos(ponte, lojas_falsas):
    r = ponte.buscar("  Sol Ring ", False, 5)
    assert r["carta"] == "Sol Ring"
    assert [l["nome"] for l in r["lojas"]] == ["Overrun"]
    janela = ponte._janela
    janela.espera(lambda ev: any(e[0] == "autoend" for e in ev))
    assert all(e[1] == r["sid"] for e in janela.eventos)
    _, _, res = next(e for e in janela.eventos if e[0] == "result")
    assert res["status"] == "found"
    assert [(i["nome"], i["pre"], i["pre_data"]) for i in res["itens"]] == [
        ("Anel Solar", True, "13/11/2026"), ("Sol Ring (Human)", False, "")]
    assert janela.tipos() == ["result", "autostart", "offers", "autostep", "offers", "autostep", "autoend"]
    _, _, (loja, item, ofertas) = next(e for e in janela.eventos if e[0] == "offers")
    assert loja == "https://www.overrun.com.br"
    assert ofertas[0] == {"edicao": "Star Trek Commander", "idioma": "Inglês", "qualidade": "NM", "extras": "",
                          "estoque": 8, "preco": 6.9, "preco_original": None, "promo": 0,
                          "pre": True, "pre_data": "13/11/2026", "obs": ""}
    assert len(lojas_falsas) == 2  # uma página por item, nunca mais


def test_limite_zero_desliga_os_detalhes_automaticos(ponte, lojas_falsas):
    ponte.buscar("Sol Ring", False, 0)
    ponte._janela.espera(lambda ev: ev and ev[0][0] == "result")
    time.sleep(0.3)
    assert ponte._janela.tipos() == ["result"]
    assert lojas_falsas == []


def test_nova_busca_para_a_anterior(ponte, monkeypatch, lojas_falsas):
    liberar = threading.Event()
    original = ponte_mod.safe_search

    def lenta(store, card):
        liberar.wait(2)
        return original(store, card)

    monkeypatch.setattr(ponte_mod, "safe_search", lenta)
    primeira = ponte.buscar("Sol Ring", False, 5)
    ctl = ponte._ctl
    ponte.cancelar()
    assert ctl.stop.is_set()
    liberar.set()
    time.sleep(0.3)
    assert ponte._janela.eventos == []  # o resultado atrasado da busca cancelada não vai para a tela
    assert primeira["sid"] < ponte._sid


def test_nome_exato_marca_os_itens(ponte, monkeypatch, lojas_falsas):
    monkeypatch.setattr(ponte_mod, "resolve_names", lambda card: ({"anel solar"}, True))
    ponte.buscar("Sol Ring", True, 0)
    janela = ponte._janela
    janela.espera(lambda ev: {"names", "result"} <= {e[0] for e in ev})
    _, _, res = next(e for e in janela.eventos if e[0] == "result")
    _, _, nomes = next(e for e in janela.eventos if e[0] == "names")
    marcas = nomes["marcas"].get("https://www.overrun.com.br") or [i["exato"] for i in res["itens"]]
    assert marcas == [True, False]  # só "Anel Solar" está entre os nomes aceitos


def test_nome_exato_depois_da_busca(ponte, monkeypatch):
    monkeypatch.setattr(ponte_mod, "resolve_names", lambda card: ({"thalia"}, False))
    r = ponte.nomes_exatos("Thalia", {"https://loja": ["Thalia", "Tenente de Thalia"]})
    assert r == {"nomes": ["thalia"], "ok": False, "marcas": {"https://loja": [True, False]}}


def test_detalhes_sob_demanda(ponte, lojas_falsas):
    r = ponte.detalhes("https://www.overrun.com.br", "https://produto/1")
    assert r["status"] == "ok"
    assert len(r["ofertas"]) == 15
    assert r["ofertas"][0]["pre_data"] == "13/11/2026"


def test_abrir_so_aceita_links_da_web(ponte, monkeypatch):
    abertos = []
    monkeypatch.setattr(ponte_mod.webbrowser, "open_new_tab", abertos.append)
    ponte.abrir(["https://a", "file:///c:/x", "javascript:alert(1)"])
    ponte.abrir("http://b")
    assert abertos == ["https://a", "http://b"]


def test_abrir_lojas_monta_a_busca_de_cada_loja_marcada(ponte, monkeypatch):
    abertos = []
    monkeypatch.setattr(ponte_mod.webbrowser, "open_new_tab", abertos.append)
    ponte.abrir_lojas("Sol Ring")
    assert abertos == ["https://www.overrun.com.br/?view=ecom/itens&busca=Sol+Ring"
                       "&txt_estoque=1&txt_order=3&txt_limit=120&page=1"]


def test_primeira_linha_do_texto_colado():
    assert primeira_linha_limpa("\n  Sol   Ring \nOutra linha") == "Sol Ring"
    assert primeira_linha_limpa("") == ""
