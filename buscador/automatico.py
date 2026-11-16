"""Detalhes automáticos, com freios para não sobrecarregar as lojas nem ser bloqueado."""

import random
import threading
import time

from buscador.config import AUTO_DELAY
from buscador.rede import fetch_product
from buscador.scryfall import matches_exact


class AutoCtl:
    """Orçamento total de requisições da busca + freio de emergência compartilhado entre as lojas."""

    def __init__(self, cap, stop=None):
        """stop: freio de outro controle, para parar junto (ex.: o da busca)."""
        self.cap = cap
        self.lock = threading.Lock()
        self.stop = stop or threading.Event()

    def take(self):
        with self.lock:
            if self.cap <= 0:
                return False
            self.cap -= 1
            return True


def auto_details(res, limit, ctl, exact, names_box, names_ready, post):
    """Lê, uma por vez e devagar, as páginas dos itens de UMA loja (se forem poucos)."""
    items = res.items
    if exact:
        names_ready.wait(timeout=10)
        names = names_box.get("names")
        if names:
            items = [i for i in items if matches_exact(i.name, names)]
    todo = [i for i in items if i.offers is None]
    if not todo or len(items) > limit:
        return
    load_items(res.store, todo, ctl, post)


def load_items(store, todo, ctl, post):
    """Lê, uma por vez e devagar, as páginas de produto dos itens `todo` de uma loja.

    Usado pelos detalhes automáticos e pelo botão "Carregar todos os preços" da loja.
    """
    store_url = store["url"]
    post("autostart", (store_url, [i.url for i in todo]))
    done = 0
    try:
        for n, it in enumerate(todo):
            if ctl.stop.is_set() or not ctl.take():
                return
            time.sleep(0.3 if n == 0 else random.uniform(AUTO_DELAY, AUTO_DELAY * 1.5))
            data = fetch_product(store, it.url)
            done += 1
            status = data["status"]
            if status == "ok":
                post("offers", (store_url, it.url, data["offers"]))
            post("autostep", (store_url, it.url))
            if status in ("blocked", "error"):
                ctl.stop.set()  # qualquer sinal de bloqueio: todas as lojas param
                post("autostop", store["name"])
                return
            if status == "unreadable":
                return  # esta loja não entrega os números como texto: não adianta insistir
    finally:
        post("autoend", (store_url, [i.url for i in todo[done:]]))
