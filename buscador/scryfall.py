"""Consultas ao Scryfall: nomes da carta em inglês e português ("Apenas nome exato", lista) e arte.
As respostas ficam guardadas em disco (scryfall.json) por algumas semanas (MemoriaEmDisco)."""

import atexit
import json
import os
import re
import threading
import time

try:
    import requests
except ImportError:  # sem a biblioteca a busca interna fica desligada (ver rede.HAS_SCRAPING)
    requests = None

from buscador.texto import norm, strip_suffix


SCRY_HEADERS = {"User-Agent": "BuscaCartas/1.0", "Accept": "application/json;q=0.9,*/*;q=0.8"}
SCRY_API = "https://api.scryfall.com"

# Limites do Scryfall (scryfall.com/docs/api/rate-limits, nov/2026): /cards/search e /cards/named,
# 2 por segundo; os outros, 10 por segundo. Um 429 limita o acesso por 30 s, e insistir pode bloquear
# o programa de vez. Por isso: um ritmo só para o programa inteiro (todas as threads), com folga, e
# depois de um 429 nenhuma consulta por SCRY_PAUSA_429 segundos.
SCRY_INTERVALO_CARTAS = 0.55
SCRY_INTERVALO_OUTROS = 0.12
SCRY_PAUSA_429 = 60


class ScryfallEmPausa(Exception if requests is None else requests.RequestException):
    """O Scryfall pediu para esperar (429): a consulta nem é feita. Quem chama trata como falha de rede."""


class _Ritmo:
    """Fila das consultas ao Scryfall: uma de cada vez, no intervalo pedido. As urgentes (a arte ao
    parar o mouse, o "Apenas nome exato") passam na frente das que não têm pressa (os nomes da lista)."""

    def __init__(self):
        self._cond = threading.Condition()
        self._proxima = 0.0
        self.pausa_ate = 0.0
        self._urgentes = 0

    def vez(self, intervalo, urgente=True):
        with self._cond:
            if urgente:
                self._urgentes += 1
            try:
                while True:
                    agora = time.monotonic()
                    if agora < self.pausa_ate:
                        raise ScryfallEmPausa("Scryfall pediu para esperar")
                    if not urgente and self._urgentes:
                        self._cond.wait(0.1)
                        continue
                    if agora >= self._proxima:
                        self._proxima = agora + intervalo
                        return
                    self._cond.wait(self._proxima - agora)
            finally:
                if urgente:
                    self._urgentes -= 1
                    self._cond.notify_all()

    def pausar(self, segundos):
        with self._cond:
            self.pausa_ate = max(self.pausa_ate, time.monotonic() + segundos)
            self._cond.notify_all()


RITMO = _Ritmo()


# ---- memória em disco (scryfall.json) ----------------------------------------------------------
# O Scryfall pede para guardar as respostas por pelo menos 24 h. Os nomes da carta e o endereço da
# arte quase nunca mudam: ficam guardados por SCRY_DIAS dias, e "não achei" só por SCRY_DIAS_SEM_RESPOSTA
# (pode ser uma carta nova, que o Scryfall ainda não tinha). Falhas e 429 nunca são guardados.
SCRY_DIAS = 30
SCRY_DIAS_SEM_RESPOSTA = 1
SCRY_DIAS_EDICOES = 7      # a lista de edições (/sets): edições novas saem algumas vezes por mês
SCRY_MAX_GUARDADOS = 5000  # por tipo; passou disso, saem os que vencem primeiro
SCRY_GRAVAR_DEPOIS = 5     # segundos: junta várias respostas numa gravação só


