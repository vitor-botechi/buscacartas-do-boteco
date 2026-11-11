"""Busca numa loja e página do produto, com as respostas das lojas simuladas (nenhuma requisição de verdade)."""

import pytest

from buscador import rede

LOJA = {"name": "Loja Teste", "url": "https://www.overrun.com.br"}


class RespostaFalsa:
    def __init__(self, text, status_code=200, url="https://www.overrun.com.br/?view=ecom/itens"):
        self.text, self.status_code, self.url = text, status_code, url


@pytest.fixture
def lojas_falsas(monkeypatch, tmp_path):
    """Troca o requests.get por respostas prontas e manda a pasta debug/ para uma pasta temporária.
    Devolve (respostas, pedidos): coloque em respostas[url_parcial] a resposta e veja em pedidos as URLs pedidas."""
    respostas, pedidos = {}, []

    def get_falso(url, **_kwargs):
        pedidos.append(url)
        for trecho, resposta in respostas.items():
            if trecho in url:
                return resposta
        raise AssertionError(f"requisição inesperada: {url}")

    monkeypatch.setattr(rede.requests, "get", get_falso)
    monkeypatch.setattr(rede, "app_dir", lambda: str(tmp_path))
    monkeypatch.setattr(rede, "PRODUCT_CACHE", {})
    monkeypatch.setattr("builtins.print", lambda *a, **k: None)  # save_debug escreve no console
    return respostas, pedidos


def test_lista_vira_resultado_found(lojas_falsas, pagina):
    respostas, pedidos = lojas_falsas
    respostas["busca=Thalia"] = RespostaFalsa(pagina("busca_lista"))
    res = rede.search_store(LOJA, "Thalia")
    assert res.status == "found"
    assert len(res.items) == 4
    assert len(pedidos) == 1  # 4 resultados cabem numa página: uma requisição só


def test_produto_direto_ja_traz_as_ofertas(lojas_falsas, pagina):
    respostas, _ = lojas_falsas
    respostas["busca="] = RespostaFalsa(pagina("busca_produto_direto"))
    res = rede.search_store(LOJA, "Unholy Grotto")
    assert res.status == "found"
    [item] = res.items
    assert item.name == "Gruta Profana / Unholy Grotto"
    assert item.price == 13.9
    assert len(item.offers) == 2


def test_sem_resultados_vira_none(lojas_falsas, pagina):
    respostas, _ = lojas_falsas
    respostas["busca="] = RespostaFalsa(pagina("busca_sem_resultado"))
    assert rede.search_store(LOJA, "Unholy Grotto").status == "none"


CARRINHO_VAZIO = ('<div class="carrinho dropdown-cart"><div class="nomessages">'
                  'Nenhum item em seu carrinho.</div></div>')


def test_carrinho_vazio_nao_conta_como_busca_sem_resultado(lojas_falsas):
    # página que não é de busca (sem o filtro txt_estoque) e sem itens: não sabemos ler -> "unknown",
    # mesmo com o resumo do carrinho dizendo "Nenhum item em seu carrinho"
    respostas, _ = lojas_falsas
    respostas["busca="] = RespostaFalsa(f"<html><body>{CARRINHO_VAZIO}<p>Página em manutenção</p></body></html>")
    assert rede.search_store(LOJA, "Sol Ring").status == "unknown"


def test_frase_de_busca_vazia_fora_do_carrinho_continua_valendo(lojas_falsas):
    respostas, _ = lojas_falsas
    respostas["busca="] = RespostaFalsa(f"<html><body>{CARRINHO_VAZIO}"
                                        "<p>Nenhum item encontrado com os filtros utilizados.</p></body></html>")
    assert rede.search_store(LOJA, "Sol Ring").status == "none"


@pytest.mark.parametrize("codigo", [403, 429, 503])
def test_bloqueio_vira_blocked(lojas_falsas, codigo):
    respostas, _ = lojas_falsas
    respostas["busca="] = RespostaFalsa("<html><body>Acesso negado</body></html>", status_code=codigo)
    assert rede.search_store(LOJA, "Sol Ring").status == "blocked"


def test_pagina_de_captcha_vira_blocked(lojas_falsas):
    respostas, _ = lojas_falsas
    respostas["busca="] = RespostaFalsa("<html><body>Just a moment... checking your browser</body></html>")
    assert rede.search_store(LOJA, "Sol Ring").status == "blocked"


def test_erro_inesperado_nao_trava_a_busca(lojas_falsas, monkeypatch):
    monkeypatch.setattr(rede, "search_store", lambda *_: 1 / 0)
    res = rede.safe_search(LOJA, "Sol Ring")
    assert res.status == "error"
    assert "ZeroDivisionError" in res.msg


def test_falha_de_conexao_vira_error(lojas_falsas, monkeypatch):
    def sem_conexao(*_a, **_k):
        raise rede.requests.ConnectionError("sem internet")

    monkeypatch.setattr(rede.requests, "get", sem_conexao)
    res = rede.search_store(LOJA, "Sol Ring")
    assert (res.status, res.msg) == ("error", "sem internet")


def test_debug_grava_a_pagina_recebida(lojas_falsas, pagina, tmp_path):
    respostas, _ = lojas_falsas
    respostas["busca="] = RespostaFalsa(pagina("busca_sem_resultado"))
    rede.search_store(LOJA, "Unholy Grotto")
    assert (tmp_path / "debug" / "debug_overrun.com.br.html").exists()


# ---- página do produto ----

def test_pagina_do_produto_usa_cache(lojas_falsas, pagina):
    respostas, pedidos = lojas_falsas
    url = "https://www.overrun.com.br/?view=ecom/item&refid=abc"
    respostas["refid=abc"] = RespostaFalsa(pagina("produto_promocao"))
    primeira = rede.fetch_product(LOJA, url)
    segunda = rede.fetch_product(LOJA, url)
    assert primeira["status"] == "ok"
    assert segunda == primeira
    assert len(pedidos) == 1  # a segunda leitura veio do cache, sem nova requisição


def test_pagina_do_produto_bloqueada_nao_entra_no_cache(lojas_falsas):
    respostas, pedidos = lojas_falsas
    url = "https://www.overrun.com.br/?view=ecom/item&refid=xyz"
    respostas["refid=xyz"] = RespostaFalsa("", status_code=429)
    assert rede.fetch_product(LOJA, url)["status"] == "blocked"
    rede.fetch_product(LOJA, url)
    assert len(pedidos) == 2
