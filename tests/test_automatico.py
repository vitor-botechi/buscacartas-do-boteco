"""Detalhes automáticos: limites, ordem das mensagens para a tela e freio de emergência."""

import pytest

from buscador import automatico
from buscador.automatico import AutoCtl, auto_details
from buscador.modelos import Item, StoreResult

LOJA = {"name": "Loja Teste", "url": "https://loja.example"}


def resultado(n):
    itens = [Item(f"Carta {i}", None, f"https://loja.example/item{i}") for i in range(n)]
    return StoreResult(LOJA, "https://loja.example/busca", "found", itens)


@pytest.fixture
def paginas(monkeypatch):
    """Simula fetch_product sem esperar as pausas. Devolve o dicionário url -> status (padrão 'ok')."""
    status = {}
    monkeypatch.setattr(automatico.time, "sleep", lambda _s: None)
    monkeypatch.setattr(automatico, "fetch_product",
                        lambda _loja, url: {"status": status.get(url, "ok"), "offers": [f"oferta de {url}"]})
    return status


def rodar(res, limite=5, ctl=None):
    mensagens = []
    auto_details(res, limite, ctl or AutoCtl(24), False, {}, None, lambda tipo, dados: mensagens.append(tipo))
    return mensagens


def test_orcamento_acaba():
    ctl = AutoCtl(2)
    assert [ctl.take() for _ in range(3)] == [True, True, False]


def test_poucos_itens_sao_detalhados(paginas):
    assert rodar(resultado(2)) == ["autostart", "offers", "autostep", "offers", "autostep", "autoend"]


def test_muitos_itens_nao_sao_detalhados(paginas):
    assert rodar(resultado(6), limite=5) == []


def test_respeita_o_teto_total_da_busca(paginas):
    mensagens = rodar(resultado(3), ctl=AutoCtl(1))
    assert mensagens.count("offers") == 1


def test_bloqueio_para_todas_as_lojas(paginas):
    paginas["https://loja.example/item0"] = "blocked"
    ctl = AutoCtl(24)
    mensagens = rodar(resultado(3), ctl=ctl)
    assert ctl.stop.is_set()
    assert "autostop" in mensagens
    assert mensagens.count("autostep") == 1  # parou logo no primeiro item
    # outra loja na mesma busca nem começa a ler
    assert rodar(resultado(2), ctl=ctl) == ["autostart", "autoend"]


def test_loja_sem_numeros_em_texto_desiste_sem_parar_as_outras(paginas):
    paginas["https://loja.example/item0"] = "unreadable"
    ctl = AutoCtl(24)
    mensagens = rodar(resultado(3), ctl=ctl)
    assert mensagens.count("autostep") == 1
    assert not ctl.stop.is_set()


def test_item_que_ja_tem_ofertas_nao_e_lido_de_novo(paginas):
    res = resultado(2)
    res.items[0].offers = []
    assert rodar(res).count("autostep") == 1
