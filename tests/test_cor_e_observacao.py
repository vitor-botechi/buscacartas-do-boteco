"""Cor principal do site da loja e observação que a loja coloca numa oferta."""

from buscador.lojas.ligamagic import parse_product_page, product_from_page, theme_color, theme_logo, web_image
from buscador.texto import offer_desc


def test_cor_principal_do_site():
    assert theme_color("<style>:root {--color-primary:#990000;--color-secondary:#121212;}</style>") == "#990000"


def test_cor_cinza_branca_ou_ausente_nao_serve():
    assert theme_color(":root {--color-primary:#4F4F4F;}") is None  # cinza
    assert theme_color(":root {--color-primary:#FFFFFF;}") is None
    assert theme_color("<html>sem cor</html>") is None


def test_observacao_vira_campo_separado_dos_extras(pagina):
    nome, _, ofertas, _ = product_from_page(pagina("produto_observacao"), "https://www.legacytcg.com.br")
    assert "Omnath" in nome
    com_obs = [o for o in ofertas if o.note]
    assert len(com_obs) == 1
    o = com_obs[0]
    assert o.extras == "Foil"  # sem o "Visualizar observação" grudado
    assert "6x no cartão" in o.note and "{{br}}" not in o.note
    assert "contém observação" in offer_desc(o)
    assert all("observa" not in x.extras.lower() for x in ofertas)


def test_logo_da_pagina_inicial():
    html = '<a href="./"><img src="//repositorio.sbrauble.com/arquivos/up/ecom/logo/abc-123.jpg"/></a>'
    assert theme_logo(html) == "https://repositorio.sbrauble.com/arquivos/up/ecom/logo/abc-123.jpg"
    assert theme_logo("<img src='/imagens/banner.jpg'>") == ""


def test_so_imagens_da_web():
    assert web_image("//cdn.loja/x.svg") == "https://cdn.loja/x.svg"
    assert web_image("https://cdn.loja/x.svg") == "https://cdn.loja/x.svg"
    assert web_image("javascript:alert(1)") == ""
    assert web_image('https://a/"onerror="x') == ""


def test_bandeira_do_idioma():
    linha = """
    <div class="table-cards-row">
      <div class="table-cards-body-cell"><img class="icon-edicao" title="Fallout"></div>
      <div class="table-cards-body-cell"><img src='https://www.lmcorp.com.br/images/bandeiras/pten.svg'
           title='Português / Inglês'></div>
      <div class="table-cards-body-cell quality"><i>NM</i></div>
      <div class="table-cards-body-cell card-extras">-</div>
      <div class="table-cards-body-cell">2 unid.</div>
      <div class="table-cards-body-cell card-preco">R$ 10,00</div>
    </div>"""
    ofertas, _ = parse_product_page(linha)
    assert ofertas[0].language == "Português / Inglês"
    assert ofertas[0].language_flag == "https://www.lmcorp.com.br/images/bandeiras/pten.svg"
