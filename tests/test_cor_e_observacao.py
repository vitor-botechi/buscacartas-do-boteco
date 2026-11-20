"""Cor principal do site da loja e observação que a loja coloca numa oferta."""

from buscador.lojas.ligamagic import (parse_product_page, product_from_page, svg_colors, theme_color, theme_logo,
                                      web_image)


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


def test_codigo_da_edicao_no_icone():
    linha = """
    <div class="table-cards-row">
      <div class="table-cards-body-cell"><img src='//repositorio.sbrauble.com/arquivos/up/ed_mtg/BRC_U.gif'
           title="A Guerra dos Irm&atilde;os Commander" class='icon icon-edicao'></div>
      <div class="table-cards-body-cell"><img title='Inglês'></div>
      <div class="table-cards-body-cell quality"><i>NM</i></div>
      <div class="table-cards-body-cell card-extras">-</div>
      <div class="table-cards-body-cell">2 unid.</div>
      <div class="table-cards-body-cell card-preco">R$ 10,00</div>
    </div>"""
    ofertas, _ = parse_product_page(linha)
    assert ofertas[0].edition == "A Guerra dos Irmãos Commander"
    assert ofertas[0].edition_code == "brc"
    sem_icone, _ = parse_product_page(linha.replace("ed_mtg/BRC_U.gif", "outra.gif"))
    assert sem_icone[0].edition_code == ""


def test_icone_da_edicao_depois_da_foto_do_item():
    linha = """
    <div class="table-cards-row">
      <div class="table-cards-body-cell"><div class="espaco-foto-personalizada"><img src="https://loja/foto.jpg"></div>
        <img src='//repositorio.sbrauble.com/arquivos/up/ed_mtg/LTC_U.gif' title="Contos da Terra Média Commander"
             class='icon icon-edicao'></div>
      <div class="table-cards-body-cell"><img title='Inglês'></div>
      <div class="table-cards-body-cell quality"><i>NM</i></div>
      <div class="table-cards-body-cell card-extras">-</div>
      <div class="table-cards-body-cell">2 unid.</div>
      <div class="table-cards-body-cell card-preco">R$ 10,00</div>
    </div>"""
    ofertas, _ = parse_product_page(linha)
    assert ofertas[0].edition == "Contos da Terra Média Commander"
    assert ofertas[0].edition_code == "ltc"


def test_logo_e_cor_de_loja_com_layout_proprio():
    # Epic One: logo com class="logo" e outra no rodapé; cor na <meta theme-color>
    epic = ('<meta name="theme-color" content="#ef930c">'
            '<img src="//www.lmcorp.com.br/arquivos/ecom/461/img/logo_epicone.png" class="logo">'
            '<img src="//www.lmcorp.com.br/arquivos/ecom/461/img/logo_epicone_rodape.png" class="img_logo_rodape" />')
    assert theme_logo(epic) == "https://www.lmcorp.com.br/arquivos/ecom/461/img/logo_epicone.png"
    assert theme_color(epic) == "#ef930c"
    # Meruru: a logo vem depois de outras imagens; as de pagamento ficam de fora; theme-color cinza não serve
    meruru = ('<meta name="theme-color" content="#222222"><img src="//www.lmcorp.com.br/arquivos/ecom/64102/images/banner.jpg">'
              '<img src="//www.lmcorp.com.br/arquivos/ecom/64102/images/logo_pix.png" alt="Logo PIX">'
              '<img src="//www.lmcorp.com.br/arquivos/ecom/64102/images/logo.svg" alt="Logo Meruru">')
    assert theme_logo(meruru) == "https://www.lmcorp.com.br/arquivos/ecom/64102/images/logo.svg"
    assert theme_color(meruru) is None
    assert theme_logo('<img src="//cdn.x.com/img/logo.png">') == ""  # imagem de fora da loja


def test_cores_da_logo_em_svg():
    svg = '<svg fill="#e14681"><g fill="#a6bf36"/><g fill="#a6bf36"/><g fill="#000000"/><g fill="#FFFFFF"/></svg>'
    assert svg_colors(svg) == ["#a6bf36", "#e14681"]  # mais usada primeiro; preto e branco ficam de fora
    assert svg_colors("<svg/>") == []
