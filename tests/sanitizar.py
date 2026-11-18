"""Limpa uma página salva de loja para virar fixture de teste.

Uso:
    python tests/sanitizar.py pagina_original.html tests/fixtures/nome.html "descrição curta"

Remove o que não serve para a leitura e o que pode ter dados de sessão ou da conta:
scripts, estilos, comentários, cabeçalho, rodapé, menus, formulários de login/newsletter,
campos ocultos, metadados (exceto og:url) e atributos que não usamos (src, style, data-*...).
Depois confere que o programa lê a página limpa exatamente como lia a original
e procura sinais de dados pessoais. Mesmo assim, abra o resultado e confira antes do commit.
"""

import os
import re
import sys

from bs4 import BeautifulSoup, Comment

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from buscador.lojas.ligamagic import (  # noqa: E402
    BLOCK_MARKERS,
    ITEM_MOUSE_RE,
    NONE_PHRASES,
    parse_product_page,
    parse_results,
    product_from_page,
)

REMOVER_TAGS = ["script", "style", "noscript", "iframe", "link", "svg", "header", "footer", "nav", "button",
                "select", "textarea", "video", "audio", "source", "picture"]
ATRIBUTOS_MANTIDOS = {"class", "id", "href", "title", "alt", "name", "value", "type", "content", "property",
                      "observacao"}  # observacao: aviso público da loja numa oferta
IMAGENS_PUBLICAS = re.compile(r"^(https:)?//(repositorio\.sbrauble\.com/arquivos/(in/magic|up/ed_mtg|up/ecom/tcg/fotos)/"
                              r"|www\.lmcorp\.com\.br/images/bandeiras/)")
# links de conta, carrinho, contato e com identificadores (token, _ga, sessão)
LINKS_REMOVIDOS = re.compile(r"carrinho|logar|wishlist|email-protection|whatsapp|mailto:|tel:|token|_ga=|sess", re.I)
SUSPEITOS =re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|sess(ion|ao)|token|csrf|cpf|senha|password|ol[aá],|minha conta|"
                       r"logout|sair da conta|meus pedidos", re.I)


def sanitizar(html):
    soup = BeautifulSoup(html, "html.parser")
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    for tag in soup(REMOVER_TAGS):
        tag.decompose()
    for meta in soup("meta"):
        if meta.get("property") != "og:url":
            meta.decompose()
    for form in soup("form"):  # fica só o formulário de busca (os demais são login, newsletter etc.)
        if not form.find("input", attrs={"name": re.compile("busca|txt_")}):
            form.decompose()
    # o resumo do carrinho fica: o programa não usa conta, então ele vem sempre vazio, e o texto
    # "Nenhum item em seu carrinho" conta para a leitura (ver NONE_PHRASES)
    for a in soup.find_all("a", href=LINKS_REMOVIDOS):
        a.decompose()
    for inp in soup("input"):
        if inp.get("type") == "hidden" and not str(inp.get("name", "")).startswith(("txt_", "view")):
            inp.decompose()
    for tag in soup.find_all(True):
        attrs = {k: v for k, v in tag.attrs.items() if k in ATRIBUTOS_MANTIDOS}
        # imagens públicas do padrão LigaMagic (carta na edição, ícone da edição, fotos do item, bandeira)
        if tag.name == "img" and IMAGENS_PUBLICAS.search(tag.get("src") or ""):
            attrs["src"] = tag["src"]
        if ITEM_MOUSE_RE.fullmatch(str(tag.get("onmouseover") or "").strip().rstrip(";")):
            attrs["onmouseover"] = tag["onmouseover"]  # liga a linha da oferta à imagem dela
        tag.attrs = attrs
    texto = str(soup)
    return re.sub(r"\n\s*\n+", "\n", texto)


def leitura(html):
    """O que o programa extrai da página (para comparar antes e depois)."""
    itens, texto = parse_results(html, "https://loja.example")
    return (product_from_page(html, "https://loja.example/"),
            itens,
            parse_product_page(html),
            "txt_estoque" in html,
            [p for p in NONE_PHRASES + BLOCK_MARKERS if p in texto],
            re.findall(r"\d+-\d+ de (\d+)", texto)[:1])


def main():
    origem, destino, descricao = sys.argv[1], sys.argv[2], sys.argv[3]
    original = open(origem, encoding="utf-8").read()
    limpo = sanitizar(original)
    if leitura(original) != leitura(limpo):
        sys.exit("A página limpa é lida de forma diferente da original; nada foi gravado.")
    achados = sorted({m.group(0) for m in SUSPEITOS.finditer(limpo)})
    with open(destino, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"<!-- Fixture sanitizada: {descricao} -->\n{limpo}")
    print(f"{destino}: {len(original)} -> {len(limpo)} caracteres")
    if achados:
        print("  CONFERIR na mão (possíveis dados pessoais):", achados)


if __name__ == "__main__":
    main()