class MemoriaEmDisco:
    """Respostas do Scryfall guardadas num arquivo JSON, para não perguntar de novo depois de fechar o
    programa. {"versao": 1, tipo: {chave: [vence_em (time.time), valor]}}. Arquivo estragado ou de
    outra versão: começa do zero, sem erro. A gravação é feita numa cópia que depois substitui o arquivo."""

    VERSAO = 1

    def __init__(self, caminho=None, agora=time.time):
        self._caminho = caminho  # None = scryfall.json na pasta do programa (config.app_dir)
        self._agora = agora
        self._trava = threading.Lock()
        self._dados = None
        self._mudou = False
        self._timer = None

    def caminho(self):
        if self._caminho is None:
            from buscador.config import app_dir
            self._caminho = os.path.join(app_dir(), "scryfall.json")
        return self._caminho

    def _carregar(self):
        if self._dados is not None:
            return
        try:
            with open(self.caminho(), encoding="utf-8") as f:
                dados = json.load(f)
            if not isinstance(dados, dict) or dados.get("versao") != self.VERSAO:
                raise ValueError("versão diferente")
        except (OSError, ValueError):
            dados = {}
        self._dados = {k: v for k, v in dados.items() if k != "versao" and isinstance(v, dict)}

    def pegar(self, tipo, chave):
        """O valor guardado, ou None se não houver (ou já venceu)."""
        with self._trava:
            self._carregar()
            item = self._dados.get(tipo, {}).get(chave)
            if not (isinstance(item, list) and len(item) == 2 and isinstance(item[0], (int, float))):
                return None
            if item[0] <= self._agora():
                return None
            return item[1]

    def guardar(self, tipo, chave, valor, dias):
        with self._trava:
            self._carregar()
            grupo = self._dados.setdefault(tipo, {})
            grupo[chave] = [self._agora() + dias * 86400, valor]
            if len(grupo) > SCRY_MAX_GUARDADOS:
                for k in sorted(grupo, key=lambda k: grupo[k][0])[: len(grupo) - SCRY_MAX_GUARDADOS]:
                    del grupo[k]
            self._agendar()

    def esquecer(self, tipo, chave):
        with self._trava:
            self._carregar()
            if self._dados.get(tipo, {}).pop(chave, None) is not None:
                self._agendar()

    def _agendar(self):
        self._mudou = True
        if self._timer is None:
            self._timer = threading.Timer(SCRY_GRAVAR_DEPOIS, self.gravar)
            self._timer.daemon = True
            self._timer.start()

    def gravar(self):
        """Grava no disco, se algo mudou. Também chamada ao fechar o programa."""
        with self._trava:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            if not self._mudou or self._dados is None:
                return
            agora = self._agora()
            dados = {"versao": self.VERSAO}
            for tipo, grupo in self._dados.items():
                dados[tipo] = {k: v for k, v in grupo.items() if v[0] > agora}
            temp = self.caminho() + ".tmp"
            try:
                with open(temp, "w", encoding="utf-8") as f:
                    json.dump(dados, f, ensure_ascii=False, separators=(",", ":"))
                os.replace(temp, self.caminho())
                self._mudou = False
            except OSError:
                pass  # sem como gravar (pasta só de leitura?): segue só com a memória


DISCO = MemoriaEmDisco()
atexit.register(lambda: DISCO.gravar())


def scry_get(path, params, urgente=True):
    """Uma consulta ao Scryfall, no ritmo pedido por ele. Em pausa depois de um 429: ScryfallEmPausa."""
    RITMO.vez(SCRY_INTERVALO_CARTAS if path.startswith("/cards/") else SCRY_INTERVALO_OUTROS, urgente)
    r = requests.get(SCRY_API + path, params=params, headers=SCRY_HEADERS, timeout=10)
    if r.status_code == 429:
        RITMO.pausar(SCRY_PAUSA_429)
    return r


def add_names(names, text):
    n = norm(text or "")
    if not n:
        return
    names.add(n)
    for part in n.split("//"):  # cartas de duas faces: aceita cada face
        if part.strip():
            names.add(part.strip())


def matches_exact(item_name, names):
    base = norm(strip_suffix(item_name))
    parts = [p.strip() for p in re.split(r"/+", base) if p.strip()]  # "Nome PT / Nome EN" ou "A // B"
    return base in names or any(p in names for p in parts)


