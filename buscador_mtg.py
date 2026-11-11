"""
Buscador de Cartas Magic: The Gathering
---------------------------------------
Digite o nome da carta, escolha as lojas e veja num só lugar quais têm a carta
e por quanto. Funciona com lojas no padrão LigaMagic.

Instalação (uma vez):
    pip install requests beautifulsoup4

Uso:
    python buscador_mtg.py      (ou: python -m buscador)
"""

from buscador.interface.app import main


if __name__ == "__main__":
    main()
