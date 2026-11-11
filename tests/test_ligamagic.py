"""Leitura das páginas no padrão LigaMagic, com páginas reais sanitizadas (tests/fixtures/)."""

from buscador.lojas.ligamagic import build_search_url, parse_product_page, parse_results, product_from_page

OVERRUN = "https://www.overrun.com.br"


def test_url_de_busca_so_com_estoque_e_menor_preco():
    url = build_search_url("https://www.overrun.com.br/", "Sol Ring", page=2)
    assert url == ("https://www.overrun.com.br/?view=ecom/itens&busca=Sol+Ring"
                   "&txt_estoque=1&txt_order=3&txt_limit=120&page=2")


# ---- lista de busca com vários resultados ----

def test_lista_traz_os_4_resultados(pagina):
    itens, _ = parse_results(pagina("busca_lista"), OVERRUN)
    assert [i.name for i in itens] == [
        "Thalia, Guardiã de Thraben (Art Card)",
        "Thalia, the Survivor",
        "Tenente de Thalia",
        "Thalia, Guardiã de Thraben",
    ]


def test_lista_tem_links_completos_para_o_produto(pagina):
    itens, _ = parse_results(pagina("busca_lista"), OVERRUN)
    for item in itens:
        assert item.url.startswith(OVERRUN + "/?view=ecom/item&refid=")
        assert item.available


def test_lista_nao_le_preco_desenhado_com_imagem(pagina):
    # na lista o preço vem em imagens embaralhadas; por decisão do projeto não é lido (sem OCR)
    itens, _ = parse_results(pagina("busca_lista"), OVERRUN)
    assert all(i.price is None for i in itens)


def test_lista_informa_o_total_de_resultados(pagina):
    _, texto = parse_results(pagina("busca_lista"), OVERRUN)
    assert "1-4 de 4" in texto


def test_lista_nao_e_pagina_de_produto(pagina):
    assert product_from_page(pagina("busca_lista"), OVERRUN) is None


# ---- busca com um único resultado: a loja devolve direto a página do produto ----

def test_busca_com_um_resultado_devolve_o_produto(pagina):
    nome, url, ofertas, status = product_from_page(pagina("busca_produto_direto"), "https://pagina.pedida/")
    assert nome == "Gruta Profana / Unholy Grotto"
    assert url == OVERRUN + "/?view=ecom/item&refid=mOK_EDdFVxtJGerjk8JTQg"  # vem do og:url
    assert status == "ok"
    assert [(o.edition, o.price) for o in ofertas] == [("Aetherdrift Commander", 13.9), ("The List", 34.9)]


def test_ofertas_trazem_idioma_qualidade_e_estoque(pagina):
    _, _, ofertas, _ = product_from_page(pagina("busca_produto_direto"), "https://pagina.pedida/")
    primeira = ofertas[0]
    assert (primeira.language, primeira.quality, primeira.stock) == ("Inglês", "NM", 1)
    assert primeira.extras == ""
    assert not primeira.preorder


# ---- página do produto com promoção e linhas sem estoque ----

def test_promocao_usa_o_preco_novo_e_guarda_o_riscado(pagina):
    ofertas, status = parse_product_page(pagina("produto_promocao"))
    assert status == "ok"
    assert len(ofertas) == 1
    oferta = ofertas[0]
    assert oferta.price == 6.75
    assert oferta.original_price == 7.5
    assert (oferta.edition, oferta.stock) == ("Lorwyn Eclipsed Commander", 2)


def test_linhas_sem_estoque_sao_ignoradas(pagina):
    html = pagina("produto_promocao")
    assert html.count("table-cards-row") > 1  # a página lista várias edições ("Avise quando chegar")...
    ofertas, _ = parse_product_page(html)
    assert all(o.stock for o in ofertas)  # ...mas só as que têm estoque viram ofertas


# ---- busca sem resultados ----

def test_busca_sem_resultados(pagina):
    html = pagina("busca_sem_resultado")
    itens, _ = parse_results(html, "https://www.legacytcg.com.br")
    assert itens == []
    assert product_from_page(html, "https://x/") is None
    assert parse_product_page(html) == ([], "empty")


def test_pagina_sem_linhas_de_oferta_e_vazia():
    assert parse_product_page("<html><body><p>nada</p></body></html>") == ([], "empty")
