"""Estruturas de dados: item da busca, resultado de uma loja e oferta da página do produto."""

from dataclasses import dataclass, field


@dataclass
class Item:
    name: str
    price: float | None
    url: str
    available: bool = True
    offers: list | None = None  # preenchido quando a busca já devolveu a página do produto
    preorder: bool = False  # a lista da loja marcou o item com o "P" de pré-venda
    preorder_date: str = ""  # previsão de envio, como a loja escreve (ex.: "13/11/2026")


@dataclass
class StoreResult:
    store: dict
    search_url: str
    status: str  # found | soldout | none | blocked | unknown | error
    items: list = field(default_factory=list)
    msg: str = ""


@dataclass
class Offer:
    edition: str
    language: str
    quality: str
    extras: str
    stock: int | None
    price: float | None
    preorder: bool = False
    original_price: float | None = None  # preço riscado, quando a oferta está em promoção
    preorder_date: str = ""  # previsão de envio da pré-venda (ex.: "13/11/2026")
    note: str = ""  # observação que a loja colocou na oferta ("Visualizar observação")
    language_flag: str = ""  # endereço da bandeira que a loja usa para o idioma
    edition_code: str = ""  # código da edição no ícone da loja (".../ed_mtg/AFC_U.gif" -> "afc")
    image: str = ""  # imagem da carta nesta edição (a que o site mostra ao passar o mouse na linha)
    photos: list = field(default_factory=list)  # fotos do próprio item que a loja colocou
