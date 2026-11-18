"""Lado Python da interface HTML: a página chama os métodos públicos da Ponte.

Regras (as mesmas da interface Tkinter):
- Cada busca recebe um search_id (sid). Ao iniciar outra busca, ou ao cancelar, o sid aumenta e o
  AutoCtl da busca anterior é parado; a página ignora acontecimentos com sid antigo.
- Acontecimentos da busca vão para a página por app.evento(tipo, sid, dados). Tipos: result, names,
  offers, autostart, autostep, autoend, autostop.
- O pywebview roda cada chamada da página numa thread própria, por isso "detalhes" e "nomes_exatos"
  podem esperar a resposta da loja sem travar a janela.
- Atributos começam com "_" para o pywebview não expô-los à página.
"""

import json
import sys
import threading
import time
import webbrowser
from concurrent.futures import ThreadPoolExecutor

from buscador import __version__
from buscador.armazenamento import (
    default_name,
    host_key,
    load_settings,
    load_stores,
    normalize_base,
    save_settings,
    save_stores,
)
from buscador.automatico import AutoCtl, auto_details, load_items
from buscador.config import (
    AUTO_TOTAL_CAP,
    BLOCK_COOLDOWN,
    DEFAULT_AUTO_LIMIT,
    HISTORY_MAX,
    MAX_AUTO_LIMIT,
    MAX_ITEMS_PER_STORE,
    STALE_AFTER,
)
from buscador.lojas.ligamagic import build_search_url
from buscador.rede import HAS_SCRAPING, fetch_product, fetch_store_look, safe_search
from buscador.scryfall import card_art, matches_exact, resolve_names
from buscador.texto import clean_card_name, norm
from buscador.web import serializar


def ler_area_de_transferencia():
    """Texto copiado (Windows). Devolve None fora do Windows: aí a página tenta pelo navegador."""
    if sys.platform != "win32":
        return None
    import ctypes

    u, k = ctypes.windll.user32, ctypes.windll.kernel32
    u.GetClipboardData.restype = ctypes.c_void_p
    k.GlobalLock.restype = ctypes.c_void_p
    k.GlobalLock.argtypes = [ctypes.c_void_p]
    k.GlobalUnlock.argtypes = [ctypes.c_void_p]
    if not u.OpenClipboard(None):
        return ""
    try:
        h = u.GetClipboardData(13)  # CF_UNICODETEXT
        if not h:
            return ""
        p = k.GlobalLock(h)
        if not p:
            return ""
        try:
            return ctypes.wstring_at(p)
        finally:
            k.GlobalUnlock(h)
    finally:
        u.CloseClipboard()


def primeira_linha_limpa(texto):
    return clean_card_name(next((ln for ln in (texto or "").splitlines() if ln.strip()), ""))


