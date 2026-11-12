"""Gera o programa para Windows (BuscadorMTG.exe) e o .zip para publicar nas versões do GitHub.

Uso (na pasta do projeto):
    py -m pip install -r instalador/requirements.txt
    py instalador/gerar_exe.py

Resultado em dist/:
    dist/BuscadorMTG/                      pasta do programa (BuscadorMTG.exe e _internal/)
    dist/BuscadorMTG-<versão>-windows.zip  o que vai para a página de versões do GitHub

Formato "pasta" (--onedir) em vez de um .exe único: abre mais rápido (não descompacta a cada uso)
e costuma gerar menos alarmes falsos de antivírus. O programa grava lojas.json, config.json e debug/
ao lado do .exe, por isso a pasta deve ficar num lugar com permissão de escrita (Documentos, Área
de Trabalho...), e não em "Arquivos de Programas".
"""

import os
import shutil
import sys
import zipfile

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
    except ImportError:
        # sem elas o .exe abriria com a busca desligada (ver rede.HAS_SCRAPING)
        sys.exit("Faltam requests/beautifulsoup4. Rode: py -m pip install -r requirements.txt")

    PyInstaller.__main__.run([
        os.path.join(RAIZ, "buscador_mtg.py"),
        "--name", NOME,
        "--onedir",
        "--windowed",  # sem a janela preta do terminal
        "--noconfirm",
        "--clean",
        "--distpath", DIST,
        "--workpath", BUILD,
        "--specpath", BUILD,
        "--version-file", arquivo_de_versao(),
        "--paths", RAIZ,
    ])

    pasta = os.path.join(DIST, NOME)
    shutil.copy(os.path.join(RAIZ, "LICENSE"), os.path.join(pasta, "LICENSE.txt"))
    shutil.copy(os.path.join(RAIZ, "instalador", "LEIA-ME.txt"), os.path.join(pasta, "LEIA-ME.txt"))

    zip_path = os.path.join(DIST, f"{NOME}-{__version__}-windows.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for base, _, arquivos in os.walk(pasta):
            for nome in arquivos:
                completo = os.path.join(base, nome)
                z.write(completo, os.path.relpath(completo, DIST))  # dentro do zip: BuscadorMTG/...
    print(f"\nPronto: {zip_path} ({os.path.getsize(zip_path) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
