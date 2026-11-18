"""
BuscaCartas do Boteco: busca cartas de Magic: The Gathering nas lojas
---------------------------------------
Digite o nome da carta, escolha as lojas e veja num só lugar quais têm a carta
e por quanto. Funciona com lojas no padrão LigaMagic.

Instalação (uma vez):
    pip install -r requirements.txt

Uso:
    python buscador_mtg.py      (ou: python -m buscador)
"""

from buscador.web.app import main


if __name__ == "__main__":
    main()
