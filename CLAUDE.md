# Buscador de Cartas MTG: guia para o Claude Code

Este arquivo é lido no início de cada sessão. Explica o projeto, as decisões já tomadas e as regras de trabalho.
O roteiro de melhorias e o histórico de decisões estão em `docs/ROTEIRO.md`.

## O que é

Programa de computador (Windows, Python, com a tela em HTML numa janela do pywebview) que busca cartas de **Magic: The Gathering** em várias lojas ao mesmo tempo.
A pessoa digita o nome da carta, marca as lojas e vê em quais há estoque, com edições, idioma, qualidade e preço.
As lojas usam o padrão **LigaMagic**. O público é a comunidade local de Magic: o programa precisa ser prático, rápido e intuitivo.
Todo o texto da interface e os comentários estão em **português do Brasil**; mantenha assim.

## Como rodar

```
pip install -r requirements.txt
python buscador_mtg.py        (ou: python -m buscador)
```

Python 3.10 ou mais novo. Dependências: `requests`, `beautifulsoup4` (o app abre sem elas, mas a busca interna fica desligada; ver `HAS_SCRAPING` em `rede.py`).

## Estrutura (pacote `buscador/`)

`buscador_mtg.py` é só o ponto de entrada. A versão fica em `buscador/__init__.py` (`__version__`).
As importações dentro do pacote são absolutas (`from buscador.config import ...`).

1. **`config.py`**: lojas padrão (`DEFAULT_STORES`), modelo da URL de busca (`SEARCH_PATH`), constantes de limites (`AUTO_*`, `BLOCK_COOLDOWN`, `CACHE_TTL`, `HISTORY_MAX`, `STALE_AFTER`) e `app_dir()` (pasta do programa, que é a pasta *acima* de `buscador/`, ou a do `.exe`).
2. **`armazenamento.py`**: `lojas.json` (lojas, seleção e, se a pessoa arrastou, a ordem: `manual_order`) e `config.json` (preferências), na pasta de `app_dir()` (projeto pelo código-fonte; `%APPDATA%\BuscadorMTG` no `.exe`); `normalize_base`, `host_key`.
3. **`modelos.py`**: `Item`, `StoreResult`, `Offer`.
4. **`texto.py`**: `norm`, `clean_card_name`, `strip_suffix`, `money`, `age_text`, `offer_desc`.
5. **`lojas/ligamagic.py`**: só leitura de HTML, **sem requisições**: `build_search_url`, `parse_results`, `product_from_page`, `parse_product_page` (edição, idioma, qualidade, extras, estoque, preço, promoção e observação da loja), `theme_color` e `theme_logo` (cor principal e logo do site) e os marcadores de bloqueio/sem resultado. Uma loja de outro padrão ganha um módulo próprio em `lojas/`.
6. **`rede.py`**: requisições: `search_store`, `safe_search`, `fetch_product` com cache curto, `fetch_store_look` (cor e logo, uma vez, ao adicionar uma loja), gravação em `debug/`.
7. **`automatico.py`**: `auto_details` e `AutoCtl` (orçamento total e freio de emergência).
8. **`scryfall.py`**: `resolve_names` consulta o Scryfall para nomes em inglês e português; `matches_exact` compara; `card_art` dá a imagem da carta (da edição, pelo nome ou pelo código do ícone) para a arte ao passar o mouse, com cache e uma consulta por vez.
9. **`web/`** (interface atual): **`ponte.py`**, classe `Ponte`, o lado Python que a página chama (buscar, detalhes, arte da carta, lojas, colar, abrir no navegador); **`serializar.py`** converte `Item`/`Offer`/`StoreResult` em dicionários; **`app.py`** abre a janela (`main()`); **`pagina/`** tem `index.html`, `estilo.css` e `app.js`, que só desenham a tela e guardam o estado dela (o que está aberto, histórico Voltar/Avançar).
10. **`interface/`** (reserva, Tkinter): a interface antiga, aberta só quando o pywebview não está instalado. Será removida depois que a nova for aprovada.

Só `interface/` usa o Tkinter; só `web/` usa o pywebview.

Fora do pacote: `instalador/gerar_exe.py` gera o `BuscadorMTG.exe` (PyInstaller, arquivo único) publicado nas versões do GitHub (`py instalador/gerar_exe.py`, resultado em `dist/`, que não é versionado). Licença MIT (`LICENSE`).

## Regras de funcionamento a preservar

- **Acontecimentos da busca vão para a página** por `app.evento(tipo, sid, dados)` (`Ponte._enviar`, que usa `evaluate_js`). Tipos: `result`, `names`, `offers`, `autostart`, `autostep`, `autoend`, `autostop`. Os detalhes sob demanda e o "Apenas nome exato" depois da busca são chamadas diretas da página (`detalhes`, `nomes_exatos`), que o pywebview roda numa thread própria.
- **Atributos da `Ponte` começam com `_`**: o pywebview expõe à página tudo que é público na classe.
- **`search_id`** invalida respostas atrasadas: a página ignora acontecimentos de uma busca antiga. Ao iniciar, cancelar ou voltar para outra busca, o `search_id` aumenta e o `AutoCtl` da busca anterior é parado (`Ponte.buscar`, `Ponte.cancelar`).
- **Histórico**: fica na página (`app.js`); cada entrada é uma cópia do estado da tela. Entradas com mais de `STALE_AFTER` (30 min) são refeitas em vez de restauradas.
- A leitura é feita **por requisição única por loja e por busca**; páginas de produto só sob demanda ou automaticamente para poucos itens.

