"""Aviso de versão nova: confere no GitHub se saiu uma versão mais nova do programa.

Uma consulta leve à API do GitHub (a última versão publicada), no máximo uma vez por dia; o resultado
fica guardado no config.json. Sem internet, sem a biblioteca requests ou com qualquer erro, fica em
silêncio: o aviso é só uma ajuda. O programa nunca baixa nem troca o .exe sozinho; o botão do aviso
abre o download no navegador da pessoa.
"""

import re
import time

try:
    import requests
except ImportError:
    requests = None

from buscador import __version__
from buscador.armazenamento import load_settings, save_settings

REPOSITORIO = "vitor-botechi/buscacartas-do-boteco"
API_ULTIMA = f"https://api.github.com/repos/{REPOSITORIO}/releases/latest"
PAGINA_VERSOES = f"https://github.com/{REPOSITORIO}/releases/"
INTERVALO = 24 * 3600  # uma consulta por dia, no máximo
ADIAR = 3 * 24 * 3600  # "Agora não": o aviso da mesma versão volta depois de 3 dias
TEMPO_LIMITE = 6
NOME_EXE = "BuscaCartas.exe"


def numero(versao):
    """'v2.3.0' ou '2.3.0' -> (2, 3, 0); outra coisa -> None."""
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", (versao or "").strip())
    return tuple(int(x) for x in m.groups()) if m else None


def mais_nova(versao, atual=__version__):
    a, b = numero(versao), numero(atual)
    return bool(a and b and a > b)


def ler_lancamento(dados):
    """Resposta da API -> {"versao", "pagina", "download"}; None se faltar algo ou o endereço for estranho."""
    if not isinstance(dados, dict) or dados.get("draft") or dados.get("prerelease"):
        return None
    tag = dados.get("tag_name") or ""
    pagina = dados.get("html_url") or ""
    if not numero(tag) or not pagina.startswith(PAGINA_VERSOES):
        return None
    download = ""
    for arq in dados.get("assets") or []:
        url = (arq or {}).get("browser_download_url") or ""
        if (arq or {}).get("name") == NOME_EXE and url.startswith(PAGINA_VERSOES + "download/"):
            download = url
    return {"versao": tag.lstrip("v"), "pagina": pagina, "download": download}


def consultar():
    """Uma requisição à API do GitHub. Sem resposta boa, None."""
    if requests is None:
        return None
    try:
        r = requests.get(API_ULTIMA, timeout=TEMPO_LIMITE, headers={
            "Accept": "application/vnd.github+json", "User-Agent": f"BuscaCartas/{__version__}"})
        if r.status_code != 200:
            return None
        return ler_lancamento(r.json())
    except Exception:  # sem internet, resposta estranha...: o aviso fica para outro dia
        return None


def verificar(agora=None, consultar=consultar):
    """A versão mais nova que a atual, se houver e se a pessoa não pediu "Agora não" há pouco; senão None."""
    agora = time.time() if agora is None else agora
    cfg = load_settings()
    guardada = cfg.get("versao_ultima") if isinstance(cfg.get("versao_ultima"), dict) else None
    checada = cfg.get("versao_checada_em")
    if not isinstance(checada, (int, float)) or not 0 <= agora - checada < INTERVALO:
        nova = consultar()
        cfg = load_settings()  # relê: a página pode ter gravado outra preferência enquanto isso
        cfg["versao_checada_em"] = agora
        if nova:
            cfg["versao_ultima"] = guardada = nova
        save_settings(cfg)
    if not guardada or not mais_nova(guardada.get("versao")):
        return None
    adiada = cfg.get("versao_adiada")
    if isinstance(adiada, dict) and adiada.get("versao") == guardada.get("versao") \
            and isinstance(adiada.get("em"), (int, float)) and 0 <= agora - adiada["em"] < ADIAR:
        return None
    return guardada


def adiar(versao, agora=None):
    """'Agora não': o aviso desta versão some por ADIAR segundos."""
    cfg = load_settings()
    cfg["versao_adiada"] = {"versao": str(versao), "em": time.time() if agora is None else agora}
    save_settings(cfg)
