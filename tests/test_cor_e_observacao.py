"""Cor principal do site da loja e observação que a loja coloca numa oferta."""

from buscador.lojas.ligamagic import product_from_page, theme_color
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
