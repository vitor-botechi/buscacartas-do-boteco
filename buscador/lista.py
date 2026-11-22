"""Busca de uma lista inteira de cartas: leitura da lista colada e a busca, carta por carta, em cada loja.

Ritmo próprio, mais lento que o da busca de uma carta (ver config.LISTA_*): em cada loja, uma requisição
por vez, com pausa entre elas; as lojas andam ao mesmo tempo (são sites diferentes). Por carta: uma busca
(só a primeira página) e, para os itens com o nome exato, a página do produto (onde preço e unidades estão
em texto), no máximo LISTA_ITENS_POR_CARTA. Se uma loja der sinal de bloqueio, só ela para (Freio):
espera (LISTA_RETOMAR), tenta sozinha de novo e passa a ir mais devagar; depois da última espera,
desiste e as cartas que faltavam nela ficam como "não verificada". As outras lojas continuam.
"""

import math
import random
import re
import threading
import time

from buscador.config import (
    LISTA_ITENS_POR_CARTA,
    LISTA_PAUSA,
    LISTA_PAUSA_MAX,
    LISTA_PAUSA_PASSO,
    LISTA_RETOMAR,
)
from buscador.rede import fetch_product, safe_search
from buscador.scryfall import matches_exact
from buscador.texto import clean_card_name, is_art_card, norm

# ---- leitura da lista ----------------------------------------------------------------------------

# títulos de seção das listas exportadas (Arena, MTGO, Moxfield, LigaMagic...): não são cartas
SECAO_RE = re.compile(
    r"^(deck|main ?deck|main ?board|mainboard|sideboard|side ?board|side|commander|commanders|comandante|"
    r"companion|companheiro|maybeboard|maybe|considering|tokens?|lands?|terrenos?|"
    r"criaturas?|creatures?|instants?|m[aá]gicas? instant[aâ]neas?|sorceries|sorcery|feiti[cç]os?|"
    r"artifacts?|artefatos?|enchantments?|encantamentos?|planeswalkers?|batalhas?|battles?|outros?|others?)"
    r"\s*:?\s*(\(\d+\))?\s*:?$", re.I)
QTD_RE = re.compile(r"^(\d{1,3})\s*[xX]?\s+(.+)$|^(\d{1,3})[xX](\S.*)$")
QTD_FIM_RE = re.compile(r"^(.+?)\s+[xX]?(\d{1,3})[xX]?$")  # "Lightning Bolt x4"

BASICOS = {norm(n) for n in (
    "Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes",
    "Snow-Covered Plains", "Snow-Covered Island", "Snow-Covered Swamp", "Snow-Covered Mountain",
    "Snow-Covered Forest", "Snow-Covered Wastes",
    "Planície", "Ilha", "Pântano", "Montanha", "Floresta", "Ermos",
)}


def limpar_linha(nome):
    """Tira da linha o que não é o nome da carta: edição, número de coleção, foil e marcações."""
    nome = re.sub(r"\^[^^]*\^", " ", nome)                 # Archidekt: ^Have,#37d67a^
    nome = re.sub(r"\[[^\]]*\]", " ", nome)                # [C21], [Ramp]
    nome = re.sub(r"\*[A-Za-z]{1,6}\*", " ", nome)         # *F*, *E*, *CMDR*
    nome = re.sub(r"\s#\S*", " ", nome)                    # #123, #!Commander
    nome = clean_card_name(nome)
    # (CMM) 410 / (cmm) / (PLST) LRW-256 / (SLD) 123★ no fim
    prev = None
    while prev != nome:
        prev = nome
        nome = re.sub(r"\s*\([A-Za-z0-9]{2,6}\)(\s+[\w★†-]+)?\s*$", "", nome).strip()
    nome = re.sub(r"\s+-\s*(foil|etched|non-?foil)\s*$", "", nome, flags=re.I)
    return nome.strip(" -–;,")


