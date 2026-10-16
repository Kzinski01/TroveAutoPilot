"""Persistencia de configuracao do Trove AutoBot (JSON)."""

import copy
import json
import math
import os
import re
import sys

# Congelado no exe, __file__ aponta para a pasta temporaria do PyInstaller.
# A config e os templates precisam ficar ao lado do executavel.
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")

# Cada slot de skill: recorte da tela + pontuacao de "pronto" aprendida na calibracao.
DEFAULT_SKILLS = [
    {"id": "m2", "name": "M2", "key": "mouse_right", "enabled": True,
     "region": None, "ready_score": 0.0, "cooldown_score": 0.0,
     "threshold": 0.80, "min_interval": 0.6},
    {"id": "s1", "name": "1", "key": "1", "enabled": True,
     "region": None, "ready_score": 0.0, "cooldown_score": 0.0,
     "threshold": 0.80, "min_interval": 0.6},
    {"id": "s2", "name": "2", "key": "2", "enabled": True,
     "region": None, "ready_score": 0.0, "cooldown_score": 0.0,
     "threshold": 0.80, "min_interval": 0.6},
]

SECONDARY_DEFAULTS = {"selected_window": None, "input_mode": "messages",
                      "enabled": False, "key": "e", "interval": 20.0}

DEFAULTS = {
    "auto_slots": {"enabled": False},
    "secondary": copy.deepcopy(SECONDARY_DEFAULTS),
    "selected_window": None,
    "input_mode": "foreground",
    "only_when_focused": True,
    "target_window": "Trove",
    # Outros titulos que tambem contam como "o jogo", separados por virgula.
    # O Trove troca o titulo da janela em algumas telas (login, carregamento).
    "extra_windows": "",

    # Liga/desliga de cada funcao (o que os switches da aba "Funcoes" controlam).
    "features": {
        "autoclick": True,
        "skills": True,
        "potion": True,
        "dialogs": True,
        "holdkey": False,
    },

    "autoclick": {
        "mode": "click",          # "click" = spam de cliques | "hold" = segurar o botao
        "cps": 12.0,
        "button": "left",
    },
    "skills": copy.deepcopy(DEFAULT_SKILLS),
    "potion": {
        "key": "q",
        "interval": 10.0,
    },
    # Segura uma tecla por alguns segundos, solta e repete sem pausa.
    "holdkey": {
        "key": "t",
        "duration": 3.0,
    },
    "claim": {
        "enabled": True,
        "template": "",           # png capturado na calibracao (janela CLAIMS)
        "template_region": None,  # onde o template foi capturado (para o offset)
        "confidence": 0.80,
        "action": "click",        # "click" no X | "key" (pressiona a tecla abaixo)
        "key": "l",
        # deslocamento do centro do template ate o botao X (preenchido na calibracao)
        "click_offset": [0, 0],
        "cooldown": 1.5,
    },
    "invite": {
        "enabled": True,
        "template": "",           # png do botao STAY
        "template_region": None,
        "confidence": 0.80,
        "action": "click",
        "key": "",
        "click_offset": [0, 0],
        "cooldown": 1.5,
    },

    "hotkeys": {
        "master": "f5",
        "autoclick": "f6",
        "skills": "f7",
        "potion": "f8",
        "dialogs": "f9",
        "holdkey": "f10",
        "panic": "f12",
    },
    "scan_interval": 0.10,        # intervalo do loop de skills (s)
    "dialog_interval": 0.50,      # intervalo do loop de deteccao de janelas (s)
    "pause_on_dialog": True,      # pausa o autoclick enquanto uma janela estiver aberta
}


def _merge(base, override):
    """Merge recursivo preservando chaves novas dos defaults."""
    out = copy.deepcopy(base)
    if not isinstance(override, dict):
        return out
    for key, value in (override or {}).items():
        if key in out and isinstance(out[key], dict):
            if isinstance(value, dict):
                out[key] = _merge(out[key], value)
        elif isinstance(out.get(key), bool):
            if type(value) is bool or (type(value) is int and value in (0, 1)):
                out[key] = bool(value)
        elif isinstance(out.get(key), (float, int)) and (
                isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value)):
            continue
        elif isinstance(out.get(key), str) and not isinstance(value, str):
            continue
        else:
            out[key] = copy.deepcopy(value)
    return out


def _merge_skills(saved):
    """Skills sao lista: casa por id e mantem slots desconhecidos fora."""
    skills = []
    saved_by_id = {s["id"]: s for s in (saved if isinstance(saved, list) else [])
                   if isinstance(s, dict) and isinstance(s.get("id"), str)}
    for default_skill in DEFAULT_SKILLS:
        skills.append(_merge(default_skill,
                             saved_by_id.get(default_skill["id"], {})))
    return skills


def window_titles(cfg):
    """Todos os titulos aceitos como sendo o jogo, em ordem de preferencia."""
    nomes = [cfg.get("target_window", "")]
    separadores = "[,;" + chr(10) + "]"
    nomes += re.split(separadores, cfg.get("extra_windows", "") or "")
    vistos, resultado = set(), []
    for nome in nomes:
        nome = nome.strip()
        if nome and nome.lower() not in vistos:
            vistos.add(nome.lower())
            resultado.append(nome)
    return resultado


def matches_window(cfg, title):
    """True se o titulo em foco corresponde a algum dos nomes aceitos."""
    atual = (title or "").lower()
    return any(nome.lower() in atual for nome in window_titles(cfg))


def resolve_template(value):
    """Aceita nome simples ou caminho antigo absoluto.

    Guardamos so o nome do arquivo para o exe poder ser movido de pasta sem
    perder os templates.
    """
    if not value:
        return ""
    if not isinstance(value, str):
        return ""
    if os.path.isabs(value):
        value = os.path.basename(value)
    path = os.path.realpath(os.path.join(TEMPLATE_DIR, value))
    try:
        if os.path.commonpath([os.path.realpath(TEMPLATE_DIR), path]) != os.path.realpath(TEMPLATE_DIR):
            return ""
    except ValueError:
        return ""
    return os.path.join(TEMPLATE_DIR, value)


def _drop_obsolete(cfg):
    """Tira do arquivo salvo o que deixou de existir no programa.

    O merge preserva chaves desconhecidas, o que e bom para nao perder ajustes
    entre versoes. Mas uma rotina removida (o auto retry, por exemplo) ficaria
    para sempre no config.json de quem ja usou o bot.
    """
    for secao in ("features", "hotkeys"):
        for chave in set(cfg[secao]) - set(DEFAULTS[secao]):
            del cfg[secao][chave]
    for chave in set(cfg) - set(DEFAULTS):
        del cfg[chave]
    return cfg


def load():
    os.makedirs(TEMPLATE_DIR, exist_ok=True)
    if not os.path.exists(CONFIG_PATH):
        return copy.deepcopy(DEFAULTS)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return copy.deepcopy(DEFAULTS)

    if not isinstance(raw, dict):
        return copy.deepcopy(DEFAULTS)

    cfg = _merge(DEFAULTS, raw)
    cfg["skills"] = _merge_skills(raw.get("skills"))
    if not isinstance(cfg.get("selected_window"), (dict, type(None))):
        cfg["selected_window"] = None
    from config_validation import sanitize
    return sanitize(_drop_obsolete(cfg), DEFAULTS)


def save(cfg):
    os.makedirs(TEMPLATE_DIR, exist_ok=True)
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2, ensure_ascii=False, allow_nan=False)
    os.replace(tmp, CONFIG_PATH)
