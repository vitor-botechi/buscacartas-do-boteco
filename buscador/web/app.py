"""Abre a janela do programa com a interface em HTML (pywebview).

Sem o pywebview instalado, abre a interface antiga (Tkinter), que continua no pacote como reserva.
"""

import os
import sys

from buscador.web.ponte import Ponte

TITULO = "Buscador de Cartas MTG"


def pasta_da_pagina():
    """Pasta com index.html, estilo.css e app.js (no .exe, o PyInstaller os coloca em _MEIPASS)."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, "buscador", "web", "pagina")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "pagina")


LARGURA, ALTURA = 1400, 900       # tamanho preferido da janela ao abrir
MIN_LARGURA, MIN_ALTURA = 900, 560


def tamanho_inicial(tela_largura, tela_altura, escala=1.0):
    """Tamanho da janela ao abrir: o preferido, mas sem passar de ~90% da tela (em pixels lógicos)."""
    escala = escala if escala and escala > 1 else 1.0
    largura = min(LARGURA, int(tela_largura / escala * 0.9))
    altura = min(ALTURA, int(tela_altura / escala * 0.88))
    return max(largura, MIN_LARGURA), max(altura, MIN_ALTURA)


def _tamanho_da_tela(webview):
    try:
        tela = webview.screens[0]
        return tamanho_inicial(tela.width, tela.height, getattr(tela, "scale", 1.0))
    except Exception:
        return 1200, 760


def main():
    try:
        import webview
    except ImportError:
        from buscador.interface.app import main as main_tkinter

        main_tkinter()
        return

    ponte = Ponte()
    largura, altura = _tamanho_da_tela(webview)
    janela = webview.create_window(
        TITULO, url=os.path.join(pasta_da_pagina(), "index.html"), js_api=ponte,
        width=largura, height=altura, min_size=(MIN_LARGURA, MIN_ALTURA),
        background_color="#f6f7f9", text_select=True,
    )
    ponte._janela = janela
    webview.start()


if __name__ == "__main__":
    main()
