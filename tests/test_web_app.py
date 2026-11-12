"""Tamanho da janela ao abrir (buscador/web/app.py)."""

from buscador.web.app import ALTURA, LARGURA, MIN_ALTURA, MIN_LARGURA, tamanho_inicial


def test_tela_grande_usa_o_tamanho_preferido():
    assert tamanho_inicial(2560, 1440) == (LARGURA, ALTURA)


def test_tela_menor_nao_passa_de_90_por_cento():
    largura, altura = tamanho_inicial(1366, 768)
    assert largura <= 1366 * 0.9 and altura <= 768 * 0.88


def test_escala_do_windows_conta_em_pixels_logicos():
    assert tamanho_inicial(1920, 1080, 1.5) == (1152, 633)


def test_nunca_abaixo_do_minimo():
    assert tamanho_inicial(800, 500) == (MIN_LARGURA, MIN_ALTURA)
