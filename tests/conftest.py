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
