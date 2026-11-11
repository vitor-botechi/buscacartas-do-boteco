"""Estruturas de dados: item da busca, resultado de uma loja e oferta da página do produto."""

from dataclasses import dataclass, field


@dataclass
class Item:
    name: str
    price: float | None
    url: str
    available: bool = True
    offers: list | None = None  # preenchido quando a busca já devolveu a página do produto


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
