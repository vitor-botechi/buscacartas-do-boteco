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
- Pré-venda: as lojas marcam com um "P" verde, com a previsão de envio no `title` ("Data de previsão de envio do item: 13/11/2026"). O programa lê o "P" na lista de busca (item com alguma oferta em pré-venda) e em cada oferta da página do produto, e mostra em verde: "(P)" no nome e "pré-venda, envio DD/MM/AAAA" na coluna Situação (no painel, "(pré-venda)" na edição e a data em Extras) (nov/2026, fixtures `produto_pre_venda` e `busca_lista_pre_venda`, Anel Solar da Star Trek Commander na Overrun).

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

1. **Versionamento no GitHub**: feito. Versões marcadas com tags: `v0.1.0` (primeira versão, arquivo único), `v0.2.0` (refatoração em módulos, testes e correções), `v0.3.0` (pré-venda com data, licença MIT e primeiro programa para Windows, em .zip) e `v0.4.0` (`.exe` único, dados em `%APPDATA%`). A cada versão: subir `__version__` em `buscador/__init__.py`, juntar na `main`, criar a tag no commit da `main`, gerar o `.exe` (`py instalador/gerar_exe.py`) e publicá-lo na página de versões (Releases) do GitHub.
2. **Refatoração**: concluída e juntada na `main` (PR #1, versão `0.2.0`).
   - Feito (novembro de 2026): código dividido no pacote `buscador/` (config, armazenamento, modelos, texto, `lojas/ligamagic.py`, rede, automático, Scryfall, `interface/`), número de versão em `buscador/__init__.py`, ponto de entrada único (`buscador_mtg.py` ou `python -m buscador`). Código movido sem alterações de lógica; conferido comparando a leitura de páginas salvas e a tela de buscas reais com a versão anterior.
   - Feito: testes automáticos com pytest (64 testes na versão 0.2.0, sem requisições), com 5 páginas reais sanitizadas em `tests/fixtures/` (lista com vários resultados, produto devolvido direto pela busca, produto com promoção e linhas sem estoque, busca sem resultado) e o script `tests/sanitizar.py` para criar novas.
   - Conferido na tela (nov/2026): detalhes automáticos de uma lista com poucos itens ("Thalia" na Overrun, 4 resultados, todos com ofertas e preço "a partir de").
   - Fixtures: há páginas da Overrun, Jackpot, Legacy TCG e Deckmaster (as 4 lojas que vêm no programa). Lojas adicionadas por cada pessoa não precisam de fixture.
   - Corrigido: toda página traz o resumo do carrinho vazio ("Nenhum item em seu carrinho"), e "nenhum item" está em `NONE_PHRASES`. Uma página sem itens e sem o filtro `txt_estoque` aparecia como "não encontrada" em vez de "não consegui ler". Agora `parse_results` ignora o bloco `.carrinho` ao montar o texto da página; a frase real de busca vazia ("Nenhum item encontrado com os filtros utilizados") continua valendo.
   - Corrigido: "Apenas nome exato" com nome ambíguo. "Thalia" corresponde a várias cartas; o Scryfall recusa a busca aproximada e o programa ficava com a primeira carta da busca em português ("Thalia e O Monstro Gitrog"), uma escolha quase ao acaso. Agora a busca em português só vale se o nome bater por inteiro; senão, fica só o nome digitado. A regra continua sendo o nome completo (não um trecho).
   - Lojas fora do padrão LigaMagic: em nov/2026 não achamos nenhuma loja brasileira de cartas avulsas fora do padrão (testadas Cards of Paradise, Cardtutor, Bazar de Bagdá, Magic Domain e Epic Game/Epic One, todas LigaMagic). Fica em espera; a estrutura (um módulo por padrão em `buscador/lojas/`) já permite se aparecer uma.
3. **Programa para Windows**: feito (PR #4, versão `0.3.0`, em .zip; PR #6, versão `0.4.0`, `.exe` único).
   - Feito (nov/2026): licença **MIT** (`LICENSE`).
   - Feito: `instalador/gerar_exe.py` gera, com o PyInstaller, o `BuscadorMTG.exe` (sem janela de terminal, com nome e versão nas propriedades do arquivo). Testado numa pasta limpa, sem depender do Python instalado.
   - Versão 0.3.0: era uma pasta (`--onedir`) num `.zip`. Problema: quem abria o `.exe` de dentro do zip (Explorador do Windows, 7-Zip) recebia só o `.exe`, sem a pasta `_internal`, e via uma janela de erro; e as lojas e preferências iam para uma pasta temporária.
   - Decisão (nov/2026, PR #6, versão 0.4.0): **`.exe` único** (`--onefile`), sem zip e sem instalador clássico, e os dados do `.exe` em **`%APPDATA%\BuscadorMTG`**. Funciona de qualquer pasta, e as lojas e preferências continuam ao trocar de versão. Custo: abre em ~2 s (descompacta numa pasta temporária a cada uso) e alguns antivírus desconfiam mais desse formato. Pelo código-fonte, os arquivos continuam na pasta do projeto. Na primeira vez, o `.exe` copia `lojas.json` e `config.json` que estejam ao lado dele (quem usou a 0.3.0).
   - A cada versão, publicar o `.exe` na página de versões do GitHub (tag `vX.Y.Z`). O aviso do SmartScreen continua porque o programa não tem assinatura digital (certificado pago). Ícone próprio fica para a etapa de design.

## Melhorias futuras anotadas

- Comparar com o menor preço da LigaMagic, para ver se as lojas estão muito acima de um preço justo. Primeiro verificar se a LigaMagic entrega os preços como texto ao programa. Decidir se o estado (NM/SP) entra na comparação.
- **Design (em andamento, ramificação `interface-html`)**: cores diferentes para idioma, qualidade (NM/SP), unidades e preço; linhas separadoras mais suaves.
  - Decisão (nov/2026): a tabela do Tkinter só pinta a linha inteira. Comparamos dois protótipos com a mesma busca: Tkinter com ttkbootstrap + tksheet (cor por célula, visual de planilha; o tksheet parou de ser desenvolvido) e **HTML numa janela de programa (pywebview)**, que foi o escolhido: visual mais agradável e facilita arte da carta, animações e tutorial. Também consideradas: CustomTkinter (sem tabela), Qt/PySide6 (`.exe` bem maior), Flet e NiceGUI (mais pesadas).
  - Feito (etapa 1): interface nova em `buscador/web/` com todas as funções da antiga. Mudanças visíveis: cada loja é um cartão; as edições e preços abrem dentro da lista (não há mais o painel lateral); cada item tem "Ver edições e preços" e "Abrir ↗"; cada loja tem "Abrir no navegador ↗"; etiquetas coloridas (NM verde, SP âmbar, MP/HP vermelho, Foil roxo, promoção coral, pré-venda verde, Português azul). A interface Tkinter fica como reserva até a aprovação. O `.exe` passou de 16,9 para 18,5 MB.
  - Pendente:
    - **Tela de abertura animada** enquanto o `.exe` abre (~2 s, tempo que ele leva para se descompactar): algo amigável, talvez um desenho de Magic ou uma animação "procurando cartas" (o protótipo HTML tinha uma). A tela de abertura do PyInstaller (`--splash`, imagem parada) aparece antes de o Python carregar; a animação em HTML só quando a janela já abriu. Talvez combinar as duas.
    - Ícone próprio para o `.exe` e para a janela.
    - Arte da carta ao passar o mouse (Scryfall; o protótipo HTML tinha uma versão simples).
    - Remover a interface Tkinter (`buscador/interface/`) depois da aprovação.
- **Nome do aplicativo**: escolher um nome melhor que "Buscador de Cartas MTG". Ideias de partida: um trocadilho com "Botechi" ou com o "Boteco de Pedidos" (o esquema de pedidos da comunidade). Ao trocar, atualizar título da janela, nome do `.exe` (`NOME` em `instalador/gerar_exe.py`), pasta em `%APPDATA%` (migrar a antiga), README e repositório.
- Busca inteligente que tolere erro de digitação: avisar que o nome parece errado, sugerir o certo (como o Google) e pesquisar mesmo assim. Incluir o caso de nome ambíguo em "Apenas nome exato" (ex.: "Thalia"): avisar que há várias cartas e sugerir os nomes completos (o Scryfall já informa a ambiguidade).
- Tutorial dentro do aplicativo, para ensinar a usar.
- Pesquisar uma lista inteira de cartas: aceitar um nome por linha e formatos como `1 Sol Ring` e `4x Island`. Exige ritmo mais lento (uma lista de 30 cartas em 4 lojas são 120 buscas) e talvez sem detalhes automáticos; mostrar por loja quantas cartas da lista ela tem.
- Talvez: histórico persistente entre sessões (hoje o Voltar/Avançar some ao fechar o programa).
- **Programa pronto para Linux e macOS**, como o `.exe` do Windows. O PyInstaller só gera programa para o sistema em que roda, então seria preciso gerar em cada sistema: num Mac e num Linux, ou automaticamente pelo GitHub Actions (máquinas Windows, macOS e Linux na nuvem, que geram e publicam os três a cada versão). No macOS: um `.app` (talvez num `.dmg`), com aviso do Gatekeeper por não ter assinatura da Apple, e dados em `~/Library/Application Support/`. No Linux: um executável ou AppImage, com dados em `~/.local/share/`. Exige ajustar `user_data_dir()` em `config.py` para cada sistema e testar antes em cada um (hoje nunca foi testado fora do Windows).

## Perguntas em aberto

- Qual o limite seguro de requisições por loja? Registrar aqui o que for observado nos testes (bloqueios, avisos de "detalhes automáticos pausados").
- Como avisar a comunidade de versões novas? (Hoje: baixar o `.exe` novo na página de versões; as preferências continuam. Poderia haver um aviso no programa quando sair versão nova.)
- Linux e macOS: o programa roda pelo código-fonte (nada no código é exclusivo do Windows), mas nunca foi testado nesses sistemas. Programa pronto para eles: ver "Melhorias futuras anotadas".