class Ponte:
    def __init__(self, janela=None):
        self._janela = janela
        self._lock = threading.Lock()
        self._sid = 0
        self._ctl = None
        self._lojas = load_stores()
        self._carta = ""
        self._resultados = {}  # url da loja -> StoreResult da busca atual
        self._nomes = None  # nomes aceitos pelo "Apenas nome exato" na busca atual
        self._postar = None  # como a busca atual manda as edições carregadas para a página
        self._carregando = set()  # lojas com "Carregar todos os preços" em andamento
        self._sid_busca = 0  # busca a que _resultados pertence
        self._bloqueio_em = None  # quando uma loja limitou as requisições nesta busca (time.monotonic)

    # ---- envio para a página ---------------------------------------------------
    def _enviar(self, tipo, sid, dados):
        if self._janela is None:
            return
        js = f"window.app && app.evento({json.dumps(tipo)}, {sid}, {json.dumps(dados, ensure_ascii=False)})"
        try:
            self._janela.evaluate_js(js)
        except Exception:  # noqa: BLE001 - janela fechando: nada a fazer
            pass

    # ---- início e preferências -------------------------------------------------
    def iniciar(self):
        return {
            "versao": __version__,
            "lojas": [serializar.loja(s) for s in self._lojas],
            "auto_limite": self._auto_limite_salvo(),
            "auto_max": MAX_AUTO_LIMIT,
            "itens_por_loja": MAX_ITEMS_PER_STORE,
            "historico_max": HISTORY_MAX,
            "velho_depois": STALE_AFTER,
            "tem_bibliotecas": HAS_SCRAPING,
            "pausa_bloqueio": BLOCK_COOLDOWN,
        }

    @staticmethod
    def _auto_limite_salvo():
        try:
            v = int(load_settings().get("auto_limit", DEFAULT_AUTO_LIMIT))
        except (TypeError, ValueError):
            v = DEFAULT_AUTO_LIMIT
        return max(0, min(MAX_AUTO_LIMIT, v))

    def salvar_auto_limite(self, valor):
        try:
            v = max(0, min(MAX_AUTO_LIMIT, int(valor)))
        except (TypeError, ValueError):
            v = DEFAULT_AUTO_LIMIT
        data = load_settings()
        data["auto_limit"] = v
        save_settings(data)
        return v

    # ---- lojas -------------------------------------------------------------------
    def marcar_lojas(self, marcadas):
        """marcadas: {url: true/false}."""
        for s in self._lojas:
            if s["url"] in marcadas:
                s["enabled"] = bool(marcadas[s["url"]])
        save_stores(self._lojas)
        return [serializar.loja(s) for s in self._lojas]

    def ordenar_lojas(self, urls):
        """Nova ordem das lojas (arrastadas na lista), na mesma ordem das próximas buscas."""
        pos = {u: i for i, u in enumerate(urls or [])}
        with self._lock:
            self._lojas.sort(key=lambda s: pos.get(s["url"], len(pos)))
            save_stores(self._lojas, manual_order=True)
            return [serializar.loja(s) for s in self._lojas]

    def adicionar_loja(self, link, nome=""):
        try:
            base = normalize_base(link or "")
        except ValueError:
            return {"erro": "Isso não parece o link de um site. Exemplo: www.minhaloja.com.br"}
        if any(host_key(s["url"]) == host_key(base) for s in self._lojas):
            return {"erro": "Essa loja já está na lista."}
        ok, cor, logo = fetch_store_look(base)  # confere o site e lê cor e logo, para o cartão
        if not ok:
            return {"erro": f"Não consegui acessar {base}. Confira se o link está certo."}
        with self._lock:
            if any(host_key(s["url"]) == host_key(base) for s in self._lojas):
                return {"erro": "Essa loja já está na lista."}
            self._lojas.append({"name": (nome or "").strip() or default_name(base),
                                "url": base, "builtin": False, "enabled": True,
                                "color": cor or "", "logo": logo or ""})
        save_stores(self._lojas)
        return {"lojas": [serializar.loja(s) for s in self._lojas]}

    def remover_loja(self, url):
        self._lojas = [s for s in self._lojas if s["builtin"] or s["url"] != url]
        save_stores(self._lojas)
        return [serializar.loja(s) for s in self._lojas]

    def _marcadas(self):
        return [s for s in self._lojas if s["enabled"]]

    # ---- utilidades --------------------------------------------------------------
    def colar(self):
        """Primeira linha do texto copiado, limpa. None = a página deve tentar ler sozinha."""
        texto = ler_area_de_transferencia()
        return None if texto is None else primeira_linha_limpa(texto)

    def limpar_nome(self, texto):
        return primeira_linha_limpa(texto)

    def abrir(self, urls):
        for u in urls if isinstance(urls, list) else [urls]:
            if isinstance(u, str) and u.startswith(("http://", "https://")):
                webbrowser.open_new_tab(u)

    def abrir_lojas(self, carta):
        """Abre a busca da carta nas lojas marcadas, no navegador."""
        carta = clean_card_name(carta or "")
        if carta:
            self.abrir([build_search_url(s["url"], carta) for s in self._marcadas()])

    # ---- busca -------------------------------------------------------------------
    def cancelar(self):
        """Interrompe a busca em andamento; acontecimentos atrasados passam a ser ignorados."""
        with self._lock:
            self._sid += 1
            if self._ctl:
                self._ctl.stop.set()
            return self._sid

    def buscar(self, carta, exato, limite):
        """Começa a busca nas lojas marcadas. Devolve {sid, lojas} ou {erro}."""
        carta = clean_card_name(carta or "")
        lojas = self._marcadas()
        if not carta:
            return {"erro": "Digite o nome da carta."}
        if not lojas:
            return {"erro": "Marque ao menos uma loja."}
        if not HAS_SCRAPING:
            return {"erro": "sem_bibliotecas"}
        try:
            limite = max(0, min(MAX_AUTO_LIMIT, int(limite)))
        except (TypeError, ValueError):
            limite = DEFAULT_AUTO_LIMIT

        with self._lock:
            if self._ctl:
                self._ctl.stop.set()  # a busca anterior não precisa mais carregar detalhes
            self._sid += 1
            sid = self._sid
            self._carta = carta
            self._resultados = {}
            self._nomes = None
            self._ctl = ctl = AutoCtl(AUTO_TOTAL_CAP)
            self._carregando = set()
            self._sid_busca = sid
            self._bloqueio_em = None

        caixa_nomes = {"names": None}
        nomes_prontos = threading.Event()

        def postar(tipo, dados):
            if tipo == "offers":
                loja_url, item_url, ofs = dados
                with self._lock:
                    res = self._resultados.get(loja_url) if sid == self._sid else None
                    if res:
                        for it in res.items:
                            if it.url == item_url:
                                it.offers = ofs
                dados = (loja_url, item_url, serializar.ofertas(ofs))
            elif tipo == "autostop":
                with self._lock:
                    if sid == self._sid:
                        self._bloqueio_em = time.monotonic()  # conta a pausa a partir daqui
                dados = {"loja": dados, "pausa": BLOCK_COOLDOWN}
            self._enviar(tipo, sid, dados)

        with self._lock:
            if sid == self._sid:
                self._postar = postar  # o botão "Carregar todos os preços" usa o mesmo caminho

        def nomes_job():
            nomes, ok = resolve_names(carta)
            caixa_nomes["names"] = nomes
            nomes_prontos.set()
            self._publicar_nomes(sid, nomes, ok)

        def loja_job(loja):
            res = safe_search(loja, carta)
            with self._lock:
                if sid != self._sid:
                    return
                self._resultados[loja["url"]] = res
                nomes = self._nomes
            self._enviar("result", sid, serializar.resultado(res, nomes))
            if limite > 0 and res.status == "found":
                try:
                    auto_details(res, limite, ctl, exato, caixa_nomes, nomes_prontos, postar)
                except Exception:  # noqa: BLE001 - detalhes são um extra; nunca derrubam a busca
                    pass

        def trabalho():
            with ThreadPoolExecutor(max_workers=max(6, len(lojas))) as ex:
                for loja in lojas:
                    ex.submit(loja_job, loja)

        if exato:
            threading.Thread(target=nomes_job, daemon=True).start()
        else:
            nomes_prontos.set()
        threading.Thread(target=trabalho, daemon=True).start()
        return {"sid": sid, "carta": carta,
                "lojas": [{**serializar.aparencia(s), "nome": s["name"], "url": s["url"],
                           "url_busca": build_search_url(s["url"], carta)}
                          for s in lojas]}

    def carregar_loja(self, loja_url, item_urls):
        """Botão "Carregar todos os preços" de uma loja: lê as páginas dos itens pedidos, uma por vez,
        no mesmo ritmo e com o mesmo freio dos detalhes automáticos (até AUTO_TOTAL_CAP por clique).

        Os resultados chegam como os automáticos (autostart, offers, autostep, autoend, autostop).
        Devolve {total, restantes} ou {erro}.
        """
        with self._lock:
            res = self._resultados.get(loja_url) if self._sid == self._sid_busca else None
            ctl, postar = self._ctl, self._postar
            if res is None or ctl is None or postar is None:
                return {"erro": "Faça a busca de novo para carregar os preços."}
            if ctl.stop.is_set():
                # parado por bloqueio: depois da pausa, a pessoa pode tentar de novo (com um orçamento novo)
                if self._bloqueio_em is None:
                    return {"erro": "Faça a busca de novo para carregar os preços."}
                falta = self._falta_pausa()
                if falta:
                    return {"erro": f"Uma loja limitou as requisições. Tente novamente em {falta} s.",
                            "espera": falta}
                self._ctl = ctl = AutoCtl(AUTO_TOTAL_CAP)  # nova busca ou cancelar param este também
                self._bloqueio_em = None
            if loja_url in self._carregando:
                return {"total": 0, "restantes": 0}
            pedidos = set(item_urls or [])
            # só itens desta busca e desta loja, ainda sem edições, na ordem da lista (menor preço primeiro)
            faltam = [it for it in res.items if it.url in pedidos and it.offers is None]
            todo = faltam[:AUTO_TOTAL_CAP]
            if not todo:
                return {"total": 0, "restantes": 0}
            self._carregando.add(loja_url)
            carregando = self._carregando

        lote = AutoCtl(AUTO_TOTAL_CAP, stop=ctl.stop)  # nova busca ou bloqueio param este lote também

        def trabalho():
            try:
                load_items(res.store, todo, lote, postar)
            except Exception:  # noqa: BLE001 - um extra; nunca derruba o programa
                pass
            finally:
                with self._lock:
                    carregando.discard(loja_url)

        threading.Thread(target=trabalho, daemon=True).start()
        return {"total": len(todo), "restantes": len(faltam) - len(todo)}

    def _publicar_nomes(self, sid, nomes, ok):
        """Guarda os nomes exatos e manda para a página quais itens de cada loja batem com eles."""
        with self._lock:
            if sid != self._sid:
                return None
            self._nomes = nomes
            marcas = {url: [serializar.item(i, nomes)["exato"] for i in res.items]
                      for url, res in self._resultados.items()}
        dados = {"nomes": sorted(nomes), "ok": ok, "marcas": marcas}
        self._enviar("names", sid, dados)
        return dados

    def nomes_exatos(self, carta, lojas):
        """A pessoa marcou "Apenas nome exato" depois da busca (ou numa busca do histórico).
        lojas: {url da loja: [nomes dos itens]}. Devolve {nomes, ok, marcas: {url: [bate?]}}."""
        nomes, ok = resolve_names(carta)
        with self._lock:
            if norm(carta) == norm(self._carta):
                self._nomes = nomes  # resultados que ainda chegarem desta busca já vêm marcados
        marcas = {url: [matches_exact(n, nomes) for n in itens] for url, itens in (lojas or {}).items()}
        return {"nomes": sorted(nomes), "ok": ok, "marcas": marcas}

    def arte(self, nome, edicao="", codigo=""):
        """Imagem da carta para mostrar ao passar o mouse (Scryfall). Devolve {url} ("" se não houver)."""
        if not HAS_SCRAPING:
            return {"url": ""}
        return {"url": card_art(nome, edicao, codigo)}

    # ---- detalhes de um produto (sob demanda) ---------------------------------------
    def detalhes(self, loja_url, item_url):
        """Lê a página de um produto ("Ver edições e preços"). Devolve {status, ofertas, msg}.

        Segue a mesma pausa do "Carregar todos os preços": durante ela devolve status "espera" (com os
        segundos que faltam), e um bloqueio aqui também começa a pausa (status "blocked", com "pausa").
        """
        with self._lock:
            falta = self._falta_pausa()
        if falta:
            return {"status": "espera", "espera": falta, "msg": "", "ofertas": []}
        loja = next((s for s in self._lojas if s["url"] == loja_url), None) or {"name": "", "url": loja_url}
        data = fetch_product(loja, item_url)
        resposta = {"status": data.get("status"), "msg": data.get("msg", ""),
                    "ofertas": serializar.ofertas(data.get("offers") or [])}
        with self._lock:
            res = self._resultados.get(loja_url)
            if res and data.get("status") == "ok":
                for it in res.items:
                    if it.url == item_url:
                        it.offers = data["offers"]
            if data.get("status") == "blocked":  # a loja limitou: pausa tudo, como nos automáticos
                if self._ctl:
                    self._ctl.stop.set()
                self._bloqueio_em = time.monotonic()
                resposta["pausa"] = BLOCK_COOLDOWN
        return resposta

    def _falta_pausa(self):
        """Segundos que faltam da pausa depois de um bloqueio (0 = liberado). Chamar com o _lock."""
        if self._bloqueio_em is None:
            return 0
        falta = BLOCK_COOLDOWN - (time.monotonic() - self._bloqueio_em)
        return int(falta) + 1 if falta > 0 else 0
