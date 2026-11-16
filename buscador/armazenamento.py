"""Lojas e preferências salvas (lojas.json e config.json, na pasta de config.app_dir())."""

import json
import re
from urllib.parse import urlparse

from buscador.config import CONFIG_FILE, DEFAULT_STORES, SETTINGS_FILE


def load_settings():
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(data):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def normalize_base(url):
    url = url.strip()
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    p = urlparse(url)
    # endereço de site: partes com letras, números e hífen, separadas por ponto, terminando em letras
    if not re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}(?::\d+)?", p.netloc.lower()):
        raise ValueError("Link inválido")
    return f"{p.scheme}://{p.netloc}"


def host_key(url):
    return urlparse(url).netloc.lower().replace("www.", "")


def default_name(url):
    return host_key(url).split(".")[0].capitalize()


def load_stores():
    """Lojas padrão + lojas adicionadas, com o que ficou salvo (marcadas e, se a pessoa arrastou, a ordem)."""
    stores = [dict(s, builtin=True, enabled=True) for s in DEFAULT_STORES]
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            data = json.load(f)
        saved = data.get("stores", [])
        manual_order = bool(data.get("manual_order"))
    except (OSError, ValueError, AttributeError):
        return stores

    by_host = {host_key(s["url"]): s for s in stores}
    for s in saved:
        try:
            key = host_key(s["url"])
        except (KeyError, TypeError):
            continue
        if key in by_host:  # loja padrão: só lembra se estava marcada
            by_host[key]["enabled"] = bool(s.get("enabled", True))
        else:  # loja adicionada pelo usuário
            stores.append(
                {
                    "name": s.get("name") or default_name(s["url"]),
                    "url": s["url"],
                    "color": s.get("color") or "",
                    "logo": s.get("logo") or "",
                    "builtin": False,
                    "enabled": bool(s.get("enabled", True)),
                }
            )
    if manual_order:  # a ordem que a pessoa escolheu arrastando; loja padrão nova vai para o fim
        pos = {}
        for i, s in enumerate(saved):
            try:
                pos.setdefault(host_key(s["url"]), i)
            except (KeyError, TypeError):
                pass
        stores.sort(key=lambda s: pos.get(host_key(s["url"]), len(saved)))
    return stores


def save_stores(stores, manual_order=None):
    """manual_order: True quando a pessoa arrastou as lojas (None = mantém o que estava salvo)."""
    if manual_order is None:
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                manual_order = bool(json.load(f).get("manual_order"))
        except (OSError, ValueError, AttributeError):
            manual_order = False
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"manual_order": manual_order, "stores": stores}, f, ensure_ascii=False, indent=2)
    except OSError:
        pass
