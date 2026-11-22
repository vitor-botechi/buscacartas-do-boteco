"""Configuração: lojas padrão, modelo da URL de busca, limites de requisição e pasta de dados."""

import os
import shutil
import sys


# Lojas que já vêm no programa. Para incluir mais por padrão, basta adicionar aqui.
# Aparência de cada loja no cartão de resultados, tirada da logo:
# color = cor principal (faixa, fundo e botões; escura o bastante para texto),
# color2 = segunda cor da logo (opcional), logo = endereço da logo no site da loja.
_LOGO = "https://repositorio.sbrauble.com/arquivos/up/ecom/logo/"
DEFAULT_STORES = [
    {"name": "Deckmaster Games", "url": "https://www.deckmastergames.com.br", "color": "#9b1219", "color2": "#e3c902",
     "logo": _LOGO + "631a2bcfac179-t24ac-2uvhb-1812612191631a2bcfac20d.jpg"},
    {"name": "Overrun", "url": "https://www.overrun.com.br", "color": "#8b1418",
     "logo": _LOGO + "628788f5e7069-ugon3-qys8u-1764028231628788f5e70b5.jpg"},
    {"name": "Jackpot Jogos", "url": "https://www.jackpotjogos.com.br", "color": "#00a443",
     "logo": _LOGO + "62bf4165a522e-ou4qf-qi9a6-94855302662bf4165a5272.jpg"},
    {"name": "Legacy TCG", "url": "https://www.legacytcg.com.br", "color": "#0b3d63",
     "logo": _LOGO + "6a24662356396-fw8kx-t1cuj-18574839646a2466235639d.jpg"},
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
BLOCK_COOLDOWN = 8          # segundos de espera, depois de uma loja limitar as requisições, para tentar de novo
CACHE_TTL = 300             # segundos que uma página de produto lida fica guardada
HISTORY_MAX = 10            # quantas buscas o Voltar/Avançar lembram
STALE_AFTER = 30 * 60       # resultados guardados mais velhos que isto (30 min) são refeitos ao voltar/avançar

# Busca de uma lista inteira (buscador/lista.py): ritmo próprio, mais lento que o da busca de uma carta.
LISTA_MAX_CARTAS = 100      # cartas diferentes por lista (um deck de Commander)
# Teste real (nov/2026): a 1,2-1,8 s por requisição, a proteção do site (Cloudflare, 429 "Just a moment")
# barrou a loja depois de ~6 requisições em ~10 s. Por isso a pausa é bem maior que a da busca de uma carta.
LISTA_PAUSA = 3.0           # segundos entre requisições na MESMA loja (sorteado entre 1x e 1,5x)
LISTA_ITENS_POR_CARTA = 2   # páginas de produto lidas por carta em cada loja (só itens com o nome exato)
LISTA_PAUSA_PASSO = 1.0     # cada bloqueio deixa a loja 1 s mais lenta na lista...
LISTA_PAUSA_MAX = 8.0       # ...até este máximo
# loja bloqueou: espera e tenta sozinha de novo (as outras lojas seguem); depois da última, desiste.
# Teste real (nov/2026): no mesmo segundo em que a Legacy deu 429, as outras 4 lojas respondiam normalmente.
LISTA_RETOMAR = (10, 20, 40, 80, 160)

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


DATA_DIR_NAME = "BuscaCartas"
OLD_DATA_DIR_NAME = "BuscadorMTG"  # nome da pasta até a versão 1.0.0


def user_data_dir(name=DATA_DIR_NAME):
    """Pasta de dados do usuário no Windows: %APPDATA%/BuscaCartas."""
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, name)


def app_dir():
    """Pasta onde o programa guarda lojas.json, config.json e debug/.

    - Pelo código-fonte: a pasta do projeto (a de cima de buscador/), como sempre foi.
    - No .exe (PyInstaller): %APPDATA%/BuscaCartas. Assim o .exe funciona de qualquer lugar
      (Downloads, Área de Trabalho, de dentro de um zip) e as lojas e preferências continuam
      ao trocar por uma versão nova."""
    if getattr(sys, "frozen", False):
        return user_data_dir()
    # este arquivo fica em buscador/; a pasta do programa é a de cima
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def migrate_from_exe_folder(exe_dir, data_dir):
    """Copia lojas.json e config.json de uma pasta antiga para a pasta de dados, se a pasta de dados
    ainda não tem esses arquivos (não apaga os antigos). Usada para %APPDATA%/BuscadorMTG (nome
    antigo, até a 1.0.0) e para a pasta do .exe (até a 0.3.0 os arquivos ficavam ao lado dele)."""
    try:
        os.makedirs(data_dir, exist_ok=True)
        for name in DATA_FILES:
            old, new = os.path.join(exe_dir, name), os.path.join(data_dir, name)
            if os.path.isfile(old) and not os.path.exists(new):
                shutil.copy2(old, new)
    except OSError:
        pass  # sem permissão: o programa abre com as lojas padrão, como numa primeira vez


if getattr(sys, "frozen", False):
    migrate_from_exe_folder(user_data_dir(OLD_DATA_DIR_NAME), app_dir())
    migrate_from_exe_folder(os.path.dirname(sys.executable), app_dir())

CONFIG_FILE = os.path.join(app_dir(), "lojas.json")
SETTINGS_FILE = os.path.join(app_dir(), "config.json")
