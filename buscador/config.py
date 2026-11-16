"""Configuração: lojas padrão, modelo da URL de busca, limites de requisição e pasta de dados."""

import os
import shutil
import sys


# Lojas que já vêm no programa. Para incluir mais por padrão, basta adicionar aqui.
# color: cor principal da loja (do logotipo ou do site), usada no destaque do cartão de resultados
DEFAULT_STORES = [
    {"name": "Deckmaster Games", "url": "https://www.deckmastergames.com.br", "color": "#00758f"},
    {"name": "Overrun", "url": "https://www.overrun.com.br", "color": "#8b1418"},
    {"name": "Jackpot Jogos", "url": "https://www.jackpotjogos.com.br", "color": "#00a443"},
    {"name": "Legacy TCG", "url": "https://www.legacytcg.com.br", "color": "#0b3d63"},
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


DATA_FILES = ("lojas.json", "config.json")


def user_data_dir():
    """Pasta de dados do usuário no Windows: %APPDATA%/BuscadorMTG."""
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "BuscadorMTG")


def app_dir():
    """Pasta onde o programa guarda lojas.json, config.json e debug/.

    - Pelo código-fonte: a pasta do projeto (a de cima de buscador/), como sempre foi.
    - No .exe (PyInstaller): %APPDATA%/BuscadorMTG. Assim o .exe funciona de qualquer lugar
      (Downloads, Área de Trabalho, de dentro de um zip) e as lojas e preferências continuam
      ao trocar por uma versão nova."""
    if getattr(sys, "frozen", False):
        return user_data_dir()
    # este arquivo fica em buscador/; a pasta do programa é a de cima
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def migrate_from_exe_folder(exe_dir, data_dir):
    """Até a versão 0.3.0 o .exe guardava lojas.json e config.json ao lado dele. Se a pasta de
    dados ainda não tem esses arquivos e a pasta do .exe tem, copia (não apaga os antigos)."""
    try:
        os.makedirs(data_dir, exist_ok=True)
        for name in DATA_FILES:
            old, new = os.path.join(exe_dir, name), os.path.join(data_dir, name)
            if os.path.isfile(old) and not os.path.exists(new):
                shutil.copy2(old, new)
    except OSError:
        pass  # sem permissão: o programa abre com as lojas padrão, como numa primeira vez


if getattr(sys, "frozen", False):
    migrate_from_exe_folder(os.path.dirname(sys.executable), app_dir())

CONFIG_FILE = os.path.join(app_dir(), "lojas.json")
SETTINGS_FILE = os.path.join(app_dir(), "config.json")
