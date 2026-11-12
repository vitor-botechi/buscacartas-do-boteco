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


def main():
    try:
        import webview
    except ImportError:
        from buscador.interface.app import main as main_tkinter

        main_tkinter()
        return

    ponte = Ponte()
    janela = webview.create_window(
        TITULO, url=os.path.join(pasta_da_pagina(), "index.html"), js_api=ponte,
        width=1200, height=760, min_size=(900, 560), background_color="#f6f7f9", text_select=True,
    )
    ponte._janela = janela
    webview.start()


if __name__ == "__main__":
    main()
