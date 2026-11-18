"""Pasta de dados: projeto quando roda pelo código-fonte, %APPDATA%/BuscaCartas no .exe."""

import os
import sys

from buscador import config


def test_pelo_codigo_fonte_usa_a_pasta_do_projeto():
    projeto = os.path.dirname(os.path.dirname(os.path.abspath(config.__file__)))
    assert config.app_dir() == projeto


def test_no_exe_usa_a_pasta_de_dados_do_usuario(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert config.app_dir() == os.path.join(str(tmp_path), "BuscaCartas")


def test_migra_os_arquivos_que_ficavam_ao_lado_do_exe(tmp_path):
    exe, dados = tmp_path / "exe", tmp_path / "dados"
    exe.mkdir()
    (exe / "lojas.json").write_text("antigo", encoding="utf-8")
    config.migrate_from_exe_folder(str(exe), str(dados))
    assert (dados / "lojas.json").read_text(encoding="utf-8") == "antigo"
    assert not (dados / "config.json").exists()
    assert (exe / "lojas.json").exists()  # o antigo não é apagado


def test_migracao_nao_sobrescreve_dados_existentes(tmp_path):
    exe, dados = tmp_path / "exe", tmp_path / "dados"
    exe.mkdir()
    dados.mkdir()
    (exe / "lojas.json").write_text("antigo", encoding="utf-8")
    (dados / "lojas.json").write_text("atual", encoding="utf-8")
    config.migrate_from_exe_folder(str(exe), str(dados))
    assert (dados / "lojas.json").read_text(encoding="utf-8") == "atual"


def test_migra_da_pasta_com_o_nome_antigo(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    antiga = tmp_path / "BuscadorMTG"
    antiga.mkdir()
    (antiga / "lojas.json").write_text("minhas lojas", encoding="utf-8")
    (antiga / "config.json").write_text("minhas preferências", encoding="utf-8")
    nova = config.user_data_dir()
    assert nova == os.path.join(str(tmp_path), "BuscaCartas")
    config.migrate_from_exe_folder(config.user_data_dir(config.OLD_DATA_DIR_NAME), nova)
    assert (tmp_path / "BuscaCartas" / "lojas.json").read_text(encoding="utf-8") == "minhas lojas"
    assert (tmp_path / "BuscaCartas" / "config.json").read_text(encoding="utf-8") == "minhas preferências"
    assert (antiga / "lojas.json").exists()  # a pasta antiga fica, para quem voltar à versão anterior
