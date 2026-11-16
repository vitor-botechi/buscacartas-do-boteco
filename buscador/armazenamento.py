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
    if not p.netloc or "." not in p.netloc:
        raise ValueError("Link inválido")
    return f"{p.scheme}://{p.netloc}"


def host_key(url):
    return urlparse(url).netloc.lower().replace("www.", "")


def default_name(url):
    return host_key(url).split(".")[0].capitalize()


def load_stores():
    stores = [dict(s, builtin=True, enabled=True) for s in DEFAULT_STORES]
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            saved = json.load(f).get("stores", [])
    except (OSError, ValueError):
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
    return stores


def save_stores(stores):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"stores": stores}, f, ensure_ascii=False, indent=2)
    except OSError:
        pass
