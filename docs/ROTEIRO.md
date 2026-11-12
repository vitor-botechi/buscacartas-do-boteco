# Roteiro e decisões do projeto

Última atualização: novembro de 2026. Atualize este arquivo ao concluir cada etapa.

## Já está funcionando

- Lojas pré-cadastradas (Overrun, Jackpot Jogos, Legacy TCG, Deckmaster Games) com checkboxes e opção de adicionar novas lojas pelo link; seleção salva.
- Busca em paralelo, só com estoque, do menor para o maior preço, com paginação.
- Link direto para a página do produto em cada resultado.
- Painel lateral "Edições e preços" (estoque, qualidade, extras e promoções), que cresce a janela ao abrir e atualiza ao clicar em outro item.
- Detalhes automáticos quando a loja tem até N itens (padrão 5, ajustável de 0 a 10), com freios.
- Caixa "Apenas nome exato" (Scryfall para nomes em inglês e português).
- Botão "Colar nome", Voltar e Avançar (resultados com mais de 30 min são refeitos), Ctrl+Backspace, janela centralizada e adaptada à tela.
- Aviso na tela para itens com detalhes sob demanda; "Recolher/Expandir listas".

## Decisões tomadas

| Decisão | Motivo |
| --- | --- |
| App de computador em Python/Tkinter, e não um site | Cada pessoa usa o próprio IP, o que reduz o risco de bloqueio pelas lojas; um servidor central teria endereço de datacenter. |
| Não ler preço/estoque da lista de busca | As lojas desenham esses números com imagens para impedir leitura automática. Não vamos contornar (sem OCR). |
| Detalhes só sob demanda ou para poucos itens | Evita sobrecarregar as lojas e ser bloqueado. |
| Não automatizar o botão Comprar | Abrir a página do produto para a pessoa adicionar ao carrinho já basta. |
| Resultados guardados valem 30 min | Preço e estoque mudam durante o dia; depois disso, a busca é refeita. |
| Limites iniciais conservadores (5 itens, ~1 página/s por loja, teto de 24 páginas por busca) | Valor definitivo só se descobre testando. Subir aos poucos (5, depois 8, depois 10) e observar avisos de bloqueio. |

## Próximos passos (em ordem sugerida)