def ler_linha(linha):
    """(quantidade, nome) de uma linha; None se a linha não for uma carta (título, comentário, vazia)."""
    linha = clean_card_name(linha)
    if not linha or linha.startswith(("//", "#")):
        return None
    linha = re.sub(r"^SB:\s*", "", linha, flags=re.I)  # MTGO antigo: "SB: 2 Counterspell"
    if SECAO_RE.match(linha):
        return None
    qtd = 1
    m = QTD_RE.match(linha)
    if m:
        qtd, linha = int(m.group(1) or m.group(3)), (m.group(2) or m.group(4))
    else:
        m = QTD_FIM_RE.match(linha)
        if m and re.search(r"[xX]", linha[len(m.group(1)):]):  # só aceita "Nome x4" / "Nome 4x"
            qtd, linha = int(m.group(2)), m.group(1)
    nome = limpar_linha(linha)
    # sem nenhuma letra (ou só "4x"): não é carta
    if not re.search(r"[^\W\d_]", nome) or re.fullmatch(r"\d+\s*[xX]", nome) or qtd <= 0:
        return None
    return qtd, nome


def ler_lista(texto):
    """Lê a lista colada. Devolve {"cartas": [{qtd, nome, basico}], "ignoradas": [linhas]}.

    A mesma carta em várias linhas (deck e sideboard) soma; a ordem é a da primeira vez que aparece.
    "ignoradas" são as linhas com texto que não viraram carta, exceto títulos de seção conhecidos.
    """
    cartas, por_nome, ignoradas = [], {}, []
    for linha in (texto or "").splitlines():
        lida = ler_linha(linha)
        if lida is None:
            limpa = clean_card_name(linha)
            if limpa and not limpa.startswith(("//", "#")) and not SECAO_RE.match(re.sub(r"^SB:\s*", "", limpa, flags=re.I)):
                ignoradas.append(limpa)
            continue
        qtd, nome = lida
        k = norm(nome)
        if k in por_nome:
            por_nome[k]["qtd"] += qtd
        else:
            por_nome[k] = {"qtd": qtd, "nome": nome, "basico": k in BASICOS}
            cartas.append(por_nome[k])
    return {"cartas": cartas, "ignoradas": ignoradas}


def segundos_estimados(n_cartas):
    """Tempo aproximado da busca: as lojas andam juntas; em cada uma, ~2 páginas por carta."""
    return round(n_cartas * 2 * LISTA_PAUSA * 1.25)


# ---- busca ---------------------------------------------------------------------------------------

class Nomes:
    """Nomes aceitos de cada carta da lista (Scryfall), resolvidos uma vez, na ordem da lista,
    enquanto as lojas buscam. As lojas esperam o nome da carta que vão conferir."""

    def __init__(self, cartas, resolver, parar):
        self._cartas = cartas
        self._resolver = resolver
        self._parar = parar
        self._nomes = [None] * len(cartas)
        self._prontos = [threading.Event() for _ in cartas]

    def trabalhar(self, precisa=None):
        """precisa: índices das cartas que alguma loja vai buscar (None = todas); as outras ficam
        com o nome digitado, sem consultar o Scryfall."""
        for i, carta in enumerate(self._cartas):
            if self._parar.is_set():
                break
            if precisa is not None and i not in precisa:
                self._nomes[i] = {norm(carta)}
                self._prontos[i].set()
                continue
            try:
                nomes, _ok = self._resolver(carta)
            except Exception:  # noqa: BLE001 - sem Scryfall, vale o nome digitado
                nomes = {norm(carta)}
            self._nomes[i] = nomes
            self._prontos[i].set()
        for e in self._prontos:  # parou: ninguém fica esperando
            e.set()

    def de(self, i):
        self._prontos[i].wait(timeout=30)
        return self._nomes[i] or {norm(self._cartas[i])}


def esperar(segundos, parar, dormir=None):
    """Espera em pedacinhos, para parar logo quando a pessoa cancela. False se parou."""
    dormir = dormir or time.sleep
    falta = segundos
    while falta > 0:
        if parar.is_set():
            return False
        passo = min(0.25, falta)
        dormir(passo)
        falta -= passo
    return not parar.is_set()


