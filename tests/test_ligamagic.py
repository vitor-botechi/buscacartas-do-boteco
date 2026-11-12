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


def test_deckmaster_produto_com_muitas_edicoes_sem_estoque(pagina):
    nome, url, ofertas, status = product_from_page(pagina("busca_produto_deckmaster"), "https://pagina.pedida/")
    assert status == "ok"
    assert nome == "Anel Solar / Sol Ring"
    assert url.startswith("https://www.deckmastergames.com.br/?view=ecom/item&refid=")
    assert len(ofertas) == 6  # a página tem mais de 150 linhas, só 6 com estoque
    assert [o.price for o in ofertas] == sorted(o.price for o in ofertas)  # do menor para o maior
    assert (ofertas[0].edition, ofertas[0].quality, ofertas[0].price) == ("Commander 2014", "SP", 8.4)


def test_deckmaster_extras_foil(pagina):
    _, _, ofertas, _ = product_from_page(pagina("busca_produto_deckmaster"), "https://pagina.pedida/")
    foils = [o for o in ofertas if o.extras == "Foil"]
    assert [(o.edition, o.price) for o in foils] == [("Foundations (Promos)", 21.89)]


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


# ---- pré-venda: o "P" verde, com a data prevista de envio no title ----

def test_pre_venda_na_pagina_do_produto_traz_a_data(pagina):
    ofertas, status = parse_product_page(pagina("produto_pre_venda"))
    assert status == "ok"
    pre = [o for o in ofertas if o.preorder]
    assert [(o.edition, o.stock, o.price, o.preorder_date) for o in pre] == [("Star Trek Commander", 8, 6.9, "13/11/2026")]


def test_ofertas_normais_nao_sao_pre_venda(pagina):
    ofertas, _ = parse_product_page(pagina("produto_pre_venda"))
    normais = [o for o in ofertas if not o.preorder]
    assert len(normais) == len(ofertas) - 1
    assert all(o.preorder_date == "" for o in normais)


def test_pre_venda_na_lista_de_busca(pagina):
    itens, _ = parse_results(pagina("busca_lista_pre_venda"), OVERRUN)
    marcados = {i.name: i.preorder_date for i in itens if i.preorder}
    assert marcados == {"Anel Solar": "13/11/2026"}
    assert any(not i.preorder for i in itens)


def test_pre_venda_sem_data():
    html = ("<div class='table-cards-row'><div class='table-cards-body-cell'><img title='Edição X'></div>"
            "<div class='table-cards-body-cell'><img title='Inglês'></div>"
            "<div class='table-cards-body-cell'><div class='icone-pre-order'>P</div> 3 unid.</div>"
            "<div class='table-cards-body-cell card-preco'>R$ 1,00</div></div>")
    ofertas, _ = parse_product_page(html)
    assert (ofertas[0].preorder, ofertas[0].preorder_date) == (True, "")


# ---- busca sem resultados ----

def test_busca_sem_resultados(pagina):
    html = pagina("busca_sem_resultado")
    itens, _ = parse_results(html, "https://www.legacytcg.com.br")
    assert itens == []
    assert product_from_page(html, "https://x/") is None
    assert parse_product_page(html) == ([], "empty")


def test_texto_da_pagina_ignora_o_resumo_do_carrinho(pagina):
    _, texto = parse_results(pagina("busca_sem_resultado"), "https://www.legacytcg.com.br")
    assert "nenhum item encontrado com os filtros utilizados" in texto
    assert "seu carrinho" not in texto


def test_pagina_sem_linhas_de_oferta_e_vazia():
    assert parse_product_page("<html><body><p>nada</p></body></html>") == ([], "empty")
