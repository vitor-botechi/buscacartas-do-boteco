"""Peças compartilhadas pelos testes (o pytest carrega este arquivo sozinho)."""

import os

import pytest

PASTA_FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def pagina():
    """Devolve uma função que lê uma página salva: pagina("busca_lista")."""

    def ler(nome):
        with open(os.path.join(PASTA_FIXTURES, nome + ".html"), encoding="utf-8") as f:
            return f.read()

    return ler


@pytest.fixture(autouse=True)
def scryfall_em_disco_de_teste(tmp_path, monkeypatch):
    """As respostas guardadas do Scryfall vão para um arquivo temporário de cada teste, nunca para o
    scryfall.json de verdade."""
    from buscador import scryfall

    disco = scryfall.MemoriaEmDisco(str(tmp_path / "scryfall.json"))
    monkeypatch.setattr(scryfall, "DISCO", disco)
    return disco
