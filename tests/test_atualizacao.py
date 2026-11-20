"""Aviso de versão nova (sem requisições: a resposta do GitHub é simulada)."""

import json

import pytest

from buscador import __version__, armazenamento, atualizacao
from buscador.atualizacao import ler_lancamento, mais_nova, numero

REL = "https://github.com/vitor-botechi/buscacartas-do-boteco/releases/"


def resposta(tag="v9.0.0", **mais):
    return {"tag_name": tag, "html_url": REL + "tag/" + tag, "draft": False, "prerelease": False,
            "assets": [{"name": "BuscaCartas.exe", "browser_download_url": REL + f"download/{tag}/BuscaCartas.exe"}],
            **mais}


@pytest.fixture
def cfg(monkeypatch, tmp_path):
    arq = tmp_path / "config.json"
    monkeypatch.setattr(armazenamento, "SETTINGS_FILE", str(arq))
    return lambda: json.loads(arq.read_text(encoding="utf-8"))


def test_compara_versoes():
    assert numero("v2.10.0") == (2, 10, 0) and numero("2.1") is None
    assert mais_nova("v2.10.0", "2.9.9") and not mais_nova("2.2.0", "2.2.0") and not mais_nova("v1.9.0", "2.0.0")
    assert not mais_nova("lixo", "2.0.0")


def test_le_a_resposta_do_github():
    assert ler_lancamento(resposta()) == {"versao": "9.0.0", "pagina": REL + "tag/v9.0.0",
                                          "download": REL + "download/v9.0.0/BuscaCartas.exe"}
    assert ler_lancamento(resposta(prerelease=True)) is None
    assert ler_lancamento(resposta(html_url="https://outro.site/x")) is None  # só endereços do próprio projeto
    sem_exe = ler_lancamento(resposta(assets=[{"name": "BuscaCartas.exe", "browser_download_url": "https://outro.site/a.exe"}]))
    assert sem_exe["download"] == ""  # o botão abre a página da versão


def test_avisa_e_consulta_no_maximo_uma_vez_por_dia(cfg):
    chamadas = []
    consultar = lambda: chamadas.append(1) or ler_lancamento(resposta())
    assert atualizacao.verificar(agora=1000, consultar=consultar)["versao"] == "9.0.0"
    assert atualizacao.verificar(agora=1000 + 3600, consultar=consultar)["versao"] == "9.0.0"  # do config.json
    assert len(chamadas) == 1
    atualizacao.verificar(agora=1000 + 25 * 3600, consultar=consultar)
    assert len(chamadas) == 2
    assert cfg()["versao_ultima"]["versao"] == "9.0.0"


def test_sem_internet_ou_mesma_versao_fica_quieto(cfg):
    assert atualizacao.verificar(agora=1000, consultar=lambda: None) is None
    assert cfg()["versao_checada_em"] == 1000  # não tenta de novo no mesmo dia
    atual = ler_lancamento(resposta("v" + __version__))
    assert atualizacao.verificar(agora=1000 + 25 * 3600, consultar=lambda: atual) is None


def test_agora_nao_adia_o_aviso_por_tres_dias(cfg):
    consultar = lambda: ler_lancamento(resposta())
    atualizacao.verificar(agora=0, consultar=consultar)
    atualizacao.adiar("9.0.0", agora=10)
    assert atualizacao.verificar(agora=3600, consultar=consultar) is None
    assert atualizacao.verificar(agora=10 + 3 * 24 * 3600, consultar=consultar)["versao"] == "9.0.0"


def test_versao_mais_nova_que_a_adiada_avisa_logo(cfg):
    atualizacao.verificar(agora=0, consultar=lambda: ler_lancamento(resposta()))
    atualizacao.adiar("9.0.0", agora=0)
    assert atualizacao.verificar(agora=25 * 3600, consultar=lambda: ler_lancamento(resposta("v9.1.0")))["versao"] == "9.1.0"
