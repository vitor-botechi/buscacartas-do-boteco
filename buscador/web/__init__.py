"""Interface em HTML numa janela de programa (pywebview).

- ponte.py: o lado Python. A página chama as funções da classe Ponte (buscar, detalhes, lojas...)
  e recebe os acontecimentos da busca pela função JavaScript app.evento(tipo, sid, dados).
- serializar.py: converte os resultados (Item, Offer, StoreResult) em dicionários para a página.
- pagina/: index.html, estilo.css e app.js (só desenham a tela e guardam o estado dela).
- app.py: abre a janela (main).
"""