1. **Versionamento no GitHub**: feito. Versões marcadas com tags: `v0.1.0` (primeira versão, arquivo único) e `v0.2.0` (refatoração em módulos, testes e correções). A cada versão, subir `__version__` em `buscador/__init__.py` e criar a tag no commit da `main`.
2. **Refatoração**: concluída e juntada na `main` (PR #1, versão `0.2.0`).
   - Feito (novembro de 2026): código dividido no pacote `buscador/` (config, armazenamento, modelos, texto, `lojas/ligamagic.py`, rede, automático, Scryfall, `interface/`), número de versão em `buscador/__init__.py`, ponto de entrada único (`buscador_mtg.py` ou `python -m buscador`). Código movido sem alterações de lógica; conferido comparando a leitura de páginas salvas e a tela de buscas reais com a versão anterior.
   - Feito: testes automáticos com pytest (64 testes, sem requisições), com 5 páginas reais sanitizadas em `tests/fixtures/` (lista com vários resultados, produto devolvido direto pela busca, produto com promoção e linhas sem estoque, busca sem resultado) e o script `tests/sanitizar.py` para criar novas.
   - Conferido na tela (nov/2026): detalhes automáticos de uma lista com poucos itens ("Thalia" na Overrun, 4 resultados, todos com ofertas e preço "a partir de").
   - Fixtures: há páginas da Overrun, Jackpot, Legacy TCG e Deckmaster (as 4 lojas que vêm no programa). Lojas adicionadas por cada pessoa não precisam de fixture.
   - Corrigido: toda página traz o resumo do carrinho vazio ("Nenhum item em seu carrinho"), e "nenhum item" está em `NONE_PHRASES`. Uma página sem itens e sem o filtro `txt_estoque` aparecia como "não encontrada" em vez de "não consegui ler". Agora `parse_results` ignora o bloco `.carrinho` ao montar o texto da página; a frase real de busca vazia ("Nenhum item encontrado com os filtros utilizados") continua valendo.
   - Corrigido: "Apenas nome exato" com nome ambíguo. "Thalia" corresponde a várias cartas; o Scryfall recusa a busca aproximada e o programa ficava com a primeira carta da busca em português ("Thalia e O Monstro Gitrog"), uma escolha quase ao acaso. Agora a busca em português só vale se o nome bater por inteiro; senão, fica só o nome digitado. A regra continua sendo o nome completo (não um trecho).
   - Lojas fora do padrão LigaMagic: em nov/2026 não achamos nenhuma loja brasileira de cartas avulsas fora do padrão (testadas Cards of Paradise, Cardtutor, Bazar de Bagdá, Magic Domain e Epic Game/Epic One, todas LigaMagic). Fica em espera; a estrutura (um módulo por padrão em `buscador/lojas/`) já permite se aparecer uma.
3. **Programa para Windows**: em andamento (ramificação `instalador`).
   - Feito (nov/2026): licença **MIT** (`LICENSE`).
   - Feito: `instalador/gerar_exe.py` gera, com o PyInstaller, a pasta `dist/BuscadorMTG/` (`BuscadorMTG.exe`, sem janela de terminal, com nome e versão nas propriedades do arquivo) e o `BuscadorMTG-<versão>-windows.zip` com `LEIA-ME.txt` e `LICENSE.txt`. Testado descompactando numa pasta limpa, sem depender do Python instalado.
   - Decisão: distribuir como pasta compactada (.zip), e não com instalador clássico. O programa grava `lojas.json`, `config.json` e `debug/` ao lado do `.exe`; em "Arquivos de Programas" isso exigiria administrador. Formato pasta (`--onedir`) em vez de `.exe` único: abre mais rápido e gera menos alarme falso de antivírus.
   - Pendente: publicar o .zip na página de versões do GitHub a cada versão (tag `vX.Y.Z`); o aviso do SmartScreen continua porque o programa não tem assinatura digital (certificado pago). Ícone próprio fica para a etapa de design.
   - Se um dia houver instalador clássico (Inno Setup, com atalho no menu Iniciar), os arquivos do usuário precisam ir para `%APPDATA%`; isso muda `app_dir()`.

## Melhorias futuras anotadas

- Arte do card ao passar o mouse sobre cada linha.
- Comparar com o menor preço da LigaMagic, para ver se as lojas estão muito acima de um preço justo. Primeiro verificar se a LigaMagic entrega os preços como texto ao programa. Decidir se o estado (NM/SP) entra na comparação.
- Design mais moderno, com cores diferentes para idioma, qualidade (NM/SP), unidades e preço. Avaliar linhas separadoras mais suaves (hoje há só listras alternadas).
- Busca inteligente que tolere erro de digitação: avisar que o nome parece errado, sugerir o certo (como o Google) e pesquisar mesmo assim. Incluir o caso de nome ambíguo em "Apenas nome exato" (ex.: "Thalia"): avisar que há várias cartas e sugerir os nomes completos (o Scryfall já informa a ambiguidade).
- Tutorial dentro do aplicativo, para ensinar a usar.
- Pesquisar uma lista inteira de cartas: aceitar um nome por linha e formatos como `1 Sol Ring` e `4x Island`. Exige ritmo mais lento (uma lista de 30 cartas em 4 lojas são 120 buscas) e talvez sem detalhes automáticos; mostrar por loja quantas cartas da lista ela tem.
- Talvez: botão "Avançar" e histórico persistente entre sessões (hoje o histórico some ao fechar).

## Perguntas em aberto

- Qual o limite seguro de requisições por loja? Registrar aqui o que for observado nos testes (bloqueios, avisos de "detalhes automáticos pausados").
- Como distribuir atualizações para a comunidade depois do instalador?
