"""Gera o programa para Windows (BuscadorMTG.exe), um arquivo único para publicar nas versões do GitHub.

Uso (na pasta do projeto):
    py -m pip install -r instalador/requirements.txt
    py instalador/gerar_exe.py

Resultado: dist/BuscadorMTG.exe, o arquivo publicado na página de versões do GitHub.

Arquivo único (--onefile): a pessoa baixa e abre, de qualquer lugar, sem descompactar nada.
Custo: abre uns segundos mais devagar, porque se descompacta numa pasta temporária a cada uso.
Até a versão 0.3.0 era uma pasta num .zip, e quem abria o .exe de dentro do zip (sem a pasta
_internal) via só uma janela de erro.

O .exe grava lojas.json, config.json e debug/ em %APPDATA%/BuscadorMTG (ver config.app_dir).
"""

import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from buscador import __version__  # noqa: E402

NOME = "BuscadorMTG"
BUILD = os.path.join(RAIZ, "build")
DIST = os.path.join(RAIZ, "dist")


def arquivo_de_versao():
    """Informações que o Windows mostra em Propriedades > Detalhes do .exe."""
    numeros = [int(x) for x in __version__.split(".")[:3]] + [0]
    tupla = tuple(numeros[:4])
    texto = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={tupla}, prodvers={tupla}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('041604B0', [
      StringStruct('ProductName', 'Buscador de Cartas MTG'),
      StringStruct('FileDescription', 'Buscador de Cartas MTG'),
      StringStruct('ProductVersion', '{__version__}'),
      StringStruct('FileVersion', '{__version__}'),
      StringStruct('OriginalFilename', '{NOME}.exe'),
      StringStruct('LegalCopyright', 'Licença MIT')])]),
    VarFileInfo([VarStruct('Translation', [0x0416, 1200])])
  ]
)
"""
    os.makedirs(BUILD, exist_ok=True)
    caminho = os.path.join(BUILD, "versao.txt")
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(texto)
    return caminho


def main():
    try:
        import PyInstaller.__main__
    except ImportError:
        sys.exit("Falta o PyInstaller. Rode: py -m pip install -r instalador/requirements.txt")
    try:
        import bs4  # noqa: F401
        import requests  # noqa: F401
        import webview  # noqa: F401
    except ImportError:
        # sem elas o .exe abriria com a busca desligada (rede.HAS_SCRAPING) ou nem abriria (sem o pywebview)
        sys.exit("Faltam bibliotecas. Rode: py -m pip install -r requirements.txt")

    PyInstaller.__main__.run([
        os.path.join(RAIZ, "buscador_mtg.py"),
        "--name", NOME,
        "--onefile",
        "--windowed",  # sem a janela preta do terminal
        "--noconfirm",
        "--clean",
        "--distpath", DIST,
        "--workpath", BUILD,
        "--specpath", BUILD,
        "--version-file", arquivo_de_versao(),
        "--paths", RAIZ,
        # a página da interface (HTML, CSS e JS) vai dentro do .exe; ver web/app.py:pasta_da_pagina
        "--add-data", os.pathsep.join([os.path.join(RAIZ, "buscador", "web", "pagina"),
                                       os.path.join("buscador", "web", "pagina")]),
    ])

    exe = os.path.join(DIST, f"{NOME}.exe")
    print(f"\nPronto: {exe} ({os.path.getsize(exe) / 1e6:.1f} MB), versão {__version__}")


if __name__ == "__main__":
    main()