## Regras de ética e de conduta com as lojas (importante)

- **Não contornar a proteção de preços das lojas.** Na lista de busca, as lojas desenham preço e quantidade com imagens (sprites) e classes embaralhadas, para impedir leitura automática. Decidimos **não** usar OCR nem outro desvio. O preço vem da página do produto, onde está em texto, e só quando a pessoa pede ou para poucos itens.
- **Ritmo de requisições conservador** (vale também para o botão "Carregar todos os preços" da loja, `Ponte.carregar_loja`, que só roda quando a pessoa pede): uma página por vez em cada loja, com pausa de ~0,8 a 1,2 s, teto de `AUTO_TOTAL_CAP` páginas por busca e cache de `CACHE_TTL`. Qualquer sinal de bloqueio (403/429/503, captcha) pausa todos os detalhes automáticos; o botão "Carregar todos os preços" só volta depois de `BLOCK_COOLDOWN` segundos, e só se a pessoa clicar. Não aumentar esses limites sem testar com cuidado e sem registrar no roteiro.
- Nunca fazer varreduras em massa. Uma futura "busca de lista inteira" precisa de um desenho próprio, com ritmo mais lento.
- **Não automatizar o botão Comprar.** Abrir a página do produto para a pessoa adicionar ao carrinho já basta.
- **Não versionar dados pessoais**: nada de páginas salvas do navegador (`view-source_*.html`, que trazem nome e carrinho da conta), nem a pasta `debug/`, `lojas.json` ou `config.json`. Fixtures de teste devem ser **sanitizadas** (sem nome, carrinho, e-mail ou identificadores de sessão).

## Particularidades das lojas (padrão LigaMagic)

- Busca: `/?view=ecom/itens&busca=NOME&txt_estoque=1&txt_order=3&txt_limit=120&page=1` (`txt_estoque=1` = só com estoque, `txt_order=3` = menor preço).
- Quando a busca tem **um único resultado**, a loja devolve direto a **página do produto** (`#product--list`). Por isso `product_from_page` existe.
- Resultados da lista estão em `.cards:not(.cards-hint) .card-item`. O bloco **"Cards Associados"** (`.cards-hint`) não faz parte da busca e deve ser ignorado.
- Os nomes podem vir como `Nome PT / Nome EN` e com sufixos entre parênteses (`Ilha (#266)`); `matches_exact` trata isso.
- Página do produto: ofertas em `div.table-cards-row` (edição, idioma, qualidade, extras, estoque, preço). Linhas com "Avise quando chegar" não têm estoque e são ignoradas. **Promoção**: preço riscado vem antes do novo; o programa usa o último valor. **Observação da loja**: ícone `.icon-observacao` nos extras, com o texto no atributo `observacao` (`{{br}}` = quebra de linha) e um "Visualizar observação" escondido ao lado; vai para `Offer.note`, não para os extras.
- Cores e logo: o site traz `--color-primary` no `:root` e a logo numa imagem `.../ecom/logo/...` (CDN `repositorio.sbrauble.com`). Para as lojas padrão, cores e logo ficam fixas em `DEFAULT_STORES` (cores tiradas da logo, que às vezes difere do site: a Jackpot usa vermelho no site e verde na logo).
- Idioma: a bandeira é a imagem da própria loja (`lmcorp.com.br/images/bandeiras/xx.svg`; `pten.svg` = Português / Inglês), em `Offer.language_flag`. O ícone da edição (`.../ed_mtg/LTC_U.gif`) traz o código dela, em `Offer.edition_code`; o nome da edição às vezes vem em português. Cada linha de oferta tem `onmouseover="itemMouseOver(N)"`, e a página traz a imagem da carta naquela edição em `#stickyN` (`Offer.image`, usada na arte ao passar o mouse) e as fotos do item tiradas pela loja em `#stickyN_2`, `#stickyN_3`... (`Offer.photos`). Endereços de imagem só entram na página se forem `https://` (`web_image`).
- As lojas podem mudar o HTML a qualquer momento: se a leitura quebrar, comparar com uma página nova (sanitizada) antes de mexer.

## Como trabalhar neste repositório

- Fazer mudanças em **ramificação** (`git switch -c nome`) e commits pequenos, com mensagens em português.
- **Testes**: `pip install -r requirements-dev.txt` e depois `py -m pytest` (no Windows do dono do projeto, `pytest` e `python -m pytest` não funcionam porque a pasta Scripts do Python não está no PATH; use sempre `py -m pytest` nas instruções). Os testes não fazem requisições: as respostas das lojas são simuladas e as páginas vêm de `tests/fixtures/` (HTML real sanitizado). Rodar antes de cada commit. A interface não tem teste automático: rode o programa e confira de verdade.
- **Nova fixture** (loja mudou o HTML, loja nova, caso novo): `python tests/sanitizar.py pagina.html tests/fixtures/nome.html "descrição"`. O script só grava se a página limpa for lida igual à original e avisa sobre possíveis dados pessoais; mesmo assim, abra e confira o arquivo antes do commit.
- Não alterar o comportamento visível sem pedir: o dono do projeto testa e ajusta a interface passo a passo.
- Ao concluir uma etapa, atualizar `docs/ROTEIRO.md` (o que foi feito, o que ficou pendente).
