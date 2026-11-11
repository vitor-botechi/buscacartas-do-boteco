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

1. **Versionamento no GitHub**: feito (repositório criado). Marcar versões com tags (`v0.1.0`...).
2. **Refatoração** (ramificação `refatoracao`):
   - Feito (novembro de 2026): código dividido no pacote `buscador/` (config, armazenamento, modelos, texto, `lojas/ligamagic.py`, rede, automático, Scryfall, `interface/`), versão `0.1.0` em `buscador/__init__.py`, ponto de entrada único (`buscador_mtg.py` ou `python -m buscador`). Código movido sem alterações de lógica; conferido comparando a leitura de páginas salvas e a tela de buscas reais com a versão anterior.
   - Pendente: testes automáticos (pytest) com HTMLs **sanitizados** de busca e de produto de cada loja; conferir na mão os detalhes automáticos de uma lista com poucos itens; juntar na `main`.
   - Depois: suporte a lojas fora do padrão LigaMagic (um módulo por padrão em `buscador/lojas/`).
3. **Instalador para Windows**: gerar um executável/instalador (por exemplo com PyInstaller) e publicar nas versões do GitHub; escolher a **licença** antes de tornar o repositório público.

## Melhorias futuras anotadas

- Arte do card ao passar o mouse sobre cada linha.
- Comparar com o menor preço da LigaMagic, para ver se as lojas estão muito acima de um preço justo. Primeiro verificar se a LigaMagic entrega os preços como texto ao programa. Decidir se o estado (NM/SP) entra na comparação.
- Design mais moderno, com cores diferentes para idioma, qualidade (NM/SP), unidades e preço. Avaliar linhas separadoras mais suaves (hoje há só listras alternadas).
- Busca inteligente que tolere erro de digitação: avisar que o nome parece errado, sugerir o certo (como o Google) e pesquisar mesmo assim.
- Tutorial dentro do aplicativo, para ensinar a usar.
- Pesquisar uma lista inteira de cartas: aceitar um nome por linha e formatos como `1 Sol Ring` e `4x Island`. Exige ritmo mais lento (uma lista de 30 cartas em 4 lojas são 120 buscas) e talvez sem detalhes automáticos; mostrar por loja quantas cartas da lista ela tem.
- Talvez: botão "Avançar" e histórico persistente entre sessões (hoje o histórico some ao fechar).

## Perguntas em aberto

- Qual o limite seguro de requisições por loja? Registrar aqui o que for observado nos testes (bloqueios, avisos de "detalhes automáticos pausados").
- Qual licença usar quando o repositório for público?
- Como distribuir atualizações para a comunidade depois do instalador?
