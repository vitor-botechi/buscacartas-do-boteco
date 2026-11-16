# Buscador de Cartas MTG

Programa de computador (Windows) para buscar cartas de **Magic: The Gathering** em várias lojas ao mesmo tempo.
Digite o nome da carta, escolha as lojas e veja em quais há estoque, com edições, idioma, qualidade e preço.
Feito para lojas que usam o padrão **LigaMagic**.

## Recursos

- Lojas pré-cadastradas (liga e desliga em cada uma) e opção de **adicionar outras lojas** pelo link.
- Resultados por loja, cada uma num cartão destacado com a cor da loja (a cor de uma loja nova é lida do site dela), com link direto para a página do produto e para a busca na loja.
- **Edições e preços** de cada item (idioma, qualidade, estoque, extras, promoção, pré-venda e observação da loja, com cores), carregados com um clique em "Ver edições e preços" ou automaticamente quando a loja tem poucos itens.
- Opção **Apenas nome exato**, que usa o [Scryfall](https://scryfall.com/) para reconhecer o nome da carta em inglês e português.
- Botões **Voltar** e **Avançar** entre as buscas; buscas antigas (mais de 30 minutos) são refeitas.
- Botão **Colar nome**, que limpa o campo e cola o texto copiado. Ao voltar para a janela, basta apertar Enter duas vezes: o primeiro cola o nome, o segundo busca.

## Como instalar e rodar

**Jeito fácil (Windows):** baixe o `BuscadorMTG.exe` na página de
[versões (Releases)](https://github.com/vitor-botechi/buscador-mtg/releases) e abra. Não precisa instalar o Python
nem descompactar nada; o arquivo pode ficar em qualquer pasta. Para atualizar, basta baixar o novo `.exe`:
as lojas e preferências continuam.
Na primeira vez, o Windows pode avisar que protegeu o computador: clique em "Mais informações" e "Executar assim mesmo"
(o programa não tem assinatura digital paga).

**Pelo código-fonte:**

1. Instale o [Python 3.10 ou mais novo](https://www.python.org/downloads/) (marque *Add Python to PATH*).
2. No terminal, dentro da pasta do projeto:

   ```
   pip install -r requirements.txt
   python buscador_mtg.py
   ```

   (também funciona `python -m buscador`)

   Em **Linux ou macOS**, o programa deve rodar do mesmo jeito pelo código-fonte (use `python3`). A janela usa o
   [pywebview](https://pywebview.flowrl.com/), que no Linux precisa de pacotes do sistema (GTK ou Qt com WebKit).
   Sem o pywebview, o programa abre a interface antiga (Tkinter). Ainda não foi testado nesses sistemas.
   O `.exe` da página de versões é só para Windows.

## Gerar o programa para Windows

```
py -m pip install -r instalador/requirements.txt
py instalador/gerar_exe.py
```

O resultado é `dist/BuscadorMTG.exe`, um arquivo único, que é o publicado
na página de versões do GitHub. Detalhes no início de `instalador/gerar_exe.py`.

## Organização do código

O código fica no pacote `buscador/`: configuração, lojas salvas, leitura das páginas no padrão LigaMagic (`lojas/`),
requisições (`rede.py`), detalhes automáticos, Scryfall e a interface. A interface é uma página HTML numa janela de
programa (`web/`, com o pywebview); a interface antiga em Tkinter (`interface/`) fica como reserva. O `buscador_mtg.py`
só inicia o programa.

## Testes

```
pip install -r requirements-dev.txt
py -m pytest
```

No Windows, use `py -m pytest` (o lançador `py` vem com o instalador do Python). Só `pytest`, ou mesmo
`python -m pytest`, pode não ser encontrado quando a pasta de comandos do Python não está no PATH.

Os testes usam páginas reais das lojas, **sanitizadas**, em `tests/fixtures/`, e não fazem requisições.

## Atalhos

| Atalho | Ação |
| --- | --- |
| Enter (no campo) | Buscar |
| Enter ou Espaço (no botão Colar nome) | Colar o nome copiado |
| Ctrl+V (no botão Colar nome) | Colar o nome copiado |
| Alt+← / Alt+→ | Voltar / Avançar |
| Ctrl+Backspace | Apagar a palavra anterior |
| Duplo clique numa edição | Abrir a página do produto na loja |

## Como funciona (e limites)

- Lê as páginas públicas de busca das lojas, uma requisição por loja e por busca.
- As páginas de produto são lidas só sob demanda, ou automaticamente para poucos itens, com pausa entre as requisições e um teto por busca. Se alguma loja sinalizar bloqueio, a leitura automática é pausada.
- Algumas lojas não entregam o preço e o estoque da lista de busca como texto; por isso eles aparecem ao abrir os detalhes do item.
- Arquivos locais: `lojas.json` (lojas e seleção), `config.json` (preferências) e a pasta `debug/` (páginas recebidas, para diagnóstico). No `.exe`, ficam em `%APPDATA%\BuscadorMTG` (cole esse endereço na barra do Explorador de Arquivos para abrir); rodando pelo código-fonte, ficam na pasta do projeto. Nenhum deles vai para o repositório.

## Aviso

Projeto independente, sem vínculo com as lojas, com a LigaMagic ou com a Wizards of the Coast.
*Magic: The Gathering* é marca da Wizards of the Coast LLC. Os dados mostrados pertencem às respectivas lojas.
Use com moderação: o programa foi feito para consultas pontuais de um usuário, não para varreduras em massa.

## Licença

[MIT](LICENSE): qualquer pessoa pode usar, copiar, modificar e redistribuir o programa, desde que mantenha
o aviso de autoria e da licença. O programa é oferecido sem garantia.