class Freio:
    """Pausa e ritmo de UMA loja na busca da lista (cada loja tem o seu: o teste real mostrou que a
    proteção barra uma loja enquanto as outras seguem respondendo).

    Cada bloqueio novo usa a próxima espera de `retomar` e deixa a loja mais lenta dali em diante
    (`ritmo` sobe LISTA_PAUSA_PASSO, até LISTA_PAUSA_MAX): ela se ajusta ao limite da loja. Uma carta
    lida com sucesso depois da pausa volta as esperas para a primeira. Depois da última espera, desiste.
    agora: relógio em segundos (trocado nos testes).
    """

    def __init__(self, retomar=None, agora=None):
        self.retomar = tuple(LISTA_RETOMAR if retomar is None else retomar)
        self.agora = agora or time.monotonic
        self._lock = threading.Lock()
        self.ate = 0.0
        self.tentativa = 0
        self.desistiu = False
        self.ritmo = LISTA_PAUSA  # pausa mínima entre requisições desta loja (sorteada até 1,5x)

    def falta(self):
        """Segundos que faltam da pausa (sobra de arredondamento, menos de 0,01 s, conta como zero)."""
        with self._lock:
            falta = self.ate - self.agora()
            return falta if falta > 0.01 else 0.0

    def bloqueou(self):
        with self._lock:
            agora = self.agora()
            if self.ate - agora > 0.01 or self.desistiu:  # já em pausa
                return
            if self.tentativa >= len(self.retomar):
                self.desistiu = True
                return
            self.ate = agora + self.retomar[self.tentativa]
            self.tentativa += 1
            self.ritmo = min(LISTA_PAUSA_MAX, self.ritmo + LISTA_PAUSA_PASSO)

    def deu_certo(self):
        with self._lock:
            if self.ate <= self.agora():
                self.tentativa = 0


CANCELOU, FREIO = "cancelou", "freio"


def uma_carta(loja, carta, nomes, pausar):
    """Busca UMA carta numa loja. Devolve (StoreResult com só os itens de nome exato, bloqueou?).

    pausar(): a pausa antes de cada requisição; devolve True para seguir, CANCELOU (a pessoa cancelou:
    devolve (None, False)) ou FREIO (a loja está em pausa: devolve (None, True), para esperar e repetir).
    """
    def seguir():
        r = pausar()
        return r is True, (None, r == FREIO)

    ok, parar = seguir()
    if not ok:
        return parar
    res = safe_search(loja, carta, 1)
    if res.status == "blocked":
        return res, True
    if res.status != "found":
        return res, False
    res.items = [i for i in res.items if not is_art_card(i.name) and matches_exact(i.name, nomes)]
    if not res.items:
        res.status = "none"
        return res, False
    for it in [i for i in res.items if i.offers is None][:LISTA_ITENS_POR_CARTA]:
        ok, parar = seguir()
        if not ok:
            return parar
        data = fetch_product(loja, it.url)
        if data["status"] == "blocked":
            return res, True
        if data["status"] in ("ok", "empty"):
            it.offers = data["offers"]
    return res, False


def buscar_na_loja(loja, cartas, nomes, parar, postar, dormir=None, freio=None, indices=None):
    """Busca a lista inteira numa loja, carta por carta.

    freio: a pausa e o ritmo desta loja (Freio).
    indices: as cartas (posições em `cartas`) que esta loja ainda precisa buscar (None = todas). Ao
    editar a lista, as que já foram buscadas há pouco ficam de fora.
    postar(tipo, dados): "lista" (resultado de uma carta: {"i", "res"}), "listapausa" ({"segundos",
    "tentativa"}), "listaretoma", "listadesiste" ({"de": índice da primeira carta não verificada}) e
    "listafim".
    """
    freio = freio or Freio()
    primeira = [True]

    def pausar():
        if primeira[0]:
            primeira[0] = False
        elif not esperar(random.uniform(freio.ritmo, freio.ritmo * 1.5), parar, dormir):
            return CANCELOU
        if parar.is_set():
            return CANCELOU
        return FREIO if freio.falta() > 0 else True

    fila = list(range(len(cartas)) if indices is None else indices)
    k = 0
    while k < len(fila):
        i = fila[k]
        if parar.is_set():
            return
        if freio.desistiu:
            postar("listadesiste", {"de": i})
            return
        falta = freio.falta()
        if falta > 0:
            postar("listapausa", {"segundos": math.ceil(falta), "tentativa": freio.tentativa})
            if not esperar(falta, parar, dormir):
                return
            postar("listaretoma", {})
            primeira[0] = True  # depois da espera longa, a próxima requisição sai sem pausa curta
            continue
        res, bloqueou = uma_carta(loja, cartas[i], nomes.de(i), pausar)
        if bloqueou:
            if res is not None:
                freio.bloqueou()
            continue
        if res is None:
            return
        freio.deu_certo()
        postar("lista", {"i": i, "res": res})
        k += 1
    postar("listafim", {})