def english_for_portuguese(card, cards):
    """Nome em inglês da carta cujo nome em português é EXATAMENTE o digitado; None se nenhuma ou várias.

    A busca do Scryfall por "Thalia" em português traz todas as cartas que CONTÊM a palavra
    ("Thalia e O Monstro Gitrog", "Tenente de Thalia"...). Antes o programa ficava com a primeira da
    lista, uma escolha quase ao acaso; agora só aceita a carta se o nome em português bater por inteiro.
    """
    wanted = norm(card)
    found = set()
    for c in cards:
        printed = [c.get("printed_name")] + [f.get("printed_name") for f in c.get("card_faces", []) or []]
        if any(p and norm(p) == wanted for p in printed) and c.get("name"):
            found.add(c["name"])
    return found.pop() if len(found) == 1 else None


_nomes = {}  # nomes já resolvidos nesta execução (o Scryfall pede para guardar as respostas)


def resolve_names(card, urgente=True):
    """Devolve (conjunto de nomes aceitos, scryfall_respondeu). Sempre inclui o texto digitado.

    urgente=False: consulta sem pressa (os nomes da busca de lista), que espera as urgentes passarem.
    Respostas boas ficam guardadas na memória e no disco (DISCO).
    """
    chave = norm(card or "")
    if chave in _nomes:
        return set(_nomes[chave]), True
    guardados = DISCO.pegar("nomes", chave) if chave else None
    if isinstance(guardados, list):
        _nomes[chave] = set(guardados)
        return set(guardados), True
    names, ok, achou = _resolve_names(card, urgente)
    if ok:
        _nomes[chave] = set(names)
        if chave:  # achou: o Scryfall reconheceu a carta; senão, pode ser carta nova e vale só 1 dia
            DISCO.guardar("nomes", chave, sorted(names), SCRY_DIAS if achou else SCRY_DIAS_SEM_RESPOSTA)
    return names, ok


def _resolve_names(card, urgente):
    """(nomes, o Scryfall respondeu, o Scryfall reconheceu a carta)."""
    names = set()
    add_names(names, card)
    try:
        english = None
        r = scry_get("/cards/named", {"fuzzy": card}, urgente)
        if r.status_code == 200:
            english = r.json().get("name")
        else:  # nome ambíguo, com erro de digitação ou em português
            r2 = scry_get("/cards/search", {"q": f'"{card}" lang:pt', "include_multilingual": "true",
                                            "unique": "prints"}, urgente)
            if r2.status_code == 200:
                english = english_for_portuguese(card, r2.json().get("data", []))
        if english:
            add_names(names, english)
            r3 = scry_get("/cards/search", {"q": f'!"{english}" lang:pt', "include_multilingual": "true",
                                            "unique": "prints"}, urgente)
            if r3.status_code == 429:  # sem os nomes em português: não guarda como resposta boa
                return names, False, True
            if r3.status_code == 200:
                for c in r3.json().get("data", []):
                    add_names(names, c.get("printed_name"))
                    for face in c.get("card_faces", []) or []:
                        add_names(names, face.get("printed_name"))
        return names, True, bool(english)
    except (requests.RequestException, ValueError):
        return names, False, False


# ---- arte da carta (ao passar o mouse) ---------------------------------------------------------
# Para mostrar a arte da edição certa, a edição é procurada no Scryfall pelo nome ("Magic 2012"; com e
# sem o que vem entre parênteses) e pelo código do ícone da loja ("afc"; também sem números no fim:
# "sld107" -> "sld"). Algumas edições as lojas escrevem em português; aí vale o código. Se nada servir,
# fica a arte da carta numa edição qualquer. Cada carta/edição é consultada uma vez por execução (fica
# guardada aqui), e as consultas passam uma por vez (trava), no ritmo de scry_get.

_arte_trava = threading.Lock()
_artes = {}       # (nome, edição) normalizados -> endereço da imagem ("" = o Scryfall não tem)
_edicoes = None   # nome normalizado da edição -> código ("m12"), lido uma vez de /sets
_codigos = set()  # códigos de edição que o Scryfall conhece


