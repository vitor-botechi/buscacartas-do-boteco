"""Configuração: lojas padrão, modelo da URL de busca, limites de requisição e pasta do programa."""

import os
import sys


# Lojas que já vêm no programa. Para incluir mais por padrão, basta adicionar aqui.
DEFAULT_STORES = [
    {"name": "Overrun", "url": "https://www.overrun.com.br"},
    {"name": "Jackpot Jogos", "url": "https://www.jackpotjogos.com.br"},
    {"name": "Legacy TCG", "url": "https://www.legacytcg.com.br"},
    {"name": "Deckmaster Games", "url": "https://www.deckmastergames.com.br"},
]

# Padrão de busca das lojas LigaMagic: só itens COM ESTOQUE, do menor para o maior
# preço, 120 por página. Se alguma loja usar outro formato, mude este modelo.
SEARCH_PATH = "/?view=ecom/itens&busca={query}&txt_estoque=1&txt_order=3&txt_limit=120&page={page}"
PAGE_SIZE = 120
MAX_PAGES = 3

# Detalhes automáticos (edições e preços sem precisar clicar). Valores conservadores de propósito:
DEFAULT_AUTO_LIMIT = 5      # só detalha sozinho quando a loja tem até N itens
MAX_AUTO_LIMIT = 10         # teto do controle na tela
AUTO_TOTAL_CAP = 24         # no máximo N páginas de produto por busca, somando todas as lojas
AUTO_DELAY = 0.8            # segundos entre páginas da MESMA loja (mais um pouco de aleatoriedade)
CACHE_TTL = 300             # segundos que uma página de produto lida fica guardada
HISTORY_MAX = 10            # quantas buscas o Voltar/Avançar lembram
STALE_AFTER = 30 * 60       # resultados guardados mais velhos que isto (30 min) são refeitos ao voltar/avançar
DETAIL_W = 560              # largura do painel de edições e preços (a janela cresce isso ao abri-lo)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}
TIMEOUT = 15
MAX_ITEMS_PER_STORE = 8


def app_dir():
    if getattr(sys, "frozen", False):  # quando virar .exe com PyInstaller
        return os.path.dirname(sys.executable)
    # este arquivo fica em buscador/; a pasta do programa é a de cima
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


CONFIG_FILE = os.path.join(app_dir(), "lojas.json")
SETTINGS_FILE = os.path.join(app_dir(), "config.json")
