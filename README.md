# Buscador de Cartas MTG

Programa de computador (Windows) para buscar cartas de **Magic: The Gathering** em várias lojas ao mesmo tempo.
Digite o nome da carta, escolha as lojas e veja em quais há estoque, com edições, idioma, qualidade e preço.
Feito para lojas que usam o padrão **LigaMagic**.

## Recursos

- Lojas pré-cadastradas (marcadas por checkbox) e opção de **adicionar outras lojas** pelo link.
- Resultados lado a lado, com link direto para a página do produto em cada loja.
- Painel **Edições e preços** (estoque, qualidade, extras e promoções), carregado sob demanda ou automaticamente quando a loja tem poucos itens.
- Opção **Apenas nome exato**, que usa o [Scryfall](https://scryfall.com/) para reconhecer o nome da carta em inglês e português.
- Botões **Voltar** e **Avançar** entre as buscas; buscas antigas (mais de 30 minutos) são refeitas.
- Botão **Colar nome**, que limpa o campo e cola o texto copiado.

## Como instalar e rodar

1. Instale o [Python 3.10 ou mais novo](https://www.python.org/downloads/) (marque *Add Python to PATH*).
2. No terminal, dentro da pasta do projeto:

   ```
   pip install -r requirements.txt
   python buscador_mtg.py
   ```

   (também funciona `python -m buscador`)

## Organização do código

O código fica no pacote `buscador/`: configuração, lojas salvas, leitura das páginas no padrão LigaMagic (`lojas/`),
requisições (`rede.py`), detalhes automáticos, Scryfall e a interface (`interface/`). O `buscador_mtg.py` só inicia o programa.

## Testes

```
pip install -r requirements-dev.txt
pytest
```

Os testes usam páginas reais das lojas, **sanitizadas**, em `tests/fixtures/`, e não fazem requisições.

## Atalhos

| Atalho | Ação |
| --- | --- |
| Enter (no campo) | Buscar |
| Enter ou Espaço (no botão Colar nome) | Colar o nome copiado |
| Enter (com um item selecionado) | Abrir Edições e preços |
| Alt+← / Alt+→ | Voltar / Avançar |
| Ctrl+Backspace | Apagar a palavra anterior |

## Como funciona (e limites)

- Lê as páginas públicas de busca das lojas, uma requisição por loja e por busca.
- As páginas de produto são lidas só sob demanda, ou automaticamente para poucos itens, com pausa entre as requisições e um teto por busca. Se alguma loja sinalizar bloqueio, a leitura automática é pausada.
- Algumas lojas não entregam o preço e o estoque da lista de busca como texto; por isso eles aparecem ao abrir os detalhes do item.
- Arquivos locais criados ao lado do programa: `lojas.json` (lojas e seleção), `config.json` (preferências) e a pasta `debug/` (páginas recebidas, para diagnóstico). Nenhum deles vai para o repositório.

## Aviso

Projeto independente, sem vínculo com as lojas, com a LigaMagic ou com a Wizards of the Coast.
*Magic: The Gathering* é marca da Wizards of the Coast LLC. Os dados mostrados pertencem às respectivas lojas.
Use com moderação: o programa foi feito para consultas pontuais de um usuário, não para varreduras em massa.

## Licença

A definir.