def card_query_name(item_name):
    """Nome para o Scryfall a partir do nome na loja: 'Ilha / Island (#266)' -> 'Island'.

    " / " separa o nome em português do nome em inglês; "A // B" (carta de duas faces) fica inteiro.
    """
    base = strip_suffix(item_name)
    partes = [p.strip() for p in re.split(r"\s/\s", base) if p.strip()]
    return partes[-1] if partes else base


def card_image(card):
    """Endereço da imagem "normal" (488×680) da carta; nas de duas faces, a da frente. "" se não houver."""
    uris = card.get("image_uris") or ((card.get("card_faces") or [{}])[0] or {}).get("image_uris") or {}
    url = uris.get("normal") or ""
    return url if url.startswith("https://") else ""


def set_codes(edition, code=""):
    """Códigos do Scryfall que podem ser a edição (no máximo 2, do mais provável ao menos).
    Lê a lista de edições uma vez."""
    global _edicoes, _codigos
    if not edition and not code:
        return []
    if _edicoes is None:
        guardadas = DISCO.pegar("edicoes", "todas")
        if isinstance(guardadas, dict) and isinstance(guardadas.get("nomes"), dict):
            _edicoes, _codigos = guardadas["nomes"], set(guardadas.get("codigos") or [])
        else:
            r = scry_get("/sets", {})
            if r.status_code != 200:
                return []  # tenta de novo na próxima vez
            dados = [s for s in r.json().get("data", []) if s.get("code")]
            _edicoes = {norm(s["name"]): s["code"] for s in dados if s.get("name")}
            _codigos = {s["code"] for s in dados}
            DISCO.guardar("edicoes", "todas", {"nomes": _edicoes, "codigos": sorted(_codigos)}, SCRY_DIAS_EDICOES)
    achados = [_edicoes.get(norm(edition or "")), _edicoes.get(norm(strip_suffix(edition or "")))]
    code = (code or "").lower()
    achados += [c for c in (code, re.sub(r"\d+$", "", code)) if c in _codigos]
    return list(dict.fromkeys(c for c in achados if c))[:2]


def _buscar_carta(nome, edicao, codigo=""):
    for code in set_codes(edicao, codigo):
        r = scry_get("/cards/named", {"exact": nome, "set": code})
        if r.status_code == 200:
            return r.json()
    r = scry_get("/cards/named", {"fuzzy": nome})
    if r.status_code == 200:
        return r.json()
    # nome só em português: descobre o nome em inglês e tenta de novo
    r = scry_get("/cards/search", {"q": f'"{nome}" lang:pt', "include_multilingual": "true", "unique": "prints"})
    english = english_for_portuguese(nome, r.json().get("data", [])) if r.status_code == 200 else None
    if english and norm(english) != norm(nome):
        return _buscar_carta(english, edicao, codigo)
    return None


def card_art(item_name, edition="", code=""):
    """Endereço da imagem da carta (da edição, se o Scryfall a conhecer). "" se não houver.

    Falha de rede não fica guardada: a pessoa pode passar o mouse de novo para tentar.
    """
    chave = (norm(item_name or ""), norm(edition or ""), (code or "").lower())
    if not chave[0] or requests is None:
        return ""
    with _arte_trava:
        if chave in _artes:
            return _artes[chave]
        guardada = DISCO.pegar("artes", "|".join(chave))
        if isinstance(guardada, str):
            _artes[chave] = guardada
            return guardada
        try:
            carta = _buscar_carta(card_query_name(item_name), edition, code)
        except (requests.RequestException, ValueError):
            return ""
        _artes[chave] = card_image(carta) if carta else ""
        DISCO.guardar("artes", "|".join(chave), _artes[chave], SCRY_DIAS if _artes[chave] else SCRY_DIAS_SEM_RESPOSTA)
        return _artes[chave]


def forget_art(item_name, edition="", code=""):
    """A imagem guardada não abriu (o endereço mudou?): esquece, para consultar de novo."""
    chave = (norm(item_name or ""), norm(edition or ""), (code or "").lower())
    with _arte_trava:
        _artes.pop(chave, None)
    DISCO.esquecer("artes", "|".join(chave))
